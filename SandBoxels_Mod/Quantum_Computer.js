/*
  ============================================================================
  quantum_computer.js  —  Sandboxels mod
  ============================================================================
  Adds a "Quantum Computer" machine element to Sandboxels (sandboxels.r74n.com,
  also playable on neal.fun). Click a placed Quantum Computer pixel to open an
  in-game command console that drives a REAL statevector quantum simulator:

    - true complex amplitudes (not a fake/approximated model)
    - single-qubit gates: H, X, Y, Z, S, S†, T, T†, RX, RY, RZ
    - two-qubit gates: CNOT/CX, CZ, SWAP
    - three-qubit gate: CCX (Toffoli)
    - Born-rule measurement with wavefunction collapse
    - entanglement detection via reduced-density-matrix purity
    - LINK command to physically entangle two separate Quantum Computer
      pixels placed next to each other into one shared register

  INSTALL
    Open Sandboxels -> Mods button -> type: quantum_computer.js
    (or paste a raw URL to this file) -> press Enter -> refresh the page.

  USAGE
    1. Place a "Quantum Computer" pixel (category: Special).
    2. Click on the placed pixel to open its console.
    3. Type "help" and press Enter for the full command list.

  QUICK EXAMPLE (Bell pair / entanglement)
    init 2
    h 0
    cx 0 1
    state
    measure 0
    measure 1        <- always matches the result of qubit 0

  Author: community mod, built from documented Sandboxels modding API
  (elements.js properties, pixelMap, changePixel, createPixel, onClicked).
  ============================================================================
*/
(function () {
  "use strict";

  if (typeof elements === "undefined") {
    console.warn("quantum_computer.js: Sandboxels globals not found. Load this as a Sandboxels mod.");
    return;
  }

  var MAX_QUBITS = 10; // 2^10 = 1024 amplitudes per register; keeps things fast & stable

  // ==========================================================================
  // 1. LINEAR ALGEBRA CORE — statevector simulation with parallel re[]/im[]
  // ==========================================================================

  function C(re, im) { return { re: re, im: im || 0 }; }

  var SQRT1_2 = Math.SQRT1_2;

  function newState(n) {
    var size = 1 << n;
    var re = new Float64Array(size);
    var im = new Float64Array(size);
    re[0] = 1; // |00...0>
    return { n: n, re: re, im: im };
  }

  function normalize(s) {
    var norm = 0;
    for (var i = 0; i < s.re.length; i++) norm += s.re[i] * s.re[i] + s.im[i] * s.im[i];
    norm = Math.sqrt(norm);
    if (norm < 1e-12) return;
    for (var i = 0; i < s.re.length; i++) { s.re[i] /= norm; s.im[i] /= norm; }
  }


  // ==========================================================================
  // NOISE / DECOHERENCE MODEL
  // ==========================================================================
  // This is a stochastic quantum-trajectory approximation. It keeps a pure
  // statevector while reproducing the expected behavior of common noise
  // channels over many runs. It is NOT a physical hardware simulation.
  function probabilityQ1(s, q) {
    var bit = 1 << q, p = 0;
    for (var i = 0; i < s.re.length; i++) {
      if (i & bit) p += s.re[i] * s.re[i] + s.im[i] * s.im[i];
    }
    return Math.max(0, Math.min(1, p));
  }

  function applyPauliNoise(s, q, kind) {
    if (kind === "x") apply1(s, q, GATES.x);
    else if (kind === "y") apply1(s, q, GATES.y);
    else if (kind === "z") apply1(s, q, GATES.z);
  }

  function amplitudeDampTrajectory(s, q, p) {
    p = Math.max(0, Math.min(1, p));
    if (Math.random() >= p) {
      // No-jump trajectory: suppress |1> amplitudes and renormalize.
      var bit = 1 << q, keep = Math.sqrt(1 - p);
      for (var i = 0; i < s.re.length; i++) if (i & bit) {
        s.re[i] *= keep; s.im[i] *= keep;
      }
      normalize(s);
      return false;
    }
    // Jump trajectory: project onto |1>, then flip to |0>.
    var bit2 = 1 << q;
    for (var j = 0; j < s.re.length; j++) if (!(j & bit2)) {
      s.re[j] = 0; s.im[j] = 0;
    }
    normalize(s);
    apply1(s, q, GATES.x);
    return true;
  }

  function phaseDampTrajectory(s, q, p) {
    p = Math.max(0, Math.min(1, p));
    // A Z phase kick with probability p reproduces dephasing statistics.
    if (Math.random() < p) apply1(s, q, GATES.z);
  }

  function depolarizeTrajectory(s, q, p) {
    p = Math.max(0, Math.min(1, p));
    if (Math.random() >= p) return;
    var r = Math.random();
    if (r < 1 / 3) applyPauliNoise(s, q, "x");
    else if (r < 2 / 3) applyPauliNoise(s, q, "y");
    else applyPauliNoise(s, q, "z");
  }

  function readoutError(bit, p) {
    return Math.random() < p ? 1 - bit : bit;
  }

  // Apply a 2x2 complex matrix [[a,b],[c,d]] to a single target qubit
  function apply1(s, target, m) {
    var bit = 1 << target;
    for (var i = 0; i < s.re.length; i++) {
      if (i & bit) continue; // only process the "0" half of each pair
      var j = i | bit;
      var r0 = s.re[i], q0 = s.im[i], r1 = s.re[j], q1 = s.im[j];
      var nr0 = m.a.re * r0 - m.a.im * q0 + m.b.re * r1 - m.b.im * q1;
      var nq0 = m.a.re * q0 + m.a.im * r0 + m.b.re * q1 + m.b.im * r1;
      var nr1 = m.c.re * r0 - m.c.im * q0 + m.d.re * r1 - m.d.im * q1;
      var nq1 = m.c.re * q0 + m.c.im * r0 + m.d.re * q1 + m.d.im * r1;
      s.re[i] = nr0; s.im[i] = nq0; s.re[j] = nr1; s.im[j] = nq1;
    }
  }

  // Apply a 2x2 matrix to `target` only when `control` bit is 1 (controlled-U)
  function applyControlled1(s, control, target, m) {
    var cbit = 1 << control, tbit = 1 << target;
    for (var i = 0; i < s.re.length; i++) {
      if (i & tbit) continue;
      if (!(i & cbit)) continue;
      var j = i | tbit;
      var r0 = s.re[i], q0 = s.im[i], r1 = s.re[j], q1 = s.im[j];
      var nr0 = m.a.re * r0 - m.a.im * q0 + m.b.re * r1 - m.b.im * q1;
      var nq0 = m.a.re * q0 + m.a.im * r0 + m.b.re * q1 + m.b.im * r1;
      var nr1 = m.c.re * r0 - m.c.im * q0 + m.d.re * r1 - m.d.im * q1;
      var nq1 = m.c.re * q0 + m.c.im * r0 + m.d.re * q1 + m.d.im * r1;
      s.re[i] = nr0; s.im[i] = nq0; s.re[j] = nr1; s.im[j] = nq1;
    }
  }

  function applyCZ(s, a, b) {
    var abit = 1 << a, bbit = 1 << b;
    for (var i = 0; i < s.re.length; i++) {
      if ((i & abit) && (i & bbit)) { s.re[i] *= -1; s.im[i] *= -1; }
    }
  }

  function applySwap(s, a, b) {
    var abit = 1 << a, bbit = 1 << b;
    for (var i = 0; i < s.re.length; i++) {
      var ba = (i & abit) ? 1 : 0, bb = (i & bbit) ? 1 : 0;
      if (ba === bb) continue;
      var j = i ^ abit ^ bbit;
      if (i < j) {
        var tr = s.re[i]; s.re[i] = s.re[j]; s.re[j] = tr;
        var ti = s.im[i]; s.im[i] = s.im[j]; s.im[j] = ti;
      }
    }
  }

  function applyToffoli(s, c1, c2, target) {
    var c1b = 1 << c1, c2b = 1 << c2, tb = 1 << target;
    for (var i = 0; i < s.re.length; i++) {
      if (i & tb) continue;
      if (!(i & c1b) || !(i & c2b)) continue;
      var j = i | tb;
      var tr = s.re[i]; s.re[i] = s.re[j]; s.re[j] = tr;
      var ti = s.im[i]; s.im[i] = s.im[j]; s.im[j] = ti;
    }
  }

  function measureQubit(s, target) {
    var bit = 1 << target, p1 = 0;
    for (var i = 0; i < s.re.length; i++) if (i & bit) p1 += s.re[i] * s.re[i] + s.im[i] * s.im[i];
    var outcome = Math.random() < p1 ? 1 : 0;
    for (var i = 0; i < s.re.length; i++) {
      var b = (i & bit) ? 1 : 0;
      if (b !== outcome) { s.re[i] = 0; s.im[i] = 0; }
    }
    normalize(s);
    return { outcome: outcome, prob: outcome === 1 ? p1 : 1 - p1 };
  }

  // Reduced density matrix (2x2) for one qubit, tracing out all others
  function reducedRho(s, target) {
    var bit = 1 << target;
    var r00 = 0, r11 = 0, r01re = 0, r01im = 0;
    for (var i = 0; i < s.re.length; i++) {
      if (i & bit) continue;
      var j = i | bit;
      var ar = s.re[i], ai = s.im[i], br = s.re[j], bi = s.im[j];
      r00 += ar * ar + ai * ai;
      r11 += br * br + bi * bi;
      r01re += ar * br + ai * bi;
      r01im += ai * br - ar * bi;
    }
    return { r00: r00, r11: r11, r01re: r01re, r01im: r01im };
  }

  function purityOf(rho) {
    return rho.r00 * rho.r00 + rho.r11 * rho.r11 + 2 * (rho.r01re * rho.r01re + rho.r01im * rho.r01im);
  }

  // Kronecker product of two statevectors -> combined register (A's qubits
  // keep indices 0..nA-1, B's qubits are appended at nA..nA+nB-1)
  function kron(sA, sB) {
    var n = sA.n + sB.n;
    var sizeA = sA.re.length, sizeB = sB.re.length;
    var out = newState(n);
    for (var ib = 0; ib < sizeB; ib++) {
      for (var ia = 0; ia < sizeA; ia++) {
        var idx = ia | (ib << sA.n);
        // (ar+i*ai)*(br+i*bi)
        var ar = sA.re[ia], ai = sA.im[ia], br = sB.re[ib], bi = sB.im[ib];
        out.re[idx] = ar * br - ai * bi;
        out.im[idx] = ar * bi + ai * br;
      }
    }
    return out;
  }

  var GATES = {
    h:   { a: C(SQRT1_2), b: C(SQRT1_2), c: C(SQRT1_2), d: C(-SQRT1_2) },
    x:   { a: C(0), b: C(1), c: C(1), d: C(0) },
    y:   { a: C(0), b: C(0, -1), c: C(0, 1), d: C(0) },
    z:   { a: C(1), b: C(0), c: C(0), d: C(-1) },
    s:   { a: C(1), b: C(0), c: C(0), d: C(0, 1) },
    sdg: { a: C(1), b: C(0), c: C(0), d: C(0, -1) },
    t:   { a: C(1), b: C(0), c: C(0), d: C(SQRT1_2, SQRT1_2) },
    tdg: { a: C(1), b: C(0), c: C(0), d: C(SQRT1_2, -SQRT1_2) },
    id:  { a: C(1), b: C(0), c: C(0), d: C(1) }
  };
  function RX(t) { var c = Math.cos(t / 2), s = Math.sin(t / 2); return { a: C(c), b: C(0, -s), c: C(0, -s), d: C(c) }; }
  function RY(t) { var c = Math.cos(t / 2), s = Math.sin(t / 2); return { a: C(c), b: C(-s), c: C(s), d: C(c) }; }
  function RZ(t) { var c = Math.cos(t / 2), s = Math.sin(t / 2); return { a: C(c, -s), b: C(0), c: C(0), d: C(c, s) }; }

  // ==========================================================================
  // 2. QUANTUM REGISTER WRAPPER — used by each Quantum Computer pixel
  // ==========================================================================

  function QuantumRegister(n) {
    this.state = newState(n);
    this.history = []; // list of applied gate labels, for display

    // Educational hardware/noise model. Time constants are in microseconds.
    this.noise = {
      enabled: false,
      t1_us: 100000,
      t2_us: 80000,
      depolarizing: 0,
      readout: 0,
      gateError: 0,
      temperature_mK: 10,
      time_us: 0
    };
  }
  QuantumRegister.prototype.n = function () { return this.state.n; };
  QuantumRegister.prototype.checkQ = function (q) {
    if (typeof q !== "number" || isNaN(q) || q < 0 || q >= this.n()) {
      throw new Error("Qubit index out of range (0-" + (this.n() - 1) + ")");
    }
  };
  QuantumRegister.prototype.gate1 = function (name, q) {
    this.checkQ(q);
    apply1(this.state, q, GATES[name]);
    this.applyGateError(q);
    this.history.push(name.toUpperCase() + " q" + q);
  };
  QuantumRegister.prototype.rot = function (name, q, theta) {
    this.checkQ(q);
    var m = name === "rx" ? RX(theta) : name === "ry" ? RY(theta) : RZ(theta);
    apply1(this.state, q, m);
    this.applyGateError(q);
    this.history.push(name.toUpperCase() + " q" + q + " (" + theta.toFixed(3) + " rad)");
  };
  QuantumRegister.prototype.cx = function (c, t) {
    this.checkQ(c); this.checkQ(t);
    if (c === t) throw new Error("Control and target must differ");
    applyControlled1(this.state, c, t, GATES.x);
    this.applyGateError(c); this.applyGateError(t);
    this.history.push("CNOT q" + c + " -> q" + t);
  };
  QuantumRegister.prototype.cz = function (a, b) {
    this.checkQ(a); this.checkQ(b);
    if (a === b) throw new Error("Qubits must differ");
    applyCZ(this.state, a, b);
    this.applyGateError(a); this.applyGateError(b);
    this.history.push("CZ q" + a + ", q" + b);
  };
  QuantumRegister.prototype.swap = function (a, b) {
    this.checkQ(a); this.checkQ(b);
    if (a === b) throw new Error("Qubits must differ");
    applySwap(this.state, a, b);
    this.applyGateError(a); this.applyGateError(b);
    this.history.push("SWAP q" + a + ", q" + b);
  };
  QuantumRegister.prototype.ccx = function (c1, c2, t) {
    this.checkQ(c1); this.checkQ(c2); this.checkQ(t);
    if (c1 === c2 || c1 === t || c2 === t) throw new Error("Qubits must all differ");
    applyToffoli(this.state, c1, c2, t);
    this.applyGateError(c1); this.applyGateError(c2); this.applyGateError(t);
    this.history.push("TOFFOLI q" + c1 + ", q" + c2 + " -> q" + t);
  };
  QuantumRegister.prototype.measure = function (q) {
    this.checkQ(q);
    var r = measureQubit(this.state, q);
    var physicalOutcome = readoutError(r.outcome, this.noise.readout);
    this.history.push("MEASURE q" + q + " = " + physicalOutcome + " (p=" + r.prob.toFixed(3) + ")");
    r.trueOutcome = r.outcome;
    r.outcome = physicalOutcome;
    return r;
  };

  QuantumRegister.prototype.injectError = function (q, kind) {
    this.checkQ(q);
    kind = String(kind || "").toLowerCase();
    if (kind !== "x" && kind !== "y" && kind !== "z") {
      throw new Error("Error type must be X, Y, or Z");
    }
    applyPauliNoise(this.state, q, kind);
    this.history.push("ERROR " + kind.toUpperCase() + " q" + q);
  };

  QuantumRegister.prototype.applyGateError = function (q) {
    if (this.noise.gateError > 0 && Math.random() < this.noise.gateError) {
      var r = Math.random();
      applyPauliNoise(this.state, q, r < 1/3 ? "x" : r < 2/3 ? "y" : "z");
      return true;
    }
    return false;
  };

  QuantumRegister.prototype.decohere = function (dt_us) {
    if (!this.noise.enabled || this.n() < 1) return { t1: 0, t2: 0, dep: 0 };
    dt_us = Math.max(0, dt_us);
    this.noise.time_us += dt_us;

    var pT1 = this.noise.t1_us > 0 ? 1 - Math.exp(-dt_us / this.noise.t1_us) : 0;
    var pT2 = this.noise.t2_us > 0 ? 1 - Math.exp(-dt_us / this.noise.t2_us) : 0;
    var counts = { t1: 0, t2: 0, dep: 0 };

    for (var q = 0; q < this.n(); q++) {
      if (pT1 > 0 && amplitudeDampTrajectory(this.state, q, pT1)) counts.t1++;
      if (pT2 > 0) {
        var before = this.state.re.slice();
        var beforeIm = this.state.im.slice();
        phaseDampTrajectory(this.state, q, Math.min(1, pT2 / 2));
        var changed = false;
        for (var k = 0; k < before.length; k++) {
          if (before[k] !== this.state.re[k] || beforeIm[k] !== this.state.im[k]) { changed = true; break; }
        }
        if (changed) counts.t2++;
      }
      if (this.noise.depolarizing > 0) {
        var oldX = this.state.re.slice(), oldY = this.state.im.slice();
        depolarizeTrajectory(this.state, q, this.noise.depolarizing);
        for (var z = 0; z < oldX.length; z++) {
          if (oldX[z] !== this.state.re[z] || oldY[z] !== this.state.im[z]) { counts.dep++; break; }
        }
      }
    }
    return counts;
  };

  QuantumRegister.prototype.hardwareInfo = function () {
    return {
      qubits: this.n(),
      temperature_mK: this.noise.temperature_mK,
      t1_us: this.noise.t1_us,
      t2_us: this.noise.t2_us,
      noise: this.noise.enabled,
      gateError: this.noise.gateError,
      readoutError: this.noise.readout,
      depolarizing: this.noise.depolarizing,
      elapsed_us: this.noise.time_us
    };
  };

  QuantumRegister.prototype.purity = function (q) {
    this.checkQ(q);
    return purityOf(reducedRho(this.state, q));
  };
  QuantumRegister.prototype.bloch = function (q) {
    this.checkQ(q);
    var rho = reducedRho(this.state, q);
    return { x: 2 * rho.r01re, y: 2 * rho.r01im, z: rho.r00 - rho.r11, purity: purityOf(rho) };
  };
  // Average P(|1>) across all qubits — used to drive the pixel's glow color
  QuantumRegister.prototype.avgProb1 = function () {
    var total = 0;
    for (var q = 0; q < this.n(); q++) {
      var bit = 1 << q, p = 0;
      for (var i = 0; i < this.state.re.length; i++) {
        if (i & bit) p += this.state.re[i] * this.state.re[i] + this.state.im[i] * this.state.im[i];
      }
      total += p;
    }
    return this.n() ? total / this.n() : 0;
  };
  // "superposition-ness": how far amplitudes are from a single basis state (0 = classical, 1 = maximal spread)
  QuantumRegister.prototype.entropyEstimate = function () {
    var probs = [], H = 0;
    for (var i = 0; i < this.state.re.length; i++) {
      var p = this.state.re[i] * this.state.re[i] + this.state.im[i] * this.state.im[i];
      if (p > 1e-12) H -= p * Math.log2(p);
    }
    var maxH = Math.log2(this.state.re.length) || 1;
    return H / maxH;
  };
  QuantumRegister.prototype.stateLines = function (maxLines) {
    var lines = [];
    for (var i = 0; i < this.state.re.length; i++) {
      var re = this.state.re[i], im = this.state.im[i];
      var p = re * re + im * im;
      if (p < 1e-6) continue;
      var label = i.toString(2);
      while (label.length < this.n()) label = "0" + label;
      var amp = re.toFixed(3) + (im >= 0 ? "+" : "-") + Math.abs(im).toFixed(3) + "i";
      lines.push("|" + label + "\u27E9  amp=" + amp + "  P=" + (p * 100).toFixed(1) + "%");
      if (lines.length >= maxLines) { lines.push("... (truncated)"); break; }
    }
    return lines;
  };

  // ==========================================================================
  // 3. UI — floating command console injected into the page
  // ==========================================================================

  var activePixel = null; // the pixel object whose console is currently open

  function ensureStyles() {
    if (document.getElementById("qc-style")) return;
    var css =
      "#qc-modal{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);" +
      "width:420px;max-width:92vw;background:#0b0620;border:2px solid #8a4dff;" +
      "border-radius:10px;box-shadow:0 0 30px rgba(138,77,255,.6);z-index:99999;" +
      "font-family:'Consolas',monospace;color:#d9c9ff;display:none;}" +
      "#qc-header{display:flex;justify-content:space-between;align-items:center;" +
      "padding:8px 12px;background:linear-gradient(90deg,#3a1a70,#7a2bd6);" +
      "border-radius:8px 8px 0 0;font-weight:bold;color:#fff;}" +
      "#qc-close{cursor:pointer;background:#ff4d6d;border:none;color:#fff;" +
      "border-radius:5px;padding:2px 8px;font-weight:bold;}" +
      "#qc-log{height:260px;overflow-y:auto;padding:8px 10px;font-size:12px;" +
      "white-space:pre-wrap;background:#050213;line-height:1.35;}" +
      "#qc-inputrow{display:flex;border-top:1px solid #4b2a8f;}" +
      "#qc-input{flex:1;background:#120a2e;border:none;color:#e6d9ff;padding:8px 10px;" +
      "font-family:inherit;font-size:13px;outline:none;}" +
      "#qc-run{background:#8a4dff;border:none;color:#fff;padding:0 14px;cursor:pointer;" +
      "font-weight:bold;}" +
      "#qc-log::-webkit-scrollbar{width:8px;}#qc-log::-webkit-scrollbar-thumb{background:#5a2fb0;border-radius:4px;}" +
      ".qc-err{color:#ff6b6b;}.qc-ok{color:#7CFFCB;}.qc-cmd{color:#9fd7ff;}";
    var style = document.createElement("style");
    style.id = "qc-style";
    style.textContent = css;
    document.head.appendChild(style);
  }
function ensureModal() {
  ensureStyles();

  var modal = document.getElementById("qc-modal");
  if (modal) return modal;

  modal = document.createElement("div");
  modal.id = "qc-modal";

  modal.innerHTML =
    '<div id="qc-header">' +
      '<span id="qc-title">⚛ Quantum Computer</span>' +
      '<button id="qc-close" type="button">X</button>' +
    '</div>' +
    '<div id="qc-log"></div>' +
    '<div id="qc-inputrow">' +
      '<input id="qc-input" type="text" ' +
      'placeholder="type a command... (try: help)" autocomplete="off"/>' +
      '<button id="qc-run" type="button">RUN</button>' +
    '</div>';

  document.body.appendChild(modal);

  document.getElementById("qc-close").addEventListener(
    "click",
    closeConsole
  );

  document.getElementById("qc-run").addEventListener(
    "click",
    runFromInput
  );

  document.getElementById("qc-input").addEventListener(
    "keydown",
    function (e) {
      if (e.key === "Enter") {
        runFromInput();
      }
    }
  );

  return modal;
}

  function logLine(text, cls) {
    var log = document.getElementById("qc-log");
    var div = document.createElement("div");
    if (cls) div.className = cls;
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  function clearLog() {
    document.getElementById("qc-log").innerHTML = "";
  }

  function openConsole(pixel) {
    if (!pixel.qc) initPixelRegister(pixel, 1);
    ensureModal();
    activePixel = pixel;
    document.getElementById("qc-modal").style.display = "block";
    document.getElementById("qc-title").textContent =
      "Quantum Computer @ (" + pixel.x + "," + pixel.y + ")  —  " + pixel.qc.reg.n() + " qubit(s)";
    clearLog();
    logLine("Quantum console ready. Type 'help' for commands.", "qc-ok");
    if (pixel.qc.linked) logLine("[linked register: qubits shared with another computer]", "qc-ok");
    document.getElementById("qc-input").focus();
  }

  function closeConsole() {
    var modal = document.getElementById("qc-modal");
    if (modal) modal.style.display = "none";
    activePixel = null;
  }

  function runFromInput() {
    var input = document.getElementById("qc-input");
    var text = input.value;
    input.value = "";
    if (!text.trim()) return;
    logLine("> " + text, "qc-cmd");
    if (!activePixel || activePixel.element !== "quantum_computer") {
      logLine("This computer is no longer on the board.", "qc-err");
      return;
    }
    try {
      runCommand(activePixel, text.trim());
    } catch (e) {
      logLine("Error: " + e.message, "qc-err");
    }
  }

  // ==========================================================================
  // 4. COMMAND PARSER
  // ==========================================================================

  function initPixelRegister(pixel, n) {
    pixel.qc = { reg: new QuantumRegister(Math.max(1, Math.min(MAX_QUBITS, n | 0))), linked: false };
  }

  var HELP_TEXT = [
    "== Quantum Computer console ==",
    "init <n>            reset with n fresh qubits in |0>  (max " + MAX_QUBITS + ")",
    "h <q>                Hadamard (creates superposition)",
    "x|y|z <q>            Pauli gates",
    "s|sdg|t|tdg <q>      phase gates (S, S-dagger, T, T-dagger)",
    "rx|ry|rz <q> <deg>   rotation gate by an angle in degrees",
    "cx <c> <t>           CNOT (also: cnot)  — entangles c and t",
    "cz <a> <b>           controlled-Z",
    "swap <a> <b>         swap two qubits",
    "ccx <c1> <c2> <t>    Toffoli (also: toffoli)",
    "measure <q>          collapse one qubit (Born rule), print result",
    "measureall           collapse and print every qubit",
    "state                list nonzero amplitudes & probabilities",
    "probs                bar chart of P(qubit=1) for each qubit",
    "bloch <q>            approx. Bloch vector (x,y,z) + purity",
    "entangled            list which qubits are entangled with the rest",
    "link                 fuse with an adjacent Quantum Computer's register",
    "reset                clear back to |0...0> (keeps qubit count)",
    "error <q> <x|y|z>    inject a Pauli quantum error",
    "noise on|off         enable/disable hardware noise model",
    "t1 <microseconds>    set relaxation time T1",
    "t2 <microseconds>    set dephasing time T2",
    "temp <mK>            set simulated cryostat temperature",
    "gateerror <0..1>     set per-gate stochastic error rate",
    "readouterror <0..1>  set measurement readout error rate",
    "depolarize <0..1>    set depolarizing noise probability per tick",
    "hardware             show simulated hardware/noise status",
    "cooldown <mK>        move simulated temperature toward target",
    "clear                clear the console log",
    "help                 show this list"
  ].join("\n");

  function fmt(n) { return (Math.round(n * 1000) / 1000).toString(); }
  function degToRad(d) { return (d * Math.PI) / 180; }

  function findAdjacentQuantumComputer(pixel) {
    if (typeof pixelMap === "undefined") return null;
    var dirs = [[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]];
    for (var i = 0; i < dirs.length; i++) {
      var nx = pixel.x + dirs[i][0], ny = pixel.y + dirs[i][1];
      if (!pixelMap[nx] || !pixelMap[nx][ny]) continue;
      var np = pixelMap[nx][ny];
      if (np.element === "quantum_computer" && np !== pixel) return np;
    }
    return null;
  }

  function runCommand(pixel, raw) {
    var parts = raw.split(/\s+/);
    var cmd = parts[0].toLowerCase();
    var reg = pixel.qc.reg;

    function nums(count) {
      var out = [];
      for (var i = 1; i <= count; i++) {
        var v = parseFloat(parts[i]);
        if (isNaN(v)) throw new Error("Expected " + count + " numeric argument(s) for '" + cmd + "'");
        out.push(v);
      }
      return out;
    }

    switch (cmd) {
      case "help":
        HELP_TEXT.split("\n").forEach(function (l) { logLine(l); });
        return;

      case "init": {
        var n = nums(1)[0] | 0;
        if (n < 1 || n > MAX_QUBITS) throw new Error("n must be 1-" + MAX_QUBITS);
        initPixelRegister(pixel, n);
        document.getElementById("qc-title").textContent =
          "Quantum Computer @ (" + pixel.x + "," + pixel.y + ")  —  " + n + " qubit(s)";
        logLine("Initialized " + n + " qubit(s) in |" + "0".repeat(n) + "\u27E9.", "qc-ok");
        return;
      }

      case "h": case "x": case "y": case "z": case "s": case "sdg": case "t": case "tdg": {
        var q = nums(1)[0] | 0;
        reg.gate1(cmd, q);
        logLine(cmd.toUpperCase() + " applied to qubit " + q + ".", "qc-ok");
        return;
      }

      case "rx": case "ry": case "rz": {
        var a = nums(2);
        var q2 = a[0] | 0, deg = a[1];
        reg.rot(cmd, q2, degToRad(deg));
        logLine(cmd.toUpperCase() + "(" + deg + "\u00B0) applied to qubit " + q2 + ".", "qc-ok");
        return;
      }

      case "cx": case "cnot": {
        var cc = nums(2);
        reg.cx(cc[0] | 0, cc[1] | 0);
        logLine("CNOT: control q" + (cc[0] | 0) + " -> target q" + (cc[1] | 0) + ".", "qc-ok");
        return;
      }

      case "cz": {
        var cz = nums(2);
        reg.cz(cz[0] | 0, cz[1] | 0);
        logLine("CZ applied between q" + (cz[0] | 0) + " and q" + (cz[1] | 0) + ".", "qc-ok");
        return;
      }

      case "swap": {
        var sw = nums(2);
        reg.swap(sw[0] | 0, sw[1] | 0);
        logLine("Swapped q" + (sw[0] | 0) + " and q" + (sw[1] | 0) + ".", "qc-ok");
        return;
      }

      case "ccx": case "toffoli": {
        var tf = nums(3);
        reg.ccx(tf[0] | 0, tf[1] | 0, tf[2] | 0);
        logLine("Toffoli: controls q" + (tf[0]|0) + ",q" + (tf[1]|0) + " -> target q" + (tf[2]|0) + ".", "qc-ok");
        return;
      }

      case "measure": {
        var mq = nums(1)[0] | 0;
        var r = reg.measure(mq);
        logLine("Qubit " + mq + " collapsed to |" + r.outcome + "\u27E9  (probability was " + fmt(r.prob * 100) + "%).", "qc-ok");
        return;
      }

      case "measureall": {
        var outs = [];
        for (var i = 0; i < reg.n(); i++) outs.push(reg.measure(i).outcome);
        logLine("Result: |" + outs.join("") + "\u27E9", "qc-ok");
        return;
      }

      case "state": {
        var lines = reg.stateLines(32);
        if (!lines.length) logLine("(zero state — this shouldn't happen)");
        else lines.forEach(function (l) { logLine(l); });
        return;
      }

      case "probs": {
        for (var qi = 0; qi < reg.n(); qi++) {
          var bit = 1 << qi, p1 = 0;
          for (var i2 = 0; i2 < reg.state.re.length; i2++) {
            if (i2 & bit) p1 += reg.state.re[i2] * reg.state.re[i2] + reg.state.im[i2] * reg.state.im[i2];
          }
          var barLen = Math.round(p1 * 20);
          logLine("q" + qi + " P(1)=" + fmt(p1 * 100).padStart(5) + "%  [" + "#".repeat(barLen) + "-".repeat(20 - barLen) + "]");
        }
        return;
      }

      case "bloch": {
        var bq = nums(1)[0] | 0;
        var b = reg.bloch(bq);
        logLine("q" + bq + " Bloch vector: x=" + fmt(b.x) + " y=" + fmt(b.y) + " z=" + fmt(b.z));
        logLine("purity=" + fmt(b.purity) + (b.purity < 0.999 ? "  (mixed -> entangled with other qubits)" : "  (pure state)"));
        return;
      }

      case "entangled": {
        var any = false;
        for (var eq = 0; eq < reg.n(); eq++) {
          var pur = reg.purity(eq);
          if (pur < 0.999) { logLine("q" + eq + " is entangled (purity=" + fmt(pur) + ")", "qc-ok"); any = true; }
        }
        if (!any) logLine("No entanglement detected — all qubits are in pure product states.");
        return;
      }

      case "link": {
        var other = findAdjacentQuantumComputer(pixel);
        if (!other) throw new Error("No adjacent Quantum Computer pixel found to link with.");
        if (pixel.qc.reg === other.qc.reg) throw new Error("Already linked to that computer.");
        var totalN = reg.n() + other.qc.reg.n();
        if (totalN > MAX_QUBITS) throw new Error("Linking would exceed the " + MAX_QUBITS + "-qubit limit.");
        var offsetB = reg.n();
        var combined = new QuantumRegister(0);
        combined.state = kron(reg.state, other.qc.reg.state);
        combined.history = reg.history.concat(other.qc.reg.history);
        pixel.qc.reg = combined;
        other.qc.reg = combined;
        pixel.qc.linked = true;
        other.qc.linked = true;
        logLine("Linked! Combined register now has " + totalN + " qubits.", "qc-ok");
        logLine("This computer owns qubits 0-" + (offsetB - 1) + "; the other owns qubits " + offsetB + "-" + (totalN - 1) + ".", "qc-ok");
        logLine("Any gate you run here (e.g. 'cx " + (offsetB - 1) + " " + offsetB + "') can now entangle the two machines.", "qc-ok");
        return;
      }


      case "error": {
        if (parts.length < 3) throw new Error("Usage: error <q> <x|y|z>");
        reg.injectError(parseInt(parts[1], 10), parts[2]);
        logLine("Injected " + parts[2].toUpperCase() + " error into q" + (parseInt(parts[1],10)) + ".", "qc-ok");
        return;
      }

      case "noise": {
        if (parts[1] !== "on" && parts[1] !== "off") throw new Error("Usage: noise on|off");
        reg.noise.enabled = parts[1] === "on";
        logLine("Hardware noise model: " + (reg.noise.enabled ? "ON" : "OFF"), "qc-ok");
        return;
      }

      case "t1": {
        var t1 = nums(1)[0];
        if (t1 <= 0) throw new Error("T1 must be > 0 microseconds");
        reg.noise.t1_us = t1;
        logLine("T1 = " + t1 + " µs", "qc-ok");
        return;
      }

      case "t2": {
        var t2 = nums(1)[0];
        if (t2 <= 0) throw new Error("T2 must be > 0 microseconds");
        reg.noise.t2_us = t2;
        logLine("T2 = " + t2 + " µs", "qc-ok");
        return;
      }

      case "temp": {
        var temp = nums(1)[0];
        if (temp < 0) throw new Error("Temperature cannot be negative");
        reg.noise.temperature_mK = temp;
        logLine("Simulated cryostat temperature = " + temp + " mK", "qc-ok");
        return;
      }

      case "gateerror": {
        var ge = nums(1)[0];
        if (ge < 0 || ge > 1) throw new Error("gateerror must be between 0 and 1");
        reg.noise.gateError = ge;
        logLine("Gate error rate = " + (ge * 100).toFixed(4) + "%", "qc-ok");
        return;
      }

      case "readouterror": {
        var re = nums(1)[0];
        if (re < 0 || re > 1) throw new Error("readouterror must be between 0 and 1");
        reg.noise.readout = re;
        logLine("Readout error rate = " + (re * 100).toFixed(4) + "%", "qc-ok");
        return;
      }

      case "depolarize": {
        var dp = nums(1)[0];
        if (dp < 0 || dp > 1) throw new Error("depolarize must be between 0 and 1");
        reg.noise.depolarizing = dp;
        logLine("Depolarizing probability/tick = " + (dp * 100).toFixed(4) + "%", "qc-ok");
        return;
      }

      case "hardware": {
        var hi = reg.hardwareInfo();
        logLine("=== Simulated superconducting hardware ===");
        logLine("Qubits: " + hi.qubits);
        logLine("Cryostat: " + hi.temperature_mK + " mK");
        logLine("T1: " + hi.t1_us + " µs | T2: " + hi.t2_us + " µs");
        logLine("Noise: " + (hi.noise ? "ON" : "OFF"));
        logLine("Gate error: " + (hi.gateError * 100).toFixed(4) + "%");
        logLine("Readout error: " + (hi.readoutError * 100).toFixed(4) + "%");
        logLine("Depolarizing: " + (hi.depolarizing * 100).toFixed(4) + "%/tick");
        logLine("Simulated time: " + hi.elapsed_us.toFixed(1) + " µs");
        return;
      }

      case "cooldown": {
        var target = nums(1)[0];
        if (target < 0) throw new Error("Target temperature cannot be negative");
        var current = reg.noise.temperature_mK;
        reg.noise.temperature_mK = current + (target - current) * 0.25;
        logLine("Cryostat temperature: " + reg.noise.temperature_mK.toFixed(3) + " mK", "qc-ok");
        return;
      }

      case "reset": {
        initPixelRegister(pixel, reg.n());
        logLine("Register reset to |" + "0".repeat(reg.n()) + "\u27E9.", "qc-ok");
        return;
      }

      case "clear":
        clearLog();
        return;

      default:
        throw new Error("Unknown command '" + cmd + "'. Type 'help' for the list.");
    }
  }

  // ==========================================================================
  // 5. VISUAL SUPERCONDUCTING HARDWARE
  // ==========================================================================
  // These elements model the architecture visually. They do not themselves
  // perform quantum computation; the Quantum Computer element owns the simulator.

  function visualElement(name, displayName, color, desc) {
    elements[name] = {
      name: displayName,
      desc: desc,
      category: "special",
      color: color,
      state: "solid",
      density: 2700,
      hardness: 0.7,
      movable: false
    };
  }

  visualElement("qc_transmon", "Transmon Qubit",
    ["#b8c7d9", "#dce6f2", "#8fa6bd"],
    "Visual superconducting transmon-style qubit. Simulation is controlled by a Quantum Computer element.");

  visualElement("qc_josephson_junction", "Josephson Junction",
    ["#ff7a00", "#ffd166", "#ff9f43"],
    "Visual Josephson-junction barrier between superconducting electrodes; not a physical junction.");

  visualElement("qc_readout_resonator", "Readout Resonator",
    ["#32d1ff", "#4ea8de", "#90e0ef"],
    "Visual microwave readout resonator coupled to a qubit.");

  visualElement("qc_microwave_line", "Microwave Control Line",
    ["#b45cff", "#d6a3ff", "#7c4dff"],
    "Visual microwave control wiring used to drive qubit rotations.");

  visualElement("qc_coupler", "Qubit Coupler",
    ["#d79b5b", "#f0bd7a", "#a86f3d"],
    "Visual tunable/capacitive coupling path between neighboring qubits.");

  visualElement("qc_cryostat", "Cryostat",
    ["#31506b", "#537895", "#789bb8"],
    "Visual dilution-refrigerator/cryostat enclosure. Temperature is simulated in the command console.");

  visualElement("qc_control_electronics", "Control Electronics",
    ["#334155", "#64748b", "#94a3b8"],
    "Visual room-temperature/cryogenic control electronics and signal routing.");

  visualElement("qc_amplifier", "Quantum Amplifier",
    ["#4b5563", "#9ca3af", "#d1d5db"],
    "Visual low-noise microwave amplifier for qubit readout.");

  // ==========================================================================
  // 6. THE ELEMENT
  // ==========================================================================

  elements.quantum_computer = {
    name: "Quantum Computer",
    desc: "A programmable machine that manipulates real qubits: superposition, quantum gates, and entanglement. Click it to open the console.",
    category: "special",
    color: ["#241452", "#3a1a70", "#5a2fb0", "#7a2bd6"],
    colorOn: ["#8a4dff", "#b088ff"],
    state: "solid",
    density: 4200,
    hardness: 0.35,
    conduct: 0.65,
    insulate: false,
    movable: false,
    tempHigh: 1200,
    stateHigh: "lava",
    breakInto: "scrap_metal",

    onPlace: function (pixel) {
      initPixelRegister(pixel, 1);
    },

    onClicked: function (pixel /*, element */) {
      openConsole(pixel);
    },

    onDelete: function (pixel) {
      if (activePixel === pixel) closeConsole();
    },

    hoverStat: function (pixel) {
      if (!pixel.qc) return "Uninitialized";
      var reg = pixel.qc.reg;
      var ent = reg.n() > 1 ? (function () {
        for (var i = 0; i < reg.n(); i++) if (reg.purity(i) < 0.999) return "yes";
        return "no";
      })() : "no";
      return reg.n() + " qubit(s) | superposition: " + (reg.entropyEstimate() * 100).toFixed(0) +
        "% | entangled: " + ent + (pixel.qc.linked ? " | LINKED" : "");
    },

    tick: function (pixel) {
      if (!pixel.qc) { initPixelRegister(pixel, 1); return; }
      // Visual feedback: glow color pulses with how much superposition/activity
      // is currently stored in the register (purely cosmetic, doesn't affect sim).
      var reg = pixel.qc.reg;
      // One Sandboxels tick is treated as ~33.3 ms of simulated hardware time.
      if (reg.noise.enabled) reg.decohere(33333.333);
      var mix = reg.entropyEstimate(); // 0 = classical bit, 1 = maximal superposition
      var hue = 250 + Math.round(mix * 60 + 8 * Math.sin(Date.now() / 300 + (pixel.x + pixel.y)));
      var light = 28 + Math.round(mix * 30);
      pixel.color = "hsl(" + hue + ",85%," + light + "%)";

      // Water shorts the circuit out.
      if (typeof pixelMap !== "undefined" && typeof changePixel === "function") {
        var neighbors = [[1,0],[-1,0],[0,1],[0,-1]];
        for (var i = 0; i < neighbors.length; i++) {
          var nx = pixel.x + neighbors[i][0], ny = pixel.y + neighbors[i][1];
          var np = pixelMap[nx] && pixelMap[nx][ny];
          if (np && (np.element === "water" || np.element === "salt_water")) {
            if (Math.random() < 0.02) {
              if (activePixel === pixel) closeConsole();
              changePixel(pixel, "smoke");
              return;
            }
          }
        }
      }
    }
  };

  console.log("quantum_computer.js loaded: place a Quantum Computer and click it to open the console.");
})();