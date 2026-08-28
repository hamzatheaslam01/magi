from app.consensus import ConsensusEngine
from app.models import AgentDecision, AgentName, Severity, Verdict


decisions = [
    AgentDecision(
        agent=AgentName.MELCHIOR,
        verdict=Verdict.APPROVE,
        confidence=0.90,
        severity=Severity.INFO,
        summary="The proposal is logically sound."
    ),

    AgentDecision(
        agent=AgentName.BALTHASAR,
        verdict=Verdict.REJECT,
        confidence=0.95,
        severity=Severity.HIGH,
        summary="The proposal introduces security risks."
    ),

    AgentDecision(
        agent=AgentName.CASPER,
        verdict=Verdict.APPROVE,
        confidence=0.80,
        severity=Severity.INFO,
        summary="The proposal is practical."
    )
]


engine = ConsensusEngine()

result = engine.evaluate(decisions)

print(result)