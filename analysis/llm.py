"""Minimal chat client for direct (non-agent) model calls, with cost accounting.

Used for blueprints, reviews and judges. Agent runs (authoring, calibration,
red-team) go through Harbor instead. The model defaults to config.MODEL, which
is Sonnet 4.6 in official mode and DEV_MODEL in dev mode.
"""

import json
import re
import time
from dataclasses import dataclass

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from analysis.openrouter import Price
from evaluator.harbor_runner import load_prices
from generator.config import MODEL, OPENROUTER_API_BASE, OPENROUTER_API_KEY

RETRIES = 3


@dataclass(frozen=True)
class Reply:
    text: str
    model: str
    n_input_tokens: int
    n_cache_tokens: int
    n_output_tokens: int
    cost_usd: float
    seconds: float


def _client() -> OpenAI:
    return OpenAI(base_url=OPENROUTER_API_BASE, api_key=OPENROUTER_API_KEY)


def chat(
    prompt: str,
    system: str = "",
    model: str = MODEL,
    max_tokens: int = 8000,
    temperature: float = 0.7,
    prices: dict[str, Price] | None = None,
) -> Reply:
    """One chat completion, retried on transient API errors."""
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    started = time.monotonic()
    for attempt in range(RETRIES):
        try:
            response = _client().chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens, temperature=temperature
            )
            break
        except (APIConnectionError, RateLimitError) as e:
            last = e
        except APIStatusError as e:
            if e.status_code < 500:
                raise
            last = e
        time.sleep(2 * (attempt + 1))
    else:
        raise last  # type: ignore[possibly-undefined]
    usage = response.usage
    n_in = usage.prompt_tokens if usage else 0
    n_out = usage.completion_tokens if usage else 0
    details = getattr(usage, "prompt_tokens_details", None) if usage else None
    n_cache = (getattr(details, "cached_tokens", 0) or 0) if details else 0
    prices = prices if prices is not None else load_prices()
    price = prices.get(model)
    cost = price.cost(n_in, n_cache, n_out) if price else 0.0
    return Reply(
        text=response.choices[0].message.content or "",
        model=model,
        n_input_tokens=n_in,
        n_cache_tokens=n_cache,
        n_output_tokens=n_out,
        cost_usd=cost,
        seconds=time.monotonic() - started,
    )


def extract_json(text: str) -> dict:
    """Parse the first JSON object in a reply (bare, or inside a ```json fence)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text[text.find("{") : text.rfind("}") + 1]
    if not candidate:
        raise ValueError(f"no JSON object in reply: {text[:200]!r}")
    return json.loads(candidate)
