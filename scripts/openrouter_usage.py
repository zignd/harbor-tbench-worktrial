"""Show spend, limit and remaining credit for the OpenRouter key in use.

Reads OPENROUTER_API_KEY / OPENROUTER_API_BASE from the environment (load
them with `uv run --env-file .env`, or just run `make usage`). Uses OpenRouter's
per-key endpoint (GET /api/v1/key); the account-wide /credits endpoint needs a
management key, which we don't have.

Usage:
    python -m scripts.openrouter_usage          # human-readable summary
    python -m scripts.openrouter_usage --json   # raw key info, for scripts
"""

import json
import os
import sys
import urllib.error
from datetime import UTC, datetime

from analysis.openrouter import fetch_key_info


def _usd(value: float | None) -> str:
    return "unlimited" if value is None else f"${value:,.4f}"


def summarize(info: dict) -> str:
    limit = info.get("limit")
    usage = info.get("usage") or 0.0
    remaining = info.get("limit_remaining")
    used_pct = f" ({usage / limit:.2%} of limit)" if limit else ""

    lines = [
        f"limit      {_usd(limit)}",
        f"used       {_usd(usage)}{used_pct}",
        f"remaining  {_usd(remaining)}",
    ]
    if limit is not None and remaining is not None:
        # OpenRouter updates `usage` and `limit_remaining` with lag, and not in
        # sync; report both views and read again a minute after a run settles.
        lines.append(f"spent*     {_usd(limit - remaining)}  (* = limit - remaining)")
    lines += [
        f"today      {_usd(info.get('usage_daily'))}",
        f"this week  {_usd(info.get('usage_weekly'))}",
        f"this month {_usd(info.get('usage_monthly'))}",
    ]

    expires_at = info.get("expires_at")
    if expires_at:
        expiry = datetime.fromisoformat(expires_at)
        days_left = (expiry - datetime.now(UTC)).days
        lines.append(f"expires    {expiry:%Y-%m-%d %H:%M} UTC ({days_left} days left)")

    return "\n".join(lines)


def main() -> int:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is not set (copy .env.example to .env).", file=sys.stderr)
        return 1

    try:
        info = fetch_key_info()
    except urllib.error.HTTPError as e:
        print(f"OpenRouter returned HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return 1

    if "--json" in sys.argv[1:]:
        info.pop("label", None)  # masked key prefix; not useful downstream
        print(json.dumps(info, indent=2))
    else:
        print(summarize(info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
