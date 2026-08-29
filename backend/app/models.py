from enum import Enum

from pydantic import BaseModel, Field


class AgentName(str, Enum):
    MELCHIOR = "melchior"
    BALTHASAR = "balthasar"
    CASPER = "casper"


class Verdict(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    CONDITIONAL = "conditional"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MessageType(str, Enum):
    INITIAL_POSITION = "initial_position"
    CHALLENGE = "challenge"
    RESPONSE = "response"
    REVISION = "revision"


class AgentProfile(BaseModel):
    name: AgentName
    role: str
    objective: str
    priorities: list[str]
    behavioral_rules: list[str]


class AgentDecision(BaseModel):
    agent: AgentName
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity
    summary: str
    arguments: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class DebateMessage(BaseModel):
    sender: AgentName
    message_type: MessageType
    content: str
    target: AgentName | None = None
    round_number: int = Field(ge=1)


class DebateContext(BaseModel):
    question: str
    current_decision: AgentDecision
    other_decisions: list[AgentDecision] = Field(default_factory=list)
    messages: list[DebateMessage] = Field(default_factory=list)
    round_number: int = Field(ge=1)


class DebateState(BaseModel):
    question: str
    decisions: list[AgentDecision] = Field(default_factory=list)
    messages: list[DebateMessage] = Field(default_factory=list)


class SynthesisResult(BaseModel):
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    synthesis: str
    key_agreements: list[str] = Field(default_factory=list)
    key_disagreements: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    recommendation: str