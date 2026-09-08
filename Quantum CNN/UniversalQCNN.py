import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from dotenv import load_dotenv
from qiskit import QuantumCircuit, qasm3, transpile
from qiskit.transpiler import generate_preset_pass_manager
from qiskit.circuit.library import StatePreparation
from qiskit_aer import AerSimulator

load_dotenv()


@dataclass
class Sample:
    Features: Sequence[float]
    Label: int


@dataclass
class TrainingResult:
    parameters: np.ndarray
    loss: float
    accuracy: float
    epochs: int


def convolution_parameter_count():
    return 10


def pooling_parameter_count():
    return 6


def parameter_count_per_block():
    return 16


def required_qubits(feature_count):
    if feature_count < 1:
        raise ValueError("Feature count must be greater than zero.")
    return max(1, int(np.ceil(np.log2(feature_count))))


def required_class_qubits(class_count):
    if class_count < 2:
        raise ValueError("Class count must be at least 2.")
    return max(1, int(np.ceil(np.log2(class_count))))


def number_of_qcnn_blocks(qubit_count, output_qubit_count):
    if output_qubit_count > qubit_count:
        raise ValueError("Output qubit count cannot exceed input qubit count.")
    active = qubit_count
    blocks = 0
    while active > output_qubit_count:
        active = (active + 1) // 2
        blocks += 1
    return blocks


def prepare_input(features, qubit_count=None):
    values = np.asarray(features, dtype=float).flatten()
    if values.size == 0:
        raise ValueError("Features must not be empty.")
    if qubit_count is None:
        qubit_count = required_qubits(values.size)
    dimension = 2 ** qubit_count
    if values.size > dimension:
        values = values[:dimension]
    elif values.size < dimension:
        values = np.pad(values, (0, dimension - values.size))
    norm = np.linalg.norm(values)
    if norm == 0:
        values = np.zeros(dimension, dtype=float)
        values[0] = 1.0
    else:
        values = values / norm
    return values


def apply_convolution(qc, params, first, second):
    if len(params) != 10:
        raise ValueError("Convolution block requires 10 parameters.")
    qc.ry(params[0], first)
    qc.rz(params[1], first)
    qc.ry(params[2], second)
    qc.rz(params[3], second)
    qc.cx(first, second)
    qc.ry(params[4], first)
    qc.rz(params[5], first)
    qc.ry(params[6], second)
    qc.rz(params[7], second)
    qc.cx(first, second)
    qc.ry(params[8], first)
    qc.rz(params[9], second)


def apply_pooling(qc, params, survivor, discarded):
    if len(params) != 6:
        raise ValueError("Pooling block requires 6 parameters.")
    qc.ry(params[0], survivor)
    qc.rz(params[1], survivor)
    qc.ry(params[2], discarded)
    qc.rz(params[3], discarded)
    qc.cx(discarded, survivor)
    qc.ry(params[4], survivor)
    qc.rz(params[5], survivor)


def apply_block(qc, params, active):
    if len(params) != 16:
        raise ValueError("QCNN block requires 16 parameters.")
    next_active = []
    convolution_params = params[:10]
    pooling_params = params[10:]
    for index in range(0, len(active) - 1, 2):
        first = active[index]
        second = active[index + 1]
        apply_convolution(qc, convolution_params, first, second)
        apply_pooling(qc, pooling_params, first, second)
        next_active.append(first)
    if len(active) % 2:
        next_active.append(active[-1])
    for index in range(1, len(active), 2):
        qc.reset(active[index])
    return next_active


def initialize_parameters(qubit_count, class_count, seed=None):
    blocks = number_of_qcnn_blocks(
        qubit_count,
        required_class_qubits(class_count)
    )
    count = blocks * parameter_count_per_block()
    rng = np.random.default_rng(seed)
    return rng.uniform(-np.pi, np.pi, count)


def build_qcnn(features, parameters, class_count=2):
    qubit_count = required_qubits(len(features))
    output_qubits = required_class_qubits(class_count)
    blocks = number_of_qcnn_blocks(qubit_count, output_qubits)
    expected = blocks * parameter_count_per_block()
    parameters = np.asarray(parameters, dtype=float).flatten()

    if parameters.size != expected:
        raise ValueError(
            f"Expected {expected} parameters, received {parameters.size}."
        )

    qc = QuantumCircuit(qubit_count, output_qubits)
    qc.append(
        StatePreparation(prepare_input(features, qubit_count).tolist()),
        list(range(qubit_count))
    )

    active = list(range(qubit_count))

    for block_index in range(blocks):
        start = block_index * parameter_count_per_block()
        end = start + parameter_count_per_block()
        active = apply_block(qc, parameters[start:end], active)

    active = active[:output_qubits]

    for classical_index, qubit in enumerate(active):
        qc.measure(qubit, classical_index)

    return qc


def export_qasm(qc, filename="QCNN.qasm"):
    Path(filename).write_text(
        qasm3.dumps(qc),
        encoding="utf-8"
    )
    return filename


def get_execution(run_mode):
    mode = run_mode.lower().strip()

    if mode == "local":
        return {
            "mode": "local",
            "backend": AerSimulator(),
            "sampler": None
        }

    if mode == "cloud":
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

        token = os.getenv("IBM_QUANTUM_TOKEN")
        backend_name = os.getenv("IBM_QUANTUM_BACKEND")

        if not token:
            raise RuntimeError("IBM_QUANTUM_TOKEN is missing from .env.")

        if not backend_name:
            raise RuntimeError("IBM_QUANTUM_BACKEND is missing from .env.")

        service = QiskitRuntimeService(
    channel="ibm_quantum_platform",
    token=token,
    instance="Qiskit"
)
        backend = service.backend(backend_name)
        sampler = SamplerV2(mode=backend)

        return {
            "mode": "cloud",
            "backend": backend,
            "sampler": sampler
        }

    raise ValueError("run_mode must be 'local' or 'cloud'.")

def counts_from_sampler_result(result):
    pub_result = result[0]
    data = pub_result.data

    # Your circuit uses the default classical register "c"
    if hasattr(data, "c"):
        return data.c.get_counts()

    # Fallback for other register names
    names = list(data.keys())

    if not names:
        raise RuntimeError(
            "IBM Quantum returned no classical-register data."
        )

    register = getattr(data, names[0])

    if hasattr(register, "get_counts"):
        return dict(register.get_counts())

    raise RuntimeError(
        "Could not extract measurement counts from IBM Quantum result."
    )
def execute_circuit(qc, execution, shots):

    # ---------------- LOCAL ----------------
    if execution["mode"] == "local":

        circuit = transpile(
            qc,
            execution["backend"],
            optimization_level=1
        )

        result = execution["backend"].run(
            circuit,
            shots=shots
        ).result()

        return result.get_counts(circuit)

    # ---------------- CLOUD ----------------
    if execution["mode"] == "cloud":

        pass_manager = generate_preset_pass_manager(
            optimization_level=1,
            backend=execution["backend"]
        )

        circuit = pass_manager.run(qc)

        job = execution["sampler"].run(
            [circuit],
            shots=shots
        )

        result = job.result()

        return counts_from_sampler_result(result)

    raise ValueError(
        f"Unknown execution mode: {execution['mode']}"
    )

def counts_to_probabilities(counts, class_count):
    probabilities = np.zeros(class_count, dtype=float)
    total = sum(counts.values())

    if total == 0:
        return probabilities

    for bit_string, count in counts.items():
        try:
            value = int(bit_string.replace(" ", ""), 2)
        except ValueError:
            continue
        if value < class_count:
            probabilities[value] += count / total

    return probabilities


def predict_sample(sample, parameters, class_count, execution, shots):
    circuit = build_qcnn(
        sample.Features,
        parameters,
        class_count
    )
    counts = execute_circuit(
        circuit,
        execution,
        shots
    )
    probabilities = counts_to_probabilities(
        counts,
        class_count
    )
    return int(np.argmax(probabilities)), probabilities


def dataset_loss(dataset, parameters, class_count, execution, shots):
    losses = []

    for sample in dataset:
        _, probabilities = predict_sample(
            sample,
            parameters,
            class_count,
            execution,
            shots
        )
        label = int(sample.Label)

        if label < 0 or label >= class_count:
            raise ValueError(
                f"Label {label} is outside the class range 0..{class_count - 1}."
            )

        losses.append(
            -np.log(max(probabilities[label], 1e-12))
        )

    return float(np.mean(losses)) if losses else 0.0


def dataset_accuracy(dataset, parameters, class_count, execution, shots):
    if not dataset:
        return 0.0

    correct = 0

    for sample in dataset:
        prediction, _ = predict_sample(
            sample,
            parameters,
            class_count,
            execution,
            shots
        )
        correct += int(prediction == int(sample.Label))

    return correct / len(dataset)


def train(
    dataset,
    class_count,
    shots,
    epochs,
    learning_rate,
    execution,
    parameters
):
    if epochs < 1:
        raise ValueError("Epochs must be at least 1.")
    if shots < 1:
        raise ValueError("Shots must be at least 1.")
    if learning_rate <= 0:
        raise ValueError("Learning rate must be greater than zero.")

    parameters = np.asarray(parameters, dtype=float).copy()
    shift = np.pi / 2

    for epoch in range(epochs):
        gradients = np.zeros_like(parameters)

        for index in range(len(parameters)):
            plus = parameters.copy()
            minus = parameters.copy()
            plus[index] += shift
            minus[index] -= shift

            loss_plus = dataset_loss(
                dataset,
                plus,
                class_count,
                execution,
                shots
            )

            loss_minus = dataset_loss(
                dataset,
                minus,
                class_count,
                execution,
                shots
            )

            gradients[index] = 0.5 * (loss_plus - loss_minus)

        parameters -= learning_rate * gradients

        loss = dataset_loss(
            dataset,
            parameters,
            class_count,
            execution,
            shots
        )

        accuracy = dataset_accuracy(
            dataset,
            parameters,
            class_count,
            execution,
            shots
        )

        print(
            f"Epoch {epoch + 1}/{epochs} "
            f"Loss={loss:.6f} "
            f"Accuracy={accuracy:.4f}"
        )

    return TrainingResult(
        parameters=parameters,
        loss=dataset_loss(
            dataset,
            parameters,
            class_count,
            execution,
            shots
        ),
        accuracy=dataset_accuracy(
            dataset,
            parameters,
            class_count,
            execution,
            shots
        ),
        epochs=epochs
    )


def RunUniversalQCNN(
    dataset,
    classCount,
    shots,
    epochs,
    learningRate,
    run_mode="local"
):
    if not dataset:
        raise ValueError("Dataset must not be empty.")

    execution = get_execution(run_mode)
    qubit_count = required_qubits(len(dataset[0].Features))

    parameters = initialize_parameters(
        qubit_count,
        classCount
    )

    result = train(
        dataset,
        classCount,
        shots,
        epochs,
        learningRate,
        execution,
        parameters
    )

    final_circuit = build_qcnn(
        dataset[0].Features,
        result.parameters,
        classCount
    )

    export_qasm(
        final_circuit,
        "QCNN.qasm"
    )

    return result


def TrainModel(
    dataset,
    classCount,
    shots=20,
    epochs=10,
    learningRate=0.1,
    run_mode="local"
):
    return RunUniversalQCNN(
        dataset,
        classCount,
        shots,
        epochs,
        learningRate,
        run_mode
    )


def Predict(
    sample,
    parameters,
    classCount,
    shots=20,
    run_mode="local"
):
    execution = get_execution(run_mode)

    return predict_sample(
        sample,
        parameters,
        classCount,
        execution,
        shots
    )
