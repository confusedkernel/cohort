"""Closed-vocabulary and dating validation (design doc §6)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from cohort.schemas import Dating, DatingRoute, Event, Node, WitnessPayload


def test_dating_rejects_a_basis_that_is_just_a_label():
    with pytest.raises(ValidationError):
        Dating(confidence=DatingRoute.UNKNOWN, basis="unknown")


def test_dating_accepts_a_stated_basis():
    d = Dating(
        confidence=DatingRoute.SOURCE_LABEL,
        basis="the colophon names this a Northern Song printing",
    )
    assert d.value is None
    assert d.confidence == DatingRoute.SOURCE_LABEL


def test_witness_payload_requires_dating():
    with pytest.raises(ValidationError):
        WitnessPayload(canonical_ref="T01n0001")  # type: ignore[call-arg]


def test_event_rejects_an_unknown_event_type():
    with pytest.raises(ValidationError):
        Event(seq=0, event="delete_everything", authored_by="agent:x")


def test_node_rejects_an_unlisted_node_type():
    with pytest.raises(ValidationError):
        Node(id="x", type="heresy", status="proposed", payload={}, created_seq=0, updated_seq=0)  # type: ignore[arg-type]


def test_node_rejects_an_unlisted_status():
    with pytest.raises(ValidationError):
        Node(id="x", type="witness", status="on_fire", payload={}, created_seq=0, updated_seq=0)  # type: ignore[arg-type]
