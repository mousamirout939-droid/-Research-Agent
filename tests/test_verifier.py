from __future__ import annotations

from agent.models import ClaimStatus, Draft, VerificationResult
from agent.verifier import Verifier


def test_verify_returns_verification_result(mock_llm, sample_sources):
    verifier = Verifier(mock_llm)
    draft = Draft(
        markdown="The technology has grown significantly in recent years [1]. "
                  "Concerns about scalability persist among analysts [2].",
        sources_used=[1, 2],
    )
    result = verifier.verify(draft, sample_sources)

    assert isinstance(result, VerificationResult)
    assert result.total >= 1
    assert 0.0 <= result.faithfulness_score <= 1.0


def test_faithfulness_score_is_one_when_no_claims():
    result = VerificationResult(claims=[])
    assert result.faithfulness_score == 1.0
    assert result.needs_revision is False


def test_needs_revision_true_when_any_claim_unsupported():
    from agent.models import ClaimCheck

    result = VerificationResult(claims=[
        ClaimCheck(claim="a", status=ClaimStatus.SUPPORTED),
        ClaimCheck(claim="b", status=ClaimStatus.UNSUPPORTED),
    ])
    assert result.needs_revision is True
    assert result.faithfulness_score == 0.5


def test_verifier_handles_invalid_status_gracefully(sample_sources):
    class WeirdStatusLLM:
        def complete(self, *a, **k):
            return "{}"

        def complete_json(self, *a, **k):
            return {
                "claims": [
                    {"claim": "X happened", "cited_sources": [1], "status": "totally_made_up_status",
                     "explanation": "n/a"}
                ],
                "revision_notes": "",
            }

    verifier = Verifier(WeirdStatusLLM())
    draft = Draft(markdown="X happened [1].", sources_used=[1])
    result = verifier.verify(draft, sample_sources)

    # Unknown status strings should degrade to UNCITED rather than crash.
    assert result.claims[0].status == ClaimStatus.UNCITED
