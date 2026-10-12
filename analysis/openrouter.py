"""OpenRouter account data: per-key spend and per-model prices (stdlib only).

Spend comes from GET /api/v1/key. Its `usage` and `limit_remaining` counters lag
and don't update together (docs/harbor-notes.md), so `Spend.spent` takes the
larger of the two views.
"""

import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_API_BASE = "https://openrouter.ai/api/v1"


def _get(path: str, api_key: str = "", api_base: str = "") -> dict:
    api_base = api_base or os.environ.get("OPENROUTER_API_BASE", DEFAULT_API_BASE)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    request = urllib.request.Request(f"{api_base.rstrip('/')}/{path}", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_key_info(api_key: str = "", api_base: str = "") -> dict:
    """Raw per-key info (limit, usage, limit_remaining, expires_at, ...)."""
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    return _get("key", api_key, api_base)["data"]


@dataclass(frozen=True)
class Spend:
    limit: float | None
    used: float
    remaining: float | None

    @property
    def spent(self) -> float:
        """Conservative spend: the larger of `usage` and `limit - limit_remaining`."""
        if self.limit is None or self.remaining is None:
            return self.used
        return max(self.used, self.limit - self.remaining)

    @classmethod
    def from_key_info(cls, info: dict) -> "Spend":
        return cls(
            limit=info.get("limit"),
            used=float(info.get("usage") or 0.0),
            remaining=info.get("limit_remaining"),
        )


def current_spend() -> Spend:
    return Spend.from_key_info(fetch_key_info())


@dataclass(frozen=True)
class Price:
    """USD per token."""

    prompt: float
    completion: float
    cache_read: float

    def cost(self, n_input: int, n_cache: int, n_output: int) -> float:
        uncached = max(n_input - n_cache, 0)
        return uncached * self.prompt + n_cache * self.cache_read + n_output * self.completion


def fetch_prices(cache_path: Path | None = None) -> dict[str, Price]:
    """Model id -> Price from GET /models (public). Cached to `cache_path` if given."""
    if cache_path and cache_path.exists():
        raw = json.loads(cache_path.read_text())
    else:
        raw = {m["id"]: m.get("pricing", {}) for m in _get("models")["data"]}
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(raw, indent=1, sort_keys=True))
    prices = {}
    for model_id, p in raw.items():
        prompt = float(p.get("prompt") or 0)
        prices[model_id] = Price(
            prompt=prompt,
            completion=float(p.get("completion") or 0),
            cache_read=float(p.get("input_cache_read") or prompt),
        )
    return prices
