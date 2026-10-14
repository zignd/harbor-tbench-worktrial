// Visual interview deck. Same numbers as docs/result/deck_data.json.
// NODE_PATH=<pptxgenjs node_modules> node docs/result/build_deck.js
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const D = JSON.parse(fs.readFileSync(path.join(HERE, "deck_data.json")));
const approved = (D.approved_tasks || [])[0];
const acc = D.blind.accuracy.toFixed(2);
const ci0 = D.blind.wilson[0].toFixed(2);
const ci1 = D.blind.wilson[1].toFixed(2);

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
const INK = "0F1B2A";
const MUTED = "5A6B7A";
const TEAL = "2A9D8F";
const GOLD = "E9C46A";
const RED = "C0392B";
const NAVY = "0F1B2A";
const PANEL = "F3F7F6";
const WHITE = "FFFFFF";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "harbor-tbench-worktrial";
pres.title = D.title;
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };

function notes(slide, t) { slide.addNotes(t); }
function tb(slide, text, o) {
  slide.addText(text, Object.assign({ isTextBox: true, margin: 0, fontFace: "Calibri" }, o));
}
function card(slide, x, y, w, h, fill) {
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08,
  });
}

function light(title) {
  const s = pres.addSlide();
  s.background = { color: WHITE };
  tb(s, title, { x: 0.5, y: 0.28, w: 9.0, h: 0.7, fontSize: 28, bold: true, fontFace: "Cambria", color: INK });
  return s;
}

// ── 1. Title ──────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  card(s, 0.5, 1.55, 0.18, 1.35, TEAL);
  tb(s, D.title, { x: 0.9, y: 1.45, w: 8.5, h: 1.5, fontSize: 32, bold: true, fontFace: "Cambria", color: WHITE });
  tb(s, D.subtitle, { x: 0.9, y: 3.05, w: 8.2, h: 0.7, fontSize: 16, color: "CADCFC" });
  tb(s, `${D.models.author}  ·  ${D.models.solver}`, {
    x: 0.9, y: 4.85, w: 8.2, h: 0.35, fontSize: 12, color: "9FB4C8",
  });
  notes(s, "Open with the claim: we built a pipeline that authors Terminal-Bench tasks and keeps only the learnable ones. Then show what the audit actually approved.");
}

// ── 2. The band ───────────────────────────────────────────────────────────
{
  const s = light("A task is useful only in the 1-3 of 5 band");
  const labels = ["0", "1", "2", "3", "4", "5"];
  const names = ["too hard", "learnable", "learnable", "learnable", "too easy", "too easy"];
  const fills = [RED, TEAL, TEAL, TEAL, GOLD, GOLD];
  labels.forEach((lab, i) => {
    const x = 0.5 + i * 1.5;
    card(s, x, 1.25, 1.35, 2.15, fills[i]);
    tb(s, lab, { x, y: 1.45, w: 1.35, h: 1.0, align: "center", fontSize: 40, bold: true, fontFace: "Cambria", color: WHITE });
    tb(s, names[i], { x, y: 2.55, w: 1.35, h: 0.55, align: "center", fontSize: 13, color: WHITE });
  });
  tb(s, "Five runs of the calibration solver. Failures must be the model's fault — not a flaky environment, a hidden timeout, or an ambiguous spec.", {
    x: 0.5, y: 3.65, w: 9.0, h: 0.7, fontSize: 15, color: MUTED,
  });
  tb(s, "Sonnet → Opus: 0 of 9 in band. We rebuilt the pipeline and opened the model choice.", {
    x: 0.5, y: 4.45, w: 9.0, h: 0.55, fontSize: 15, color: INK,
  });
  notes(s, "The README's core deliverable is the in-band fraction with valid failures. Point at boxes 1-3: that is the only region we ship.");
}

// ── 3. Pipeline ───────────────────────────────────────────────────────────
{
  const s = light("Cheap gates first. Calibration is the only difficulty signal.");
  const row1 = ["spec", "blueprint", "author", "structure\nlint · leak", "oracle 3/3\n+ nop"];
  const row2 = ["quality\ncheck", "novelty", "red-team", "calibrate\n5×, curtailed", "ship\nin band"];
  function row(items, y, highlight) {
    items.forEach((t, i) => {
      const x = 0.45 + i * 1.9;
      const hi = t === highlight;
      card(s, x, y, 1.7, 1.15, hi ? TEAL : PANEL);
      tb(s, t, {
        x, y, w: 1.7, h: 1.15, align: "center", valign: "middle",
        fontSize: 13, bold: true, color: hi ? WHITE : INK,
      });
      if (i < items.length - 1) {
        s.addShape(pres.ShapeType.rightArrow, {
          x: x + 1.72, y: y + 0.45, w: 0.16, h: 0.22,
          fill: { color: TEAL }, line: { color: TEAL },
        });
      }
    });
  }
  row(row1, 1.25, "oracle 3/3\n+ nop");
  row(row2, 2.7, "calibrate\n5×, curtailed");
  tb(s, "Failures feed repair rounds. A directory in output/ is not approval — only a hash-bound calibration record is.", {
    x: 0.5, y: 4.15, w: 9.0, h: 0.7, fontSize: 15, color: MUTED,
  });
  notes(s, "Walk left to right. Cheap gates first; calibration is the only real difficulty signal. Failures feed repair rounds.");
}

// ── 4. Models ─────────────────────────────────────────────────────────────
{
  const s = light("One fixed pair. The band is relative to the solver.");
  const items = [
    { k: "Author", v: "gpt-5.6-luna", d: "writes, reviews, judges, red-teams" },
    { k: "Solver", v: "gpt-5.4-mini", d: "terminus-2 · 5 attempts · 100-turn cap" },
    { k: "Novelty", v: "TB 2.1", d: "89 published tasks + examples/" },
  ];
  items.forEach((it, i) => {
    const x = 0.5 + i * 3.1;
    card(s, x, 1.25, 2.95, 2.55, PANEL);
    tb(s, it.k, { x: x + 0.18, y: 1.4, w: 2.6, h: 0.35, fontSize: 13, color: TEAL, bold: true });
    tb(s, it.v, { x: x + 0.18, y: 1.85, w: 2.6, h: 0.7, fontSize: 22, bold: true, fontFace: "Cambria", color: INK });
    tb(s, it.d, { x: x + 0.18, y: 2.7, w: 2.6, h: 0.8, fontSize: 14, color: MUTED });
  });
  tb(s, "Original trial fixed Sonnet + Opus. We label every result and never mix model pairs in one funnel.", {
    x: 0.5, y: 4.15, w: 9.0, h: 0.6, fontSize: 15, color: MUTED,
  });
  notes(s, "The original trial fixed Sonnet+Opus; the user opened it. We label and separate every model pair.");
}

// ── 5. Candidate batch — bar chart ────────────────────────────────────────
{
  const s = light("The pool is bimodal. Most tasks miss the band.");
  s.addChart(pres.charts.BAR, [{
    name: "Candidates",
    labels: ["Learnable (label)", "Too easy", "Too hard", "Invalid"],
    values: [D.batch.learnable, D.batch.too_easy, D.batch.too_hard, D.batch.invalid],
  }], {
    x: 0.4, y: 1.15, w: 5.4, h: 3.7,
    barGrouping: "clustered",
    showValue: true,
    dataLabelPosition: "outEnd",
    dataLabelColor: INK,
    dataLabelFontSize: 12,
    dataLabelFontFace: "Calibri",
    chartColors: [TEAL, GOLD, RED, "7A8B99"],
    showLegend: false,
    showTitle: false,
    catAxisLabelColor: INK,
    valAxisLabelColor: MUTED,
    catAxisLabelFontSize: 12,
    valAxisLabelFontSize: 11,
    valGridLine: { color: "EAF1F8", size: 0.75 },
    catGridLine: { style: "none" },
    chartFontFace: "Calibri",
    valAxisHidden: false,
    catAxisHidden: false,
  });
  const facts = [
    { n: `${D.batch.labelled} / ${D.batch.records}`, l: "verdicts / candidate records" },
    { n: `${D.batch.fresh} / ${D.batch.reused}`, l: "fresh / reused" },
    { n: String(D.batch.learnable_full_record), l: "in band, full 5-attempt record" },
    { n: "1", l: "approved after audit" },
  ];
  facts.forEach((f, i) => {
    const y = 1.2 + i * 0.95;
    card(s, 6.05, y, 3.45, 0.86, PANEL);
    tb(s, f.n, { x: 6.2, y: y + 0.06, w: 3.15, h: 0.42, fontSize: 19, bold: true, fontFace: "Cambria", color: TEAL });
    tb(s, f.l, { x: 6.2, y: y + 0.47, w: 3.15, h: 0.32, fontSize: 12, color: MUTED });
  });
  notes(s, "Be careful: these are historical candidate records, not approvals. The ledger labels THREE candidates learnable, but re-deriving the distribution under the approval standard gives only TWO: one label rests on a curtailed 1/3, which is not a full 1-3/5 statement, and one full record ends in pipeline status failed. Neither is the approved task, which needed a repair and a second independent batch. After the audit ONE task is approved. Slide 7 has the audited number.");
}

// ── 6. Audit ──────────────────────────────────────────────────────────────
{
  const s = light("The audit rejected four previously 'shipped' tasks");
  const reasons = [
    { n: "01", t: "No hash-bound calibration inside the package" },
    { n: "02", t: "One shipped on a single judged pass, not 1-3/5" },
    { n: "03", t: "Stale READMEs citing ids that never existed" },
    { n: "04", t: "A directory is not approval. They were archived, not deleted." },
  ];
  reasons.forEach((r, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.5 + col * 4.7, y = 1.25 + row * 1.7;
    card(s, x, y, 4.5, 1.5, PANEL);
    tb(s, r.n, { x: x + 0.25, y: y + 0.25, w: 1.0, h: 0.45, fontSize: 18, bold: true, fontFace: "Cambria", color: TEAL });
    tb(s, r.t, { x: x + 0.25, y: y + 0.75, w: 4.0, h: 0.55, fontSize: 15, color: INK });
  });
  notes(s, "I re-audited my own earlier success claims and found they did not hold up.");
}

// ── 7. Approved task ──────────────────────────────────────────────────────
{
  const s = light("One task approved: optimize-policy-decision-audit");
  const outcomes = (approved && approved.calibration && approved.calibration.outcomes) || ["pass", "pass", "pass", "fail", "fail"];
  outcomes.forEach((o, i) => {
    const x = 0.5 + i * 1.85;
    const ok = o === "pass";
    card(s, x, 1.2, 1.7, 1.7, ok ? TEAL : RED);
    tb(s, ok ? "PASS" : "FAIL", {
      x, y: 1.45, w: 1.7, h: 0.7, align: "center", fontSize: 22, bold: true, fontFace: "Cambria", color: WHITE,
    });
    tb(s, `#${i + 1}`, { x, y: 2.2, w: 1.7, h: 0.4, align: "center", fontSize: 13, color: WHITE });
  });
  const pills = [
    { n: "3 / 5", l: "honest passes" },
    { n: "7 / 10", l: "pooled = 0.70" },
    { n: "3 / 3", l: "oracle · nop 0" },
  ];
  pills.forEach((p, i) => {
    const x = 0.5 + i * 3.1;
    card(s, x, 3.15, 2.95, 1.45, PANEL);
    tb(s, p.n, { x, y: 3.3, w: 2.95, h: 0.65, align: "center", fontSize: 26, bold: true, fontFace: "Cambria", color: TEAL });
    tb(s, p.l, { x, y: 4.0, w: 2.95, h: 0.4, align: "center", fontSize: 14, color: MUTED });
  });
  notes(s, "These rules are enforced in code and unit-tested after the audit. Two independent batches: 4/5 then 3/5. Pre-registered rule required both an in-band batch and a pooled rate in [0.2, 0.8].");
}

// ── 8. Stretch ────────────────────────────────────────────────────────────
{
  const s = light("Stretch goals — measured, including negatives");
  const cells = [
    { k: "A  cost", v: "26.5% of trials saved", d: "~$3.79 vs naive 5×. Invalid-run early stops credited with nothing." },
    { k: "B  tuning", v: "not demonstrated", d: "13 hash-bound tuning experiments; 0 moved into the band." },
    { k: "C  diversity", v: "TB 2.1 pool", d: "Coverage, duplication and novelty on 89 published tasks + examples/." },
    { k: "D  likeness", v: `blind ${acc}`, d: `95% CI ${ci0}-${ci1}. Rubric overfits: examples 0/6 vs generated 3/4.` },
  ];
  cells.forEach((c, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.5 + col * 4.7, y = 1.2 + row * 1.85;
    card(s, x, y, 4.5, 1.7, PANEL);
    tb(s, c.k, { x: x + 0.25, y: y + 0.18, w: 4.0, h: 0.32, fontSize: 13, bold: true, color: TEAL });
    tb(s, c.v, { x: x + 0.25, y: y + 0.52, w: 4.0, h: 0.45, fontSize: 20, bold: true, fontFace: "Cambria", color: INK });
    tb(s, c.d, { x: x + 0.25, y: y + 1.05, w: 4.0, h: 0.5, fontSize: 13, color: MUTED });
  });
  notes(s, "A and C are solid; B is a measured negative (13 hash-bound tuning experiments, none reached the band); D is partial, and note the rubric-overfitting caveat — it passes 3 of our packages and 0 of 6 human-written reference tasks, so never quote it as general task quality.");
}

// ── 9. Cost ───────────────────────────────────────────────────────────────
{
  const s = light("Spend stayed inside the ceiling");
  const items = [
    { n: `$${D.spend.conservative.toFixed(0)}`, l: "key spend of $500" },
    { n: `$${D.spend.remaining.toFixed(0)}`, l: "remaining" },
    { n: `$${D.spend.this_run_ledger.toFixed(1)}`, l: "this pair's ledger" },
  ];
  items.forEach((it, i) => {
    const x = 0.5 + i * 3.1;
    card(s, x, 1.3, 2.95, 2.2, PANEL);
    tb(s, it.n, { x, y: 1.6, w: 2.95, h: 0.9, align: "center", fontSize: 36, bold: true, fontFace: "Cambria", color: TEAL });
    tb(s, it.l, { x, y: 2.6, w: 2.95, h: 0.5, align: "center", fontSize: 14, color: MUTED });
  });
  tb(s, "The ledger over-counts across scopes. The key is authoritative. Reconciliation is unresolved: cache accounting explains a $237 swing; a $190 residual remains.", {
    x: 0.5, y: 3.8, w: 9.0, h: 0.85, fontSize: 15, color: MUTED,
  });
  notes(s, "Wall-clock time is reported separately from summed stage time. Do not claim the ledger and the key agree.");
}

// ── 10. Limits ────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  tb(s, "What we would do next", {
    x: 0.6, y: 0.45, w: 8.8, h: 0.7, fontSize: 28, bold: true, fontFace: "Cambria", color: WHITE,
  });
  const next = [
    { k: "Small N", d: "One approved task. The pool is bimodal: 0, 0, 4, 5, 5." },
    { k: "Self-judging", d: "The author also judges and red-teams. Quality scores carry that bias." },
    { k: "Novelty", d: "TB 2.1 + examples — not full public-task decontamination." },
    { k: "Next", d: "Stronger traps, a wider solver gap, difficulty near p ≈ 0.35." },
  ];
  next.forEach((n, i) => {
    const y = 1.3 + i * 0.9;
    tb(s, n.k, { x: 0.7, y, w: 2.4, h: 0.7, fontSize: 16, bold: true, color: TEAL, valign: "middle" });
    tb(s, n.d, { x: 3.2, y, w: 6.2, h: 0.7, fontSize: 16, color: WHITE, valign: "middle" });
  });
  notes(s, "Questions: how I would scale generation, harden the novelty check, and define learnable per solver.");
}

// ── 11. Architecture ──────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  tb(s, "Architecture at a glance", {
    x: 0.6, y: 0.4, w: 8.8, h: 0.7, fontSize: 28, bold: true, fontFace: "Cambria", color: WHITE,
  });
  tb(s, "spec → blueprint → author in a container → gates → calibration → ship", {
    x: 0.6, y: 1.08, w: 8.8, h: 0.45, fontSize: 15, color: TEAL,
  });
  const arch = [
    { k: "Gates before money", d: "structure → oracle/nop → quality; cheap flags stop a run before calibration spend" },
    { k: "Verification", d: "oracle 3/3 · nop 0, plus a 16-criterion quality rubric, novelty and red-team" },
    { k: "Difficulty", d: "hidden-seed inputs and multi-stage work; no stated wall-clock budgets, no answer-bearing files" },
    { k: "Money", d: "cheap gates first; one trial ≈ $0.09, so curtailment pays for a second batch" },
  ];
  arch.forEach((a, i) => {
    const x = 0.6 + (i % 2) * 4.5, y = 1.75 + Math.floor(i / 2) * 1.75;
    card(s, x, y, 4.25, 1.55, PANEL);
    tb(s, a.k, { x: x + 0.2, y: y + 0.12, w: 3.85, h: 0.35, fontSize: 15, bold: true, color: TEAL });
    tb(s, a.d, { x: x + 0.2, y: y + 0.5, w: 3.85, h: 0.95, fontSize: 13, color: MUTED });
  });
  notes(s, "Two ideas carry the architecture. First, money only moves after the cheap gates pass, which is why one calibration trial costs about nine cents. Second, difficulty is built into the verifier - hidden-seed inputs at verify time, multi-stage dependent work - and never into a stated wall-clock budget, because that failure mode is environment-dependent and the rubric rejects it.");
}

// ── 12. Q&A ───────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  tb(s, "Q&A you should be ready for", {
    x: 0.6, y: 0.4, w: 8.8, h: 0.7, fontSize: 28, bold: true, fontFace: "Cambria", color: WHITE,
  });
  const qa = [
    { q: "Is 1–3/5 just noise?", a: "A p=0.5 task lands in band 78% of the time, so verdicts are pooled: this task gives 7/10 = 0.70 across two independent batches." },
    { q: "How do you know it wasn't a hack?", a: "Lint, leak scan, anti-cheating criteria, red-team and a command scan, then a pass audit that quotes the solver's own reasoning trace." },
    { q: "Why did four fail and one pass?", a: "The pool is bimodal. The main lever that produced in-band results was also the one the rubric rejects." },
    { q: "Would a stronger author help?", a: "A 2×2 study produced no in-band task at all: the weak author wrote 0 valid tasks of 7, and no cell cleared." },
  ];
  qa.forEach((it, i) => {
    const x = 0.6 + (i % 2) * 4.5, y = 1.2 + Math.floor(i / 2) * 2.0;
    card(s, x, y, 4.25, 1.8, PANEL);
    tb(s, it.q, { x: x + 0.2, y: y + 0.12, w: 3.85, h: 0.5, fontSize: 15, bold: true, color: TEAL });
    tb(s, it.a, { x: x + 0.2, y: y + 0.62, w: 3.85, h: 1.1, fontSize: 12.5, color: MUTED });
  });
  notes(s, "If asked about the band being arbitrary: the 1-3 of 5 rule is a wide window, and the response is the pre-registered pooling rule plus two independent batches, not a claim that 3/5 is a precise measurement. If asked about author strength: the study is the honest negative result - no cell produced an in-band task, so 'use a better author' is not supported by our data.");
}

(async () => {
  const out = path.join(HERE, "presentation.pptx");
  await pres.writeFile({ fileName: out });
  console.log("wrote", out);
})();
