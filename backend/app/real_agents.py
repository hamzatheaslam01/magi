import json

from app.models import (
    AgentDecision,
    AgentName,
    DebateMessage,
    Severity,
    Verdict,
)
from app.llm import LLMProvider


# ============================================================
# JSON HELPERS
# ============================================================

def parse_json_response(response: str) -> dict:
    """
    Extract a JSON object from an LLM response.

    Handles:
    - plain JSON
    - ```json ... ```
    - JSON surrounded by explanatory text
    """

    if not response:
        raise ValueError("LLM returned an empty response.")

    response = response.strip()

    # --------------------------------------------------------
    # Direct JSON
    # --------------------------------------------------------

    try:
        data = json.loads(response)

        if isinstance(data, dict):
            return data

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Markdown code blocks
    # --------------------------------------------------------

    if "```" in response:

        parts = response.split("```")

        for part in parts:

            cleaned = part.strip()

            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

            try:
                data = json.loads(cleaned)

                if isinstance(data, dict):
                    return data

            except json.JSONDecodeError:
                continue

    # --------------------------------------------------------
    # JSON object embedded in text
    # --------------------------------------------------------

    start = response.find("{")
    end = response.rfind("}")

    if start != -1 and end != -1 and end > start:

        candidate = response[start:end + 1]

        try:
            data = json.loads(candidate)

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "Could not parse JSON from LLM response:\n"
        f"{response}"
    )


def generate_json(
    provider: LLMProvider,
    system_prompt: str,
    user_prompt: str,
    retries: int = 2,
) -> dict:
    """
    Ask the LLM for JSON and retry when the response
    is malformed or unusable.
    """

    last_response = ""

    for attempt in range(retries + 1):

        response = provider.generate(
            system_prompt,
            user_prompt,
        )

        last_response = response

        try:
            return parse_json_response(response)

        except ValueError:

            if attempt == retries:
                raise ValueError(
                    "LLM failed to return valid JSON "
                    f"after {retries + 1} attempts.\n\n"
                    f"Last response:\n{last_response}"
                )

            user_prompt = f"""
Your previous response was invalid.

Previous response:

{response}

Return ONLY valid JSON.

Do not include:
- explanations
- markdown
- code fences
- safety messages
- introductory text
- text outside the JSON object

Follow the JSON structure requested in the previous prompt exactly.
"""

    raise RuntimeError("Unexpected JSON generation failure.")


def validate_decision_data(data: dict) -> dict:
    """
    Validate that an LLM response contains the fields
    required to construct an AgentDecision.
    """

    required = [
        "verdict",
        "confidence",
        "severity",
        "summary",
    ]

    missing = [
        field
        for field in required
        if field not in data
    ]

    if missing:
        raise ValueError(
            "Decision response is missing required fields: "
            f"{', '.join(missing)}\n"
            f"Received: {data}"
        )

    return data


# ============================================================
# REAL AGENT
# ============================================================

class RealAgent:

    def __init__(
        self,
        name: AgentName,
        provider: LLMProvider,
    ):
        self.name = name
        self.provider = provider

    # ========================================================
    # PERSONALITY
    # ========================================================

    def build_system_prompt(self) -> str:

        personalities = {

            AgentName.MELCHIOR: """
    You are MELCHIOR, the rationalist of the MAGI system.

    You approach problems through logic, evidence, consistency,
    and careful examination of assumptions.

    CORE PRINCIPLES:
    - Seek what is most logically justified.
    - Separate facts from assumptions.
    - Identify weak reasoning and unsupported claims.
    - Consider evidence before intuition.
    - Examine opportunity costs and tradeoffs.
    - Prefer precise conclusions over vague neutrality.
    - Admit uncertainty when evidence is insufficient.

    BEHAVIOR:
    - Do not agree merely because another agent agrees.
    - Challenge contradictions and logical gaps.
    - If another agent makes a strong argument, acknowledge it.
    - If your own position is weakened by new evidence, revise it.
    - Distinguish "I disagree" from "this argument is unsupported."
    - Avoid unnecessary pessimism or optimism.

    For everyday and personal questions, do not reduce everything
    to cold logic. Consider the facts and reasoning available,
    while recognizing uncertainty about human behavior.

    Your goal is not to win the debate.

    Your goal is to determine what is most defensible.
    """,

            AgentName.BALTHASAR: """
    You are BALTHASAR, the skeptic of the MAGI system.

    Your purpose is to stress-test decisions.

    CORE PRINCIPLES:
    - Search for hidden risks.
    - Examine failure scenarios.
    - Identify unintended consequences.
    - Question optimistic assumptions.
    - Look for information that may be missing.
    - Consider second-order and long-term effects.
    - Distinguish acceptable risk from unacceptable risk.

    BEHAVIOR:
    - Challenge the other agents' assumptions.
    - Ask what happens if things go wrong.
    - Do not reject an idea merely because risk exists.
    - Do not manufacture risks just to disagree.
    - If a risk is manageable, acknowledge that.
    - If another agent exposes a legitimate weakness in your
    argument, concede it.
    - Prefer robust decisions over attractive but fragile ones.

    For moral, personal, or everyday questions, consider the
    potential harm, consequences, power dynamics, and ways a
    decision could negatively affect people.

    Your skepticism must remain rational.

    Your goal is not to prevent every possible risk.

    Your goal is to expose risks that materially affect the decision.
    """,

            AgentName.CASPER: """
    You are CASPER, the humanist and pragmatic member of MAGI.

    You examine decisions through context, practicality,
    human consequences, values, and real-world constraints.

    CORE PRINCIPLES:
    - Understand the circumstances surrounding the question.
    - Consider how decisions affect real people.
    - Examine competing values and priorities.
    - Consider practical constraints.
    - Look beyond purely theoretical answers.
    - Recognize that different people may reasonably reach
    different conclusions.
    - Search for solutions that survive contact with reality.

    BEHAVIOR:
    - Challenge extreme or overly simplistic positions.
    - Do not manufacture nuance when the evidence supports
    a clear conclusion.
    - Consider emotional and social consequences when relevant.
    - Consider long-term effects as well as immediate outcomes.
    - If another agent's argument is stronger, acknowledge it.
    - If circumstances materially change the answer, explain exactly
    which circumstances matter.

    For moral and personal questions, consider intent, relationships,
    fairness, dignity, responsibility, and consequences.

    Your goal is not to split the difference between the other agents.

    Your goal is to determine what a reasonable person should actually
    do given the circumstances.
    """
        }

        return personalities[self.name]

    # ========================================================
    # INITIAL POSITION
    # ========================================================

    def initial_position(
        self,
        question: str,
    ) -> AgentDecision:

        system_prompt = self.build_system_prompt()

        user_prompt = f"""
    You are one member of the MAGI decision-making system.

    QUESTION:

    {question}

    Analyze the question independently.

    Possible verdicts:

    - approve
    - reject
    - conditional

    Use "conditional" when the correct answer genuinely depends
    on circumstances or constraints.

    Return ONLY valid JSON.

    Use exactly this structure:

    {{
        "verdict": "approve",
        "confidence": 0.0,
        "severity": "info",
        "summary": "short explanation",
        "arguments": [
            "argument 1",
            "argument 2"
        ],
        "concerns": [
            "concern 1"
        ],
        "recommendations": [
            "recommendation 1"
        ]
    }}

    Rules:

    - verdict MUST be approve, reject, or conditional
    - confidence MUST be a number from 0 to 1
    - severity MUST be info, low, medium, high, or critical
    - arguments MUST be an array
    - concerns MUST be an array
    - recommendations MUST be an array

    Do not include markdown.
    Do not include ```json.
    Do not include text outside the JSON.
    """

        data = generate_json(
            self.provider,
            system_prompt,
            user_prompt,
        )

        # Validate required fields
        validate_decision_data(data)

        # Build the actual AgentDecision
        decision = AgentDecision(
            agent=self.name,
            verdict=Verdict(data["verdict"]),
            confidence=float(data["confidence"]),
            severity=Severity(data["severity"]),
            summary=data["summary"],
            arguments=data.get("arguments", []),
            concerns=data.get("concerns", []),
            recommendations=data.get("recommendations", []),
        )

        # IMPORTANT: return it
        return decision

    # ========================================================
    # CHALLENGE
    # ========================================================

    def challenge(
        self,
        question: str,
        decisions: list[AgentDecision],
    ) -> str:

        positions = "\n\n".join(
            f"{decision.agent.value.upper()}:\n"
            f"Verdict: {decision.verdict.value}\n"
            f"Confidence: {decision.confidence}\n"
            f"Summary: {decision.summary}\n"
            f"Arguments: {'; '.join(decision.arguments)}\n"
            f"Concerns: {'; '.join(decision.concerns)}"
            for decision in decisions
        )

        user_prompt = f"""
You are participating in a structured MAGI debate.

QUESTION:

{question}

TARGET AGENT'S CURRENT POSITION:

{positions}

Challenge the target agent's reasoning.

Look for:

- weak assumptions
- contradictions
- missing evidence
- overlooked consequences
- practical limitations
- risks

Attack the reasoning, not the agent.

Return ONLY valid JSON:

{{
    "content": "A specific challenge to the target's reasoning."
}}

The "content" field MUST contain your actual challenge.

Do not return:
- an empty object
- a safety message
- markdown
- code fences
- text outside the JSON
"""

        data = generate_json(
            self.provider,
            self.build_system_prompt(),
            user_prompt,
        )

        content = data.get("content")

        if not content:
            content = data.get("challenge")

        if not content:
            content = data.get("argument")

        if not content:
            raise ValueError(
                "Challenge response did not contain usable content.\n"
                f"Received: {data}"
            )

        return content

    # ========================================================
    # RESPONSE
    # ========================================================

    def respond(
        self,
        question: str,
        challenges: list[str],
        decisions: list[AgentDecision],
    ) -> str:

        current_decision = next(
            decision
            for decision in decisions
            if decision.agent == self.name
        )

        challenge_text = "\n\n".join(
            f"- {challenge}"
            for challenge in challenges
        )

        user_prompt = f"""
You are responding to criticism during a MAGI debate.

QUESTION:

{question}

YOUR CURRENT POSITION:

Verdict:
{current_decision.verdict.value}

Confidence:
{current_decision.confidence}

Summary:
{current_decision.summary}

Arguments:
{chr(10).join("- " + argument for argument in current_decision.arguments)}

CHALLENGES AGAINST YOUR POSITION:

{challenge_text}

Respond directly to the strongest criticisms.

You may:

- defend your position
- acknowledge a valid criticism
- clarify an assumption
- modify part of your reasoning

Do not change your position merely to reach consensus.

Return ONLY valid JSON:

{{
    "content": "Your substantive response to the criticism."
}}

The "content" field MUST contain your actual response.

Do not return:
- an empty object
- a safety message
- markdown
- code fences
- text outside the JSON
"""

        data = generate_json(
            self.provider,
            self.build_system_prompt(),
            user_prompt,
        )

        content = data.get("content")

        if not content:
            content = data.get("response")

        if not content:
            content = data.get("answer")

        if not content:
            raise ValueError(
                "Response did not contain usable content.\n"
                f"Received: {data}"
            )

        return content

    # ========================================================
    # RECONSIDERATION
    # ========================================================

    def reconsider(
        self,
        question: str,
        decisions: list[AgentDecision],
        messages: list[DebateMessage],
    ) -> AgentDecision:

        debate = "\n\n".join(
            f"[Round {message.round_number}] "
            f"{message.sender.value.upper()} "
            f"{message.message_type.value.upper()}:\n"
            f"{message.content}"
            for message in messages
        )

        current_decision = next(
            decision
            for decision in decisions
            if decision.agent == self.name
        )

        user_prompt = f"""
You have completed a debate with the other MAGI agents.

QUESTION:

{question}

YOUR ORIGINAL POSITION:

Verdict:
{current_decision.verdict.value}

Confidence:
{current_decision.confidence}

Summary:
{current_decision.summary}

Arguments:
{chr(10).join("- " + argument for argument in current_decision.arguments)}

FULL DEBATE:

{debate}

Now reconsider your position.

You may:

- keep your original verdict
- change your verdict
- increase confidence
- decrease confidence

Do not change your position simply to reach consensus.

Change it only if the debate provided a meaningful reason.

Your final position must represent your own reasoning.

Possible verdicts:

- approve
- reject
- conditional

Return ONLY valid JSON.

Use exactly this structure:

{{
    "verdict": "approve",
    "confidence": 0.0,
    "severity": "info",
    "summary": "short explanation of your final position",
    "arguments": [
        "argument 1",
        "argument 2"
    ],
    "concerns": [
        "concern 1"
    ],
    "recommendations": [
        "recommendation 1"
    ]
}}

Rules:

- verdict MUST be approve, reject, or conditional
- confidence MUST be a number from 0 to 1
- severity MUST be info, low, medium, high, or critical
- summary MUST be present
- arguments MUST be an array
- concerns MUST be an array
- recommendations MUST be an array

Do not return an empty object.

Do not return a safety message.

Do not include markdown.
Do not include ```json.
Do not include text outside the JSON.
"""

        data = generate_json(
            self.provider,
            self.build_system_prompt(),
            user_prompt,
        )

        validate_decision_data(data)

        return AgentDecision(
            agent=self.name,
            verdict=Verdict(data["verdict"]),
            confidence=float(data["confidence"]),
            severity=Severity(data["severity"]),
            summary=data["summary"],
            arguments=data.get("arguments", []),
            concerns=data.get("concerns", []),
            recommendations=data.get("recommendations", []),
        )