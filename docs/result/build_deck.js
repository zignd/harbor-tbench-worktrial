// Renders docs/result/presentation.pptx from docs/result/deck_data.json (same data as the HTML deck).
// Run: NODE_PATH=<pptxgenjs node_modules> node docs/result/build_deck.js
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const D = JSON.parse(fs.readFileSync(path.join(HERE, "deck_data.json")));

const THEME = {
  name: "Learnable",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0F1B2A", lt1: "FFFFFF", dk2: "16283D", lt2: "EAF1F8",
    accent1: "2A9D8F", accent2: "E9C46A", accent3: "264653", accent4: "C0392B",
    accent5: "7A8B99", accent6: "F4A261", hlink: "2A9D8F", folHlink: "7A8B99",
  },
};
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 10;

function dark(slide) { slide.background = { color: "0F1B2A" }; return slide; }
function lightTitle(text) {
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  s.addText(text, { x: 0.5, y: 0.35, w: 9, h: 0.9, fontSize: 30, bold: true,
    fontFace: "Cambria", color: C.text1, isTextBox: true, margin: 0, objectName: "Title" });
  return s;
}
function bullets(slide, items, y = 1.4) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    { x: 0.5, y, w: 9, h: 3.6, fontSize: 17, color: C.text1, paraSpaceAfter: 10, valign: "top",
      isTextBox: true, margin: 0 });
}
function cards(slide, arr, y = 1.5) {
  const gap = 0.2, cw = (9 - gap * (arr.length - 1)) / arr.length;
  arr.forEach((c, i) => {
    const x = 0.5 + i * (cw + gap);
    slide.addShape(pres.ShapeType.roundRect, { x, y, w: cw, h: 1.7,
      fill: { color: C.background2 }, line: { color: C.background2 }, rectRadius: 0.08 });
    slide.addText(String(c.big), { x, y: y + 0.2, w: cw, h: 0.9, align: "center", fontSize: 32,
      bold: true, color: C.accent1, fontFace: "Cambria", isTextBox: true, margin: 0 });
    slide.addText(c.label, { x: x + 0.1, y: y + 1.1, w: cw - 0.2, h: 0.5, align: "center",
      fontSize: 12, color: C.text2, isTextBox: true, margin: 0 });
  });
}
function notes(slide, t) { slide.addNotes(t); }

// 1 title
let s = dark(pres.addSlide());
s.addText(D.title, { x: 0.6, y: 1.6, w: 8.8, h: 1.3, fontSize: 40, bold: true, color: "FFFFFF",
  fontFace: "Cambria", isTextBox: true, margin: 0 });
s.addText(D.subtitle, { x: 0.6, y: 3.0, w: 8.8, h: 0.8, fontSize: 17, color: "CADCFC", isTextBox: true, margin: 0 });
s.addText(`Author ${D.models.author} · solver ${D.models.solver}`, { x: 0.6, y: 4.6, w: 8.8, h: 0.5,
  fontSize: 12, color: "9FB4C8", isTextBox: true, margin: 0 });
notes(s, "Terminal-Bench task-generation pipeline. I'll show what works, what the audit changed, and the limits.");

// 2 problem
s = lightTitle("The problem: build tasks a strong model fails sometimes");
bullets(s, ["A task is useful only in the learnable band: 5 runs, exactly 1-3 pass all tests.",
  "Failures must be the model's fault — not ambiguity, timeouts or a broken environment.",
  "Sonnet→Opus produced 0 of 9 in band; we rebuilt the pipeline and opened the model choice."]);
notes(s, "The README's core deliverable is the in-band fraction with valid failures.");

// 3 models
s = lightTitle("Models and scope");
cards(s, [{ big: "Luna", label: "author · reviewer · judge · red-team" },
  { big: "mini", label: "calibration solver (terminus-2)" },
  { big: "2.1", label: "novelty pool: TB 2.1 + examples" }]);
s.addText("One fixed pair and judge per batch; the band is relative to the calibration model. Every result is labelled.",
  { x: 0.5, y: 3.6, w: 9, h: 0.7, fontSize: 15, color: C.text2, isTextBox: true, margin: 0, valign: "top" });
notes(s, "The original trial fixed Sonnet+Opus; the user opened it. We label and separate every model pair.");

// 4 pipeline
s = lightTitle("Pipeline");
const steps = ["spec", "blueprint", "rubric +\nnovelty gate", "authoring\nmeta-task", "structure\nlint, leak",
  "oracle 3/3\n+ nop", "quality\ncheck", "red-team", "calibration\n5×, curtailed", "ship in band"];
steps.forEach((t, i) => {
  const col = i % 5, row = Math.floor(i / 5);
  const x = 0.4 + col * 1.9, y = 1.5 + row * 1.7;
  s.addShape(pres.ShapeType.roundRect, { x, y, w: 1.7, h: 1.3,
    fill: { color: i === 5 ? C.accent1 : C.background2 }, line: { color: C.background2 }, rectRadius: 0.08 });
  s.addText(t, { x: x + 0.05, y: y + 0.05, w: 1.6, h: 1.2, fontSize: 12, align: "center", valign: "middle",
    color: i === 5 ? C.background1 : C.text1, isTextBox: true, margin: 0 });
});
notes(s, "Cheap gates first; calibration is the only real difficulty signal. Failures feed repair rounds.");

// 5 difficulty by construction
s = lightTitle("Difficulty by construction");
bullets(s, ["An author as strong as the solver cannot out-think it.",
  "Build difficulty into code the author controls: hidden-seed verify-time inputs.",
  "Dependent multi-stage work; shallow-self-check traps; long-horizon inputs.",
  "Every tested requirement is stated in the instruction. No hidden limits or timeouts."]);
notes(s, "This is the design response to the 0-of-9 result and the papers' weak-verification finding.");

// 6 batch
s = lightTitle("Candidate batch");
cards(s, [{ big: D.batch.records, label: "records" },
  { big: `${D.batch.fresh}/${D.batch.reused}`, label: "fresh / reused packages" },
  { big: D.batch.learnable, label: "learnable (in band)" },
  { big: `${D.batch.too_hard}/${D.batch.too_easy}`, label: "too hard / too easy" },
  { big: D.batch.invalid, label: "invalid" }]);
s.addText("Bimodal, as predicted without continuous difficulty control. Reused copies are not independent generations.",
  { x: 0.5, y: 3.6, w: 9, h: 0.7, fontSize: 15, color: C.text2, isTextBox: true, margin: 0, valign: "top" });
notes(s, "22 records: 12 fresh, 10 recalibrated copies. Three landed in band for this solver.");

// 7 audit
s = lightTitle("The audit that changed the story");
s.addText([
  { text: "Four previously 'shipped' tasks were rejected:\n", options: { bold: true, color: "C0392B", breakLine: true } },
  { text: "no immutable calibration record inside the package;\n", options: { breakLine: true } },
  { text: "one shipped on a single judged pass (curtailed), not 1-3/5;\n", options: { breakLine: true } },
  { text: "stale READMEs citing ids that never existed; report counts disagreeing.", options: {} },
], { x: 0.5, y: 1.4, w: 9, h: 2.2, fontSize: 17, color: C.text1, isTextBox: true, margin: 0, valign: "top" });
s.addText("They are archived unchanged, not deleted. A directory is not approval.", { x: 0.5, y: 3.9, w: 9, h: 0.7,
  fontSize: 15, italic: true, color: C.text2, isTextBox: true, margin: 0 });
notes(s, "I re-audited my own earlier success claims and found they did not hold up.");

// 8 verification
s = lightTitle("Verification discipline");
bullets(s, ["Approval = content-hash-bound calibration + verification record inside the package.",
  "Independent oracle 3/3 and nop re-run; verification is offline at build time.",
  "Reports use only the declared model pair; stale-version gate successes do not count.",
  "Turn-cap exhaustion is invalid — even when the verifier reward is 1."]);
notes(s, "These rules are enforced in code and unit-tested after the audit.");

// 9 stretch
s = lightTitle("Stretch goals");
const rows = [
  ["A cost-efficient eval", "curtailment lossless; ~12-23% trials saved; dollar figure caveated"],
  ["B difficulty tuning", "implemented and exercised; no in-band movement demonstrated"],
  ["C diversity", "coverage + novelty reported on the TB 2.1 pool"],
  ["D human-likeness", `blind accuracy ${D.blind.accuracy.toFixed(2)} (95% CI ${D.blind.wilson[0].toFixed(2)}-${D.blind.wilson[1].toFixed(2)})`],
];
s.addTable([[{ text: "Goal", options: { bold: true } }, { text: "Result", options: { bold: true } }]]
  .concat(rows.map(r => [{ text: r[0] }, { text: r[1] }])),
  { x: 0.5, y: 1.4, w: 9, fontSize: 14, color: "0F1B2A", border: { type: "solid", color: "CCCCCC", pt: 0.5 },
    colW: [3.0, 6.0] });
notes(s, "Two goals solid, one exercised with a negative result, one partial — reported honestly.");

// 10 cost
s = lightTitle("Cost and time");
cards(s, [{ big: `$${D.spend.conservative.toFixed(0)}`, label: "key spend of $500" },
  { big: `$${D.spend.remaining.toFixed(0)}`, label: "remaining" },
  { big: `$${D.spend.this_run_ledger.toFixed(1)}`, label: "this pair's ledger cost" }]);
s.addText("The ledger over-counts across scopes; the key is authoritative and reconciliation is open.",
  { x: 0.5, y: 3.6, w: 9, h: 0.7, fontSize: 15, color: C.text2, isTextBox: true, margin: 0, valign: "top" });
notes(s, "Wall-clock time is reported separately from summed stage time.");

// 11 limits
s = dark(pres.addSlide());
s.addText("Limitations and next steps", { x: 0.6, y: 0.7, w: 8.8, h: 0.9, fontSize: 32, bold: true,
  color: "FFFFFF", fontFace: "Cambria", isTextBox: true, margin: 0 });
s.addText(["+ Small N and a bimodal difficulty distribution.",
  "+ Self-judging bias: the author also judges and red-teams.",
  "+ Reduced novelty scope (TB 2.1 + examples), not full decontamination.",
  "+ Next: more specs, stronger traps, a wider solver gap, and a full 5-run re-audit."].join("\n"),
  { x: 0.6, y: 1.7, w: 8.8, h: 3.4, fontSize: 17, color: "FFFFFF", isTextBox: true, margin: 0, valign: "top" });
notes(s, "Questions: how I would scale generation, harden the novelty check, and define learnable per solver.");

(async () => {
  const out = path.join(HERE, "presentation.pptx");
  await pres.writeFile({ fileName: out });
  console.log("wrote", out);
})();