"""Self-check for the Q# bridge. Run with: python test_qcnn.py"""

import struct
import tempfile
from pathlib import Path

import numpy as np

import UniversalQCNN as qcnn
from qdk import qsharp
from TrainMNIST import downsample, read_mnist_images, read_mnist_labels


def test_shape_counts():
    assert qcnn.block_parameter_count() == 16
    assert qcnn.class_qubit_count(2) == 1
    assert qcnn.class_qubit_count(3) == 2
    assert qcnn.class_qubit_count(5) == 3
    assert qcnn.block_count(8, 1) == 3
    assert qcnn.block_count(5, 1) == 3
    assert qcnn.parameter_count(8, 2) == 48


def test_amplitude_encoding():
    # The rotation tree is the one piece of real new logic: check it lands on
    # the requested state, not just on some normalised state.
    amplitudes = qcnn.qubit_order(
        qcnn.prepare_input(np.arange(1, 17, dtype=float), 4), 4
    )
    qubits = qcnn._simulator.qubits(4)

    qsharp.eval(f"ResetAll({qubits});")
    qsharp.eval(
        f"UniversalQCNN.PrepareAmplitudes({qcnn._literal(amplitudes)}, {qubits});"
    )

    state = qcnn._simulator.amplitudes()
    assert np.allclose(np.abs(state) ** 2, amplitudes ** 2, atol=1e-9)


def test_qubit_zero_is_pixel_bit_zero():
    # Pixel index 1 sets qubit 0, which is the high bit of Q#'s state index.
    features = np.array([0.0, 1.0, 0.0, 0.0])
    amplitudes = qcnn.qubit_order(qcnn.prepare_input(features, 2), 2)
    qubits = qcnn._simulator.qubits(2)

    qsharp.eval(f"ResetAll({qubits});")
    qsharp.eval(
        f"UniversalQCNN.PrepareAmplitudes({qcnn._literal(amplitudes)}, {qubits});"
    )

    state = qcnn._simulator.amplitudes()
    assert int(np.argmax(np.abs(state) ** 2)) == 2


def test_probabilities_sum_to_one():
    features = np.random.default_rng(7).random(16)

    for class_count in (2, 3, 5):
        parameters = np.zeros(qcnn.parameter_count(4, class_count))
        probabilities = qcnn.class_probabilities(features, parameters, class_count, 4)

        assert probabilities.shape == (class_count,)
        assert abs(float(probabilities.sum()) - 1.0) < 1e-9


def test_odd_qubit_count_runs():
    features = np.random.default_rng(8).random(32)
    parameters = np.zeros(qcnn.parameter_count(5, 2))

    probabilities = qcnn.class_probabilities(features, parameters, 2, 5)

    assert abs(float(probabilities.sum()) - 1.0) < 1e-9


def test_wrong_parameter_count_is_rejected():
    try:
        qcnn.class_probabilities(np.ones(16), np.zeros(3), 2, 4)
    except ValueError:
        return
    raise AssertionError("expected ValueError for the wrong parameter count")


def test_negative_features_are_rejected():
    try:
        qcnn.prepare_input(np.array([1.0, -1.0]), 1)
    except ValueError:
        return
    raise AssertionError("expected ValueError for negative features")


def test_seed_is_reproducible():
    first = qcnn.initialize_parameters(4, 2, seed=3)
    second = qcnn.initialize_parameters(4, 2, seed=3)
    other = qcnn.initialize_parameters(4, 2, seed=4)

    assert np.allclose(first, second)
    assert not np.allclose(first, other)


def test_class_bit_mapping():
    # 2 qubits, qubit 0 survives and is the high bit of Q#'s state index.
    index_two = np.array([0, 0, 1, 0], dtype=complex)
    index_one = np.array([0, 1, 0, 0], dtype=complex)

    assert np.allclose(qcnn._marginalise(index_two, [0], 2, 2), [0.0, 1.0])
    assert np.allclose(qcnn._marginalise(index_one, [0], 2, 2), [1.0, 0.0])


def test_training_reduces_loss():
    rows = np.random.default_rng(11).random((4, 8))
    dataset = [
        qcnn.Sample(features=row, label=index % 2) for index, row in enumerate(rows)
    ]
    parameters = qcnn.initialize_parameters(3, 2, seed=5)

    initial = qcnn.evaluate(dataset, parameters, 2, 3)[0]
    result = qcnn.train(dataset, 2, 3, 3, 0.1, parameters)

    assert result.loss < initial


def test_mnist_parsing_and_pooling():
    pixels = np.arange(32, dtype=np.uint8).reshape(2, 4, 4)

    with tempfile.TemporaryDirectory() as directory:
        labels_path = Path(directory) / "labels"
        images_path = Path(directory) / "images"
        labels_path.write_bytes(struct.pack(">II", 2049, 2) + bytes([3, 7]))
        images_path.write_bytes(
            struct.pack(">IIII", 2051, 2, 4, 4) + pixels.tobytes()
        )

        assert list(read_mnist_labels(labels_path)) == [3, 7]

        images, rows, cols = read_mnist_images(images_path, [1, 0])
        assert (rows, cols) == (4, 4)
        assert np.allclose(images[0], pixels[1].ravel() / 255.0)

        # 4x4 pooled to 2x2 in 2x2 blocks, in the requested image order.
        expected = np.array([[18.5, 20.5], [26.5, 28.5], [2.5, 4.5], [10.5, 12.5]])
        assert np.allclose(downsample(images, rows, cols, 2), expected / 255.0)


def test_non_finite_features_are_rejected():
    try:
        qcnn.prepare_input(np.array([1.0, np.nan]), 1)
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-finite features")


def test_unreachable_class_shape_is_rejected():
    for qubit_count, class_count in ((5, 10), (2, 5), (4, 10)):
        try:
            qcnn.class_probabilities(
                np.ones(1 << qubit_count), [], class_count, qubit_count
            )
        except ValueError as error:
            assert "qubits" in str(error)
        else:
            raise AssertionError(
                f"expected ValueError for {qubit_count} qubits, {class_count} classes"
            )

    # 10 classes need 4 class qubits, and 7 is the first size that lands on
    # exactly 4 survivors (7 -> 4) with at least one trainable block.
    try:
        qcnn.class_probabilities(np.ones(32), [], 10, 5)
    except ValueError as error:
        assert "--qubits 7" in str(error)
    else:
        raise AssertionError("expected ValueError naming the smallest qubit count")


def test_training_rejects_unreachable_shape():
    dataset = [qcnn.Sample(features=np.ones(4), label=0)]

    try:
        qcnn.RunUniversalQCNN(dataset, 10, qubitCount=4, epochs=1)
    except ValueError:
        return
    raise AssertionError("expected ValueError before training a parameterless model")


def test_downsample_qubit_cap():
    try:
        downsample(np.zeros((1, 4, 4)), 4, 4, 17)
    except ValueError as error:
        assert "16" in str(error)
    else:
        raise AssertionError("expected ValueError above 16 qubits")


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]

    for test in tests:
        test()
        print(f"ok  {test.__name__}")

    print(f"\n{len(tests)} checks passed.")


if __name__ == "__main__":
    main()
