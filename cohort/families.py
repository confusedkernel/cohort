"""Which model ids count as the same reader.

Two agents on one model are not two readers: they share training priors,
prompt-shaped convergence and failure modes, so their agreement is one
observation reported twice — the error `independent_support()` catches
between witnesses, committed one layer up between readers.

This lives below both callers because the rule is now enforced in two places
with different reach, and they must agree on what "same family" means:

- `cohort.agents.roster` refuses a *roster* whose agents overlap, when a run
  is assembled. It cannot see agents registered by a different run.
- `Graph.attest()` refuses the *write*, whoever assembled the writer. It
  cannot see a run that has not written yet.

Neither subsumes the other, so both exist.

**What "family" means here, and what it cannot mean.** OpenRouter ids are
`provider/model`, so the provider prefix is the family: `z-ai/glm-5.3` and
`z-ai/glm-5.3-flash` are one family, `deepseek/deepseek-v4-flash` is another.
This is a heuristic and is stated as one — it catches the ordinary case (a
roster filled from one provider) and cannot catch the same weights served
under two provider names. It is a floor on independence, not a proof of it,
and a passing check should never be read as one.
"""
from __future__ import annotations


def model_family(model: str) -> str:
    """The provider prefix of an OpenRouter model id, lowercased.

    A bare id with no `/` is its own family: nothing else can be inferred, and
    guessing would make the check look stronger than it is.
    """
    return model.split("/", 1)[0].strip().lower() if model else ""
