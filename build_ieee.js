const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, AlignmentType,
  BorderStyle, ShadingType, LevelFormat, Footer, PageNumber, VerticalAlign, HeadingLevel, TabStopType, Tab, SectionType,
} = require("docx");

const FONT = "Times New Roman";
const BODY = 20; // 10 pt body, IEEE Access
const PAGEW = 12240, PAGEH = 15840; // US Letter
const MARG_LR = 965, MARG_T = 1080, MARG_B = 1300; // 7.16-in text block
const TEXTW = PAGEW - 2 * MARG_LR; // 10310
const GAP = 230; // 0.16-in column gap
const COLW = Math.floor((TEXTW - GAP) / 2); // 5040 = 3.5 in

// ------------------------------------------------------------------ inline markup
// **bold**, *italic*, _{sub}, ^{sup}
const MATH = [];
function runs(text, base = {}) {
  const out = [];
  const re = /(\$[^$]+\$|\[\d+(?:\s*[–,-]\s*\d+)*\]|\*\*[^*]+\*\*|\*[^*]+\*|_\{[^}]*\}|\^\{[^}]*\})/g;
  let last = 0, m;
  const push = (t, o) => { if (t) out.push(new TextRun({ text: t, font: FONT, size: base.size || BODY, ...base, ...o })); };
  while ((m = re.exec(text))) {
    push(text.slice(last, m.index), {});
    const s = m[0];
    if (s.startsWith("$")) { MATH.push({ src: s.slice(1, -1), size: base.size || BODY }); out.push(new TextRun({ text: `\u27E6M${MATH.length - 1}\u27E7` })); }
    else if (s.startsWith("[")) out.push(new TextRun({ text: `\u27E6C${s.slice(1, -1)}\u27E7`, font: FONT, size: base.size || BODY }));
    else if (s.startsWith("**")) push(s.slice(2, -2), { bold: true });
    else if (s.startsWith("*")) push(s.slice(1, -1), { italics: true });
    else if (s.startsWith("_{")) push(s.slice(2, -1), { subScript: true });
    else push(s.slice(2, -1), { superScript: true });
    last = m.index + s.length;
  }
  push(text.slice(last), {});
  return out;
}

const P = (t, o = {}) => new Paragraph({
  children: [...runs(t, o.run || {}), ...(o.qed ? [new TextRun({ children: [new Tab(), "\u220E"], font: "Cambria Math", size: BODY })] : [])],
  tabStops: o.qed ? [{ type: TabStopType.RIGHT, position: COLW }] : undefined,
  alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { after: o.after ?? 40, before: o.before ?? 0, line: o.line },
  indent: o.indent ?? (o.noindent ? undefined : { firstLine: 200 }),
  keepNext: o.keepNext,
});
let EQN = 0;
const EQ = (src) => {
  MATH.push({ src, size: BODY }); EQN += 1;
  return new Paragraph({
    tabStops: [{ type: TabStopType.CENTER, position: Math.round(COLW / 2) }, { type: TabStopType.RIGHT, position: COLW }],
    spacing: { before: 50, after: 70 }, keepLines: true,
    children: [new TextRun({ children: [new Tab()] }), new TextRun({ text: `\u27E6M${MATH.length - 1}\u27E7` }),
      new TextRun({ children: [new Tab(), `(${EQN})`], font: FONT, size: BODY })],
  });
};
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
let H1N = 0, H2N = 0;
const H1 = (t, numbered = true) => {
  let label = t.toUpperCase();
  if (numbered) { label = `${ROMAN[H1N]}. ${label}`; H1N += 1; H2N = 0; }
  return new Paragraph({ children: runs(label, { bold: true, size: BODY, color: "000000" }), heading: HeadingLevel.HEADING_1,
    alignment: numbered ? AlignmentType.LEFT : AlignmentType.LEFT, spacing: { before: 160, after: 60 }, keepNext: true });
};
const H2 = (t) => {
  const label = `${String.fromCharCode(65 + H2N)}. ${t}`; H2N += 1;
  return new Paragraph({ children: runs(label, { italics: true, size: BODY, color: "000000" }), heading: HeadingLevel.HEADING_2,
    spacing: { before: 100, after: 40 }, keepNext: true });
};
const LI = (t, ref = "num") => new Paragraph({ children: runs(t), numbering: { reference: ref, level: 0 },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 30 } });
let FIGN = 0, TABN = 0;
const CAP = (t) => { FIGN += 1; return new Paragraph({ children: runs(`**FIGURE ${FIGN}.** ${t}`, { size: 16 }), alignment: AlignmentType.JUSTIFIED,
  spacing: { before: 40, after: 160, line: 220 } }); };
const TCAP = (t) => { TABN += 1; return new Paragraph({ children: runs(`**TABLE ${TABN}.** ${t}`, { size: 16 }), alignment: AlignmentType.CENTER,
  spacing: { before: 120, after: 50, line: 220 }, keepNext: true }); };
const NOTE = (t) => new Paragraph({ children: runs(t, { size: 16 }), alignment: AlignmentType.JUSTIFIED,
  spacing: { before: 30, after: 100, line: 215 } });

// ---- two-column flow with full-width (spanning) blocks via continuous section breaks
const SECTIONS = []; let C = []; let CUR = 1;
function flush() { if (C.length) { SECTIONS.push({ cols: CUR, children: C }); C = []; } }
function TWO() { flush(); CUR = 2; }
function SPAN(...items) { flush(); SECTIONS.push({ cols: 1, children: items }); }

function pngSize(file) {
  const b = fs.readFileSync(file);
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
}
function FIG(file, widthIn) {
  const [w, h] = pngSize(file);
  const W = Math.round(widthIn * 96), H = Math.round(W * h / w);
  return new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 60, after: 0 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: W, height: H } })] });
}

const thin = { style: BorderStyle.SINGLE, size: 4, color: "808080" };
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
function TABLE(rows, widths0, opts = {}) {
  const target = opts.full ? TEXTW : COLW;
  const t0 = widths0.reduce((a, b) => a + b, 0);
  const widths = widths0.map((w) => Math.floor(w * target / t0));
  const total = widths.reduce((a, b) => a + b, 0);
  const fs_ = opts.size || 16;
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0, cantSplit: true,
      children: r.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        shading: i === 0 ? { type: ShadingType.CLEAR, fill: "E8E8E4", color: "auto" } :
          (opts.highlightLast && i === rows.length - 1 ? { type: ShadingType.CLEAR, fill: "EEF4FC", color: "auto" } : undefined),
        margins: { top: 25, bottom: 25, left: 70, right: 70 },
        verticalAlign: VerticalAlign.CENTER,
        borders: { top: i <= 1 ? thin : none, bottom: i === rows.length - 1 || i === 0 ? thin : none, left: none, right: none },
        children: [new Paragraph({ children: runs(c, { size: fs_, bold: i === 0 }), spacing: { after: 0, line: 215 },
          alignment: j === 0 || opts.leftAll ? AlignmentType.LEFT : AlignmentType.CENTER })],
      })),
    })),
  });
}

// ------------------------------------------------------------------ content
C.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 160 },
  children: runs("Dynamic Workflow Intelligence: A Verifiable State-Machine Specification for Coupling Continuous Clinical Risk Scores to Workflow Adaptation", { size: 44 }) }));
C.push(P("**[AUTHOR 1 FULL NAME]**^{1}, **[CLINICAL CO-AUTHOR FULL NAME]**^{2}, **AND [SUPERVISOR FULL NAME]**^{1}", { align: AlignmentType.LEFT, noindent: true, after: 40, run: { size: 20 } }));
C.push(P("^{1}[Department, Institution, City, Postal Code], Indonesia", { align: AlignmentType.LEFT, noindent: true, after: 0, run: { size: 16 } }));
C.push(P("^{2}[Department of Cardiology / Intensive Care, Hospital, City, Postal Code], Indonesia", { align: AlignmentType.LEFT, noindent: true, after: 40, run: { size: 16 } }));
C.push(P("Corresponding author: [Full Name] (e-mail: [institutional address]).", { align: AlignmentType.LEFT, noindent: true, after: 40, run: { size: 16 } }));
C.push(P("This work did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors. [If funded, replace with: “This work was supported by [agency] under Grant [number].”]", { align: AlignmentType.LEFT, noindent: true, after: 160, run: { size: 16 } }));
C.push(P("**ABSTRACT** Most clinical deterioration models stop at an alert, leaving the step from a continuous risk score to a change in the care process implicit, untestable, and irreproducible. This paper specifies that step as Dynamic Workflow Intelligence, a composition of three total functions: quantization of anomaly scores into typed events, aggregation into a four-level hysteretic risk state, and edge-triggered adaptation of a running workflow instance under a four-tier autonomy policy. We prove that the committed state never under-reports the instantaneous evidence, that de-escalation lag and the number of transitions, and hence the automated workload, are bounded, and that the decision trace is reproducible from an immutable log under three named assumptions. A reference implementation passed all 14,949 cases of an 18-group conformance suite, and fault injection detected all 16 planted mutants. On 40,336 real intensive care patients of the public PhysioNet/Computing in Cardiology 2019 sepsis database, with the detector trained in one hospital and tested on the other in both directions, edge-triggering reduced automated commands from 1.31 to 0.16 per patient-day (6.70 to 1.21 in the reverse direction) relative to level-triggered operation, with identical sensitivity for sepsis; the dwell gate never delayed an escalation, no patient exceeded the proved transition bound, and per-patient ordering made every shuffled replay identical to the reference. Threshold calibration, rather than the state machine, set the trade-off between sensitivity and alert burden, and thresholds calibrated in one hospital did not transfer to the other. Clinical benefit requires prospective evaluation.", { noindent: true, after: 80, run: { size: 18 } }));
C.push(P("**INDEX TERMS** Alert fatigue, clinical decision support systems, finite state machines, formal verification, hysteresis, mutation testing, workflow management software.", { noindent: true, after: 200, run: { size: 18 } }));
TWO();

// 1 Introduction
C.push(H1("Introduction"));
C.push(P("Predicting deterioration from routine hospital data is comparatively mature; acting on the prediction is not. The dominant deployment pattern remains *alert-and-wait*: a score crosses a threshold, a notification is issued, and a clinician must interpret it and manually initiate any change in monitoring, testing or staffing. Alert acceptance falls as workload and alert repetition increase [1]; a widely deployed proprietary sepsis model showed substantially worse discrimination on external validation while generating a high alert volume [2]; fit with existing workflow remains a determinant of use long after go-live [3]; and the deployments that improved outcomes paired the model with a restructured response process rather than surfacing scores alone [4–6]."));
C.push(P("The binding constraint is therefore not only predictive accuracy but the absence of a specified, verifiable mechanism connecting analytic output to process execution. Where one exists it is implicit, spread across a notification rule, a dashboard and a convention about who responds, so it cannot be tested before deployment or reproduced from a log after an adverse event."));
C.push(P("This paper specifies that mechanism. Dynamic Workflow Intelligence (DWI) treats deterioration not as an alert but as a typed event that updates a persistent per-patient state, which in turn triggers a bounded adaptation of a running workflow instance (Fig. 1). The messaging substrate, workflow engine and detector are off-the-shelf; what is new is the layer between them. We use inpatient atrial fibrillation (AF) as the running example because current AF guidelines emphasize dynamic reassessment as clinical status evolves [7,8]; the formalism is disease-agnostic, its parameterization is not. The contributions are:"));
C.push(LI("A formal specification of DWI as three composed total functions with proved properties: evidence monotonicity, conservative dominance of the committed state, a bound on de-escalation lag, and a closed-form bound on the number of transitions and hence on automated workload."));
C.push(LI("Decision tables that are pairwise disjoint and jointly exhaustive by construction, so completeness and non-overlap are checked at build time under a UNIQUE hit policy."));
C.push(LI("A determinism theorem for the *decision trace* under three named infrastructure assumptions, separated from the non-deterministic *execution trace*; per-patient partitioning follows as a correctness requirement."));
C.push(LI("Empirical evidence from a conformance suite, mutation analysis, and a two-way cross-hospital evaluation on 40,336 real intensive care patients from a public database, including three specification issues the evaluation uncovered. All code is released."));
C.push(P("The work follows the design-science paradigm [9,10]; clinical validity is outside its scope (Section VI-D)."));

SPAN(FIG("fig1_pipeline.png", 6.9),
  CAP("The three composed mappings of DWI and the edge-triggered adaptation step. Only the layer between the detector and the workflow engine is specified here; the detector is treated as a black box that honours the signature contract of Definition 1."));

// 2 Related work
C.push(H1("Related Work"));
C.push(P("Runtime change of a running process instance has a mature formal foundation: ADEPT_{flex} defined correctness-preserving change operations [11], later surveyed [12] and organized into a change-pattern catalogue [13,14]. DWI's four adaptation scopes (routing, task, role, temporal) are instances of catalogued patterns, not new operations. BPMN [15] supplies executable process semantics and DMN [16] supplies decision tables with UNIQUE, FIRST and COLLECT hit policies. Declarative approaches such as DECLARE relax an over-specified control flow into constraints [17]; DWI works in the opposite direction, tightening an under-specified trigger."));
C.push(P("In the clinical domain, guideline-based careflow systems [18], SEMPATH [19] and CONFlexFlow [20] adapt clinical pathways at run time from rules over clinical context. Early warning scores established structured physiological surveillance [21], and SMART on FHIR and CDS Hooks standardize how external services return suggestion cards the clinician may accept [22,23]. In process-industry alarm management, deadband and off-delay timers suppress chattering alarms at the cost of a bounded delay in clearing [24]; DWI's dwell gate is the off-delay timer generalized to a multi-level state that mutates a care process."));
C.push(P("Every adaptive approach above is triggered by a discrete event (a user action, modelled exception, constraint violation or rule firing). None handles a continuous score stream that must first be typed, aggregated and debounced into a discrete event, and none states a formal property of its adaptation behaviour such as a frequency bound or a reproducibility guarantee, although disjointness and completeness checks for decision tables are well established [25,26] (Table 1). That conversion is the layer DWI specifies."));

SPAN(TCAP("Positioning of DWI relative to existing approaches to process change and clinical alerting."),
  TABLE([
  ["Approach", "Trigger", "What may change", "Formal guarantee stated", "Checked before deployment"],
  ["ADEPT / change patterns [11,13]", "User action, modelled exception", "Structure of running instance", "Structural correctness", "Not applicable"],
  ["DECLARE [17]", "Constraint violation", "Space of permitted behaviour", "Temporal-logic semantics", "Model checking"],
  ["SEMPATH [19], CONFlexFlow [20]", "Rules on discrete context", "Pathway fragments", "None", "No"],
  ["Early warning score + alert [4–6,21]", "Threshold crossing", "Nothing (notification)", "None", "No"],
  ["CDS Hooks [23]", "EHR hook point", "Suggestion cards", "Interface conformance", "Conformance"],
  ["**DWI (this work)**", "Continuous score stream via typed events", "Routing, task, role, timing of running instance", "Dominance, lag and transition bounds, replay determinism", "Exhaustive ($Φ$, adaptation); property-based ($λ$)"],
], [2050, 1650, 1750, 1850, 1772], { highlightLast: true, full: true }));

// 3 Specification
C.push(H1("Formal Specification"));
C.push(H2("System Model and Assumptions"));
C.push(P("Every signature carries an event time $τ$, the clinical timestamp of the underlying observation, distinct from its processing time; all definitions are stated over event time. There is one independent state machine per patient $p$, so results compose across a cohort. The machine is evaluated at the instants", { after: 0 }));
C.push(EQ("𝒯 = @set{τ(E) : E @t{ received}} ∪ @set{t_{0} + jΔ_{tick} : j ∈ ℕ}"));
C.push(P("where the second set is an event-time clock advanced by the watermark. Without this clock, omitted in the earlier draft, a patient who stops producing signatures would never de-escalate, because windows also expire when no new data arrive. Initially $S(t_{0}) = R$ and $τ_{last} = t_{0}$. Four infrastructure assumptions are stated rather than claimed as properties of DWI.", { noindent: true }));
C.push(P("(A1) Per-patient event-time order: signatures reach the state manager in non-decreasing $τ$, realized by a watermark-driven reorder buffer. (A2) Bounded lateness: a signature whose instant has already been evaluated is logged, excluded online and flagged for offline recomputation, never silently folded in. (A3) Effectively-once processing: redeliveries are absorbed through content-derived keys (Definition 1). (A4) Bounded staleness $ε_{state}$ of state reads used to *execute* commands. A1–A3 govern the decision trace; A4 governs only the execution trace (Section III-F)."));

C.push(H2("Anomaly Signatures and Quantization"));
C.push(P("**Definition 1 (Signature).** A signature and its key are", { after: 0, keepNext: true }));
C.push(EQ("@lines{E = @ang{id, p, τ, σ, κ, h, V, c, m}, ;; id = H(p ‖ τ ‖ m),}"));
C.push(P("where $σ ∈ [0, 1]$ is the normalized anomaly score, $κ$ the severity class, $h$ an optional onset hazard, $V = (v_{cur}, v_{base})$ the current and baseline physiological vectors, $c$ the clinical context, $m$ the model provenance and $H$ a collision-resistant hash. Identical redeliveries are absorbed; if two signatures share a key but differ in $σ$, the larger is retained and the conflict logged. Because max is commutative, associative and idempotent, the retained set is independent of delivery order (the earlier draft lacked this policy; Section V-B).", { noindent: true }));
C.push(P("**Definition 2 (Quantization).** With calibrated thresholds $0 < θ_{M} < θ_{C} < 1$,", { after: 0, keepNext: true }));
C.push(EQ("κ(σ) = @cases{L, && σ < θ_{M} ;; M, && θ_{M} ≤ σ < θ_{C} ;; C, && σ ≥ θ_{C}}"));
C.push(P("which is total with exhaustive, disjoint cases (trichotomy). A change of $θ_{M}$ or $θ_{C}$ is a change of clinical specification and is versioned with the model.", { noindent: true }));

C.push(H2("Aggregation and Instantaneous Evidence"));
C.push(P("**Definition 3 (Aggregates).** For a window of length $Δ$,", { after: 0, keepNext: true }));
C.push(EQ("@lines{𝓗(t, Δ) = @set{E : t − Δ < τ(E) ≤ t}, ;; σ_{max}(t, Δ) = @low{max}{E ∈ 𝓗(t, Δ)} σ(E), ;; n_{C}(t, Δ) = @bars{@set{E ∈ 𝓗(t, Δ) : κ(E) = C}}, ;; n_{≥M}(t, Δ) = @bars{@set{E ∈ 𝓗(t, Δ) : κ(E) ∈ @set{M, C}}}}"));
C.push(P("with $σ_{max} = 0$ for an empty window. **Definition 4 (Evidence level).** With windows $Δ_{s} ≤ Δ_{m} ≤ Δ_{l}$ and thresholds $c_{W} ≤ c_{T} ≤ c_{K}$, $m_{W} ≤ m_{T}$, the guards are", { after: 0, keepNext: true, noindent: true }));
C.push(EQ("@lines{g_{K}(t) ≡ [σ_{max}(t, Δ_{s}) ≥ θ_{K}] ∨ [n_{C}(t, Δ_{s}) ≥ c_{K}] ;; g_{T}(t) ≡ [n_{C}(t, Δ_{m}) ≥ c_{T}] ∨ [n_{≥M}(t, Δ_{s}) ≥ m_{T}] ;; g_{W}(t) ≡ [n_{C}(t, Δ_{l}) ≥ c_{W}] ∨ [n_{≥M}(t, Δ_{m}) ≥ m_{W}]}"));
C.push(P("and the evidence level $λ(t) ∈ 𝒮 = @set{R, W, T, K}$ is evaluated in priority order:^{1}", { after: 0, keepNext: true, noindent: true }));
C.push(EQ("λ(t) = @cases{K, && g_{K}(t) ;; T, && ¬g_{K}(t) ∧ g_{T}(t) ;; W, && ¬g_{K}(t) ∧ ¬g_{T}(t) ∧ g_{W}(t) ;; R, && @t{otherwise.}}"));
C.push(P("The conditions of (6) are pairwise disjoint and jointly exhaustive, so $λ$ is total and single-valued (Lemma 1). A hazard clause $h ≥ θ_{h}$ may be added to $g_{K}$ once the hazard model is prospectively calibrated.", { noindent: true }));
C.push(P("**Theorem 0 (Evidence monotonicity).** If one signature's class is upgraded ($L → M$ or $M → C$) with all else fixed, $λ$ cannot decrease. *Proof.* An $L → M$ upgrade increments $n_{≥M}$ and leaves $n_{C}$ fixed; an $M → C$ upgrade increments $n_{C}$, leaves $n_{≥M}$ fixed and cannot lower $σ_{max}$. Each guard in (5) is a disjunction of predicates monotone in these arguments, so none switches from true to false and, by (6), the level can only rise.", { qed: true }));
C.push(P("The theorem fails under class-exact counting, because an $M → C$ upgrade then decrements the M count; this defect is planted as mutant M1 in Section V-A."));
C.push(P("The coherence conditions, asserted at start-up (deployment fails on violation): (C1) $c_{W} ≤ c_{T} ≤ c_{K}$ and $m_{W} ≤ m_{T}$; (C2) $θ_{M} < θ_{C} ≤ θ_{K}$; (C3) $Δ_{s} ≤ Δ_{m} ≤ Δ_{l}$. C2 matters because $θ_{C}$ is calibrated as a quantile while $θ_{K}$ was fixed: if $θ_{C} > θ_{K}$, a signature can trigger K while logged as class M, and the log contradicts the state trajectory."));
C.push(NOTE("^{1} State codes derive from the Indonesian clinical terms *Rendah, Waspada, Tinggi, Kritis* (stable, elevated, high, critical), reflecting the intended deployment setting where nursing documentation is in Indonesian."));

C.push(TCAP("Parameterization used in the evaluation. Thresholds are quantiles of hospital A calibration scores; all values are starting points, not clinical findings."));
C.push(TABLE([
  ["Parameter", "Value", "Status / rationale"],
  ["$Δ_{s} / Δ_{m} / Δ_{l}$", "6 h / 12 h / 24 h", "Pre-specified, not tuned on test data; C3 asserted"],
  ["$c_{W} / c_{T} / c_{K}$;  $m_{W} / m_{T}$", "1 / 2 / 3;  2 / 3", "Pre-specified, not tuned on test data; C1 asserted"],
  ["$θ_{M} / θ_{C}$", "P93 / P98 of calibration scores (0.068 / 0.195)", "Earlier default P70 / P90 flagged 35.5% of non-septic patients (Section V-B)"],
  ["$θ_{K}$", "P99.9 of calibration scores (0.654)", "Earlier fixed 0.95 reached in 9 of 761,995 hours (Section V-B)"],
  ["$δ_{down}$", "2 h", "Pre-specified; dwell sweep in Fig. 4b"],
  ["$Δ_{tick}$;  $ε_{state}$", "1 h;  1 s", "Evaluation clock matched to the hourly data; infrastructure parameter"],
], [2600, 2700, 3772]));

C.push(H2("Transition Function and Its Properties"));
C.push(P("The committed state differs from the evidence by asymmetric dwell, because de-escalating early leaves a deteriorating patient under-monitored whereas escalating early is bounded and reversible. **Definition 5 (Transition).** Let $S^{−}$ be the state before $t$, $τ_{last}$ the time of the last committed transition and $lvl: 𝒮 → @set{0, 1, 2, 3}$ the index on $R ≺ W ≺ T ≺ K$, and write $d(t) = t − τ_{last}$ for the elapsed dwell, $ℓ_{λ} = lvl(λ(t))$ and $ℓ^{−} = lvl(S^{−})$. The committed state $S(t) = Φ(S^{−}, λ(t), d(t))$ is", { after: 0, keepNext: true }));
C.push(EQ("S(t) = @cases{λ(t), && ℓ_{λ} > ℓ^{−}, ;; λ(t), && ℓ_{λ} < ℓ^{−} ∧ d(t) ≥ δ_{down}, ;; S^{−}, && @t{otherwise,}}"));
C.push(P("with $τ_{last}$ set to $t$ exactly when $S(t) ≠ S^{−}$. Fig. 2 renders the machine; Supplementary Table S2 enumerates its 32 input cells in 22 rules.", { noindent: true }));
C.push(P("**Proposition 1 (Totality).** $Φ$ is total on $𝒮 × 𝒮 × @set{true, false}$ because the branches of (7) partition the level trichotomy and the dwell predicate. **Proposition 2 (Conservative dominance).** $lvl(S(t)) ≥ lvl(λ(t))$ for every $t ∈ 𝒯$. *Proof.* By induction over instants: the first two branches give equality; the hold branch is reached only when $lvl(λ(t)) ≤ lvl(S^{−})$.", { qed: true }));
C.push(P("Debouncing can only delay relaxation, never onset. **Proposition 3 (Bounded de-escalation lag).** If $lvl(λ(u)) ≤ ℓ$ at every $u ∈ 𝒯 ∩ [t_{1}, t_{1} + 3(δ_{down} + Δ_{tick})]$, then $lvl(S(u)) ≤ ℓ$ from the end of that interval onward, because each dwell interval admits at most one downward step, the first admissible instant follows within $Δ_{tick}$, and $@bars{𝒮} − 1 = 3$."));
C.push(P("**Theorem 1 (Transition bound).** The number $N(T)$ of committed transitions in $@ho{0, T}$ satisfies", { after: 0, keepNext: true }));
C.push(EQ("N(T) ≤ 4 @ceil{@frac{T}{δ_{down}}} + 3."));
C.push(P("*Proof.* Successive de-escalations at $u_{j−1} < u_{j}$ satisfy $u_{j} − u_{j−1} ≥ δ_{down}$ because $τ_{last}(u_{j}) ≥ u_{j−1}$; hence their number is $d ≤ @ceil{T/δ_{down}}$. The de-escalations split $@ho{0, T}$ into $d + 1$ intervals containing only escalations, each strictly increasing $lvl$ over $@set{0, 1, 2, 3}$ and so admitting at most three. Thus $N ≤ d + 3(d + 1) = 4d + 3$.", { qed: true }));
C.push(P("Because commands are emitted only on transitions (Definition 6), $N(T)$ also bounds automated workload. **Corollary 1.** Since $@ceil{x} < x + 1$, the transition rate satisfies", { after: 0, keepNext: true }));
C.push(EQ("@frac{N(T)}{T} < @frac{4}{δ_{down}} + @frac{7}{T}."));
C.push(P("The bound is worst-case (Section V-D), so a dwell value cannot be justified from an oscillation target alone.", { noindent: true }));

SPAN(FIG("fig2_statemachine.png", 5.2),
  CAP("DWI risk state machine. Solid arcs (above) are escalations, admitted immediately; dashed arcs (below) are de-escalations, admitted only after $δ_{down}$ since the last committed transition. Each arc is labelled with its adaptation command and mutation-autonomy tier (Table 3). Hold and damped cases emit no command."));

C.push(H2("Edge-Triggered Adaptation and Autonomy"));
C.push(P("**Definition 6 (Trigger).** An adaptation is computed if and only if $S(t) ≠ S(t^{−})$. Level-triggering would re-emit a command on every signature while a patient stays elevated, the low-information repetition that drives alert non-acceptance [1]. **Definition 7 (Command).** An adaptation command is", { after: 0, keepNext: true }));
C.push(EQ("@lines{A = @ang{cid, p, wid, t, ρ, π, J}, @q cid = H(p ‖ k), ;; ρ ⊆ @set{Routing, Task, Role, Temporal},}"));
C.push(P("with scope parameters $π$, a justification record $J$ (state pair, triggering signature, rule identifier, rationale) and transition sequence number $k$, so $A$ is idempotent under redelivery. **Definition 8 (Rule evaluation).** The adaptation rules are keyed injectively on the twelve ordered pairs with $S^{−} ≠ S$ (Table 3) and closed by a terminal no-op rule under FIRST; the emitted command is therefore unique for a fixed rule-set version (Proposition 4). An optional anomaly-type overlay is *additive only* and evaluated under COLLECT; determinism survives because set union is commutative, associative and idempotent.", { noindent: true }));
C.push(P("Notification is always automatic; *mutation* is tiered (Table 3). Tier 0 (monitoring-frequency increases) and Tier 1 (dashboard-posted routing and non-critical relaxation) execute autonomously; Tier 2 (roles, resource-consuming diagnostics, every exit from K) applies only on clinician acceptance; Tier 3 (rapid response) is proposed with immediate, unconditional notification. Clinician-facing adaptations are CDS Hooks suggestion cards [23]. Three rules close the execution side: a state read older than $ε_{state}$ defers the command (Definition 9); an inadmissible injection (terminated instance, passed injection point, modification lock) queues the command and notifies the responsible role, so no command is silently dropped (Definition 10); and a clinician override lock suppresses dispatch while state updates continue and are logged (Definition 11)."));

SPAN(TCAP("Adaptation by transition (base rules, UNIQUE). Monitoring interval by state: R 4 h, W 2 h, T 1 h, K continuous."),
  TABLE([
  ["ID", "$S^{−}$→S", "Routing", "Tasks / roles", "Timing", "Tier", "Notification"],
  ["A-01", "R→W", "–", "–", "4 h→2 h", "0", "Dashboard"],
  ["A-02 / A-04", "R→T / W→T", "routine→escalation", "+ECG-12, +cardiology consult", "→1 h", "2", "Page primary nurse"],
  ["A-03 / A-05", "R→K / W→K", "→critical", "+ECG-12, +echo, +cardiology, +RRT", "→continuous", "3", "Page RRT"],
  ["A-06", "T→K", "escalation→critical", "+echo, +RRT", "→continuous", "3", "Page RRT"],
  ["A-07 / A-08 / A-09", "K→T / W / R", "critical→lower", "−RRT (A-09 also −cardiology)", "→1 / 2 / 4 h", "2", "Acknowledgement required"],
  ["A-10 / A-12", "T→W / W→R", "escalation→routine (A-10)", "–", "→2 h / →4 h", "1", "Dashboard"],
  ["A-11", "T→R", "escalation→routine", "−cardiology", "→4 h", "2", "Acknowledgement required"],
], [1450, 1150, 1500, 2150, 1050, 520, 1252], { full: true }));

C.push(H2("System-Level Guarantees"));
C.push(P("**Theorem 2 (Decision-trace determinism).** Under A1–A3, for any finite signature set of patient $p$, the decision trace", { after: 0, keepNext: true }));
C.push(EQ("D_{p} = @paren{t_{k}, S_{k}^{−}, S_{k}, r_{k}, A_{k}, cid_{k}}_{k = 1, …, N(T)}"));
C.push(P("with $r_{k}$ the rule identifier, is uniquely determined by the collision-resolved signature set, $t_{0}$, the parameter vector and the rule-set version. *Proof.* By A3 and Definition 1 the effective input is a set, independent of delivery multiplicity and order. By A1 and A2 it is presented in non-decreasing $τ$, so every aggregate (4) at every $t ∈ 𝒯$ is computed over the same contents as in the batch oracle. Lemma 1, Proposition 1, Definition 6 and Proposition 4 each yield unique values, and induction over the ordered instants gives uniqueness of $D_{p}$.", { qed: true }));
C.push(P("The *execution* trace, which records whether each command was dispatched, deferred, queued or overridden, depends additionally on processing-time events (Definitions 9–11) and is logged rather than claimed deterministic. Audit answers *why* a command was decided by recomputing $D_{p}$ and *what happened to it* from the execution log; the earlier draft wrongly claimed determinism of emitted commands. Theorem 2 also makes partition-key selection a correctness concern. Brokers order messages only within a partition [27], so a topic not keyed on the patient identifier silently breaks A1 (Section V-D)."));
C.push(P("**Theorem 3 (Degradation safety).** When the detector or state store is unavailable, $Φ_{deg}$ retains the last committed state, admits escalation on static physiological thresholds and admits no de-escalation, so $lvl(S)$ is non-decreasing throughout the outage. On recovery, replay yields $S^{rep}$; the system commits the higher of $S_{deg}$ and $S^{rep}$, records degraded-mode commands as a distinct class that replay does not re-emit, and routes every subsequent de-escalation through the dwell gate. Component failure can thus reduce responsiveness but never produce an unguarded de-escalation (correcting the earlier draft's convergence claim, which fails when degraded mode escalated on thresholds that replay does not reproduce)."));

// 4 Evaluation methods
C.push(H1("Evaluation Methods"));
C.push(H2("Reference Implementation"));
C.push(P("A dependency-free Python 3.11 module (400 lines) provides a batch oracle (de-duplicate, order by $τ$, evaluate at $𝒯$) and a streaming processor with content-key de-duplication and a watermark reorder buffer that share the same core. The $λ$ logic is held twice, as a compact FIRST table and as the expanded staircase table (Supplementary Table S1) executed under a UNIQUE check. The implementation, conformance suite, mutation analysis, real-data analysis and figure scripts regenerate every number and figure reported here and are available at [repository URL] (archived at [DOI])."));
C.push(H2("Conformance Suite"));
C.push(P("Eighteen groups trace to the definitions and theorems they exercise (Table 4). Where the domain is finite, testing is exhaustive: the 32 cells of $Φ$, the 16 state pairs of the adaptation table, and, for $λ$, all 2^{6} = 64 truth valuations of its six guard predicates. This predicate abstraction is exact, because $λ$ depends on its inputs only through those predicates. A further 9,375 concrete aggregate vectors check FIRST–UNIQUE equivalence. Universally quantified properties (Theorem 0, Propositions 2–3, Theorem 1) are tested by property-based testing [28] with Hypothesis 6.168 [29] in derandomized mode. Replay determinism compares 100 random signature streams × 10 delivery shuffles against the oracle byte for byte."));
C.push(H2("Mutation Analysis"));
C.push(P("Sixteen mutants each plant one plausible specification or implementation defect: M1 class-exact counting; M2 closed window [t − $Δ$, t]; M3 strict dwell (>); M4 symmetric hysteresis; M5 level-triggering; M6 missing terminal rule; M7 dropped staircase negation; M8 no de-duplication; M9 no reorder buffer; M10 float-accumulated clock; M11 de-escalation in degraded mode; M12 autonomous exit from K; M13 C2 unchecked; M14 override ignored; M15 recovery adopts replay state only; M16 arrival-order key collision. A mutant is killed if at least one group fails [30]."));
C.push(H2("Data and Detector"));
C.push(P("The evaluation uses the public PhysioNet/Computing in Cardiology Challenge 2019 database [31,32], which contains de-identified hourly records of 40,336 intensive care patients from two U.S. hospitals (A: 20,336; B: 20,000; 1,552,210 patient-hours) with Sepsis-3 labels. It is openly available under a Creative Commons Attribution 4.0 license, so no additional ethics approval was required. The condition is sepsis rather than atrial fibrillation, so the evaluation also tests whether the disease-agnostic state layer transfers to another condition. A gradient-boosted tree classifier with 84 features (last-observation-carried-forward vital signs and laboratory values, measurement indicators, 6-h vital-sign trends, age, sex and length of stay) was trained on 70% of hospital A patients to output an hourly anomaly score $σ$; end-tidal CO_{2} was excluded because hospital A never records it. The remaining 30% of hospital A (6,101 patients) served only to calibrate the thresholds with a quantile rule fixed before any hospital B data were examined (P93, P98 and P99.9, giving $θ_{M} = 0.068$, $θ_{C} = 0.195$ and $θ_{K} = 0.654$), and hospital B was used only for evaluation. All other parameters are those of Table 2."));
C.push(H2("Couplings, Outcomes, and Analyses"));
C.push(P("Four couplings consume the same hourly scores: B1, threshold alerting (one alert per score with $σ ≥ θ_{C}$); B2, level-triggered operation of the same state logic, with a command on every score while $S ≠ R$; B3, edge-triggering without hysteresis ($δ_{down} = 0$); and DWI with $δ_{down} = 2$ h. Because the challenge shifts each positive label 6 h ahead of clinical recognition, onset was taken as the first positive hour plus 6 h; the 919 of hospital B's 1,142 septic patients with at least one hour observed before the first positive label were evaluable. A case counted as detected if the coupling reached T or above (or, for B1, raised an alert) between 12 h before and 3 h after onset. Outcomes are commands per patient-day; detected cases and those detected at least 6 h before onset; patients flagged and the patient-level positive predictive value; the share of non-septic patients ever at T or above; and rapid reversals (an escalation and a de-escalation within 1 h) per patient-day. Intervals are 95% patient-level bootstrap intervals (1,000 resamples)."));
C.push(P("$δ_{down}$ was swept over 0, 1, 2, 4 and 6 h, and every patient's transition count was compared with the Theorem 1 bound for its length of stay. Because the guards count scores and these data arrive at one per hour, two further calibrations, also derived from hospital A only, probe the trade-off: a rate-matched rule that multiplies the tail probabilities by four (P72, P92 and P99.6), and the earlier default (P70 and P90 with a fixed $θ_{K} = 0.95$). For the ordering experiment, 500 hospital B patients were replayed 10 times with 30% of the hourly scores delayed by up to 2.5 h, through three consumers: (i) a watermark buffer with 3-h lateness (A1 enforced); (ii) no buffer, late scores folded in; (iii) no buffer, late scores dropped. Case (ii) is what a topic keyed on anything other than the patient identifier produces. Finally, the whole pipeline was repeated with the hospitals exchanged: the detector was trained on 70% of hospital B (14,000 patients), the thresholds were calibrated with the same quantile rule on the remaining 6,000 ($θ_{M} = 0.035$, $θ_{C} = 0.100$, $θ_{K} = 0.515$), and all analyses were run on the 20,336 hospital A patients, of whom 1,587 septic patients were evaluable."));

// 5 Results
C.push(H1("Results"));
C.push(H2("Conformance and Mutation Analysis"));
C.push(P("All 14,949 cases in 18 groups passed (Table 4). The first mutation run covered 15 mutants and killed 13. M1 (class-exact counting) survived because uniform scores rarely produce the configuration where Theorem 0 fails ($m_{T}$ M-class signatures in $Δ_{s}$, no C-class in $Δ_{m}$); M3 (strict dwell) survived because TC-5 exercised the table but not the machine's time comparison. A class-biased generator with a worked fixture, and three end-to-end dwell cases, killed both. M16 was added after the defect in Section V-B was found. In the final run all 16 mutants were killed."));
SPAN(TCAP("Conformance suite (final run) and the mutants each group detects."),
  TABLE([
  ["Group", "Exercises", "Method", "Cases", "Failed", "Mutants killed"],
  ["TC-1 Guard partition", "Lemma 1, Table S1", "64 predicate valuations (exhaustive) + 9,375 concrete", "9,439", "0", "M6, M7"],
  ["TC-2/3 Guard and window boundaries", "Def 3–4", "value ± $ε$; edges of $@ho{t − Δ, t}$", "27", "0", "M2"],
  ["TC-4/5 $Φ$ enumeration, dwell", "Def 5, Prop 1", "32/32 cells; dwell $δ_{down} ± ε$, end-to-end", "53", "0", "M2–M4"],
  ["TC-6 Adaptation and tiers", "Def 6–8", "12 transitions + 4 holds", "16", "0", "M12"],
  ["TC-7 Overlay commutativity", "Sec 3.5", "Random multi-match overlays", "500", "0", "–"],
  ["TC-8 Evidence monotonicity", "Thm 0", "Property-based (uniform + class-biased) + fixture", "2,001", "0", "M1"],
  ["TC-9 Idempotency, key collision", "A3, Def 1", "Redelivery 1×/2×/5×; colliding keys, both orders", "500", "0", "M8–M10, M16"],
  ["TC-10/11 Replay, late arrival", "Thm 2, A2", "100 streams × 10 shuffles; watermark edges", "1,003", "0", "M9, M10"],
  ["TC-12/14 Staleness, override", "Def 9, 11", "$ε$ ±; lock active / expiring / absent", "6", "0", "M14"],
  ["TC-13 Degradation", "Thm 3", "500 random outages + reconciliation", "500", "0", "M11, M15"],
  ["TC-15 Coherence", "C1–C3", "3 invalid + 1 valid configuration", "4", "0", "M13"],
  ["TC-16/17/18 Dominance, bound, lag", "Prop 2, Thm 1, Prop 3", "Property-based, every instant checked", "900", "0", "M4, M5"],
  ["**Total**", "", "", "**14,949**", "**0**", "**16 / 16**"],
], [2350, 1300, 2750, 800, 600, 1272], { full: true }));

C.push(H2("Specification Issues Exposed by the Evaluation"));
C.push(P("Three issues in the earlier specification were found and corrected in Section III. First, keys without a collision policy made the retained signature depend on arrival order whenever two scores shared an event time, which breaks Theorem 2; the max-$σ$ policy of Definition 1 removes the dependence and is covered by TC-9 and mutant M16. Second, the earlier fixed $θ_{K} = 0.95$ is unreachable in practice: on hospital B only 9 of 761,995 hourly scores reached it, so the $σ_{max}$ clause of $g_{K}$ fired in only 9 hours; $θ_{K}$ is now the P99.9 quantile of calibration scores. Third, the earlier default thresholds (P70 and P90) flood the count guards: on hospital B they flagged 35.5% of non-septic patients at T or above, against 2.9% under the pre-specified rule. Because the guards count signatures, $θ_{M}$ and $θ_{C}$ must be calibrated jointly with the signature rate (Section V-E)."));

C.push(H2("Workload, Sensitivity, and Escalation on Real ICU Records"));
C.push(P("On hospital B (20,000 patients, 31,750 patient-days) the detector reached an hourly area under the ROC curve of 0.73, against 0.81 within hospital A, a typical cross-hospital decline for this database. Table 5 reports the four couplings. Edge-triggering set the workload: DWI issued 0.157 commands per patient-day (95% CI 0.147–0.169) against 1.31 (1.20–1.43) for level-triggered operation of the same scores, an 8.3-fold reduction (Fig. 4a). All three state-based couplings detected the same 359 of 919 sepsis cases (39.1%), 289 of them at least 6 h before onset, so hysteresis delayed no escalation, as Proposition 2 requires; only 2.9% of non-septic patients ever reached T. B1 alerted fewer patients, with a higher positive predictive value, but detected only 218 cases (23.7%). Fig. 3 shows one detected patient."));
SPAN(TCAP("Four couplings of the same detector on 20,000 intensive care patients of hospital B (PhysioNet/CinC 2019; detector trained and thresholds calibrated on hospital A only). Brackets give 95% patient-level bootstrap intervals."),
  TABLE([
  ["Metric", "B1 Threshold alert", "B2 Level-triggered", "B3 Edge, no hysteresis", "DWI ($δ_{down} = 2$ h)"],
  ["*Pre-specified thresholds (P93/P98/P99.9)*", "", "", "", ""],
  ["Commands / patient-day", "0.333 [0.282, 0.398]", "1.31 [1.20, 1.43]", "0.157 [0.146, 0.168]", "0.157 [0.147, 0.169]"],
  ["Sepsis cases detected (of 919)", "218 (23.7%)", "359 (39.1%)", "359 (39.1%)", "359 (39.1%)"],
  ["Detected at least 6 h before onset", "144", "289", "289", "289"],
  ["Patients flagged / positive predictive value", "404 / 61.6%", "934 / 40.9%", "934 / 40.9%", "934 / 40.9%"],
  ["Non-septic patients ever at T or above", "–", "2.9%", "2.9%", "2.9%"],
  ["Reversals within 1 h / patient-day", "–", "0.0028", "0.0028", "0.0016"],
  ["*Rate-matched thresholds (P72/P92/P99.6)*", "", "", "", ""],
  ["Commands / patient-day", "1.21", "6.24", "1.03", "1.02"],
  ["Sepsis cases detected (of 919)", "430 (46.8%)", "630 (68.6%)", "630 (68.6%)", "630 (68.6%)"],
  ["Positive predictive value / non-septic flagged", "26.9% / –", "10.6% / 32.8%", "10.6% / 32.8%", "10.6% / 32.8%"],
], [2972, 1600, 1600, 1650, 1650], { full: true }));

SPAN(FIG("fig3_trace_real.png", 6.2),
  CAP("Worked trace for a real septic patient of hospital B (PhysioNet/CinC 2019 record p111072). Top: hourly anomaly scores coloured by class (grey L, yellow M, orange C) with thresholds; the shaded band is the detection window (12 h before to 3 h after onset) and the dashed line the Sepsis-3 onset at 68 h. Bottom: evidence $λ$ (orange) and committed state S (blue) with the commands emitted at each transition. The patient reaches T at 61 h, 7 h before onset. At 62 h $λ$ falls to W while S is held at T until the 2-h dwell elapses (A-10 at 63 h); escalation at 64 h (A-04) is immediate."));

C.push(H2("Dwell, Transition Bound, and Ordering"));
C.push(P("Across the dwell sweep (Fig. 4b), rapid reversals fell from 2.8 to 1.6 per 1,000 patient-days between $δ_{down} = 0$ and 2 h and to 1.4 at 4–6 h, while elevated time in non-septic patients rose only from 0.47 to 0.48 h per patient-day; sensitivity and lead time were identical for every dwell. A dwell of 1 h has no effect because consecutive evaluations are 1 h apart. No patient exceeded the Theorem 1 bound: the largest count was 25 transitions, at most 16% of the bound for that patient's stay. With A1 enforced, all 5,000 shuffled replays reproduced the oracle's decision trace exactly (Fig. 4c); without a buffer, folding late scores in reproduced it in 97.2% of replays and dropping them in 96.7%, with 27 and 28 of the 500 patients diverging at least once. The divergence raised no error, so partition-key selection belongs in the specification, not in throughput tuning."));

C.push(H2("Calibration Trade-Off"));
C.push(P("The pre-specified thresholds proved conservative at one score per hour. The rate-matched configuration raised sensitivity to 68.6% (630 of 919) at the cost of flagging 32.8% of non-septic patients (patient-level positive predictive value 10.6% versus 40.9%), and the earlier P70/P90 default behaved similarly (70.6% sensitivity, 35.5% of non-septic patients flagged). In every configuration DWI issued 6.1 to 8.3 times fewer commands than level-triggering with identical sensitivity (Table 5)."));

C.push(H2("Reverse Direction: Hospital B to Hospital A"));
C.push(P("Table 6 repeats the evaluation with the hospitals exchanged. The detector transferred comparably (hourly area under the ROC curve 0.75 on hospital A, against 0.84 within hospital B), but the thresholds did not: the hospital B calibration rule placed 5.6% of hospital A hours above $θ_{C}$, against a nominal 2% and the 1.4% observed in the original direction, because hospital A scores lie higher overall. The calibration-dependent outcomes moved accordingly. Sensitivity rose to 67.0% (1,063 of 1,587; 875 at least 6 h before onset), but 34.5% of non-septic patients reached T and the patient-level positive predictive value fell to 16.4%; B1 detected 801 cases (50.5%). The structural results replicated. DWI issued 1.21 commands per patient-day (95% CI 1.19–1.23) against 6.70 (6.56–6.85) for level-triggering, a 5.5-fold reduction with identical sensitivity; the dwell gate halved rapid reversals (0.0224 to 0.0110 per patient-day) without delaying any escalation; no patient exceeded the Theorem 1 bound (largest count 33 transitions, at most 21% of the bound); and with A1 enforced all 5,000 shuffled replays matched the oracle, whereas folding or dropping late scores reproduced it in only 79.8% and 73.4% of replays. With rate-matched thresholds, DWI again issued 7.0 times fewer commands than level-triggering (2.53 against 17.8 per patient-day)."));
C.push(TCAP("Cross-hospital evaluation in both directions (PhysioNet/CinC 2019). Each detector was trained and its thresholds calibrated on one hospital only; the other hospital was used only for evaluation."));
C.push(TABLE([
  ["Metric", "A → B", "B → A"],
  ["Test patients / evaluable septic", "20,000 / 919", "20,336 / 1,587"],
  ["Hourly AUROC, test hospital", "0.73", "0.75"],
  ["Test hours above $θ_{C}$ (nominal 2%)", "1.4%", "5.6%"],
  ["Commands / patient-day, B2 → DWI", "1.31 → 0.157", "6.70 → 1.21"],
  ["Reduction by edge-triggering", "8.3×", "5.5×"],
  ["Sensitivity, state couplings", "39.1%", "67.0%"],
  ["Positive predictive value", "40.9%", "16.4%"],
  ["Non-septic ever at T or above", "2.9%", "34.5%"],
  ["Reversals / patient-day, $δ_{down}$ 0 → 2 h", "0.0028 → 0.0016", "0.0224 → 0.0110"],
  ["Max transitions (share of bound) / violations", "25 (16%) / 0", "33 (21%) / 0"],
  ["Replays identical: A1 / fold / drop", "100 / 97.2 / 96.7%", "100 / 79.8 / 73.4%"],
], [2640, 1200, 1200]));

// 6 Discussion
C.push(H1("Discussion"));
C.push(H2("What the Specification Provides"));
C.push(P("Treating the coupling as a finite state machine yields three properties unavailable to the alerting pattern. Pre-deployment testing becomes exhaustive, because the domains of $Φ$ and of the adaptation table are finite and $λ$ admits an exact 64-cell predicate abstraction, so decision-layer conformance is complete rather than sampled. Audit becomes reproducible, because by Theorem 2 the reason the system escalated a patient at a given time can be recomputed. Automated workload becomes bounded, because Theorem 1 with edge-triggering limits the interruption rate structurally, and edge-triggering cut commands 5.5- to 8.3-fold relative to level-triggering on real patients in both directions. The nearest clinical neighbours [19,20] adapt pathways but state none of these properties; DWI's differentiation is that its adaptation layer is specified, proved and verified, and triggered by a continuous signal."));
SPAN(FIG("fig4_results_real.png", 6.9),
  CAP("Results on the 20,000 hospital B patients. (a) Automated commands per patient-day for the four couplings (log scale; error bars, 95% patient-level bootstrap intervals; B1 threshold alert, B2 level-triggered, B3 edge-triggered without hysteresis). (b) Rapid reversals per 1,000 patient-days as a function of $δ_{down}$. (c) Share of 5,000 shuffled replays (500 patients) whose decision trace is identical to the oracle, with and without per-patient ordering."));
C.push(P("The evaluation also audited the verification itself: two mutants survived a fully passing suite, and a key collision that the proof of Theorem 2 had silently assumed away was found during development."));
C.push(H2("Where the Leverage Lies"));
C.push(P("The real-data results reorder design priorities. Calibration of the quantile thresholds moved the share of non-septic patients flagged from 2.9% to 32.8% (35.5% with the earlier P70/P90 default) and sepsis sensitivity from 39.1% to 68.6% without any change to the state machine, while edge-triggering cut commands 5.5- to 8.3-fold in every configuration. Thresholds also failed to transfer between hospitals (Section V-F), so they must be calibrated locally before deployment, whereas the structural properties held in both directions. Hysteresis is a second-order control: at an hourly cadence the window aggregates already smooth the evidence, and the dwell gate removed 43% to 51% of the few remaining rapid reversals (Fig. 4b; Table 6). Calibration should therefore prioritize $θ_{M}$, $θ_{C}$ and $Δ_{m}$, matched to the signature rate of the deployment."));
C.push(H2("Safety, Autonomy, and Deployment Context"));
C.push(P("Because DWI's lowest-tier mutations execute without prior review, we treat it as software as a medical device rather than assuming a decision-support exemption, and restrict Tier 0 to increases in monitoring frequency. Reducing monitoring on a recently critical patient is the highest-risk action because its harm is silent; Proposition 2 does not make it appropriate, and the tiering closes that gap. In the intended Indonesian setting, electronic records are mandatory [33] and processors of health data carry accountability obligations [34], which the justification record and Theorem 2 support. Because neutral-seeming algorithms can encode inequity through the choice of target [35], the clinical evaluation will stratify every primary metric."));
C.push(H2("Limitations"));
C.push(P("The evaluation is retrospective and uses two hospitals of one public sepsis database rather than the atrial fibrillation setting of the running example; replication on an independent database such as MIMIC-IV, which requires credentialed access, is planned. It counts commands rather than executing them in a workflow engine, cannot observe recovery, so de-escalation lag after an episode is not measured, and relies on a deliberately simple detector (area under the ROC curve 0.73 and 0.75 on the external hospitals), so absolute sensitivities reflect the detector as much as DWI. Onset follows the challenge's Sepsis-3 labels. The proved properties are structural and say nothing about whether the escalation criteria are clinically right, which requires expert consensus and prospective evaluation. Both realizations were built by one team; latency under load is not addressed; and the parameterization and Table 3 are illustrative until endorsed by clinicians."));

C.push(H1("Conclusion"));
C.push(P("DWI specifies the step from score to process change as three composed total functions whose committed state never under-reports the evidence, whose transition count, and hence automated workload, is bounded in closed form, and whose decision trace is reproducible from a log under three named assumptions. Conformance testing audited by mutation analysis and a two-way cross-hospital evaluation on 40,336 real intensive care patients confirmed these properties in both directions, showed that edge-triggering reduces automated workload 5.5- to 8.3-fold without delaying escalation, showed that thresholds must be calibrated locally, and exposed three issues in the earlier specification. Whether the specified behaviour is also the right behaviour must now be established prospectively with clinicians."));

// Acknowledgment (IEEE Access: unnumbered, before references; AI use is disclosed here)
C.push(H1("Acknowledgment", false));
C.push(P("The authors thank the organizers of the PhysioNet/Computing in Cardiology Challenge 2019 for making the data publicly available, and [names of people who helped but do not meet authorship criteria]. During the preparation of this work the authors used [name of the AI tool] to assist with drafting text, implementing the evaluation code, and preparing figures; the AI-assisted text appears in [list the sections]. The authors reviewed and edited all content and take full responsibility for the publication.", { noindent: false }));

C.push(H1("References", false));
const REFS = [
  'J. S. Ancker, A. Edwards, S. Nosal, D. Hauser, E. Mauer, and R. Kaushal, “Effects of workload, work complexity, and repeated alerts on alert fatigue in a clinical decision support system,” *BMC Med. Informat. Decis. Making*, vol. 17, Art. no. 36, 2017, doi: 10.1186/s12911-017-0430-8.',
  'A. Wong *et al.*, “External validation of a widely implemented proprietary sepsis prediction model in hospitalized patients,” *JAMA Intern. Med.*, vol. 181, no. 8, pp. 1065–1070, 2021, doi: 10.1001/jamainternmed.2021.2626.',
  'N. Newton, A. Bamgboje-Ayodele, R. Forsyth, A. Tariq, and M. T. Baysari, “A systematic review of clinicians’ acceptance and use of clinical decision support systems over time,” *npj Digit. Med.*, vol. 8, Art. no. 309, 2025, doi: 10.1038/s41746-025-01662-7.',
  'A. A. Verma *et al.*, “Clinical evaluation of a machine learning-based early warning system for patient deterioration,” *Can. Med. Assoc. J.*, vol. 196, no. 30, pp. E1027–E1037, 2024, doi: 10.1503/cmaj.240132.',
  'S. C. Rossetti *et al.*, “Real-time surveillance system for patient deterioration: A pragmatic cluster-randomized controlled trial,” *Nature Med.*, vol. 31, no. 6, pp. 1895–1902, 2025, doi: 10.1038/s41591-025-03609-7.',
  'R. Adams *et al.*, “Prospective, multi-site study of patient outcomes after implementation of the TREWS machine learning-based early warning system for sepsis,” *Nature Med.*, vol. 28, no. 7, pp. 1455–1460, 2022, doi: 10.1038/s41591-022-01894-0.',
  'J. A. Joglar *et al.*, “2023 ACC/AHA/ACCP/HRS guideline for the diagnosis and management of atrial fibrillation: A report of the American College of Cardiology/American Heart Association Joint Committee on Clinical Practice Guidelines,” *Circulation*, vol. 149, no. 1, pp. e1–e156, 2024, doi: 10.1161/CIR.0000000000001193.',
  'I. C. Van Gelder *et al.*, “2024 ESC guidelines for the management of atrial fibrillation developed in collaboration with the European Association for Cardio-Thoracic Surgery (EACTS),” *Eur. Heart J.*, vol. 45, no. 36, pp. 3314–3414, 2024, doi: 10.1093/eurheartj/ehae176.',
  'A. R. Hevner, S. T. March, J. Park, and S. Ram, “Design science in information systems research,” *MIS Quart.*, vol. 28, no. 1, pp. 75–105, 2004.',
  'K. Peffers, T. Tuunanen, M. A. Rothenberger, and S. Chatterjee, “A design science research methodology for information systems research,” *J. Manage. Inf. Syst.*, vol. 24, no. 3, pp. 45–77, 2007.',
  'M. Reichert and P. Dadam, “ADEPTflex—Supporting dynamic changes of workflows without losing control,” *J. Intell. Inf. Syst.*, vol. 10, no. 2, pp. 93–129, 1998, doi: 10.1023/A:1008604709862.',
  'S. Rinderle, M. Reichert, and P. Dadam, “Correctness criteria for dynamic changes in workflow systems—A survey,” *Data Knowl. Eng.*, vol. 50, no. 1, pp. 9–34, 2004.',
  'B. Weber, M. Reichert, and S. Rinderle-Ma, “Change patterns and change support features—Enhancing flexibility in process-aware information systems,” *Data Knowl. Eng.*, vol. 66, no. 3, pp. 438–466, 2008, doi: 10.1016/j.datak.2008.05.001.',
  'M. Reichert and B. Weber, *Enabling Flexibility in Process-Aware Information Systems: Challenges, Methods, Technologies*. Berlin, Germany: Springer, 2012, doi: 10.1007/978-3-642-30409-5.',
  '*Business Process Model and Notation (BPMN), Version 2.0.2*, Object Manage. Group, Milford, MA, USA, 2014.',
  '*Decision Model and Notation (DMN), Version 1.3*, Object Manage. Group, Milford, MA, USA, 2019.',
  'M. Pesic, H. Schonenberg, and W. M. P. van der Aalst, “DECLARE: Full support for loosely-structured processes,” in *Proc. 11th IEEE Int. Enterprise Distrib. Object Comput. Conf. (EDOC)*, 2007, pp. 287–298, doi: 10.1109/EDOC.2007.4384001.',
  'S. Quaglini, M. Stefanelli, G. Lanzola, V. Caporusso, and S. Panzarasa, “Flexible guideline-based patient careflow systems,” *Artif. Intell. Med.*, vol. 22, no. 1, pp. 65–80, 2001.',
  'D. Alexandrou, I. Skitsas, and G. Mentzas, “A holistic environment for the design and execution of self-adaptive clinical pathways,” *IEEE Trans. Inf. Technol. Biomed.*, vol. 15, no. 1, pp. 108–118, Jan. 2011, doi: 10.1109/TITB.2010.2074205.',
  'W. Yao and A. Kumar, “CONFlexFlow: Integrating flexible clinical pathways into clinical decision support systems using context and rules,” *Decis. Support Syst.*, vol. 55, no. 2, pp. 499–515, 2013, doi: 10.1016/j.dss.2012.10.008.',
  'C. P. Subbe, M. Kruger, P. Rutherford, and L. Gemmel, “Validation of a modified early warning score in medical admissions,” *QJM*, vol. 94, no. 10, pp. 521–526, 2001, doi: 10.1093/qjmed/94.10.521.',
  'J. C. Mandel, D. A. Kreda, K. D. Mandl, I. S. Kohane, and R. B. Ramoni, “SMART on FHIR: A standards-based, interoperable apps platform for electronic health records,” *J. Amer. Med. Inform. Assoc.*, vol. 23, no. 5, pp. 899–908, 2016, doi: 10.1093/jamia/ocv189.',
  'HL7 International. *CDS Hooks Specification, Version 2.0*. Accessed: Nov. 3, 2026. [Online]. Available: https://cds-hooks.hl7.org',
  '*Management of Alarm Systems for the Process Industries*, ANSI/ISA-18.2-2016, Int. Soc. Automat., Research Triangle Park, NC, USA, 2016.',
  'D. Calvanese, M. Dumas, Ü. Laurson, F. M. Maggi, M. Montali, and I. Teinemaa, “Semantics and analysis of DMN decision tables,” in *Business Process Management* (Lecture Notes in Computer Science), vol. 9850. Cham, Switzerland: Springer, 2016, pp. 217–233, doi: 10.1007/978-3-319-45348-4_13.',
  'D. Calvanese, M. Dumas, Ü. Laurson, F. M. Maggi, M. Montali, and I. Teinemaa, “Semantics, analysis and simplification of DMN decision tables,” *Inf. Syst.*, vol. 78, pp. 112–125, 2018, doi: 10.1016/j.is.2017.11.001.',
  'J. Kreps, N. Narkhede, and J. Rao, “Kafka: A distributed messaging system for log processing,” in *Proc. NetDB Workshop*, 2011, pp. 1–7.',
  'K. Claessen and J. Hughes, “QuickCheck: A lightweight tool for random testing of Haskell programs,” in *Proc. 5th ACM SIGPLAN Int. Conf. Funct. Program. (ICFP)*, 2000, pp. 268–279, doi: 10.1145/351240.351266.',
  'D. R. MacIver and Z. Hatfield-Dodds, “Hypothesis: A new approach to property-based testing,” *J. Open Source Softw.*, vol. 4, no. 43, Art. no. 1891, 2019, doi: 10.21105/joss.01891.',
  'Y. Jia and M. Harman, “An analysis and survey of the development of mutation testing,” *IEEE Trans. Softw. Eng.*, vol. 37, no. 5, pp. 649–678, Sep. 2011, doi: 10.1109/TSE.2010.62.',
  'M. A. Reyna, C. S. Josef, R. Jeter, S. P. Shashikumar, M. B. Westover, S. Nemati, G. D. Clifford, and A. Sharma, “Early prediction of sepsis from clinical data: The PhysioNet/Computing in Cardiology Challenge 2019,” *Crit. Care Med.*, vol. 48, no. 2, pp. 210–217, 2020, doi: 10.1097/CCM.0000000000004145.',
  'A. L. Goldberger *et al.*, “PhysioBank, PhysioToolkit, and PhysioNet: Components of a new research resource for complex physiologic signals,” *Circulation*, vol. 101, no. 23, pp. e215–e220, 2000, doi: 10.1161/01.CIR.101.23.e215.',
  '*Peraturan Menteri Kesehatan Nomor 24 Tahun 2022 tentang Rekam Medis* [Minister of Health Regulation No. 24 of 2022 on Medical Records], Kementerian Kesehatan Republik Indonesia, Jakarta, Indonesia, 2022.',
  '*Undang-Undang Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi* [Law No. 27 of 2022 on Personal Data Protection], Republik Indonesia, Jakarta, Indonesia, 2022.',
  'Z. Obermeyer, B. Powers, C. Vogeli, and S. Mullainathan, “Dissecting racial bias in an algorithm used to manage the health of populations,” *Science*, vol. 366, no. 6464, pp. 447–453, 2019, doi: 10.1126/science.aax2342.',
];
REFS.forEach((r, i) => C.push(new Paragraph({ children: [
    ...(i === 0 ? [new TextRun({ text: "\u27E6BIB0\u27E7" })] : []),
    new TextRun({ text: `[${i + 1}]`, font: FONT, size: 16 }), new TextRun({ children: [new Tab()], font: FONT, size: 16 }), ...runs(r, { size: 16 }),
    ...(i === REFS.length - 1 ? [new TextRun({ text: "\u27E6BIB1\u27E7" })] : [])],
  alignment: AlignmentType.JUSTIFIED, tabStops: [{ type: TabStopType.LEFT, position: 400 }],
  spacing: { after: 20, line: 205 }, indent: { left: 400, hanging: 400 } })));

// Author biographies (IEEE Access: required for all authors, below the references)
const BIOS = [
  "**[AUTHOR 1 FULL NAME]** received the [degree] degree in [field] from [institution], [city], [country], in [year], where [he/she] is currently pursuing the Ph.D. degree in [field]. [He/She] is a Lecturer with [institution]. [His/Her] research interests include [interests]. [Replace with a biography of up to about 100 words.]",
  "**[CLINICAL CO-AUTHOR FULL NAME]** received the [degree] degree from [institution] in [year]. [He/She] is currently a [position] with the [Department of Cardiology / Intensive Care], [hospital]. [His/Her] research interests include [interests].",
  "**[SUPERVISOR FULL NAME]** received the Ph.D. degree in [field] from [institution] in [year]. [He/She] is currently a [Professor/Associate Professor] with [institution]. [His/Her] research interests include [interests].",
];
C.push(new Paragraph({ spacing: { before: 200, after: 0 }, children: [] }));
for (const b of BIOS) C.push(P(b, { run: { size: 16 }, after: 100, line: 215 }));
flush();

const pageProps = { size: { width: PAGEW, height: PAGEH }, margin: { top: MARG_T, bottom: MARG_B, left: MARG_LR, right: MARG_LR } };
const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
  children: [new TextRun({ children: ["VOLUME XX, 2026          ", PageNumber.CURRENT], font: FONT, size: 16 })] })] });
const doc = new Document({
  creator: "DWI authors", title: "Dynamic Workflow Intelligence",
  styles: { default: { document: { run: { font: FONT, size: BODY } } } },
  numbering: { config: [
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1)", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 340, hanging: 260 } } } }] },
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 300, hanging: 200 } } } }] },
  ] },
  sections: SECTIONS.map((sec, i) => ({
    properties: { page: pageProps, ...(i === 0 ? {} : { type: SectionType.CONTINUOUS }),
      column: { count: sec.cols, space: GAP, equalWidth: true } },
    footers: { default: footer },
    children: sec.children,
  })),
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(process.argv[2] || "DWI_manuscript.docx", b); fs.writeFileSync("math.json", JSON.stringify(MATH)); console.log("written", MATH.length, "math items"); });
