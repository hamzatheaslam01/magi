from collections import Counter

from app.models import AgentDecision, ConsensusResult, Verdict


class ConsensusEngine:
    """
    Determines the panel verdict and calculates a consensus-strength score.

    The confidence score is NOT an average of the agents' self-reported
    confidence. It measures how strongly the panel converged on the final
    verdict, taking both agreement and the agents' confidence into account.
    """

    def evaluate(
        self,
        decisions: list[AgentDecision],
    ) -> ConsensusResult:

        if not decisions:
            return ConsensusResult(
                verdict=Verdict.ABSTAIN,
                confidence=0.0,
                votes={},
                explanation="MAGI could not reach a consensus because no agent decisions were available.",
            )

        votes = {
            decision.agent: decision.verdict
            for decision in decisions
        }

        counts = Counter(votes.values())

        # Majority verdict.
        if counts[Verdict.REJECT] >= 2:
            final_verdict = Verdict.REJECT

        elif counts[Verdict.APPROVE] >= 2:
            final_verdict = Verdict.APPROVE

        elif counts[Verdict.CONDITIONAL] >= 2:
            final_verdict = Verdict.CONDITIONAL

        else:
            final_verdict = Verdict.ABSTAIN

        confidence = self._calculate_consensus_strength(
            decisions,
            final_verdict,
        )

        explanation = self._build_explanation(
            final_verdict,
            counts,
            confidence,
        )

        return ConsensusResult(
            verdict=final_verdict,
            confidence=confidence,
            votes=votes,
            explanation=explanation,
        )

    def _calculate_consensus_strength(
        self,
        decisions: list[AgentDecision],
        final_verdict: Verdict,
    ) -> float:
        """
        Calculate panel-level consensus strength.

        This deliberately does NOT average all agent confidence values.

        The score considers:

        1. Agreement:
           What fraction of agents reached the final verdict?

        2. Confidence of supporters:
           How confident are the agents who actually support the verdict?

        3. Opposition:
           Strong opposition reduces the score.

        With three agents:

        - 3/3 agreement produces strong consensus.
        - 2/3 agreement produces moderate consensus.
        - A highly confident dissenting agent pulls the score down.
        - Low-confidence agreement remains appropriately weak.
        """

        if not decisions or final_verdict == Verdict.ABSTAIN:
            return 0.0

        supporters = [
            decision
            for decision in decisions
            if decision.verdict == final_verdict
        ]

        opponents = [
            decision
            for decision in decisions
            if decision.verdict != final_verdict
        ]

        if not supporters:
            return 0.0

        total_agents = len(decisions)

        agreement_ratio = len(supporters) / total_agents

        supporter_confidence = (
            sum(decision.confidence for decision in supporters)
            / len(supporters)
        )

        if opponents:
            opposition_strength = (
                sum(decision.confidence for decision in opponents)
                / len(opponents)
            )
        else:
            opposition_strength = 0.0

        # Agreement is the foundation of consensus.
        #
        # Supporter confidence strengthens the score.
        #
        # Strong opposition reduces it.
        #
        # The formula intentionally rewards genuine unanimous convergence
        # without pretending that a model's confidence is objective truth.
        strength = (
            agreement_ratio
            * (
                0.65 * supporter_confidence
                + 0.35 * (1.0 - opposition_strength)
            )
        )

        # Unanimous agreement deserves a modest bonus because there is
        # no unresolved opposing position in the final panel.
        if len(opponents) == 0:
            strength += 0.10

        return round(
            max(0.0, min(1.0, strength)),
            2,
        )

    def _build_explanation(
        self,
        verdict: Verdict,
        counts: Counter,
        confidence: float,
    ) -> str:

        if verdict == Verdict.ABSTAIN:
            return (
                "MAGI could not establish a majority position. "
                "The panel remained divided."
            )

        supporters = counts[verdict]
        total = sum(counts.values())

        percentage = round((supporters / total) * 100)

        if supporters == total:
            return (
                f"All {total} agents converged on a "
                f"{verdict.value.upper()} position. "
                f"Consensus strength: {round(confidence * 100)}%."
            )

        return (
            f"{supporters} of {total} agents supported the "
            f"{verdict.value.upper()} position "
            f"({percentage}% of the panel). "
            f"Consensus strength: {round(confidence * 100)}%."
        )