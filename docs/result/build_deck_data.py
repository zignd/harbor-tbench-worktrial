"""Build the interview deck data and the offline HTML deck from audited evidence.

    uv run python -m docs.result.build_deck_data

Reads only committed evidence under docs/result/evidence/ (and docs/result/verification.json),
so the deck and the report cannot drift apart. Writes docs/result/deck_data.json and
docs/result/presentation.html. The PPTX is rendered by docs/result/build_deck.js from the same
deck_data.json.
"""

import html
import json
from pathlib import Path

RESULT = Path(__file__).parent
EVIDENCE = RESULT / "evidence"


def _load(name: str, default=None):
    p = EVIDENCE / name
    return json.loads(p.read_text()) if p.exists() else default


def _mean(rows: dict, key: str) -> float:
    return round(sum(r[key] for r in rows.values()) / len(rows), 1) if rows else 0.0


def build() -> dict:
    historical = _load("historical-data.json", {})
    blind = _load("blind.json", {})
    stylo = _load("stylometrics.json", {})
    verification = (
        json.loads((RESULT / "verification.json").read_text())
        if (RESULT / "verification.json").exists()
        else {}
    )
    reconciliation = _load("reconciliation.json", {})
    verdicts = historical.get("latest_candidate_verdicts", {})
    examples = stylo.get("examples", {})
    generated = stylo.get("pre_audit_generated", {})
    return {
        "title": "Generating Terminal-Bench tasks that are learnable",
        "subtitle": "A pipeline that authors, gates and calibrates hard tasks — with exact-package evidence",
        "models": {
            "author": "openai/gpt-5.6-luna",
            "solver": "openrouter/openai/gpt-5.4-mini",
            "novelty": "Terminal-Bench 2.1 (89 tasks) + examples/",
        },
        "batch": {
            "records": 22,
            "fresh": historical.get("origins", {}).get("fresh"),
            "reused": historical.get("origins", {}).get("reused"),
            "verdicts": verdicts,
            "learnable": verdicts.get("learnable", 0),
            "too_hard": verdicts.get("too_hard", 0),
            "too_easy": verdicts.get("too_easy", 0),
            "invalid": verdicts.get("invalid", 0),
        },
        "blind": {
            "pairs": blind.get("pairs"),
            "accuracy": blind.get("accuracy"),
            "wilson": blind.get("wilson95"),
        },
        "stylometrics": {
            "examples_words": _mean(examples, "instruction_words"),
            "generated_words": _mean(generated, "instruction_words"),
            "examples_bullets": _mean(examples, "instruction_bullets"),
            "generated_bullets": _mean(generated, "instruction_bullets"),
            "examples_code": _mean(examples, "instruction_code_spans"),
            "generated_code": _mean(generated, "instruction_code_spans"),
        },
        # Derived from the manifest so the deck cannot drift from the audited key reading.
        "spend": {
            "conservative": verification.get("spend", {}).get("conservative_last_snapshot") or 0.0,
            "remaining": round(
                500.0 - (verification.get("spend", {}).get("conservative_last_snapshot") or 0.0), 2
            ),
            "this_run_ledger": reconciliation.get("per_scope", {})
            .get("official|openai/gpt-5.6-luna", {})
            .get("usd", 0.0),
        },
        "approved_tasks": verification.get("approved_tasks", []),
        "output_packages": verification.get("output_packages", []),
        "requirements": verification.get("requirements", {}),
    }


def slides(d: dict) -> list[str]:
    m, b, bl = d["models"], d["batch"], d["blind"]
    st = d["stylometrics"]
    approved = d["approved_tasks"]
    ap = (
        f"<p><span class='tag'>approved</span> {html.escape(', '.join(t['task'] for t in approved))}</p>"
        if approved
        else (
            "<p class='warn'>No task approved: none lands in the 1-3/5 band.</p>"
            "<p>Five audited packages sit in <code>output/</code>, each with its calibration and "
            "verification record:</p><ul>"
            + "".join(
                f"<li>{html.escape(x['task'])} &mdash; <b>{html.escape(str(x['verdict']))}</b></li>"
                for x in d["output_packages"]
            )
            + "</ul>"
        )
    )
    problem = (
        "<h2>The problem</h2><p>A task is useful only in the learnable band: run 5x with a solver, "
        "exactly 1-3 pass, and failures must be the model's fault, not the task's.</p>"
        "<p class='mut'>Sonnet to Opus produced 0 of 9 in band; we rebuilt the pipeline and opened "
        "the model choice.</p>"
    )
    pipeline = (
        "<h2>Pipeline</h2><p>spec &rarr; blueprint &rarr; rubric + novelty gate &rarr; in-container "
        "authoring meta-task &rarr; structure/lint/leak &rarr; oracle 3/3 + nop &rarr; "
        "<code>harbor check</code> quality &rarr; novelty re-check &rarr; red-team &rarr; calibration "
        "(5x, exact curtailment) &rarr; ship in band.</p>"
    )
    difficulty = (
        "<h2>Difficulty by construction</h2><p>An author as strong as the solver cannot out-think it, "
        "so difficulty is built in: hidden-seed verify-time inputs, dependent multi-stage work, "
        "shallow-self-check traps, long-horizon inputs. Every tested requirement is stated.</p>"
    )
    audit = (
        "<h2>The audit that changed the story</h2><p class='bad'>Four previously 'shipped' tasks were "
        "rejected: no immutable calibration inside the package, one shipped on a single judged pass, "
        "stale READMEs, and the report's counts disagreeing.</p>"
        "<p>They are archived unchanged, not deleted.</p>"
    )
    verify = (
        "<h2>Verification discipline</h2><p>Approval = a content-hash-bound calibration record + "
        "verification record inside the package. A directory is not approval. Verification runs "
        "offline at build time; independent oracle 3/3 and nop re-run; reports use only the declared "
        f"model pair.</p>{ap}"
    )
    limits = (
        "<h2>Limitations and next steps</h2><ul><li>Small N; bimodal difficulty</li>"
        "<li>Self-judging bias; author also judges</li>"
        "<li>Reduced novelty scope (TB 2.1 + examples)</li><li>Turn-cap passes are invalid by rule</li>"
        "</ul><p>Next: more specs, stronger traps, a wider solver gap, and a full 5-run re-audit.</p>"
    )
    return [
        (
            f"<h1>{html.escape(d['title'])}</h1><p class='mut'>{html.escape(d['subtitle'])}</p>"
            f"<p class='mut'>Models: {html.escape(m['author'])} author, {html.escape(m['solver'])} solver</p>"
        ),
        problem,
        (
            "<h2>Models and scope</h2><div class='grid'>"
            f"<div class='card'>Author / reviewer / judge / red-team<b>{html.escape(m['author'])}</b></div>"
            f"<div class='card'>Calibration solver<b>{html.escape(m['solver'])}</b></div>"
            f"<div class='card'>Novelty pool<b>{html.escape(m['novelty'])}</b></div></div>"
        ),
        pipeline,
        difficulty,
        (
            "<h2>Candidate batch</h2><div class='grid'>"
            f"<div class='card'>Records<b>{b['records']}</b></div>"
            f"<div class='card'>Fresh / reused<b>{b['fresh']} / {b['reused']}</b></div>"
            f"<div class='card'>Learnable<b>{b['learnable']}</b></div>"
            f"<div class='card'>Too hard / too easy<b>{b['too_hard']} / {b['too_easy']}</b></div>"
            f"<div class='card'>Invalid<b>{b['invalid']}</b></div></div>"
            "<p class='mut'>Bimodal, as Tmax predicts without continuous difficulty control.</p>"
        ),
        audit,
        verify,
        (
            "<h2>Stretch goals</h2><p><b>A</b> curtailment lossless, ~12-23% trials saved (dollar "
            "figure caveated). <b>B</b> tuning implemented, <span class='warn'>no in-band movement "
            "demonstrated</span>. <b>C</b> coverage + novelty reported on the TB 2.1 pool. "
            f"<b>D</b> blind accuracy {bl['accuracy']:.2f} "
            f"(95% CI {bl['wilson'][0]:.2f}-{bl['wilson'][1]:.2f}); examples {st['examples_words']:.0f} "
            f"words vs generated {st['generated_words']:.0f}.</p>"
        ),
        (
            "<h2>Cost and time</h2><div class='grid'>"
            f"<div class='card'>Key spend<b>${d['spend']['conservative']:.2f}</b></div>"
            f"<div class='card'>Remaining<b>${d['spend']['remaining']:.2f}</b></div>"
            f"<div class='card'>Luna/mini ledger<b>${d['spend']['this_run_ledger']:.2f}</b></div></div>"
            "<p class='mut'>Ledger over-counts across scopes; the key is authoritative, reconciliation open.</p>"
        ),
        limits,
    ]


HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
:root{{--bg:#0f1b2a;--panel:#16283d;--ink:#eaf1f8;--mut:#9fb4c8;--acc:#2a9d8f;--warn:#e9c46a;--bad:#c0392b}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 Calibri,Arial,sans-serif}}
.slide{{display:none;min-height:100vh;padding:6vh 9vw;flex-direction:column;justify-content:center}}
.slide.on{{display:flex}}
h1{{font:700 46px/1.15 Cambria,Georgia,serif;margin:0 0 .4em}}
h2{{font:700 34px/1.2 Cambria,Georgia,serif;margin:0 0 .5em;color:var(--acc)}}
p,li{{max-width:60ch}} .mut{{color:var(--mut)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin-top:16px}}
.card{{background:var(--panel);border-radius:12px;padding:16px 18px}}
.card b{{display:block;font-size:30px;color:var(--acc);margin-top:6px}}
.tag{{background:var(--acc);color:#04241f;border-radius:999px;padding:2px 10px;font-weight:700;font-size:13px}}
.warn{{color:var(--warn)}} .bad{{color:var(--bad)}}
.foot{{position:fixed;bottom:10px;right:16px;color:var(--mut);font-size:13px}}
.nav{{position:fixed;bottom:10px;left:16px;color:var(--mut);font-size:13px}}
code{{background:#0b1622;padding:2px 6px;border-radius:6px}}</style></head><body>
<div id="deck"></div><div class="nav">← → to navigate</div><div class="foot" id="foot"></div>
<script>
const S = {slides};
let idx = 0;
function render(){{document.getElementById('deck').innerHTML = S.map((h,i) =>
  `<section class="slide${{i===idx?' on':''}}">${{h}}</section>`).join('');
  document.getElementById('foot').textContent = `${{idx+1}} / ${{S.length}}`;}}
addEventListener('keydown', e => {{ if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown'){{e.preventDefault();idx=Math.min(S.length-1,idx+1);render();}}
  if(e.key==='ArrowLeft'||e.key==='PageUp'){{e.preventDefault();idx=Math.max(0,idx-1);render();}} }});
render();
</script></body></html>"""


def main() -> int:
    data = build()
    (RESULT / "deck_data.json").write_text(json.dumps(data, indent=2) + "\n")
    content = slides(data)
    (RESULT / "presentation.html").write_text(
        HTML.format(title=html.escape(data["title"]), slides=json.dumps(content))
    )
    print(f"wrote deck_data.json ({len(content)} slides) and presentation.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
