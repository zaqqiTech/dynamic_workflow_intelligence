const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, AlignmentType,
  BorderStyle, ShadingType, LevelFormat, Footer, PageNumber, VerticalAlign, HeadingLevel, TabStopType, Tab,
} = require("docx");

const FONT = "Times New Roman";
const BODY = 22; // half-points (10.5 pt)
const TEXTW = 9072; // A4 minus 2 x 2.5 cm

// ------------------------------------------------------------------ inline markup
// **bold**, *italic*, _{sub}, ^{sup}
const MATH = [];
function runs(text, base = {}) {
  const out = [];
  const re = /(\$[^$]+\$|\*\*[^*]+\*\*|\*[^*]+\*|_\{[^}]*\}|\^\{[^}]*\})/g;
  let last = 0, m;
  const push = (t, o) => { if (t) out.push(new TextRun({ text: t, font: FONT, size: base.size || BODY, ...base, ...o })); };
  while ((m = re.exec(text))) {
    push(text.slice(last, m.index), {});
    const s = m[0];
    if (s.startsWith("$")) { MATH.push({ src: s.slice(1, -1), size: base.size || BODY }); out.push(new TextRun({ text: `\u27E6M${MATH.length - 1}\u27E7` })); }
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
  children: runs(t, o.run || {}), alignment: o.align || AlignmentType.JUSTIFIED,
  spacing: { after: o.after ?? 80, before: o.before ?? 0, line: o.line || 245 },
  indent: o.indent, keepNext: o.keepNext,
});
let EQN = 0;
const EQ = (src) => {
  MATH.push({ src, size: BODY }); EQN += 1;
  return new Paragraph({
    tabStops: [{ type: TabStopType.CENTER, position: Math.round(TEXTW / 2) }, { type: TabStopType.RIGHT, position: TEXTW }],
    spacing: { before: 50, after: 70 }, keepLines: true,
    children: [new TextRun({ children: [new Tab()] }), new TextRun({ text: `\u27E6M${MATH.length - 1}\u27E7` }),
      new TextRun({ children: [new Tab(), `(${EQN})`], font: FONT, size: BODY })],
  });
};
const H1 = (t) => new Paragraph({ children: runs(t, { bold: true, size: 23 }), heading: HeadingLevel.HEADING_1,
  spacing: { before: 170, after: 70 }, keepNext: true });
const H2 = (t) => new Paragraph({ children: runs(t, { bold: true, italics: true, size: BODY }), heading: HeadingLevel.HEADING_2,
  spacing: { before: 110, after: 50 }, keepNext: true });
const LI = (t, ref = "num") => new Paragraph({ children: runs(t), numbering: { reference: ref, level: 0 },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 40, line: 245 } });
const CAP = (t) => new Paragraph({ children: runs(t, { size: 18 }), alignment: AlignmentType.JUSTIFIED,
  spacing: { before: 40, after: 140, line: 225 } });
const TCAP = (t) => new Paragraph({ children: runs(t, { size: 18 }), alignment: AlignmentType.LEFT,
  spacing: { before: 120, after: 50, line: 225 }, keepNext: true });
const NOTE = (t) => new Paragraph({ children: runs(t, { size: 16 }), alignment: AlignmentType.JUSTIFIED,
  spacing: { before: 30, after: 130, line: 215 } });

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
function TABLE(rows, widths, opts = {}) {
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


const C=[];
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: runs("Supplementary Material — Dynamic Workflow Intelligence", { bold: true, size: 28 }) }));
C.push(TCAP("**TABLE S1.** Evidence level $λ$, expanded staircase form (hit policy UNIQUE, normative). Each rule carries the negation of every condition introduced above it plus one new condition, so for $i < j$ rule $j$ contains the negation of the condition rule $i$ introduces (pairwise disjoint), and the terminal rule G7 covers the conjunction of all negations (jointly exhaustive). Defaults: $θ_{K}$ = P99.9, $c_{K} = 3$, $c_{T} = 2$, $m_{T} = 3$, $c_{W} = 1$, $m_{W} = 2$."));
C.push(TABLE([["Rule", "$σ_{max}(Δ_{s})$", "$n_{C}(Δ_{s})$", "$n_{C}(Δ_{m})$", "$n_{≥M}(Δ_{s})$", "$n_{C}(Δ_{l})$", "$n_{≥M}(Δ_{m})$", "$λ$"], ["G1", "≥ $θ_{K}$", "–", "–", "–", "–", "–", "K"], ["G2", "< $θ_{K}$", "≥ $c_{K}$", "–", "–", "–", "–", "K"], ["G3", "< $θ_{K}$", "< $c_{K}$", "≥ $c_{T}$", "–", "–", "–", "T"], ["G4", "< $θ_{K}$", "< $c_{K}$", "< $c_{T}$", "≥ $m_{T}$", "–", "–", "T"], ["G5", "< $θ_{K}$", "< $c_{K}$", "< $c_{T}$", "< $m_{T}$", "≥ $c_{W}$", "–", "W"], ["G6", "< $θ_{K}$", "< $c_{K}$", "< $c_{T}$", "< $m_{T}$", "< $c_{W}$", "≥ $m_{W}$", "W"], ["G7", "< $θ_{K}$", "< $c_{K}$", "< $c_{T}$", "< $m_{T}$", "< $c_{W}$", "< $m_{W}$", "R"]], [900,1250,1150,1150,1250,1150,1250,972]));
C.push(NOTE("Under C3, $n_{C}(Δ_{s}) < c_{K}$ is implied by $n_{C}(Δ_{m}) < c_{T}$ in G4–G7 for the default parameters; the redundant conditions are retained to preserve the staircase form at no semantic cost."));
C.push(TCAP("**TABLE S2.** Committed-state transition $Φ$, complete enumeration (hit policy UNIQUE). A dash in the dwell column covers both values; the 22 rules cover all 32 cells of $𝒮 × 𝒮 × @set{true, false}$ exactly once ($10 × 2 + 12 × 1$). Commands for each changing transition are in Table 3."));
C.push(TABLE([["Rule", "$S^{−}$", "$λ$", "$t − τ_{last} ≥ δ_{down}$", "$S$", "Class"], ["T01", "R", "R", "–", "R", "hold"], ["T02", "R", "W", "–", "W", "escalate"], ["T03", "R", "T", "–", "T", "escalate"], ["T04", "R", "K", "–", "K", "escalate"], ["T05", "W", "R", "false", "W", "damped"], ["T06", "W", "R", "true", "R", "de-escalate"], ["T07", "W", "W", "–", "W", "hold"], ["T08", "W", "T", "–", "T", "escalate"], ["T09", "W", "K", "–", "K", "escalate"], ["T10", "T", "R", "false", "T", "damped"], ["T11", "T", "R", "true", "R", "de-escalate"], ["T12", "T", "W", "false", "T", "damped"], ["T13", "T", "W", "true", "W", "de-escalate"], ["T14", "T", "T", "–", "T", "hold"], ["T15", "T", "K", "–", "K", "escalate"], ["T16", "K", "R", "false", "K", "damped"], ["T17", "K", "R", "true", "R", "de-escalate"], ["T18", "K", "W", "false", "K", "damped"], ["T19", "K", "W", "true", "W", "de-escalate"], ["T20", "K", "T", "false", "K", "damped"], ["T21", "K", "T", "true", "T", "de-escalate"], ["T22", "K", "K", "–", "K", "hold"]], [1100,1100,1100,2400,1100,2272]));
C.push(TCAP("**TABLE S3.** Real-data evaluation protocol (PhysioNet/Computing in Cardiology Challenge 2019, version 1.0.0, CC BY 4.0)."));
C.push(TABLE([["Item","Setting"],
 ["Database","40,336 de-identified ICU patients, hospitals A (20,336) and B (20,000); 1,552,210 patient-hours; 2,932 septic patients (Sepsis-3 labels)"],
 ["Split","Hospital A split 70/30 by patient (seed 2026): 14,235 for training, 6,101 for threshold calibration; hospital B (20,000) for evaluation only"],
 ["Detector","Gradient-boosted trees (scikit-learn HistGradientBoostingClassifier; 300 iterations, learning rate 0.05, 31 leaves, L2 = 1.0); 84 features; end-tidal CO2 excluded (never recorded in hospital A)"],
 ["Features","Last-observation-carried-forward vital signs and laboratory values; per-hour measurement indicators; 6-h change and 6-h mean of HR, O2Sat, Temp, SBP, MAP, DBP, Resp; age, sex, hospital admission time, ICU length of stay"],
 ["Detector performance","Hourly area under the ROC curve 0.81 (hospital A calibration part), 0.73 (hospital B)"],
 ["Thresholds (pre-specified rule)","P93 / P98 / P99.9 of hospital A calibration scores: $θ_{M}$ = 0.068, $θ_{C}$ = 0.195, $θ_{K}$ = 0.654"],
 ["Secondary calibrations","Rate-matched P72 / P92 / P99.6; earlier default P70 / P90 with fixed $θ_{K}$ = 0.95 (both from hospital A only)"],
 ["Sepsis onset","First hour with SepsisLabel = 1 plus 6 h (undoing the challenge label shift); evaluable if at least one hour precedes the first positive label (919 of 1,142 septic patients in hospital B)"],
 ["Detection","T or above (B1: an alert) between 12 h before and 3 h after onset"],
 ["Ordering experiment","500 hospital B patients × 10 replays; 30% of hourly scores delayed U(0, 2.5) h; buffered lateness 3 h"],
 ["Uncertainty","95% patient-level bootstrap intervals, 1,000 resamples"],
 ["Reverse direction","Hospitals exchanged with the same code and seed: 70/30 split of hospital B (14,000 training, 6,000 calibration), same quantile rule ($θ_{M}$ = 0.035, $θ_{C}$ = 0.100, $θ_{K}$ = 0.515); hourly area under the ROC curve 0.84 (hospital B calibration part), 0.75 (hospital A); evaluation on all 20,336 hospital A patients (1,587 evaluable septic); ordering experiment on 500 hospital A patients"],
], [2600, 6472], { leftAll: true }));
const doc = new Document({ styles: { default: { document: { run: { font: FONT, size: BODY } } } },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1417, bottom: 1417, left: 1417, right: 1417 } } }, children: C }] });
Packer.toBuffer(doc).then((b) => { fs.writeFileSync("supp_tmp.docx", b); fs.writeFileSync("math_supp.json", JSON.stringify(MATH)); console.log("supp written", MATH.length); });
