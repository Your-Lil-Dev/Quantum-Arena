"""Classical driver for the QCNN.

Every quantum operation lives in src/QCNN.qs. This module prepares inputs,
reads exact class probabilities out of the Q# simulator, and runs the
parameter-shift optimizer. No cloud, no sampling, no shot noise.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from qdk import qsharp

PROJECT_ROOT = Path(__file__).resolve().parent
qsharp.init(project_root=str(PROJECT_ROOT))

# Loss floor, so a zero probability cannot produce an infinite loss.
PROBABILITY_FLOOR = 1e-12


@dataclass
class Sample:
    features: np.ndarray
    label: int


@dataclass
class TrainingResult:
    parameters: np.ndarray
    loss: float
    accuracy: float
    epochs: int


def _literal(values) -> str:
    """Format a sequence as a Q# Double[] literal."""
    return "[" + ", ".join(f"{float(value):.12f}" for value in values) + "]"


class _Simulator:
    """Keeps one allocated qubit array alive in the Q# interpreter."""

    def __init__(self):
        self._name = None
        self._qubit_count = 0
        self._allocation = 0

    def qubits(self, qubit_count: int) -> str:
        if qubit_count != self._qubit_count:
            # The interpreter cannot release a qubit array, and a leftover array
            # would leak into the state dump and corrupt the probability math,
            # so a change of size starts a clean interpreter.
            qsharp.init(project_root=str(PROJECT_ROOT))
            self._allocation = 1
            self._name = f"qcnnQubits{self._allocation}"
            qsharp.eval(f"use {self._name} = Qubit[{qubit_count}];")
            self._qubit_count = qubit_count
        return self._name

    def amplitudes(self) -> np.ndarray:
        return np.asarray(qsharp.dump_machine().as_dense_state(), dtype=complex)


_simulator = _Simulator()


@lru_cache(maxsize=None)
def class_qubit_count(class_count: int) -> int:
    return int(qsharp.eval(f"UniversalQCNN.ClassQubitCount({int(class_count)})"))


@lru_cache(maxsize=None)
def block_parameter_count() -> int:
    return int(qsharp.eval("UniversalQCNN.BlockParameterCount()"))


@lru_cache(maxsize=None)
def block_count(qubit_count: int, output_qubit_count: int) -> int:
    return int(
        qsharp.eval(
            f"UniversalQCNN.BlockCount({int(qubit_count)}, {int(output_qubit_count)})"
        )
    )


def minimum_qubits(feature_count: int) -> int:
    if feature_count < 1:
        raise ValueError("Feature count must be greater than zero.")
    return max(1, int(np.ceil(np.log2(feature_count))))


def parameter_count(qubit_count: int, class_count: int) -> int:
    """Trainable angles needed by a qcnn of this shape."""
    return block_count(qubit_count, class_qubit_count(class_count)) * block_parameter_count()


def prepare_input(features, qubit_count: int) -> np.ndarray:
    """Pad or trim to 2^qubit_count entries and normalise to unit length."""
    values = np.asarray(features, dtype=float).ravel()

    if values.size == 0:
        raise ValueError("Features must not be empty.")
    if values.min() < 0.0:
        raise ValueError("Amplitude encoding needs non-negative features.")

    dimension = 1 << qubit_count

    if values.size > dimension:
        values = values[:dimension]
    elif values.size < dimension:
        values = np.pad(values, (0, dimension - values.size))

    norm = np.linalg.norm(values)

    if norm == 0.0:
        # An all-zero input has no direction; |0...0> is the defined fallback.
        values = np.zeros(dimension)
        values[0] = 1.0
        return values

    return values / norm


def qubit_order(values, qubit_count: int) -> np.ndarray:
    """Reorder amplitudes so qubit 0 holds bit 0 of the feature index.

    Q#'s rotation tree splits the array on its first bit, so the amplitude at
    position i is placed on qubit 0 when i's *most* significant bit is set.
    Reversing the index bits keeps pixel order intact, so the first block pairs
    neighbouring pixels instead of opposite halves of the image.
    """
    axes = tuple(range(qubit_count - 1, -1, -1))
    return values.reshape((2,) * qubit_count).transpose(axes).ravel()


def class_probabilities(features, parameters, class_count: int, qubit_count: int) -> np.ndarray:
    parameters = np.asarray(parameters, dtype=float).ravel()
    expected = parameter_count(qubit_count, class_count)

    if parameters.size != expected:
        raise ValueError(f"Expected {expected} parameters, received {parameters.size}.")

    amplitudes = qubit_order(prepare_input(features, qubit_count), qubit_count)
    output_qubits = class_qubit_count(class_count)
    qubits = _simulator.qubits(qubit_count)

    active = qsharp.eval(
        f"UniversalQCNN.Run({_literal(amplitudes)}, {_literal(parameters)}, "
        f"{output_qubits}, {qubits})"
    )

    return _marginalise(_simulator.amplitudes(), active, class_count, qubit_count)


def _marginalise(amplitudes, active, class_count: int, qubit_count: int) -> np.ndarray:
    basis = np.arange(amplitudes.size)
    classes = np.zeros(amplitudes.size, dtype=int)

    for bit, qubit in enumerate(active):
        # Q#'s state dump stores qubit 0 in the most significant bit.
        classes |= ((basis >> (qubit_count - 1 - qubit)) & 1) << bit

    probabilities = np.zeros(class_count)
    # Outcomes past the last class (non power-of-two class counts) fold into it.
    np.add.at(probabilities, np.minimum(classes, class_count - 1), np.abs(amplitudes) ** 2)
    return probabilities


def predict_sample(sample, parameters, class_count: int, qubit_count: int):
    probabilities = class_probabilities(
        sample.features, parameters, class_count, qubit_count
    )
    return int(np.argmax(probabilities)), probabilities


def evaluate(dataset, parameters, class_count: int, qubit_count: int):
    """Mean loss and accuracy in one pass over the dataset."""
    losses = []
    correct = 0

    for sample in dataset:
        label = int(sample.label)

        if label < 0 or label >= class_count:
            raise ValueError(f"Label {label} is outside 0..{class_count - 1}.")

        probabilities = class_probabilities(
            sample.features, parameters, class_count, qubit_count
        )
        losses.append(-np.log(max(probabilities[label], PROBABILITY_FLOOR)))
        correct += int(int(np.argmax(probabilities)) == label)

    return float(np.mean(losses)), correct / len(dataset)


def initialize_parameters(qubit_count: int, class_count: int, seed=None) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(-np.pi, np.pi, parameter_count(qubit_count, class_count))


def train(dataset, class_count, qubit_count, epochs, learning_rate, parameters) -> TrainingResult:
    if not dataset:
        raise ValueError("Dataset must not be empty.")
    if epochs < 1:
        raise ValueError("Epochs must be at least 1.")
    if learning_rate <= 0:
        raise ValueError("Learning rate must be greater than zero.")

    parameters = np.array(parameters, dtype=float)
    shift = np.pi / 2

    for epoch in range(epochs):
        gradients = np.zeros_like(parameters)

        for index in range(parameters.size):
            plus = parameters.copy()
            minus = parameters.copy()
            plus[index] += shift
            minus[index] -= shift

            loss_plus, _ = evaluate(dataset, plus, class_count, qubit_count)
            loss_minus, _ = evaluate(dataset, minus, class_count, qubit_count)

            gradients[index] = 0.5 * (loss_plus - loss_minus)

        parameters -= learning_rate * gradients
        loss, accuracy = evaluate(dataset, parameters, class_count, qubit_count)

        print(
            f"Epoch {epoch + 1}/{epochs} "
            f"Loss={loss:.6f} "
            f"Accuracy={accuracy:.4f}"
        )

    return TrainingResult(
        parameters=parameters,
        loss=loss,
        accuracy=accuracy,
        epochs=epochs,
    )


def RunUniversalQCNN(dataset, classCount, qubitCount=None, epochs=10, learningRate=0.1, seed=None):
    if not dataset:
        raise ValueError("Dataset must not be empty.")

    if qubitCount is None:
        qubitCount = minimum_qubits(len(dataset[0].features))

    parameters = initialize_parameters(qubitCount, classCount, seed)

    return train(dataset, classCount, qubitCount, epochs, learningRate, parameters)


def Predict(sample, parameters, classCount, qubitCount):
    return predict_sample(sample, parameters, classCount, qubitCount)
