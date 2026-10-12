# Research papers

Papers behind `docs/plan.md`. Each has the arXiv PDF and a plain-text conversion (`pdftotext -layout`) for grepping and reading. All were read in full on 2026-10-12.

| arXiv | Title | Why it's here |
|---|---|---|
| [2604.28093](https://arxiv.org/abs/2604.28093) | What Makes a Good Terminal-Agent Benchmark Task (Bercovich) | Task-quality rules from a Terminal Bench reviewer |
| [2604.17596](https://arxiv.org/abs/2604.17596) | Terminal Wrench: 331 Reward-Hackable Environments and 3,632 Exploit Trajectories | Hackability rates, exploit taxonomy, hack elicitation, monitor AUC |
| [2608.22103](https://arxiv.org/abs/2608.22103) | Hack-Verifiable Terminal Bench | Honeypot hack rates per model, warning-prompt effects, TB 2.1 difficulty classes |
| [2606.22883](https://arxiv.org/abs/2606.22883) | CLI-Universe: Towards Verifiable Task Synthesis Engine for Terminal Agents | 4-axis taxonomy, blueprints, role-separated test/solution agents, fail-to-pass, 9-mode failure taxonomy |
| [2607.27929](https://arxiv.org/abs/2607.27929) | Meta-Task: Turning Terminal Task Synthesis into a Terminal Task | Authoring as a Harbor task, reusable meta-task template, "Hard" spec, trajectory judge prompt |
| [2606.23321](https://arxiv.org/abs/2606.23321) | Tmax: A Simple Recipe for Terminal Agents | 9 sampling axes, verifier kinds as difficulty knobs, balance score, decontamination |
| [2604.25727](https://arxiv.org/abs/2604.25727) | Toward Scalable Terminal Task Synthesis via Skill Graphs (SkillSynth) | Planner/constructor split, alignment-check stats, repair limits, inverse-frequency sampling, base rates |
| [2502.12272](https://arxiv.org/abs/2502.12272) | LILO: Learning to Reason at the Frontier of Learnability (Foster et al.) | Why p(1-p) matters, aleatoric-variance caveat, LLM-predicted learnability |

Regenerate the text files with:

```bash
for f in docs/research/*.pdf; do pdftotext -layout "$f" "${f%.pdf}.txt"; done
```
