"""Manual live smoke test for the OpenRouter transport.

Never imported by pytest, never run automatically — same discipline COHORT
already established for the (now-replaced) Anthropic worker: "not
smoke-tested against the live API... run once against a real key before
trusting it." This is that run, for real, for the first time in this
project's history.

Usage:
    .venv/bin/python scripts/smoke_openrouter.py

Requires OPENROUTER_API_KEY and OPENROUTER_MODEL — either exported into the
shell, or set in a local `.env` file (see .env.example).
"""
from __future__ import annotations

import json
import sys
import time

from cohort.agents.openrouter import OpenRouterError, complete, load_openrouter_config


def main() -> None:
    try:
        api_key, model = load_openrouter_config()
    except OpenRouterError as e:
        print(f"config error: {e}", file=sys.stderr)
        sys.exit(1)

    messages = [
        {"role": "user", "content": "Reply with exactly one word: pong."},
    ]

    started = time.monotonic()
    try:
        response = complete(model, messages, tools=[], api_key=api_key)
    except OpenRouterError as e:
        print(f"request failed ({e.cause}, status={e.status}): {e}", file=sys.stderr)
        sys.exit(1)
    latency_ms = int((time.monotonic() - started) * 1000)

    print(json.dumps({
        "model": response.model,
        "reply": response.choices[0].message.content,
        "finish_reason": response.choices[0].finish_reason,
        "latency_ms": latency_ms,
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "cost_usd": response.usage.cost,
    }, indent=2))


if __name__ == "__main__":
    main()
