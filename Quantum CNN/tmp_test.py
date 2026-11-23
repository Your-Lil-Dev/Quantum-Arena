import test_qcnn as t
tests = ['test_non_finite_features_are_rejected','test_unreachable_class_shape_is_rejected','test_training_rejects_unreachable_shape','test_training_reduces_loss','test_downsample_qubit_cap','test_mnist_parsing_and_pooling']
for name in tests:
    f = getattr(t, name)
    try:
        f()
        print('PASS', name)
    except Exception as e:
        print('FAIL', name, e)
