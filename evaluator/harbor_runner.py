"""Run Harbor jobs and turn their job dirs into typed, classified trial results.

Layout and fields are documented in docs/harbor-notes.md. Outcome classes:

- pass / fail: the verifier ran; reward 1 or 0.
- invalid:     the run ended for a reason that is never a valid failure
               (agent/verifier timeout, context overflow, turn cap). The task
               needs attention; the trial doesn't count either way.
- infra:       transient infrastructure trouble (API, network, build, missing
               reward). Retried up to INFRA_RETRIES times, then excluded.
- fatal:       configuration errors (bad key, unknown model). Abort.
"""

import contextlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from analysis.openrouter import Price, fetch_prices
from evaluator.slots import machine_slots
from generator.config import ENV_FILE, ENV_SLOTS, JOBS_DIR, RUNS_DIR

INFRA_RETRIES = 2

FATAL_EXCEPTIONS = {
    "ApiKeyRejectedError",
    "AuthenticationError",
    "AgentAuthenticationError",
    "NotAuthenticatedError",
    "ModelNotFoundError",
    "ApiUsageLimitError",
}
INVALID_EXCEPTIONS = {
    "AgentTimeoutError",
    "VerifierTimeoutError",
    "ContextLengthExceededError",
    "ContextWindowExceededError",
    "OutputLengthExceededError",
    "OutputTokenExceededError",
}
# Anything else with an exception (Api*, network, sandbox build, reward file) is infra.


class FatalRunError(RuntimeError):
    pass


def _seconds(span: dict | None) -> float:
    if not span or not span.get("started_at") or not span.get("finished_at"):
        return 0.0
    start = datetime.fromisoformat(span["started_at"])
    end = datetime.fromisoformat(span["finished_at"])
    return (end - start).total_seconds()


@dataclass(frozen=True)
class TrialResult:
    trial_name: str
    task_name: str
    trial_dir: Path
    agent: str
    model: str | None
    reward: float | None
    exception: str | None
    exception_message: str
    cost_usd: float | None  # Harbor's estimate; None when LiteLLM can't price the model
    n_input_tokens: int
    n_cache_tokens: int
    n_output_tokens: int
    n_episodes: int | None
    max_turns: int | None
    seconds: float

    @property
    def outcome(self) -> str:
        if self.exception in FATAL_EXCEPTIONS:
            return "fatal"
        if self.exception in INVALID_EXCEPTIONS:
            return "invalid"
        if self.exception:
            return "infra"
        if self.reward is None:
            return "infra"
        if self.max_turns and self.n_episodes and self.n_episodes >= self.max_turns:
            return "invalid"  # ran out of turns: never a valid failure
        if self.reward >= 1.0:
            return "pass"
        return "fail"

    @property
    def trajectory_path(self) -> Path:
        return self.trial_dir / "agent" / "trajectory.json"

    @property
    def artifacts_dir(self) -> Path:
        return self.trial_dir / "artifacts"

    def priced_cost(self, prices: dict[str, Price] | None = None) -> float:
        """Harbor's cost, or a token-based estimate from OpenRouter prices."""
        if self.cost_usd is not None:
            return self.cost_usd
        if not self.model or not (self.n_input_tokens or self.n_output_tokens):
            return 0.0
        prices = prices if prices is not None else load_prices()
        price = prices.get(self.model.removeprefix("openrouter/"))
        if price is None:
            return 0.0
        return price.cost(self.n_input_tokens, self.n_cache_tokens, self.n_output_tokens)


def load_prices() -> dict[str, Price]:
    return fetch_prices(Path(RUNS_DIR) / "prices.json")


def parse_trial(trial_dir: Path) -> TrialResult:
    trial_dir = Path(trial_dir)
    result = json.loads((trial_dir / "result.json").read_text())
    agent_cfg = result.get("config", {}).get("agent", {})
    agent_result = result.get("agent_result") or {}
    metadata = agent_result.get("metadata") or {}
    exc = result.get("exception_info") or {}
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    kwargs = agent_cfg.get("kwargs") or {}
    if not kwargs and (trial_dir / "config.json").exists():
        kwargs = (
            json.loads((trial_dir / "config.json").read_text()).get("agent", {}).get("kwargs") or {}
        )
    max_turns = kwargs.get("max_turns")
    return TrialResult(
        trial_name=result["trial_name"],
        task_name=result.get("task_name", ""),
        trial_dir=trial_dir,
        agent=agent_cfg.get("name", ""),
        model=agent_cfg.get("model_name"),
        reward=rewards.get("reward"),
        exception=exc.get("exception_type"),
        exception_message=(exc.get("exception_message") or "")[:500],
        cost_usd=agent_result.get("cost_usd"),
        n_input_tokens=agent_result.get("n_input_tokens") or 0,
        n_cache_tokens=agent_result.get("n_cache_tokens") or 0,
        n_output_tokens=agent_result.get("n_output_tokens") or 0,
        n_episodes=metadata.get("n_episodes"),
        max_turns=int(max_turns) if max_turns is not None else None,
        seconds=_seconds(result),
    )


def parse_job(job_dir: Path) -> list[TrialResult]:
    """All finished trials in a job dir (trial dirs that have a result.json)."""
    return [
        parse_trial(d)
        for d in sorted(Path(job_dir).iterdir())
        if d.is_dir() and (d / "result.json").exists()
    ]


def _harbor_bin() -> str:
    local = Path(sys.executable).parent / "harbor"
    return str(local) if local.exists() else (shutil.which("harbor") or "harbor")


def run_job(
    task_dir: Path,
    agent: str,
    job_name: str,
    model: str | None = None,
    attempts: int = 1,
    concurrent: int = 1,
    agent_kwargs: dict | None = None,
    jobs_dir: Path | str = JOBS_DIR,
    extra_args: list[str] | None = None,
    limit_envs: bool = True,
) -> list[TrialResult]:
    """Run one `harbor run` job and return its parsed trials (raises on fatal errors).

    Holds `concurrent` of the machine-wide ENV_SLOTS environment slots while it runs, so
    the machine never exhausts Docker's network address pools (Opus calibration passes
    `limit_envs=False`: it has its own trial slots).

    The job dir is always fresh: Harbor *resumes* an existing job dir with the
    same config (keeping its finished trials), which would silently reuse stale
    results from an earlier run with the same name.
    """
    jobs_dir = Path(jobs_dir)
    if (jobs_dir / job_name).exists():
        shutil.rmtree(jobs_dir / job_name)
    cmd = [
        _harbor_bin(),
        "run",
        "-p",
        str(task_dir),
        "-a",
        agent,
        "-k",
        str(attempts),
        "-n",
        str(concurrent),
        "-o",
        str(jobs_dir),
        "--job-name",
        job_name,
        "-y",
        "-q",
    ]
    if model:
        cmd += ["-m", model]
    for key, value in (agent_kwargs or {}).items():
        cmd += ["--ak", f"{key}={value}"]
    if Path(ENV_FILE).exists() and not os.environ.get("OPENROUTER_API_KEY"):
        cmd += ["--env-file", ENV_FILE]
    cmd += extra_args or []
    slots = (
        machine_slots(concurrent, ENV_SLOTS, Path(JOBS_DIR) / ".env-slots")
        if limit_envs
        else contextlib.nullcontext()
    )
    with slots:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    job_dir = jobs_dir / job_name
    if not job_dir.exists():
        raise RuntimeError(f"harbor run produced no job dir: {proc.stderr[-1000:]}")
    trials = parse_job(job_dir)
    fatal = [t for t in trials if t.outcome == "fatal"]
    if fatal:
        raise FatalRunError(f"{fatal[0].exception}: {fatal[0].exception_message}")
    return trials


def run_with_retries(
    task_dir: Path,
    agent: str,
    job_name: str,
    attempts: int = 1,
    retries: int = INFRA_RETRIES,
    **kwargs,
) -> tuple[list[TrialResult], list[TrialResult]]:
    """Run `attempts` trials, re-running infra failures up to `retries` times.

    Returns (counted, excluded): counted trials are pass/fail/invalid; excluded
    are trials still failing on infrastructure after all retries.
    """
    counted: list[TrialResult] = []
    pending = attempts
    excluded: list[TrialResult] = []
    for round_ in range(retries + 1):
        name = job_name if round_ == 0 else f"{job_name}-retry{round_}"
        trials = run_job(task_dir, agent, name, attempts=pending, **kwargs)
        counted += [t for t in trials if t.outcome != "infra"]
        excluded = [t for t in trials if t.outcome == "infra"]
        pending = len(excluded) + max(pending - len(trials), 0)
        if pending == 0:
            break
    return counted, excluded
