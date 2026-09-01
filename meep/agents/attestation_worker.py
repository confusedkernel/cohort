"""A single agent that finds attestations for claims/conjectures via an
OpenRouter tool-use loop (design doc §5 principle 3: the agent's entire
world is read graph -> call a tool -> write back; no agent-to-agent
messaging, no shared transcript, no framework beyond the transport itself).

Replaces the Anthropic SDK entirely (ROADMAP.md "Scope revision", OpenRouter
workstream) — see `meep/agents/openrouter.py` for the transport and why it's
stdlib-only rather than a client library.
"""
from __future__ import annotations

import json
import time
from typing import Any

from ..graph import Graph
from ..schemas import AgentProfile, NodeType
from ..sources.base import Source
from ..tools.find_attestations import DESCRIPTION as FIND_ATTESTATIONS_DESCRIPTION
from ..tools.find_attestations import NAME as FIND_ATTESTATIONS_NAME
from ..tools.find_attestations import FindAttestationsInput, find_attestations
from ..tools.propose_conjecture import DESCRIPTION as PROPOSE_CONJECTURE_DESCRIPTION
from ..tools.propose_conjecture import NAME as PROPOSE_CONJECTURE_NAME
from ..tools.propose_conjecture import ProposeConjectureInput, propose_conjecture
from .openrouter import complete, default_transport, load_openrouter_config

#: bump whenever SYSTEM_PROMPT or TOOLS changes shape, so logged model_call
#: events can be grouped by which prompt/tool contract actually produced them.
PROMPT_VERSION = "attestation_worker/v2-openrouter"

SYSTEM_PROMPT = (
    "You are an attestation worker in MEEP, an evidence graph for textual "
    "research. You have exactly two tools, both of which write to the graph "
    "through its own enforced rules — you cannot write structure any other "
    "way, and a call that violates a rule is refused and reported back to "
    "you, not silently dropped. find_attestations searches the corpus for a "
    "claim or conjecture and records matching passages as evidence. "
    "propose_conjecture proposes something the sources don't state outright, "
    "but requires a full dossier (derivation, corpus boundary, selection "
    "risks, alternative explanations), a prior-art query that is actually "
    "run against the corpus first, and a query that would confirm or "
    "refute the conjecture going forward — a conjecture proposed without "
    "the prospective query is refused. Call tools; do not narrate progress "
    "in text. Stop once you've made reasonable progress or run out of "
    "queries worth trying."
)


def _rejected_context(graph: Graph) -> str:
    """A summary of already-rejected claims/conjectures and why, so the
    worker doesn't repropose them.

    `witness`/`passage` don't need this: their rejection is already blocked
    mechanically at the write boundary via `canonical_ref` identity
    (`PersistentRejection`). `claim`/`conjecture` have no content-derived
    identity to block on — principle 5 forbids hashing agent-produced text
    into identity — so a rejected conjecture, reworded, would sail through
    a fresh `propose_conjecture` call unblocked. This is the mitigation:
    make the rejection visible to the model's own reasoning instead of
    faking an identity key for content the design deliberately declines to
    hash.
    """
    rejected = [
        n for t in (NodeType.CLAIM, NodeType.CONJECTURE) for n in graph.rejected(node_type=t)
    ]
    if not rejected:
        return ""
    lines = ["Already rejected by the researcher — do not repropose these or close variants of them:"]
    for n in rejected:
        text = n.payload.get("text", n.id)
        lines.append(f"- [{n.type}] {text!r} — reason: {n.rejected_reason or '(no reason recorded)'}")
    return "\n".join(lines)


def _profile_context(profile: AgentProfile | None) -> str:
    """Declared research commitments, not a cosmetic role prompt — distinct
    corpus/method scope per agent is what "viewpoint formation without
    persona theater" means (ROADMAP.md "Scope revision", agent-society
    axis): the diversity has to come from what the agent is actually scoped
    to look at, not from a personality prompt layered on an identical view
    of the whole corpus."""
    if profile is None:
        return ""
    parts = []
    if profile.corpus_scope:
        parts.append(f"corpus scope: {profile.corpus_scope}")
    if profile.method_label:
        parts.append(f"method: {profile.method_label}")
    if not parts:
        return ""
    return "Your declared research commitments — " + "; ".join(parts) + "."


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": FIND_ATTESTATIONS_NAME,
            "description": FIND_ATTESTATIONS_DESCRIPTION,
            "parameters": FindAttestationsInput.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": PROPOSE_CONJECTURE_NAME,
            "description": PROPOSE_CONJECTURE_DESCRIPTION,
            "parameters": ProposeConjectureInput.model_json_schema(),
        },
    },
]


class AttestationWorker:
    def __init__(
        self,
        graph: Graph,
        source: Source,
        *,
        authored_by: str,
        model: str | None = None,
        api_key: str | None = None,
        transport=None,
        profile: AgentProfile | None = None,
    ) -> None:
        if model is None or api_key is None:
            config_key, config_model = load_openrouter_config()
            api_key = api_key if api_key is not None else config_key
            model = model if model is not None else config_model
        self.graph = graph
        self.source = source
        self.authored_by = authored_by
        self.model = model
        self.api_key = api_key
        self.transport = transport or default_transport
        self.profile = profile

    def run(self, instructions: str, *, max_turns: int = 6) -> list[dict[str, Any]]:
        """Runs a tool-use loop against `instructions`. Returns the list of
        tool calls made (name, args, and either the result or the refusal),
        in order — this is the worker's own audit trail of its turn.

        Prepends, in order: the worker's own declared corpus/method scope
        if it has a `profile` (see `_profile_context`), then a summary of
        already-rejected claims/conjectures, if any (see
        `_rejected_context`) — this is what makes persistent rejection hold
        across a live loop for content that has no identity to block on
        mechanically."""
        parts = [
            p for p in (_profile_context(self.profile), _rejected_context(self.graph)) if p
        ]
        full_instructions = "\n\n".join([*parts, instructions]) if parts else instructions
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": full_instructions},
        ]
        log: list[dict[str, Any]] = []

        for _ in range(max_turns):
            started = time.monotonic()
            response = complete(
                self.model, messages, TOOLS, api_key=self.api_key, transport=self.transport,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            call_event = self.graph.log_model_call(
                authored_by=self.authored_by, model=response.model, provider="openrouter",
                prompt_version=PROMPT_VERSION, latency_ms=latency_ms,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                cost_usd=response.usage.cost,
            )
            choice = response.choices[0]
            messages.append({
                "role": "assistant",
                "content": choice.message.content,
                "tool_calls": [tc.model_dump() for tc in (choice.message.tool_calls or [])],
            })

            if choice.finish_reason != "tool_calls":
                break

            for tc in choice.message.tool_calls or []:
                args = json.loads(tc.function.arguments)
                is_error, result = self._dispatch(tc.function.name, args, call_event.seq)
                log.append({"tool": tc.function.name, "args": args, "result": result, "is_error": is_error})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps({"is_error": is_error, "result": result}, default=str),
                })

        return log

    def _dispatch(self, name: str, args: dict, model_call_id: int | None = None) -> tuple[bool, Any]:
        """Returns (is_error, result). A MeepError (a refused write) is
        reported back to the model as a tool error, not raised — the worker
        should see refusals and adjust, the same way the audit log does."""
        try:
            if name == FIND_ATTESTATIONS_NAME:
                parsed = FindAttestationsInput.model_validate(args)
                return False, find_attestations(
                    self.graph, self.source, parsed, authored_by=self.authored_by,
                    model_call_id=model_call_id,
                )
            if name == PROPOSE_CONJECTURE_NAME:
                parsed = ProposeConjectureInput.model_validate(args)
                return False, propose_conjecture(
                    self.graph, self.source, parsed, authored_by=self.authored_by,
                    model_call_id=model_call_id,
                )
            return True, f"unknown tool: {name}"
        except Exception as e:  # noqa: BLE001 — deliberately broad: report to the model, don't crash the loop
            return True, f"{type(e).__name__}: {e}"
