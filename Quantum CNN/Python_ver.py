import os
import struct
import argparse
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models


# ============================================================
# 1. LOAD LOCAL MNIST
# ============================================================

def load_local_mnist(images_path, labels_path):
    """Load MNIST data from explicit local IDX image/label files."""

    with open(labels_path, 'rb') as lbpath:
        magic, n = struct.unpack('>II', lbpath.read(8))
        if magic != 2049:
            raise ValueError(f"Invalid MNIST label file: {magic}")
        labels = np.fromfile(lbpath, dtype=np.uint8)

    if len(labels) != n:
        raise ValueError(f"Label count mismatch: {n} vs {len(labels)}")

    with open(images_path, 'rb') as imgpath:
        magic, num, rows, cols = struct.unpack('>IIII', imgpath.read(16))
        if magic != 2051:
            raise ValueError(f"Invalid MNIST image file: {magic}")
        images = np.fromfile(imgpath, dtype=np.uint8).reshape(num, rows, cols)

    if num != len(labels):
        raise ValueError(f"Image/label count mismatch: {num} vs {len(labels)}")
    if rows != 28 or cols != 28:
        raise ValueError(f"Expected 28x28 images, got {rows}x{cols}")

    return images, labels


def select_classes_and_samples(images, labels, class_count, per_class):
    """Select per_class examples from each class 0..class_count-1."""

    if not 1 <= class_count <= 10:
        raise ValueError("--classes must be between 1 and 10.")
    if per_class < 1:
        raise ValueError("--per-class must be at least 1.")

    selected_images = []
    selected_labels = []

    for class_id in range(class_count):
        indices = np.where(labels == class_id)[0]
        if len(indices) < per_class:
            raise ValueError(
                f"Class {class_id} has only {len(indices)} samples."
            )

        chosen = indices[:per_class]
        selected_images.append(images[chosen])
        selected_labels.append(labels[chosen])

    return (
        np.concatenate(selected_images, axis=0),
        np.concatenate(selected_labels, axis=0)
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Classical MNIST model with QCNN-compatible CLI parameters."
    )
    parser.add_argument("--images", required=True)
    parser.add_argument("--labels", required=True)
    parser.add_argument("--classes", type=int, default=10)
    parser.add_argument("--per-class", type=int, default=20)
    parser.add_argument("--shots", type=int, default=50)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    return parser.parse_args()


# ============================================================
# 2. COMMAND-LINE CONFIGURATION
# ============================================================

args = parse_args()

IMAGES_PATH = args.images
LABELS_PATH = args.labels
CLASS_COUNT = args.classes
PER_CLASS = args.per_class
SHOTS = args.shots
EPOCHS = args.epochs
LEARNING_RATE = args.learning_rate

BATCH_SIZE = 32
VALIDATION_SPLIT = 0.1

if EPOCHS < 1:
    raise ValueError("--epochs must be at least 1.")
if LEARNING_RATE <= 0:
    raise ValueError("--learning-rate must be greater than 0.")
if SHOTS < 1:
    raise ValueError("--shots must be at least 1.")


# ============================================================
# 3. LOAD DATA
# ============================================================

x_train, y_train = load_local_mnist(IMAGES_PATH, LABELS_PATH)

print("Successfully loaded classical dataset.")
print(f"Original features shape: {x_train.shape}")
print(f"Original labels shape: {y_train.shape}")


# ============================================================
# 4. SELECT SAME DATA SIZE AS QCNN
# ============================================================

x_train, y_train = select_classes_and_samples(
    x_train,
    y_train,
    CLASS_COUNT,
    PER_CLASS
)

SAMPLES_PER_EPOCH = len(x_train)

print(f"Classes used: {CLASS_COUNT}")
print(f"Samples per class: {PER_CLASS}")
print(f"Training samples: {SAMPLES_PER_EPOCH}")


# ============================================================
# 5. NORMALIZE PIXELS
# ============================================================

x_train = x_train.astype(np.float32) / 255.0

print("Pixel values normalized to [0, 1].")
print(f"Shots: {SHOTS} (QCNN parameter; not used by classical model)")
print(f"Learning rate: {LEARNING_RATE}")


# ============================================================
# 6. BUILD CLASSICAL NEURAL NETWORK
# ============================================================

model = models.Sequential([

    layers.Input(
        shape=(28, 28)
    ),

    layers.Flatten(),

    layers.Dense(
        128,
        activation='relu'
    ),

    layers.Dropout(
        0.2
    ),

    layers.Dense(
        64,
        activation='relu'
    ),

    layers.Dense(
        CLASS_COUNT,
        activation='softmax'
    )
])


# ============================================================
# 7. COMPILE MODEL
# ============================================================

model.compile(

    optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),

    loss='sparse_categorical_crossentropy',

    metrics=['accuracy']
)


# ============================================================
# 8. DISPLAY MODEL
# ============================================================

# ============================================================
# INITIAL LOSS / ACCURACY BEFORE TRAINING
# ============================================================

initial_loss, initial_accuracy = model.evaluate(
    x_train,
    y_train,
    verbose=0
)

print()
print(f"Initial training loss: {initial_loss:.6f}")
print(f"Initial training accuracy: {initial_accuracy * 100:.2f}%")


# ============================================================
# 9. TRAIN
# ============================================================

print()
print(
    f"--- Starting Classical Training ---"
)
print(f"Classes: {CLASS_COUNT}")
print(f"Samples per class: {PER_CLASS}")
print(f"Total training samples: {SAMPLES_PER_EPOCH}")
print(f"Epochs: {EPOCHS}")
print(f"Batch size: {BATCH_SIZE}")
print(f"Learning rate: {LEARNING_RATE}")
print(f"Shots: {SHOTS} (not used by classical model)")
print()


history = model.fit(

    x_train,

    y_train,

    epochs=EPOCHS,

    batch_size=BATCH_SIZE,

    validation_split=VALIDATION_SPLIT,

    shuffle=True,

    verbose=1
)


# ============================================================
# 10. TRAINING COMPLETED
# ============================================================

print()
print(
    "--- Training Completed ---"
)


# ============================================================
# 11. FINAL TRAINING ACCURACY
# ============================================================

final_loss, final_accuracy = model.evaluate(
    x_train,
    y_train,
    verbose=0
)

print(
    f"Final training loss: {final_loss:.6f}"
)

print(
    f"Final training accuracy: "
    f"{final_accuracy * 100:.2f}%"
)