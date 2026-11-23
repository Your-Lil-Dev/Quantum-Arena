"""Self-check for the Q# bridge. Run with: python test_qcnn.py"""

import numpy as np

import UniversalQCNN as qcnn
from qdk import qsharp


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


def main():
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]

    for test in tests:
        test()
        print(f"ok  {test.__name__}")

    print(f"\n{len(tests)} checks passed.")


if __name__ == "__main__":
    main()
