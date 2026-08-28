"""A single agent that finds attestations for claims/conjectures via the
plain Anthropic SDK tool-use loop (design doc §5 principle 3: the agent's
entire world is read graph -> call a tool -> write back; no agent-to-agent
messaging, no shared transcript, no framework beyond the SDK itself).

NOT smoke-tested against the live API as part of this build — no
ANTHROPIC_API_KEY was available. Run once against a real key before
trusting it; the tool-dispatch logic below (`_dispatch`, the two tools
themselves) is covered by `tests/test_tools.py` without needing the API.
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

from ..graph import Graph
from ..sources.base import Source
from ..tools.find_attestations import DESCRIPTION as FIND_ATTESTATIONS_DESCRIPTION
from ..tools.find_attestations import NAME as FIND_ATTESTATIONS_NAME
from ..tools.find_attestations import FindAttestationsInput, find_attestations
from ..tools.propose_conjecture import DESCRIPTION as PROPOSE_CONJECTURE_DESCRIPTION
from ..tools.propose_conjecture import NAME as PROPOSE_CONJECTURE_NAME
from ..tools.propose_conjecture import ProposeConjectureInput, propose_conjecture

DEFAULT_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = (
    "You are an attestation worker in MEEP, an evidence graph for textual "
    "research. You have exactly two tools, both of which write to the graph "
    "through its own enforced rules — you cannot write structure any other "
    "way, and a call that violates a rule is refused and reported back to "
    "you, not silently dropped. find_attestations searches the corpus for a "
    "claim or conjecture and records matching passages as evidence. "
    "propose_conjecture proposes something the sources don't state outright, "
    "but only together with a query that would test it — a conjecture "
    "proposed without one is refused. Call tools; do not narrate progress "
    "in text. Stop once you've made reasonable progress or run out of "
    "queries worth trying."
)

TOOLS = [
    {
        "name": FIND_ATTESTATIONS_NAME,
        "description": FIND_ATTESTATIONS_DESCRIPTION,
        "input_schema": FindAttestationsInput.model_json_schema(),
    },
    {
        "name": PROPOSE_CONJECTURE_NAME,
        "description": PROPOSE_CONJECTURE_DESCRIPTION,
        "input_schema": ProposeConjectureInput.model_json_schema(),
    },
]


class AttestationWorker:
    def __init__(
        self,
        graph: Graph,
        source: Source,
        *,
        authored_by: str,
        model: str = DEFAULT_MODEL,
        client: "anthropic.Anthropic | None" = None,
    ) -> None:
        self.graph = graph
        self.source = source
        self.authored_by = authored_by
        self.model = model
        self.client = client or anthropic.Anthropic()

    def run(self, instructions: str, *, max_turns: int = 6) -> list[dict[str, Any]]:
        """Runs a tool-use loop against `instructions`. Returns the list of
        tool calls made (name, args, and either the result or the refusal),
        in order — this is the worker's own audit trail of its turn."""
        messages: list[dict] = [{"role": "user", "content": instructions}]
        log: list[dict[str, Any]] = []

        for _ in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                is_error, result = self._dispatch(block.name, block.input)
                log.append({"tool": block.name, "args": block.input, "result": result, "is_error": is_error})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                    "is_error": is_error,
                })
            messages.append({"role": "user", "content": tool_results})

        return log

    def _dispatch(self, name: str, raw_args: dict) -> tuple[bool, Any]:
        """Returns (is_error, result). A MeepError (a refused write) is
        reported back to the model as a tool error, not raised — the worker
        should see refusals and adjust, the same way the audit log does."""
        try:
            if name == FIND_ATTESTATIONS_NAME:
                args = FindAttestationsInput.model_validate(raw_args)
                return False, find_attestations(
                    self.graph, self.source, args, authored_by=self.authored_by
                )
            if name == PROPOSE_CONJECTURE_NAME:
                args = ProposeConjectureInput.model_validate(raw_args)
                return False, propose_conjecture(self.graph, args, authored_by=self.authored_by)
            return True, f"unknown tool: {name}"
        except Exception as e:  # noqa: BLE001 — deliberately broad: report to the model, don't crash the loop
            return True, f"{type(e).__name__}: {e}"
