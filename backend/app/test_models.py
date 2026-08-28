from app.models import (
    AgentDecision,
    AgentName,
    DebateMessage,
    MessageType,
    Severity,
    Verdict,
)


decision = AgentDecision(
    agent=AgentName.MELCHIOR,
    verdict=Verdict.APPROVE,
    confidence=0.92,
    severity=Severity.INFO,
    summary="The proposed approach is logically sound.",
    concerns=[
        "Could benefit from additional testing."
    ],
    recommendations=[
        "Add edge-case tests."
    ]
)

print(decision)

message = DebateMessage(
    sender=AgentName.BALTHASAR,
    message_type=MessageType.CHALLENGE,
    content="The proposed approach introduces a security risk.",
    target=AgentName.MELCHIOR,
    round_number=1
)

print(message)