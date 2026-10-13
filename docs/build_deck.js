// Builds docs/study-deck.pptx from runs/study/results.json (+ gap.json). Run: node docs/build_deck.js
// Exploratory study deck; every number comes from the results file or is typed in ANSWER below.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL + "/scripts/apply_theme.js");

const ROOT = path.join(__dirname, "..");
const results = JSON.parse(fs.readFileSync(path.join(ROOT, "runs/study/results.json")));
const gapPath = path.join(ROOT, "runs/study/gap.json");
const gap = fs.existsSync(gapPath) ? JSON.parse(fs.readFileSync(gapPath)) : [];
const A = JSON.parse(fs.readFileSync(path.join(__dirname, "study-answer.json")));
const cells = results.summary.cells;
const validity = results.summary.validity;

const THEME = {
  name: "Study",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2A41", lt1: "FFFFFF", dk2: "324A5F", lt2: "F1F5F9",
    accent1: "2A9D8F", accent2: "E9C46A", accent3: "264653", accent4: "C0392B",
    accent5: "7A8B99", accent6: "F4A261", hlink: "2A9D8F", folHlink: "7A8B99",
  },
};
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 10, H = 5.625;

function title(slide, text, dark) {
  slide.addText(text, { x: 0.5, y: 0.3, w: 9, h: 0.8, fontSize: 30, bold: true, fontFace: "Cambria",
    color: dark ? C.background1 : C.text1, isTextBox: true, margin: 0, objectName: "Title" });
}
function content(text) {
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  title(s, text, false);
  return s;
}
function bullets(slide, items, opts) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    Object.assign({ x: 0.5, y: 1.3, w: 9, h: 3.8, fontSize: 18, color: C.text1, paraSpaceAfter: 10, valign: "top",
      isTextBox: true, margin: 0 }, opts || {}));
}
function stat(slide, x, y, w, big, small, color) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h: 1.6, fill: { color: C.background2 }, rectRadius: 0.1,
    line: { color: C.background2 } });
  slide.addText(big, { x, y: y + 0.15, w, h: 0.9, align: "center", fontSize: 40, bold: true, color: color || C.accent1,
    fontFace: "Cambria", isTextBox: true, margin: 0 });
  slide.addText(small, { x: x + 0.15, y: y + 1.0, w: w - 0.3, h: 0.5, align: "center", fontSize: 13, color: C.text2,
    isTextBox: true, margin: 0 });
}
const pct = (a, b) => (b ? `${Math.round((100 * a) / b)}%` : "n/a");

// 1 title
let s = pres.addSlide();
s.background = { color: "1B2A41" };
s.addText("Who writes the task, who solves it", { x: 0.6, y: 1.5, w: 8.8, h: 1.2, fontSize: 42, bold: true,
  color: C.background1, fontFace: "Cambria", isTextBox: true, margin: 0 });
s.addText("An exploratory 2 x 2 study of author and solver strength in Terminal-Bench task generation",
  { x: 0.6, y: 2.8, w: 8.8, h: 0.9, fontSize: 20, color: "CADCFC", isTextBox: true, margin: 0 });
s.addText(`AfterQuery work trial · exploratory, user-approved deviation · pair: ${results.meta.models.weak} (weak) / ${results.meta.models.strong} (strong)`,
  { x: 0.6, y: 4.6, w: 8.8, h: 0.5, fontSize: 12, color: "CADCFC", isTextBox: true, margin: 0 });

// 2 problem
s = content("The trial: tasks a stronger model fails sometimes");
bullets(s, [
  "Sonnet 4.6 writes tasks; Opus 4.8 (terminus-2) must pass 1 to 3 of 5 runs",
  "We built gates, levers, a tuner and a failure judge",
  "9 tasks calibrated against Opus: 8 too easy (4/4 or 5/5), 1 invalid, none in the band",
  "Tuning moved nothing; a cheaper solver (Qwen) also solved them 5/5",
]);

// 3 thesis
s = content("Thesis: a student writing problems for a professor");
bullets(s, [
  "The author cannot plant difficulty beyond what it can conceive and verify",
  "The author holds the answer, so the solver only has to find it",
  "A harness steers what the author tries, not what it is able to write",
  "Prediction: weak author → strong solver gives mostly too-easy tasks",
]);

// 4 design 2x2
s = content("Design: same harness, only the models change");
const gx = 1.2, gy = 1.45, cw = 3.5, ch = 1.4;
const names = [["weak", "weak"], ["weak", "strong"], ["strong", "weak"], ["strong", "strong"]];
s.addText("solver: weak", { x: gx + 1.2, y: gy - 0.05, w: cw, h: 0.3, fontSize: 13, color: C.text2, isTextBox: true, margin: 0, align: "center" });
s.addText("solver: strong", { x: gx + 1.2 + cw + 0.2, y: gy - 0.05, w: cw, h: 0.3, fontSize: 13, color: C.text2, isTextBox: true, margin: 0, align: "center" });
const label = { "weak->weak": "control", "weak->strong": "the trial's setup", "strong->weak": "professor for student", "strong->strong": "professor for professor" };
[["weak", 0], ["strong", 1]].forEach(([author, r]) => {
  s.addText(`author: ${author}`, { x: 0.3, y: gy + 0.4 + r * (ch + 0.2), w: 1.1, h: 0.5, fontSize: 13, color: C.text2, isTextBox: true, margin: 0 });
  ["weak", "strong"].forEach((solver, c) => {
    const key = `${author}->${solver}`;
    s.addShape(pres.ShapeType.roundRect, { x: gx + 1.2 + c * (cw + 0.2), y: gy + 0.3 + r * (ch + 0.2), w: cw, h: ch,
      fill: { color: author === "weak" && solver === "strong" ? C.accent2 : C.background2 }, rectRadius: 0.1, line: { color: C.accent5 } });
    s.addText([{ text: key, options: { bold: true, breakLine: true } }, { text: label[key] }],
      { x: gx + 1.3 + c * (cw + 0.2), y: gy + 0.4 + r * (ch + 0.2), w: cw - 0.2, h: ch - 0.2, fontSize: 16, color: C.text1,
        align: "center", valign: "middle", isTextBox: true, margin: 0 });
  });
});
s.addText("Each author writes a task from the SAME spec; every valid task is solved 5x by each solver.",
  { x: 0.5, y: 4.9, w: 9, h: 0.4, fontSize: 14, color: C.text2, isTextBox: true, margin: 0 });

// 5 pipeline
s = content("Pipeline per task (events tagged study)");
const steps = ["spec\n(fixed seed)", "blueprint\n(author)", "authoring\nmeta-task", "free gates\nbuild, oracle 3/3,\nnop 0, lint, leak", "5x terminus-2\nweak + strong", "Sonnet 4.6\nfailure judge"];
steps.forEach((t, i) => {
  const x = 0.4 + i * 1.55;
  s.addShape(pres.ShapeType.roundRect, { x, y: 2.0, w: 1.4, h: 1.5, fill: { color: i === 3 ? C.accent1 : C.background2 }, rectRadius: 0.08, line: { color: C.accent5 } });
  s.addText(t, { x: x + 0.05, y: 2.05, w: 1.3, h: 1.4, fontSize: 12, align: "center", valign: "middle", color: i === 3 ? C.background1 : C.text1, isTextBox: true, margin: 0 });
  if (i < steps.length - 1) s.addText("›", { x: x + 1.38, y: 2.4, w: 0.2, h: 0.5, fontSize: 24, color: C.accent5, isTextBox: true, margin: 0, align: "center" });
});
s.addText("A failure counts as valid only if it quotes an instruction requirement; an invalid failure voids the task's verdict.",
  { x: 0.5, y: 4.2, w: 9, h: 0.7, fontSize: 14, color: C.text2, isTextBox: true, margin: 0 });

// 6 gap
s = content("Is the pair really different? Gap check on 5 pilot packages");
const gapRows = [[{ text: "package", options: { bold: true } }, { text: "Opus 4.8", options: { bold: true } }, { text: "weak", options: { bold: true } }, { text: "strong", options: { bold: true } }]];
const opus = { "p0-ledger-reconcile": "4/4", "2f505f92f1c8": "4/5", "31ca491030e9": "4/4", "b540d2ce9b80": "5/5", "3bbd19e55510": "5/5" };
Object.keys(opus).forEach((c) => {
  const w = gap.find((r) => r.candidate === c && r.solver === "weak");
  const st = gap.find((r) => r.candidate === c && r.solver === "strong");
  const f = (r) => (r ? `${r.passes}/5` + (r.invalid ? ` (${r.invalid} inv)` : "") : "n/a");
  gapRows.push([c.slice(0, 18), opus[c], f(w), f(st)]);
});
s.addTable(gapRows, { x: 0.5, y: 1.3, w: 9, fontSize: 14, color: "1B2A41", border: { type: "solid", color: "CCCCCC", pt: 0.5 }, colW: [3.6, 1.8, 1.8, 1.8] });
s.addText(A.gap_note, { x: 0.5, y: 4.4, w: 9, h: 0.8, fontSize: 14, color: C.text2, isTextBox: true, margin: 0 });

// 7 validity
s = content("Weak authors write far fewer valid tasks");
["weak", "strong"].forEach((a, i) => {
  const v = validity[a];
  stat(s, 0.7 + i * 4.6, 1.3, 3.9, `${v.valid}/${v.attempted}`, `${a} author: tasks passing every free gate (${v.valid_first_try} on the first try)`, i ? C.accent1 : C.accent4);
});
s.addText(A.validity_note, { x: 0.5, y: 3.2, w: 9, h: 1.9, fontSize: 16, color: C.text1, valign: "top", isTextBox: true, margin: 0 });

// 8 results table
s = content("Results per author → solver cell");
const hdr = ["cell", "valid", "in band", "too easy", "too hard", "invalid", "mean pass"].map((t) => ({ text: t, options: { bold: true } }));
const rows = [hdr];
Object.entries(cells).forEach(([k, c]) => {
  const v = c.verdicts;
  rows.push([k, `${c.valid}/${c.attempted}`, `${v.in_band}`, `${v.too_easy}`, `${v.too_hard}`, `${v.invalid}`, c.mean_pass_rate == null ? "n/a" : c.mean_pass_rate.toFixed(2)]);
});
s.addTable(rows, { x: 0.5, y: 1.3, w: 9, fontSize: 14, color: "1B2A41", border: { type: "solid", color: "CCCCCC", pt: 0.5 }, colW: [2.3, 1.1, 1.1, 1.1, 1.1, 1.1, 1.2] });
s.addText(A.results_note, { x: 0.5, y: 3.7, w: 9, h: 1.5, fontSize: 14, color: C.text2, valign: "top", isTextBox: true, margin: 0 });

// 9 figure
s = content("Verdict shares per cell");
s.addImage({ path: path.join(ROOT, "docs/figures/study-2x2.png"), x: 1.2, y: 1.2, w: 7.6, h: 4.0 });

// 10 answer
s = pres.addSlide();
s.background = { color: "1B2A41" };
s.addText("Does the thesis hold?", { x: 0.6, y: 0.5, w: 8.8, h: 0.8, fontSize: 32, bold: true, color: C.background1, fontFace: "Cambria", isTextBox: true, margin: 0 });
s.addText(A.answer, { x: 0.6, y: 1.5, w: 8.8, h: 3.5, fontSize: 18, color: "FFFFFF", valign: "top", isTextBox: true, margin: 0 });

// 11 cost
s = content("Cost");
stat(s, 0.7, 1.3, 2.7, `$${results.meta.study_spend_usd.toFixed(2)}`, "study spend (ledger, all study events)");
stat(s, 3.65, 1.3, 2.7, "$40", "approved hard cap for the study", C.accent5);
stat(s, 6.6, 1.3, 2.7, "$400", "ceiling for the whole key (of $500)", C.accent5);
s.addText(A.cost_note, { x: 0.5, y: 3.2, w: 9, h: 1.9, fontSize: 16, color: C.text1, valign: "top", isTextBox: true, margin: 0 });

// 12 implications
s = content("What it means for the trial");
bullets(s, A.implications);

// 13 caveats
s = content("Caveats");
bullets(s, A.caveats, { fontSize: 16 });

(async () => {
  const out = path.join(__dirname, "study-deck.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
