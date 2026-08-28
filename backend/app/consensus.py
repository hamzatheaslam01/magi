from collections import Counter

from app.models import AgentDecision, ConsensusResult, Verdict


class ConsensusEngine:

    def evaluate(
        self,
        decisions: list[AgentDecision]
    ) -> ConsensusResult:

        votes = {
            decision.agent: decision.verdict
            for decision in decisions
        }

        counts = Counter(votes.values())

        if counts[Verdict.REJECT] >= 2:
            final_verdict = Verdict.REJECT

        elif counts[Verdict.APPROVE] >= 2:
            final_verdict = Verdict.APPROVE

        elif counts[Verdict.CONDITIONAL] >= 2:
            final_verdict = Verdict.CONDITIONAL

        else:
            final_verdict = Verdict.ABSTAIN

        confidence = self._calculate_confidence(decisions)

        explanation = self._build_explanation(
            final_verdict,
            counts
        )

        return ConsensusResult(
            verdict=final_verdict,
            confidence=confidence,
            votes=votes,
            explanation=explanation
        )

    def _calculate_confidence(
        self,
        decisions: list[AgentDecision]
    ) -> float:

        if not decisions:
            return 0.0

        total = sum(
            decision.confidence
            for decision in decisions
        )

        return total / len(decisions)

    def _build_explanation(
        self,
        verdict: Verdict,
        counts: Counter
    ) -> str:

        return (
            f"MAGI reached a {verdict.value.upper()} "
            f"consensus based on agent voting."
        )