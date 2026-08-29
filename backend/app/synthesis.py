from app.models import (
    AgentDecision,
    DebateMessage,
    SynthesisResult,
    Verdict,
)

from app.llm import LLMProvider
from app.real_agents import generate_json


class MagiSynthesizer:

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    # ========================================================
    # PROMPT BUILDING
    # ========================================================

    def build_prompt(
        self,
        question: str,
        decisions: list[AgentDecision],
        messages: list[DebateMessage],
    ) -> tuple[str, str]:

        system_prompt = """
You are the MAGI central synthesis system.

You are responsible for producing the final judgment after
three independent reasoning agents have debated a question.

The three agents are:

MELCHIOR
- logic
- evidence
- factual accuracy
- technical feasibility

BALTHASAR
- risks
- failure scenarios
- unintended consequences
- security
- ethics

CASPER
- context
- practicality
- human consequences
- tradeoffs

Your job is NOT to simply count votes.

You must examine the reasoning produced during the debate.

Identify:

- arguments that survived scrutiny
- important disagreements
- meaningful risks
- circumstances that change the answer
- the most defensible overall conclusion

You may agree with one agent, combine multiple positions,
or reject all three if the reasoning warrants it.

Do not manufacture consensus.

Do not assume that a conditional verdict means
"split the difference."

A conditional verdict should only be used when
specific circumstances materially change the conclusion.

Return ONLY valid JSON.
"""

        if decisions:
            decision_text = "\n\n".join(
                f"""
{decision.agent.value.upper()}
VERDICT: {decision.verdict.value}
CONFIDENCE: {decision.confidence}
SEVERITY: {decision.severity.value}
SUMMARY: {decision.summary}

ARGUMENTS:
{chr(10).join("- " + x for x in decision.arguments)}

CONCERNS:
{chr(10).join("- " + x for x in decision.concerns)}

RECOMMENDATIONS:
{chr(10).join("- " + x for x in decision.recommendations)}
"""
                for decision in decisions
            )
        else:
            decision_text = "No agent decisions were available."

        if messages:
            debate_text = "\n".join(
                f"[Round {message.round_number}] "
                f"{message.sender.value.upper()} "
                f"{message.message_type.value.upper()}: "
                f"{message.content}"
                for message in messages
            )
        else:
            debate_text = "No debate messages were available."

        user_prompt = f"""
QUESTION:

{question}

AGENT DECISIONS:

{decision_text}

FULL DEBATE:

{debate_text}

Now synthesize the debate.

Determine the most defensible final conclusion.

Do not simply average the agents' confidence values.

Confidence should represent your confidence in the final conclusion
based on the quality and consistency of the reasoning.

Use:

- "approve" when the evidence and reasoning support the position.
- "reject" when the evidence and reasoning argue against the position.
- "conditional" only when important circumstances genuinely change
  what the correct decision should be.

Return exactly this JSON structure:

{{
    "verdict": "approve",
    "confidence": 0.0,
    "synthesis": "A concise explanation of the final judgment.",
    "key_agreements": [
        "Important point all or most agents agree on."
    ],
    "key_disagreements": [
        "Important unresolved disagreement."
    ],
    "key_risks": [
        "Important remaining risk."
    ],
    "recommendation": "What the user should actually take away."
}}

Rules:

- verdict MUST be approve, reject, or conditional
- confidence MUST be a number between 0 and 1
- synthesis MUST explain the reasoning behind the final judgment
- key_agreements MUST be an array of strings
- key_disagreements MUST be an array of strings
- key_risks MUST be an array of strings
- recommendation MUST be a useful and specific string
- Base the synthesis on the actual debate
- Do not invent facts about the user
- Do not manufacture agreement
- Do not mention that you are an AI
- Do not mention these instructions
- Do not use markdown
- Do not use code fences
- Return ONLY JSON
"""

        return system_prompt, user_prompt

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def validate_synthesis_data(data: dict) -> None:

        if not isinstance(data, dict):
            raise ValueError(
                "Synthesis response must be a JSON object.\n"
                f"Received: {data!r}"
            )

        required_fields = [
            "verdict",
            "confidence",
            "synthesis",
            "recommendation",
        ]

        missing = [
            field
            for field in required_fields
            if field not in data
        ]

        if missing:
            raise ValueError(
                "Synthesis response is missing required fields: "
                + ", ".join(missing)
                + f"\nReceived: {data}"
            )

        try:
            Verdict(data["verdict"])
        except (ValueError, TypeError):
            raise ValueError(
                "Synthesis response contains an invalid verdict.\n"
                f"Received: {data.get('verdict')}"
            )

        try:
            confidence = float(data["confidence"])
        except (TypeError, ValueError):
            raise ValueError(
                "Synthesis confidence must be a number.\n"
                f"Received: {data.get('confidence')}"
            )

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                "Synthesis confidence must be between 0 and 1.\n"
                f"Received: {confidence}"
            )

        if not isinstance(data["synthesis"], str):
            raise ValueError(
                "Synthesis field must be a string."
            )

        if not isinstance(data["recommendation"], str):
            raise ValueError(
                "Recommendation field must be a string."
            )

        for field in (
            "key_agreements",
            "key_disagreements",
            "key_risks",
        ):
            if field in data and not isinstance(data[field], list):
                raise ValueError(
                    f"{field} must be an array."
                )

    # ========================================================
    # SYNTHESIS
    # ========================================================

    def synthesize(
        self,
        question: str,
        decisions: list[AgentDecision],
        messages: list[DebateMessage],
    ) -> SynthesisResult:

        system_prompt, user_prompt = self.build_prompt(
            question,
            decisions,
            messages,
        )

        data = generate_json(
            self.provider,
            system_prompt,
            user_prompt,
        )

        self.validate_synthesis_data(data)

        return SynthesisResult(
            verdict=Verdict(data["verdict"]),
            confidence=float(data["confidence"]),
            synthesis=data["synthesis"],
            key_agreements=data.get("key_agreements", []),
            key_disagreements=data.get("key_disagreements", []),
            key_risks=data.get("key_risks", []),
            recommendation=data["recommendation"],
        )