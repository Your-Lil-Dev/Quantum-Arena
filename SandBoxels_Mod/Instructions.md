
# ⚛ Quantum Computer for Sandboxels

This project adds an **educational quantum-computing system to Sandboxels**.

It combines the visual, particle-based sandbox environment of Sandboxels with a software-based quantum computer simulator. The goal is to let users **build and interact with a visual quantum computer while also executing real quantum-computing operations such as superposition, quantum gates, measurement, and entanglement**.

> ⚠️ **Important:** This does not turn Sandboxels into a physical quantum computer. The quantum calculations are performed by JavaScript on the classical computer running the game. Sandboxels provides the interactive visual environment, while the quantum simulator performs the mathematical quantum operations.

---

# 🎮 What is Sandboxels?

**Sandboxels** is a falling-sand physics sandbox game created by R74n.

It allows users to place different elements into a simulated environment and observe how they interact.

Examples include:

* 🌍 Land
* 💧 Liquids
* 🔥 Energy
* ⚙️ Machines
* 🧱 Solids
* 🧬 Life
* ☢️ Radiation
* 💻 Special elements

Elements can have properties such as:

* Temperature
* Gravity
* Density
* State
* Reactions
* Electrical behavior
* Movement
* Pressure
* Custom JavaScript behavior

Sandboxels is therefore also useful as a platform for experimentation and creating custom simulations.

Official project:

[https://github.com/R74nCom/sandboxels](https://github.com/R74nCom/sandboxels)

Official website:

[https://neal.fun/sandboxels/](https://neal.fun/sandboxels/)

---

# ⚛ What does this project add?

This project adds a custom **Quantum Computer** system.

The quantum computer has two parts:

```text
Sandboxels
     │
     ├── Visual quantum-computer elements
     │
     └── Quantum Computer Console
                 │
                 ├── Qubit state
                 ├── Quantum gates
                 ├── Superposition
                 ├── Entanglement
                 ├── Measurement
                 └── State-vector simulation
```

The visual components represent parts of a quantum processor, while the JavaScript simulator performs the actual quantum calculations.

---

# 🧠 How the quantum simulator works

The simulator represents a quantum system using a **state vector**.

For `N` qubits, the simulator stores:

```text
2^N
```

complex probability amplitudes.

For example, a 2-qubit system has:

```text
2² = 4
```

basis states:

```text
|00⟩
|01⟩
|10⟩
|11⟩
```

The simulator stores the complex amplitude associated with each state.

The probability of measuring a particular state is:

```text
P = |amplitude|²
```

The total probability satisfies:

```text
Σ |amplitude|² = 1
```

---

# 🔬 Qubits

A classical bit can be:

```text
0
```

or:

```text
1
```

A qubit can be represented as:

```text
|ψ⟩ = α|0⟩ + β|1⟩
```

where `α` and `β` are complex amplitudes.

The probabilities are:

```text
P(0) = |α|²
P(1) = |β|²
```

and:

```text
|α|² + |β|² = 1
```

The Sandboxels visual element represents the qubit, but its quantum state is maintained by the JavaScript quantum simulator.

---

# 🌌 Superposition

Superposition occurs when a qubit is in a combination of computational basis states.

Starting with:

```text
|0⟩
```

applying a Hadamard gate gives:

```text
H|0⟩ =
1/√2 |0⟩ +
1/√2 |1⟩
```

Therefore:

```text
P(0) = 50%
P(1) = 50%
```

The simulator calculates these amplitudes rather than simply displaying a fake "superposition" effect.

---

# 🔗 Entanglement

The simulator also supports multi-qubit entanglement.

For example:

```text
|00⟩
```

Apply:

```text
H 0
```

and then:

```text
CNOT 0 1
```

The resulting state is:

```text
1/√2 (|00⟩ + |11⟩)
```

This is a Bell state.

A measurement produces correlated results:

```text
00
```

or:

```text
11
```

with approximately equal probability.

The simulator can also analyze the state to determine whether qubits are entangled.

---

# 🎛️ Quantum gates

The quantum computer supports several gates.

## Hadamard

```text
h Q
```

Creates superposition.

Example:

```text
h 0
```

---

## Pauli-X

```text
x Q
```

Acts similarly to a quantum NOT operation:

```text
|0⟩ → |1⟩
|1⟩ → |0⟩
```

Example:

```text
x 0
```

---

## Pauli-Y

```text
y Q
```

Applies the Y Pauli operation.

---

## Pauli-Z

```text
z Q
```

Applies a phase flip.

---

## S gate

```text
s Q
```

Applies a π/2 phase operation.

---

## T gate

```text
t Q
```

Applies a π/4 phase operation.

---

## Rotation gates

The simulator supports:

```text
rx Q ANGLE
ry Q ANGLE
rz Q ANGLE
```

For example:

```text
rx 0 1.5708
```

rotates qubit 0 around the X axis.

---

# 🔗 Controlled-NOT

The CNOT gate operates on two qubits:

```text
cnot CONTROL TARGET
```

Example:

```text
cnot 0 1
```

The target qubit is flipped when the control qubit is in the `|1⟩` state.

CNOT is particularly important for creating entanglement.

### Important

The Sandboxels element called **Gate** is **not** the quantum CNOT gate.

The quantum `cnot` command is implemented by this project's quantum simulator.

---

# 🔄 SWAP

Two qubits can be exchanged with:

```text
swap Q1 Q2
```

Example:

```text
swap 0 1
```

---

# 🔗 CZ

The controlled-Z gate is available using:

```text
cz CONTROL TARGET
```

Example:

```text
cz 0 1
```

---

# 📏 Measurement

A qubit can be measured using:

```text
measure Q
```

Example:

```text
measure 0
```

The simulator calculates the probability distribution and randomly samples an outcome according to those probabilities.

Measurement also **collapses the quantum state**.

To measure every qubit:

```text
measure all
```

---

# 🖥️ Quantum Computer Console

The mod provides a command console inside Sandboxels.

Commands can be entered directly into the console.

Basic structure:

```text
command arguments
```

For example:

```text
init 2
```

creates a 2-qubit system.

Then:

```text
h 0
```

creates superposition on qubit 0.

Then:

```text
cnot 0 1
```

creates entanglement between qubits 0 and 1.

Finally:

```text
state
```

shows the quantum state.

---

# 📚 Command Reference

| Command       | Purpose                           |
| ------------- | --------------------------------- |
| `help`        | Show available commands           |
| `init N`      | Create an N-qubit system          |
| `reset`       | Reset the quantum computer        |
| `h Q`         | Hadamard gate                     |
| `x Q`         | Pauli-X                           |
| `y Q`         | Pauli-Y                           |
| `z Q`         | Pauli-Z                           |
| `s Q`         | S gate                            |
| `t Q`         | T gate                            |
| `rx Q A`      | X-axis rotation                   |
| `ry Q A`      | Y-axis rotation                   |
| `rz Q A`      | Z-axis rotation                   |
| `cnot C T`    | Controlled-NOT                    |
| `cz C T`      | Controlled-Z                      |
| `swap A B`    | Swap two qubits                   |
| `measure Q`   | Measure one qubit                 |
| `measure all` | Measure all qubits                |
| `state`       | Display state vector              |
| `probs`       | Display measurement probabilities |
| `entangle`    | Check for entanglement            |
| `bell A B`    | Create a Bell pair                |
| `clear`       | Clear console output              |

---

# 🧪 Example: Create a Bell Pair

Start with two qubits:

```text
init 2
```

Apply Hadamard:

```text
h 0
```

Apply CNOT:

```text
cnot 0 1
```

View the state:

```text
state
```

The result should correspond to:

```text
1/√2(|00⟩ + |11⟩)
```

Then:

```text
measure all
```

will produce either:

```text
00
```

or:

```text
11
```

with approximately equal probability.

---

# ⚛️ Using the Bell Command

The simulator also provides a shortcut:

```text
bell 0 1
```

This prepares a Bell pair between qubits 0 and 1.

It is essentially equivalent to:

```text
init 2
h 0
cnot 0 1
```

when starting from the appropriate initial state.

---

# 🧩 Visual Quantum Computer Elements

The mod also provides visual elements representing components of a quantum computer.

These include:

```text
Quantum Qubit
Quantum Coupler
Josephson Junction
Readout Resonator
Microwave Control
Quantum Measurement
```

These elements are primarily **visual representations of quantum-computer hardware**.

They do not individually perform quantum calculations through Sandboxels' particle physics.

The quantum state is maintained by the JavaScript simulator.

---

# 🧊 Relationship to real quantum computers

The architecture is inspired by modern superconducting quantum computers.

A simplified real architecture looks like:

```text
Classical Computer
       │
       ▼
Control Electronics
       │
       ▼
Microwave Signals
       │
       ▼
Cryogenic Wiring
       │
       ▼
Superconducting QPU
       │
       ├── Transmon Qubits
       ├── Couplers
       └── Readout Resonators
       │
       ▼
Measurement
       │
       ▼
Readout Electronics
       │
       ▼
Classical Computer
```

Real superconducting quantum computers operate at extremely low temperatures and require specialized microwave control and measurement hardware.

Sandboxels cannot reproduce those physical processes accurately. This project instead creates an **interactive conceptual representation** while performing the quantum mathematics in software.

---

# 🏗️ Project Architecture

The project can be thought of as three layers.

### Layer 1 — Sandboxels

Provides:

* Visual environment
* Particle simulation
* Custom elements
* User interaction
* Rendering

### Layer 2 — Quantum Computer Interface

Provides:

* Quantum Computer element
* Command console
* User commands
* State display
* Measurement display

### Layer 3 — Quantum Simulator

Performs:

* Complex-number calculations
* State-vector evolution
* Quantum gates
* Measurement
* State collapse
* Entanglement operations
* Probability calculations

The important distinction is:

```text
Sandboxels physics ≠ Quantum mechanics engine
```

The quantum simulator is implemented separately in JavaScript.

---

# 📁 Installing the Mod

This project is a Sandboxels JavaScript mod.

The mod file is:

```text
quantum_computer.js
```

For a local development copy of Sandboxels, place the mod where your Sandboxels installation expects custom mods.

Then load the mod through the Sandboxels **Mods** system.

If using the Mod Manager, provide the JavaScript filename or a complete URL to the `.js` file.

After loading the mod, refresh Sandboxels.

---

# 🛠️ Development

This project is designed to be developed alongside a local copy of Sandboxels.

Recommended structure:

```text
sandboxels-main/
│
├── index.html
├── ...
│
├── mods/
│   └── quantum_computer.js
│
└── README.md
```

The exact location may depend on how the local Sandboxels installation is configured.

---

# 🔧 Mod Development

Sandboxels mods are JavaScript files.

A mod can define custom elements and behavior using Sandboxels' modding API.

The quantum computer mod uses this capability to add custom quantum-computing elements and a user interface.

The quantum simulator itself is ordinary JavaScript and is independent from Sandboxels' falling-sand physics engine.

---

# ⚠️ Limitations

This project is a **quantum-computing simulator integrated into a sandbox game**, not a physical quantum computer.

It does not simulate:

* Actual superconducting materials
* Real Josephson-junction physics
* Electromagnetic fields
* Cryogenic temperatures
* Microwave hardware at physical scale
* Quantum decoherence at full physical fidelity
* Real hardware noise
* Real quantum processors
* Physical quantum tunneling in the Sandboxels environment

Instead, it implements the mathematical behavior of quantum states and gates using a classical computer.

---

# 🚀 Future Development

Possible future versions could add:

* Quantum circuit visualization
* Quantum gate blocks
* Circuit editor
* Bloch-sphere visualization
* Multi-qubit visualization
* Quantum teleportation
* Quantum Fourier Transform
* Grover's algorithm
* Deutsch-Jozsa algorithm
* Quantum error correction
* Noise models
* Decoherence simulation
* Measurement histograms
* Shot-based experiments
* Circuit export/import
* QASM support
* Qiskit interoperability
* Larger quantum systems
* Visual quantum wiring
* Automatic circuit execution
* Quantum algorithm demonstrations

---

# 🎯 Project Goal

The goal of this project is to make quantum computing **interactive and understandable**.

Instead of only writing:

```text
H → CNOT → Measure
```

users can interact with a visual quantum-computer environment while seeing the underlying quantum state and results.

The project therefore combines:

```text
🎮 Sandbox simulation
        +
⚛️ Quantum computing
        +
💻 JavaScript
        +
🧮 Linear algebra
        =
Interactive Quantum Computer
```

---

# 📜 Disclaimer

This project is an **educational software simulation**.

It should not be interpreted as a real quantum processor or a physically accurate simulation of a superconducting quantum computer.

The quantum operations are calculated classically using a state-vector representation. Sandboxels provides the interactive visualization and sandbox environment.

---

# Credits

This project builds upon the **Sandboxels** game and its modding system.

Sandboxels is developed by **R74n**.

Sandboxels:

[https://neal.fun/sandboxels/](https://neal.fun/sandboxels/)

Sandboxels source code:

[https://github.com/R74nCom/sandboxels/](https://github.com/R74nCom/sandboxels/)

This quantum-computing project is an independent educational modification and is not presented as an official Sandboxels feature.
