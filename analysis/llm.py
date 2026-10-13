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
MAX_TOKENS_CAP = 32000


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
    """One chat completion, retried on transient API errors.

    Reasoning models (e.g. the dev model) can spend the whole token budget on
    hidden reasoning and return empty content with finish_reason "length"; in
    that case the call is repeated with a larger budget (up to MAX_TOKENS_CAP),
    and the cost of every attempt is counted.
    """
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    prices = prices if prices is not None else load_prices()
    price = prices.get(model)
    started = time.monotonic()
    totals = [0, 0, 0]  # input, cached, output
    budget = max_tokens
    while True:
        response = _create(messages, model, budget, temperature)
        usage = response.usage
        details = getattr(usage, "prompt_tokens_details", None) if usage else None
        totals[0] += usage.prompt_tokens if usage else 0
        totals[1] += (getattr(details, "cached_tokens", 0) or 0) if details else 0
        totals[2] += usage.completion_tokens if usage else 0
        choice = response.choices[0]
        text = choice.message.content or ""
        if text or choice.finish_reason != "length" or budget >= MAX_TOKENS_CAP:
            break
        budget = min(budget * 2, MAX_TOKENS_CAP)
    return Reply(
        text=text,
        model=model,
        n_input_tokens=totals[0],
        n_cache_tokens=totals[1],
        n_output_tokens=totals[2],
        cost_usd=price.cost(*totals) if price else 0.0,
        seconds=time.monotonic() - started,
    )


def _create(messages: list[dict], model: str, max_tokens: int, temperature: float):
    for attempt in range(RETRIES):
        try:
            return _client().chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens, temperature=temperature
            )
        except (APIConnectionError, RateLimitError) as e:
            last = e
        except APIStatusError as e:
            if e.status_code < 500:
                raise
            last = e
        time.sleep(2 * (attempt + 1))
    raise last  # type: ignore[possibly-undefined]


_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def extract_json(text: str) -> dict:
    """Parse the first JSON object in a reply (bare, or inside a ```json fence).

    Scans for the first `{` that starts a decodable object, so prose around it or a
    second object after it doesn't matter, and retries with trailing commas removed
    (both seen in Sonnet replies under load).
    """
    decoder = json.JSONDecoder()
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    for source in [*fenced, text]:
        start = source.find("{")
        while start != -1:
            for attempt in (source[start:], _TRAILING_COMMA.sub(r"\1", source[start:])):
                try:
                    obj, _ = decoder.raw_decode(attempt)
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    pass
            start = source.find("{", start + 1)
    raise ValueError(f"no JSON object in reply: {text[:200]!r}")
