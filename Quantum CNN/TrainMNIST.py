import argparse
import struct
from pathlib import Path

from UniversalQCNN import Sample, RunUniversalQCNN


def read_mnist_images(filename):
    with open(filename, "rb") as f:
        magic, count, rows, cols = struct.unpack(">IIII", f.read(16))

        if magic != 2051:
            raise ValueError(f"Invalid MNIST image file: {filename}")

        data = f.read(count * rows * cols)

    images = []

    image_size = rows * cols

    for i in range(count):
        start = i * image_size
        end = start + image_size

        image = data[start:end]

        # Convert pixels to floating-point values in [0, 1]
        features = [pixel / 255.0 for pixel in image]

        images.append(features)

    return images


def read_mnist_labels(filename):
    with open(filename, "rb") as f:
        magic, count = struct.unpack(">II", f.read(8))

        if magic != 2049:
            raise ValueError(f"Invalid MNIST label file: {filename}")

        data = f.read(count)

    return list(data)


def load_dataset(images_file, labels_file, limit=None, classes=2):
    images = read_mnist_images(images_file)
    labels = read_mnist_labels(labels_file)

    if len(images) != len(labels):
        raise ValueError(
            "Number of images and labels does not match."
        )

    dataset = []

    for features, label in zip(images, labels):

        # Keep only requested classes
        if label >= classes:
            continue

        dataset.append(
            Sample(
                Features=features,
                Label=int(label)
            )
        )

        if limit is not None and len(dataset) >= limit:
            break

    if not dataset:
        raise ValueError(
            "No samples found for the requested classes."
        )

    return dataset


def main():

    parser = argparse.ArgumentParser(
        description="Train Universal QCNN on MNIST."
    )

    parser.add_argument(
        "--images",
        required=True,
        help="Path to MNIST image file."
    )

    parser.add_argument(
        "--labels",
        required=True,
        help="Path to MNIST label file."
    )

    parser.add_argument(
        "--classes",
        type=int,
        default=2,
        help="Number of classes."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of samples to load."
    )

    parser.add_argument(
        "--shots",
        type=int,
        default=20,
        help="Number of quantum shots."
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=10,
        help="Number of training epochs."
    )

    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.1,
        help="Training learning rate."
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed."
    )

    parser.add_argument(
        "--run-mode",
        choices=["local", "cloud"],
        default="local",
        help="Quantum execution mode: local Aer or IBM Quantum cloud."
    )

    args = parser.parse_args()



    if not Path(args.images).is_file():
        raise FileNotFoundError(
            f"MNIST image file not found: {args.images}"
        )

    if not Path(args.labels).is_file():
        raise FileNotFoundError(
            f"MNIST label file not found: {args.labels}"
        )

    if args.classes < 2:
        raise ValueError(
            "--classes must be at least 2."
        )

    if args.limit is not None and args.limit < 1:
        raise ValueError(
            "--limit must be greater than zero."
        )


    print("Loading MNIST dataset...")

    dataset = load_dataset(
        args.images,
        args.labels,
        args.limit,
        args.classes
    )

    print(f"Loaded samples: {len(dataset)}")
    print(f"Classes: {args.classes}")
    print(f"Features per sample: {len(dataset[0].Features)}")
    print(f"Run mode: {args.run_mode}")



    print()
    print("Starting Universal QCNN training...")

    result = RunUniversalQCNN(
        dataset,
        args.classes,
        args.shots,
        args.epochs,
        args.learning_rate,
        args.run_mode
    )


    print()

    print("Training complete")


    print(f"Run mode : {args.run_mode}")
    print(f"Loss     : {result.loss:.6f}")
    print(f"Accuracy : {result.accuracy:.4f}")
    print(f"Epochs   : {result.epochs}")

    print()
    print("Final parameters:")
    print(result.parameters)

    print()
    print("QASM circuit exported to:")
    print("QCNN.qasm")


if __name__ == "__main__":
    main()