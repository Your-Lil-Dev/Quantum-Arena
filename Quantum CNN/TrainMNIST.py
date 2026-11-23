"""Train the QCNN on MNIST and report predictions."""

import argparse
import struct
from pathlib import Path

import numpy as np

from UniversalQCNN import Predict, RunUniversalQCNN, Sample


def read_mnist_labels(filename):
    with open(filename, "rb") as handle:
        magic, count = struct.unpack(">II", handle.read(8))

        if magic != 2049:
            raise ValueError(f"Invalid MNIST label file: {filename}")

        data = np.frombuffer(handle.read(count), dtype=np.uint8)

    if data.size != count:
        raise ValueError(f"MNIST label file is truncated: {filename}")

    return data


def read_mnist_images(filename, indices):
    """Read only the requested records, so --limit does not pay for all 60,000."""
    with open(filename, "rb") as handle:
        magic, count, rows, cols = struct.unpack(">IIII", handle.read(16))

        if magic != 2051:
            raise ValueError(f"Invalid MNIST image file: {filename}")

        size = rows * cols
        images = np.empty((len(indices), size), dtype=np.uint8)

        for position, index in enumerate(indices):
            if index < 0 or index >= count:
                raise ValueError(f"Image index {index} is outside 0..{count - 1}.")

            handle.seek(16 + index * size)
            record = handle.read(size)

            if len(record) != size:
                raise ValueError(f"MNIST image file is truncated: {filename}")

            images[position] = np.frombuffer(record, dtype=np.uint8)

    return images / 255.0, rows, cols


def downsample(images, rows, cols, qubit_count):
    """Area-pool each image to a square grid that fits 2^qubit_count amplitudes."""
    side = max(1, int(np.sqrt(1 << qubit_count)))
    block = max(1, int(np.ceil(max(rows, cols) / side)))
    padded_side = side * block

    padded = np.zeros((images.shape[0], padded_side, padded_side))
    padded[:, :rows, :cols] = images.reshape(-1, rows, cols)

    pooled = padded.reshape(-1, side, block, side, block).mean(axis=(2, 4))
    return pooled.reshape(images.shape[0], -1)


def load_dataset(images_file, labels_file, limit, classes, qubit_count):
    labels = read_mnist_labels(labels_file)

    keep = np.flatnonzero(labels < classes)

    if limit is not None:
        keep = keep[:limit]

    if keep.size == 0:
        raise ValueError("No samples found for the requested classes.")

    images, rows, cols = read_mnist_images(images_file, keep)
    features = downsample(images, rows, cols, qubit_count)

    return [
        Sample(features=features[position], label=int(labels[index]))
        for position, index in enumerate(keep)
    ]


def main():
    parser = argparse.ArgumentParser(description="Train Universal QCNN on MNIST.")

    parser.add_argument("--images", required=True, help="Path to MNIST image file.")
    parser.add_argument("--labels", required=True, help="Path to MNIST label file.")
    parser.add_argument("--classes", type=int, default=2, help="Number of classes.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of samples to load.")
    parser.add_argument(
        "--qubits",
        type=int,
        default=8,
        help="Qubits to simulate. Higher is exponentially slower.",
    )
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs.")
    parser.add_argument(
        "--learning-rate", type=float, default=0.1, help="Training learning rate."
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed.")

    args = parser.parse_args()

    if not Path(args.images).is_file():
        raise FileNotFoundError(f"MNIST image file not found: {args.images}")
    if not Path(args.labels).is_file():
        raise FileNotFoundError(f"MNIST label file not found: {args.labels}")
    if args.classes < 2:
        raise ValueError("--classes must be at least 2.")
    if args.qubits < 1:
        raise ValueError("--qubits must be at least 1.")
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be greater than zero.")

    print("Loading MNIST dataset...")

    dataset = load_dataset(
        args.images, args.labels, args.limit, args.classes, args.qubits
    )

    print(f"Loaded samples : {len(dataset)}")
    print(f"Classes        : {args.classes}")
    print(f"Qubits         : {args.qubits}")
    print(f"Features       : {len(dataset[0].features)}")
    print(f"Seed           : {args.seed}")
    print()
    print("Starting Universal QCNN training...")

    result = RunUniversalQCNN(
        dataset,
        args.classes,
        args.qubits,
        args.epochs,
        args.learning_rate,
        args.seed,
    )

    print()
    print("Training complete")
    print(f"Loss           : {result.loss:.6f}")
    print(f"Accuracy       : {result.accuracy:.4f}")
    print(f"Epochs         : {result.epochs}")
    print(f"Parameters     : {len(result.parameters)}")

    print()
    print("Sample predictions:")

    for sample in dataset[:5]:
        prediction, probabilities = Predict(
            sample, result.parameters, args.classes, args.qubits
        )
        print(
            f"  P(class {prediction}) = {probabilities[prediction]:.4f} "
            f"| predicted {prediction} | actual {sample.label}"
        )


if __name__ == "__main__":
    main()
