namespace UniversalQCNN {

    open Std.Intrinsic;
    open Std.Math;

    // ------------------------------------------------------------------
    // Shape of the ansatz. These are the only gate counts in the project:
    // everything else is derived from them.
    // ------------------------------------------------------------------

    function ConvolutionParameterCount () : Int {
        return 10;
    }

    function PoolingParameterCount () : Int {
        return 6;
    }

    function BlockParameterCount () : Int {
        return ConvolutionParameterCount() + PoolingParameterCount();
    }

    /// Number of blocks needed to reduce qubitCount down to outputQubitCount.
    function BlockCount (qubitCount : Int, outputQubitCount : Int) : Int {
        if qubitCount < 1 {
            fail "qubitCount must be at least 1.";
        }
        if outputQubitCount < 1 {
            fail "outputQubitCount must be at least 1.";
        }
        if outputQubitCount > qubitCount {
            fail "outputQubitCount cannot exceed qubitCount.";
        }

        mutable active = qubitCount;
        mutable blocks = 0;

        while active > outputQubitCount {
            set active = (active + 1) / 2;
            set blocks += 1;
        }

        return blocks;
    }

    /// Qubits needed to hold classCount distinct outcomes.
    function ClassQubitCount (classCount : Int) : Int {
        if classCount < 2 {
            fail "classCount must be at least 2.";
        }

        mutable qubits = 0;
        mutable reachable = 1;

        while reachable < classCount {
            set reachable = reachable * 2;
            set qubits += 1;
        }

        return qubits;
    }

    // ------------------------------------------------------------------
    // Amplitude encoding
    // ------------------------------------------------------------------

    function SumSquares (values : Double[]) : Double {
        mutable total = 0.0;
        for value in values {
            set total += value * value;
        }
        return total;
    }

    function Scale (values : Double[], factor : Double) : Double[] {
        mutable scaled = [0.0, size = Length(values)];
        for index in 0 .. Length(values) - 1 {
            set scaled w/= index <- values[index] / factor;
        }
        return scaled;
    }

    /// |0...0> -> sum over i of amplitudes[i] |i>.
    /// Rotation tree of 2^n - 1 rotations, one per node.
    /// shortcut: magnitudes only, so amplitudes must be non-negative.
    /// Upgrade to a sign-aware version (extra Z per level) only if signed
    /// inputs are ever needed; MNIST pixels are non-negative.
    operation PrepareAmplitudes (amplitudes : Double[], qubits : Qubit[]) : Unit is Adj + Ctl {
        if Length(qubits) < 1 {
            fail "PrepareAmplitudes needs at least one qubit.";
        }
        if Length(amplitudes) != 1 <<< Length(qubits) {
            fail "PrepareAmplitudes needs exactly 2^qubitCount amplitudes.";
        }

        let norm = Sqrt(SumSquares(amplitudes));

        if norm <= 0.0 {
            fail "Amplitudes must not be all zero.";
        }

        PrepareRotationTree(Scale(amplitudes, norm), qubits);
    }

    operation PrepareRotationTree (amplitudes : Double[], qubits : Qubit[]) : Unit is Adj + Ctl {
        if Length(qubits) == 1 {
            Ry(2.0 * ArcTan2(amplitudes[1], amplitudes[0]), qubits[0]);
        } else {
            let half = Length(amplitudes) / 2;
            let left = amplitudes[0 .. half - 1];
            let right = amplitudes[half .. Length(amplitudes) - 1];
            let leftNorm = Sqrt(SumSquares(left));
            let rightNorm = Sqrt(SumSquares(right));
            let rest = qubits[1 .. Length(qubits) - 1];

            Ry(2.0 * ArcTan2(rightNorm, leftNorm), qubits[0]);

            // q0 = |0> branch prepares the left half, q0 = |1> the right half.
            X(qubits[0]);
            if leftNorm > 0.0 {
                Controlled PrepareRotationTree([qubits[0]], (Scale(left, leftNorm), rest));
            }
            X(qubits[0]);
            if rightNorm > 0.0 {
                Controlled PrepareRotationTree([qubits[0]], (Scale(right, rightNorm), rest));
            }
        }
    }

    // ------------------------------------------------------------------
    // Convolution and pooling
    // ------------------------------------------------------------------

    operation ApplyConvolution (parameters : Double[], first : Qubit, second : Qubit) : Unit is Adj + Ctl {
        if Length(parameters) != ConvolutionParameterCount() {
            fail "ApplyConvolution needs ConvolutionParameterCount() angles.";
        }

        Ry(parameters[0], first);
        Rz(parameters[1], first);
        Ry(parameters[2], second);
        Rz(parameters[3], second);
        CNOT(first, second);
        Ry(parameters[4], first);
        Rz(parameters[5], first);
        Ry(parameters[6], second);
        Rz(parameters[7], second);
        CNOT(first, second);
        Ry(parameters[8], first);
        Rz(parameters[9], second);
    }

    /// Entangles the pair and leaves the survivor in the reduced state of the
    /// pair. The discarded qubit is never touched again, so measuring only the
    /// survivor is the same as resetting the other one - no Reset needed.
    operation ApplyPooling (parameters : Double[], survivor : Qubit, discarded : Qubit) : Unit is Adj + Ctl {
        if Length(parameters) != PoolingParameterCount() {
            fail "ApplyPooling needs PoolingParameterCount() angles.";
        }

        Ry(parameters[0], survivor);
        Rz(parameters[1], survivor);
        Ry(parameters[2], discarded);
        Rz(parameters[3], discarded);
        CNOT(discarded, survivor);
        Ry(parameters[4], survivor);
        Rz(parameters[5], survivor);
    }

    /// Applies one block and returns the surviving qubit indices.
    operation ApplyBlock (parameters : Double[], active : Int[], qubits : Qubit[]) : Int[] {
        if Length(parameters) != BlockParameterCount() {
            fail "ApplyBlock needs BlockParameterCount() angles.";
        }
        if Length(active) < 1 {
            fail "ApplyBlock needs at least one active qubit.";
        }

        let convolution = parameters[0 .. ConvolutionParameterCount() - 1];
        let pooling = parameters[ConvolutionParameterCount() .. Length(parameters) - 1];

        mutable survivors = [];
        mutable index = 0;

        while index + 1 < Length(active) {
            let first = active[index];
            let second = active[index + 1];
            ApplyConvolution(convolution, qubits[first], qubits[second]);
            ApplyPooling(pooling, qubits[first], qubits[second]);
            set survivors += [first];
            set index += 2;
        }

        // Odd qubit count: the last qubit passes through untouched.
        if index < Length(active) {
            set survivors += [active[index]];
        }

        return survivors;
    }

    /// Prepares the input, runs every block, and returns the indices of the
    /// output qubits. The qubits stay entangled in the simulator so the caller
    /// can read exact amplitudes.
    operation Run (amplitudes : Double[], parameters : Double[], outputQubitCount : Int, qubits : Qubit[]) : Int[] {
        let qubitCount = Length(qubits);
        let blocks = BlockCount(qubitCount, outputQubitCount);

        if Length(parameters) != blocks * BlockParameterCount() {
            fail "Parameter count does not match BlockCount * BlockParameterCount.";
        }

        ResetAll(qubits);
        PrepareAmplitudes(amplitudes, qubits);

        mutable active = [];
        for index in 0 .. qubitCount - 1 {
            set active += [index];
        }

        for block in 0 .. blocks - 1 {
            let start = block * BlockParameterCount();
            let blockParameters = parameters[start .. start + BlockParameterCount() - 1];
            set active = ApplyBlock(blockParameters, active, qubits);
        }

        return active;
    }
}
