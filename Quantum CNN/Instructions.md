# UniversalQCNN

A **dynamic Quantum Convolutional Neural Network (QCNN)** for image classification, implemented with **Python, Qiskit, Qiskit Aer, OpenQASM 3, and IBM Quantum**.

UniversalQCNN is a hybrid quantum-classical machine-learning project that processes classical image data through a parameterized quantum circuit and uses classical optimization to train the quantum parameters.

The architecture is designed to be **dynamic**: the number of QCNN blocks and trainable parameters are calculated from the number of input qubits and required output qubits instead of manually defining a fixed number of blocks.

---

## Overview

The project follows this pipeline:

```text
MNIST Image
     │
     ▼
Pixel Normalization
     │
     ▼
Feature Vector
     │
     ▼
Quantum State Preparation
     │
     ▼
Quantum Convolution
     │
     ▼
Quantum Pooling
     │
     ▼
Qubit Reduction
     │
     ▼
Repeat Until Required Output Qubits Remain
     │
     ▼
Measurement
     │
     ▼
Class Probabilities
     │
     ▼
Prediction
     │
     ▼
Loss
     │
     ▼
Parameter Optimization
```

The project can execute the quantum circuit either on a **local Qiskit Aer simulator** or through **IBM Quantum**.

---

# What Is a QCNN?

A Quantum Convolutional Neural Network is a quantum machine-learning architecture inspired by the structure of classical convolutional neural networks.

Instead of applying classical filters to image pixels, a QCNN applies parameterized quantum operations to groups of qubits.

The architecture repeatedly performs:

```text
Convolution
     ↓
Pooling
     ↓
Qubit reduction
```

until only the number of qubits required for the output classes remains.

For example, a binary classifier using 8 input qubits can follow:

```text
8 qubits
   ↓
4 qubits
   ↓
2 qubits
   ↓
1 qubit
   ↓
Measurement
```

The number of blocks is calculated programmatically rather than manually specified.

---

# Main Features

* Dynamic QCNN architecture
* Dynamic qubit calculation
* Dynamic block calculation
* Parameterized quantum convolution
* Parameterized quantum pooling
* Quantum state preparation
* Classical loss calculation
* Parameter optimization
* MNIST support
* Local quantum simulation
* IBM Quantum cloud execution
* Measurement-based classification
* OpenQASM 3 circuit export
* Command-line training configuration

---

# Architecture

The project contains three major components.

## `UniversalQCNN.py`

This is the main quantum machine-learning implementation.

It contains:

* Dataset sample definitions
* QCNN parameter management
* Input preparation
* Quantum circuit construction
* Quantum convolution
* Quantum pooling
* Circuit execution
* Probability calculation
* Prediction
* Loss calculation
* Accuracy calculation
* Parameter training
* Local/cloud execution
* QASM export

The quantum circuit is built using Qiskit's `QuantumCircuit` and `StatePreparation`.

---

## `TrainMNIST.py`

This file provides the MNIST training interface.

It:

1. Reads the MNIST IDX image file.
2. Reads the MNIST IDX label file.
3. Selects the requested classes.
4. Converts pixel values to floating-point features.
5. Creates `Sample` objects.
6. Calls the UniversalQCNN training system.
7. Displays the final loss, accuracy, epochs, and learned parameters.

The MNIST images are converted from integer pixel values into normalized values in the range `[0, 1]`.

---

## `Python_ver.py`

This is a **classical baseline model** used for comparison.

It loads the same type of MNIST data and trains a classical neural network consisting of:

```text
28 × 28 Input
     ↓
Flatten
     ↓
Dense 128 + ReLU
     ↓
Dropout
     ↓
Dense 64 + ReLU
     ↓
Output Layer
```

The output layer contains one neuron for each selected class and uses softmax.

This provides a classical reference point for evaluating the QCNN.

---

# Quantum Data Encoding

The first stage of the quantum model converts the classical feature vector into a quantum state.

The required number of qubits is calculated from the number of input features:

$$
n = \lceil \log_2(N) \rceil
$$

where:

* \(N\) = number of input features
* \(n\) = required number of qubits

The implementation automatically calculates this value.

For example:

```text
256 features
     ↓
ceil(log2(256))
     ↓
8 qubits
```

The feature vector is then padded or truncated to match the quantum-state dimension:

$$
2^n
$$

and normalized before state preparation.

---

# Quantum State Preparation

The prepared feature vector is encoded into the quantum register using Qiskit's `StatePreparation`.

Conceptually:

$$
|\psi\rangle =
\sum_{i=0}^{2^n-1} a_i |i\rangle
$$

where \(a_i\) represents the normalized feature amplitude.

The important design choice is that the state preparation is generated from the **current input features**.

The project therefore does not require a giant fixed gate sequence corresponding to one particular image.

---

# Quantum Convolution

Each convolution operation works on two qubits.

The implementation uses **10 trainable parameters** per convolution.

Its basic sequence contains:

```text
RY
RZ
RY
RZ
CNOT
RY
RZ
RY
RZ
CNOT
RY
RZ
```

The rotation angles come from the model's trainable parameter vector rather than being permanently fixed in the circuit.

The CNOT operations allow information between the two qubits to become entangled.

---

# Quantum Pooling

Pooling reduces the number of active qubits.

Each pooling operation uses **6 trainable parameters**.

Its structure consists of:

```text
RY/RZ on survivor
RY/RZ on discarded qubit
CNOT discarded → survivor
RY/RZ on survivor
```

After the operation, the discarded qubit is reset and removed from the active QCNN structure.

Therefore:

```text
2 qubits → 1 active qubit
```

---

# Dynamic QCNN Blocks

A key feature of UniversalQCNN is that the individual blocks are generated algorithmically.

The program maintains an `active` list containing the qubits currently participating in the QCNN.

For example:

```text
Initial:

[0, 1, 2, 3, 4, 5, 6, 7]
```

The first block creates pairs:

```text
(0,1)
(2,3)
(4,5)
(6,7)
```

After pooling:

```text
[0,2,4,6]
```

The next block automatically operates on:

```text
(0,2)
(4,6)
```

producing:

```text
[0,4]
```

The next block produces:

```text
[0]
```

This behavior is implemented through a loop over the active qubits rather than separate manually written Block 0, Block 1, and Block 2 functions.

---

# Trainable Parameters

Each QCNN block contains:

```text
10 convolution parameters
+
6 pooling parameters
=
16 parameters
```

The implementation calculates the required number of blocks and allocates:

$$
16 \times \text{number of blocks}
$$

trainable parameters.
For the common 8-qubit binary-classification configuration:

```text
8 qubits → 4 qubits → 2 qubits → 1 qubit

3 blocks × 16 parameters

= 48 trainable parameters
```

---

# Classification

The number of output qubits is determined from the number of classes.

The implementation calculates:

$$
n_{classes} = \lceil \log_2(C) \rceil
$$

where \(C\) is the number of classes.

For binary classification:

```text
2 classes
   ↓
1 output qubit
```

For four classes:

```text
4 classes
   ↓
2 output qubits
```

After the QCNN reaches the required number of output qubits, they are measured.

The resulting measurement counts are converted into class probabilities.

The predicted class is the class with the highest probability.

---

# Loss Function

The project uses a negative log-likelihood style loss.

For the correct class \(y\):

$$
L = -\log(P_y)
$$

where \(P_y\) is the probability assigned to the correct class.

The dataset loss is the mean loss across all samples.

---

# Training

The QCNN parameters are optimized classically.

For each parameter, the training process evaluates the loss at:

$$
\theta_i + \frac{\pi}{2}
$$

and:

$$
\theta_i - \frac{\pi}{2}
$$

The gradient estimate is then calculated as:

$$
g_i =
\frac{L(\theta_i+\pi/2)-L(\theta_i-\pi/2)}{2}
$$

and the parameters are updated using:

$$
\theta_i \leftarrow \theta_i-\eta g_i
$$

where \(\eta\) is the learning rate.

The implementation performs these evaluations for every trainable parameter during each epoch.

---

# Local Quantum Execution

The default execution mode is local.

The project uses:

**Qiskit Aer Simulator**

for local circuit execution.

The circuit is transpiled and executed for the requested number of shots.

Example:

```text
Circuit
   ↓
Qiskit Aer
   ↓
Measurement
   ↓
Counts
   ↓
Probabilities
```

---

# IBM Quantum Execution

The project can also execute circuits through IBM Quantum.

The cloud mode reads:

```text
IBM_QUANTUM_TOKEN
IBM_QUANTUM_BACKEND
```

from environment variables.

The circuit is then transpiled for the selected IBM Quantum backend and executed using the Qiskit Runtime sampler interface.

This allows the same QCNN implementation to be tested beyond a local simulator.

---

# OpenQASM Export

After training, the project constructs a final QCNN circuit using the learned parameters.

The circuit is exported using Qiskit's OpenQASM 3 functionality:

```python
qasm3.dumps(qc)
```

and written to:

```text
QCNN.qasm
```

## This allows the generated quantum circuit to be inspected or used in other OpenQASM-compatible workflows.

# MNIST Workflow

The MNIST training program accepts:

```text
--images
--labels
--classes
--limit
--shots
--epochs
--learning-rate
--seed
--run-mode
```

These parameters allow experiments to be configured without modifying the source code.

Example:

```bash
python TrainMNIST.py ^
  --images "MNIST/train-images.idx3-ubyte" ^
  --labels "MNIST/train-labels.idx1-ubyte" ^
  --classes 2 ^
  --limit 20 ^
  --shots 20 ^
  --epochs 1 ^
  --learning-rate 0.1 ^
  --run-mode local
```

For IBM Quantum execution:

```bash
python TrainMNIST.py ^
  --images "MNIST/train-images.idx3-ubyte" ^
  --labels "MNIST/train-labels.idx1-ubyte" ^
  --classes 2 ^
  --limit 20 ^
  --shots 20 ^
  --epochs 1 ^
  --learning-rate 0.1 ^
  --run-mode cloud
```

The training program passes the dataset and configuration into `RunUniversalQCNN()`.

---

# Classical Baseline

The repository also contains a classical neural-network implementation for comparison.

The classical model uses:

```text
Flatten
  ↓
Dense(128, ReLU)
  ↓
Dropout(0.2)
  ↓
Dense(64, ReLU)
  ↓
Softmax output
```

It is trained using the Adam optimizer and sparse categorical cross-entropy.

This is useful because QCNN performance should be evaluated against classical approaches rather than assuming that a quantum model is automatically superior.

---

# Project Structure

```text
UniversalQCNN/
│
├── UniversalQCNN.py
├── TrainMNIST.py
├── Python_ver.py
│
├── MNIST/
│   ├── train-images.idx3-ubyte
│   └── train-labels.idx1-ubyte
│
├── QCNN.qasm
├── .env
├── README.md
└── LICENSE
```

---

# Installation

Install the required Python packages:

```bash
pip install numpy qiskit qiskit-aer python-dotenv
```

For IBM Quantum cloud execution, install the required IBM Runtime package:

```bash
pip install qiskit-ibm-runtime
```

The project imports Qiskit, Qiskit Aer, NumPy, and `python-dotenv` directly.

---

# IBM Quantum Configuration

Cloud execution requires environment variables.

Create a `.env` file:

```text
IBM_QUANTUM_TOKEN=YOUR_TOKEN
IBM_QUANTUM_BACKEND=YOUR_BACKEND
```

Do **not** commit your real IBM Quantum token to GitHub.

Add `.env` to `.gitignore`:

```text
.env
```

---

# Why This Project Is Different

The main architectural idea behind UniversalQCNN is **dynamic QCNN generation**.

A conventional experimental implementation might manually define:

```text
Block 0
Block 1
Block 2
```

with fixed qubit connections.

UniversalQCNN instead determines:

```text
Input feature count
        ↓
Required qubits
        ↓
Required output qubits
        ↓
Required QCNN blocks
        ↓
Generate active-qubit pairs
        ↓
Apply convolution + pooling
        ↓
Reduce active qubits
```

This makes the implementation more general and easier to experiment with.

---

# Current Scope

The project currently focuses on demonstrating a hybrid quantum-classical classification pipeline.

It supports:

* Multiple class counts
* Variable input feature sizes
* Dynamically calculated qubit counts
* Dynamically calculated QCNN blocks
* Local quantum simulation
* IBM Quantum execution
* Parameterized QCNN training
* OpenQASM 3 export

The MNIST training interface currently reads the original 28 × 28 MNIST images and converts their pixels into feature vectors.

---

# Limitations

This project should **not** be interpreted as proof of quantum advantage.

Important limitations include:

* Quantum simulation becomes increasingly expensive as the number of qubits increases.
* State preparation can be a significant computational cost.
* Real quantum hardware introduces noise and gate errors.
* Parameter optimization can require many circuit evaluations.
* Small experimental datasets may not represent real-world performance.
* Classical neural networks can be extremely competitive for image classification.

Therefore, meaningful evaluation requires comparison with classical baselines and careful benchmarking.

---

# Future Development

Potential future work includes:

* Multi-class QCNN experiments
* Larger training datasets
* Alternative quantum convolution ansätze
* Alternative pooling strategies
* Different qubit-pairing architectures
* Noise-aware training
* Quantum error mitigation
* Hardware benchmarking
* More efficient feature encoding
* Comparison with CNN architectures
* Larger-scale experiments
* Gradient-based optimization improvements

---

# Research Objective

The long-term objective of UniversalQCNN is to explore whether dynamically generated QCNN architectures can provide useful approaches for hybrid quantum-classical machine learning.

The project focuses particularly on the relationship between:

```text
Data Encoding
      +
Quantum Feature Extraction
      +
Qubit Reduction
      +
Parameter Optimization
      ↓
Quantum Machine Learning
```

Rather than claiming that quantum models are automatically better, the project provides a framework in which their behavior can be experimentally investigated.

---

# Disclaimer

UniversalQCNN is an experimental and educational quantum machine-learning project.

It does not claim practical quantum advantage. Any comparison with classical machine-learning models should be based on reproducible experiments, appropriate datasets, computational resources, and statistically meaningful evaluation.

---
