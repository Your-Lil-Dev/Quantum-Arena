# UniversalQCNN

A dynamic Quantum Convolutional Neural Network for image classification, written in **Q#** with a thin Python driver.

All quantum work — state preparation, convolution, pooling, measurement — happens in `src/QCNN.qs`. Python only reads MNIST, feeds amplitudes in, and runs the classical optimizer. There is no cloud execution and no shot sampling.

---

## Pipeline

```text
MNIST image
     │
     ▼
Area-pool to a square grid
     │
     ▼
Normalise to unit length
     │
     ▼
Q#: amplitude encoding
     │
     ▼
Q#: convolution → pooling → qubit reduction   (repeated until output qubits remain)
     │
     ▼
Q#: state vector
     │
     ▼
Exact class probabilities
     │
     ▼
Loss, prediction, parameter shift
```

---

## Files

```text
qsharp.json          Q# project marker
src/QCNN.qs          the whole quantum model
UniversalQCNN.py     driver: input prep, probabilities, optimizer
TrainMNIST.py        command line entry point
test_qcnn.py         self-checks (no test framework needed)
MNIST/               IDX files
```

---

## Running

```bash
pip install numpy qdk
python TrainMNIST.py --images "MNIST/train-images.idx3-ubyte" --labels "MNIST/train-labels.idx1-ubyte" --classes 2 --limit 20 --qubits 8 --epochs 1 --seed 7
```

| Flag | Meaning | Default |
|------|---------|---------|
| `--images`, `--labels` | MNIST IDX files | required |
| `--classes` | number of classes, labels `0 .. classes-1` | 2 |
| `--limit` | stop after this many matching samples | all |
| `--qubits` | qubits to simulate | 8 |
| `--epochs` | training epochs | 10 |
| `--learning-rate` | gradient step size | 0.1 |
| `--seed` | parameter seed; same seed, same run | random |

Self-checks:

```bash
python test_qcnn.py
```

---

## The circuit

### Encoding

The feature vector is area-pooled to `side × side`, where `side = floor(sqrt(2^qubits))` — 28×28 becomes 16×16 at 8 qubits. It is padded or trimmed to `2^qubits` values and normalised, then loaded as amplitudes:

```text
|0…0>  →  Σ aᵢ |i>
```

`PrepareAmplitudes` builds this with a rotation tree of `2^n - 1` rotations: one `Ry` per node, each child branch controlled on its parent. It uses magnitudes only, so features must be non-negative — true for pixels, and checked in Python.

### Convolution

Ten angles per convolution, applied to a pair of qubits:

```text
RY RZ (first) → RY RZ (second) → CNOT → RY RZ (first) → RY RZ (second) → CNOT → RY (first) RZ (second)
```

### Pooling

Six angles per pair. The pair is entangled and only the survivor is read afterwards:

```text
RY RZ (survivor) → RY RZ (discarded) → CNOT (discarded → survivor) → RY RZ (survivor)
```

The discarded qubit is never used again, so keeping its state and reading only the survivor gives the same reduced state as resetting it. No `Reset` is needed.

### Blocks

One block is convolution plus pooling: **16 angles**. The number of blocks comes from the qubit budget:

```text
BlockCount(qubits, outputQubits)  →  reduce by half (ceil) until outputQubits remain
```

For 8 qubits and 2 classes: `8 → 4 → 2 → 1`, so 3 blocks and **48 angles**. Nothing in the code fixes those numbers; they are computed from `ConvolutionParameterCount() + PoolingParameterCount()` and the qubit count.

Within a block, one set of 16 angles is shared by every pair — that is weight sharing, the same choice a classical convolution makes.

---

## Classification

`ClassQubitCount(classes)` rounds up to the next power of two. The survivors are ordered, and each survivor becomes one bit of the class index. Probabilities are read from the final state vector by summing `|amplitude|²` over all basis states with that bit pattern.

When `classes` is not a power of two, the unused bit patterns fold into the last class, so the probabilities always sum to 1.

Because the state vector is read directly, probabilities are **exact**. There are no shots and no sampling noise, which also means each circuit is simulated once instead of once per shot.

---

## Training

Negative log-likelihood, averaged over the dataset:

```text
L = -log(P[correct class])
```

Gradients use the parameter-shift rule, two circuit evaluations per angle:

```text
gᵢ = (L(θᵢ + π/2) − L(θᵢ − π/2)) / 2
θᵢ ← θᵢ − η gᵢ
```

Each epoch: `2 × angles × samples` circuit evaluations for the gradient, plus `samples` for loss and accuracy together.

---

## Cost

Q# has no direct state-vector load, so encoding a `2^n` amplitude vector costs a rotation tree whose simulation grows roughly fourfold per extra qubit. Measured on one machine, per circuit:

| Qubits | Features | Per circuit | One epoch, 20 samples |
|--------|----------|-------------|------------------------|
| 6 | 8 × 8 | ~0.004 s | ~10 s |
| 8 | 16 × 16 | ~0.06 s | ~2 min |
| 10 | 32 × 32 | ~1.8 s | ~1 h |

`--qubits 8` is the default because it is the largest budget that still trains in minutes. Ten qubits fits a full 28×28 image without downsampling, at roughly thirty times the cost.

---

## Limits

- Not a demonstration of quantum advantage. It is a small educational model.
- Simulation cost grows exponentially with qubits; 10 is the practical ceiling here.
- Accuracy is reported on the training set. There is no validation split.
- The encoder handles non-negative amplitudes only.
- One process, one machine. Nothing here is concurrent or resumable.

---

## Requirements

- Python 3.10+
- `numpy`
- `qdk` (provides the Q# interpreter; no .NET SDK install needed)

The IBM Quantum runtime, Qiskit, Aer and `python-dotenv` are no longer used.
