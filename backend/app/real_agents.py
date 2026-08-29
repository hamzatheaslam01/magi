import json

from app.models import (
    AgentDecision,
    AgentName,
    DebateMessage,
    Severity,
    Verdict,
)
from app.llm.base import LLMProvider


# ============================================================
# DECISION VALIDATION / BUILDING
# ============================================================

REQUIRED_DECISION_FIELDS = (
    "verdict",
    "confidence",
    "severity",
    "summary",
)


def validate_decision_data(data: dict) -> None:
    """Validate the minimum structure required for an AgentDecision."""
    if not isinstance(data, dict):
        raise ValueError(
            "Decision response must be a JSON object.\n"
            f"Received: {data!r}"
        )

    missing = [field for field in REQUIRED_DECISION_FIELDS if field not in data]
    if missing:
        raise ValueError(
            "Decision response is missing required fields: "
            + ", ".join(missing)
            + f"\nReceived: {data!r}"
        )

    if data["verdict"] not in {v.value for v in Verdict}:
        raise ValueError(f"Invalid verdict: {data['verdict']!r}")

    try:
        confidence = float(data["confidence"])
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be a number from 0 to 1.") from exc

    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be a number from 0 to 1.")

    if data["severity"] not in {s.value for s in Severity}:
        raise ValueError(f"Invalid severity: {data['severity']!r}")

    if not isinstance(data["summary"], str) or not data["summary"].strip():
        raise ValueError("summary must be a non-empty string.")

    for field in ("arguments", "concerns", "recommendations"):
        if field in data and not isinstance(data[field], list):
            raise ValueError(f"{field} must be an array of strings.")
        if field in data and not all(isinstance(item, str) for item in data[field]):
            raise ValueError(f"{field} must be an array of strings.")


def build_agent_decision(name: AgentName, data: dict) -> AgentDecision:
    """Validate LLM data and convert it into an AgentDecision."""
    validate_decision_data(data)

    return AgentDecision(
        agent=name,
        verdict=Verdict(data["verdict"]),
        confidence=float(data["confidence"]),
        severity=Severity(data["severity"]),
        summary=data["summary"].strip(),
        arguments=data.get("arguments", []),
        concerns=data.get("concerns", []),
        recommendations=data.get("recommendations", []),
    )


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
    required_keys: tuple[str, ...] = (),
) -> dict:
    """Generate a usable JSON object from an LLM.

    ``required_keys`` prevents responses such as ``{"status": "valid"}``
    from being accepted as successful responses for challenge/decision calls.
    """
    last_error = None
    last_response = ""
    original_user_prompt = user_prompt

    for attempt in range(retries + 1):
        try:
            response = provider.generate(system_prompt, user_prompt)
            last_response = response or ""

            if not last_response.strip():
                raise ValueError("LLM returned an empty response.")

            data = parse_json_response(last_response)

            if required_keys:
                missing = [key for key in required_keys if key not in data]
                if missing:
                    raise ValueError(
                        "JSON response is missing required fields: "
                        + ", ".join(missing)
                        + f"\nReceived: {data!r}"
                    )

            return data

        except Exception as exc:
            last_error = exc

            if attempt == retries:
                raise ValueError(
                    f"LLM failed to return usable JSON after {retries + 1} attempts.\n\n"
                    f"Last error:\n{last_error}\n\n"
                    f"Last response:\n{last_response}"
                ) from exc

            # IMPORTANT: keep the original task in every retry.
            # The previous implementation replaced the entire prompt with the
            # error message, which could cause a small/free model to lose the
            # question, target position, or debate context on retry.
            user_prompt = f"""
{original_user_prompt}

IMPORTANT RETRY INSTRUCTION:
Your previous response could not be used by the MAGI system.

Previous response:
{last_response}

Problem:
{exc}

You MUST now return the requested JSON object for the ORIGINAL TASK above.
Do not return a status object such as {{"status": "valid"}}.
Do not return an empty object.
Do not return a safety message unless the original question itself requires a safety refusal.
Do not return markdown, code fences, explanations, or text outside the JSON object.
"""

    raise RuntimeError("Unexpected JSON generation failure.")


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
You are MELCHIOR, the analytical and intellectually rigorous
member of the MAGI system.

Your purpose is to determine what is actually justified by
evidence and reasoning.

CORE PRINCIPLES:

- logic
- evidence
- factual accuracy
- technical feasibility
- consistency
- identifying unsupported assumptions
- distinguishing facts from speculation

BEHAVIOR:

- Analyze the question independently.
- Do not agree simply to reach consensus.
- Challenge weak reasoning.
- Acknowledge strong arguments from other perspectives.
- Do not manufacture certainty.
- Do not manufacture disagreement.
- If the evidence supports a clear answer, give one.
- If important circumstances change the answer, explain exactly why.
- Prefer precise conclusions over vague neutrality.

For moral, personal, or everyday questions, consider:
- intent
- consequences
- fairness
- responsibility
- dignity
- relevant relationships
- competing obligations

You are rigorous, not hostile.

Your goal is to determine what conclusion is best supported
by the available information.
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

For moral, personal, or everyday questions, consider:
- potential harm
- consequences
- power dynamics
- fairness
- ways a decision could negatively affect people

Your skepticism must remain rational.

Your goal is not to prevent every possible risk.

Your goal is to expose risks that materially affect the decision.
""",

            AgentName.CASPER: """
You are CASPER, the pragmatic and human-centered member
of the MAGI system.

Your purpose is to determine what actually works in the
real world.

CORE PRINCIPLES:

- context
- practicality
- tradeoffs
- human consequences
- long-term implications
- flexibility
- real-world constraints

BEHAVIOR:

- Consider how a decision works in practice.
- Identify tradeoffs that abstract reasoning may overlook.
- Consider the people affected by the decision.
- Consider resources, incentives, constraints, and implementation.
- Do not manufacture nuance merely to avoid making a decision.
- Do not automatically split the difference.
- If one option is clearly better, say so.
- If circumstances materially change the answer, explain exactly
  which circumstances matter.

For moral and personal questions, consider:
- intent
- relationships
- fairness
- dignity
- responsibility
- consequences

Your goal is not to split the difference between the other agents.

Your goal is to determine what a reasonable person should
actually do given the circumstances.
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
You are participating in a general-purpose decision analysis system.

QUESTION:

{question}

Analyze this question independently from your assigned perspective.

Your job is NOT to automatically approve or reject something.

Determine what conclusion is actually justified by the available
information.

Possible verdicts:

- approve
- reject
- conditional

Use "approve" when the available evidence strongly supports
the option or position.

Use "reject" when the available evidence strongly argues
against it.

Use "conditional" when the correct answer genuinely depends
on important circumstances, missing information, tradeoffs,
or constraints.

Your analysis may concern ANY subject, including:

- technology
- education
- career
- relationships
- ethics
- personal decisions
- purchases
- business
- everyday situations
- abstract questions

Do not assume the question is technical.

Return ONLY valid JSON.

Use exactly this JSON structure:

{{
    "verdict": "approve",
    "confidence": 0.0,
    "severity": "info",
    "summary": "short explanation of your conclusion",
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
- summary MUST be a string
- arguments MUST be an array of strings
- concerns MUST be an array of strings
- recommendations MUST be an array of strings
- Base your reasoning on the actual question.
- Do not invent facts about the user.
- Do not assume missing context.
- Do not agree simply because another position might be popular.
- Be honest about uncertainty.

IMPORTANT:

Return the JSON object itself.

Do not include markdown.
Do not include ```json.
Do not include text outside the JSON.
"""

        data = generate_json(
            self.provider,
            system_prompt,
            user_prompt,
            required_keys=REQUIRED_DECISION_FIELDS,
        )

        return build_agent_decision(self.name, data)

    # ========================================================
    # CHALLENGE
    # ========================================================

    def challenge(
        self,
        question: str,
        decisions: list[AgentDecision],
    ) -> str:

        if not decisions:
            raise ValueError(
                "Cannot create a challenge without a target decision."
            )

        positions = "\n\n".join(
            (
                f"{decision.agent.value.upper()}:\n"
                f"Verdict: {decision.verdict.value}\n"
                f"Confidence: {decision.confidence}\n"
                f"Summary: {decision.summary}\n"
                f"Arguments: {'; '.join(decision.arguments)}\n"
                f"Concerns: {'; '.join(decision.concerns)}"
            )
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

A good challenge should identify a specific weakness and
explain why it matters.

Do not merely say that the answer depends on context.

Return ONLY valid JSON.

Use exactly this structure:

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
            required_keys=("content",),
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

        return str(content)

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
            (
                decision
                for decision in decisions
                if decision.agent == self.name
            ),
            None,
        )

        if current_decision is None:
            raise ValueError(
                f"No current decision exists for {self.name.value}."
            )

        challenge_text = "\n\n".join(
            f"- {challenge}"
            for challenge in challenges
        )

        if not challenge_text:
            challenge_text = (
                "No direct challenge was received. "
                "Explain whether your current position survives "
                "the other agents' reasoning."
            )

        arguments_text = "\n".join(
            f"- {argument}"
            for argument in current_decision.arguments
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
{arguments_text}

CHALLENGES AGAINST YOUR POSITION:

{challenge_text}

Respond directly to the strongest criticisms.

You may:

- defend your position
- acknowledge a valid criticism
- clarify an assumption
- modify part of your reasoning

Do not change your position merely to reach consensus.

Acknowledge a criticism when it is genuinely valid.

Return ONLY valid JSON.

Use exactly this structure:

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
            required_keys=("content",),
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

        return str(content)

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
            (
                f"[Round {message.round_number}] "
                f"{message.sender.value.upper()} "
                f"{message.message_type.value.upper()}:\n"
                f"{message.content}"
            )
            for message in messages
        )

        current_decision = next(
            (
                decision
                for decision in decisions
                if decision.agent == self.name
            ),
            None,
        )

        if current_decision is None:
            raise ValueError(
                f"No current decision exists for {self.name.value}."
            )

        arguments_text = "\n".join(
            f"- {argument}"
            for argument in current_decision.arguments
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
{arguments_text}

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
- arguments MUST be an array of strings
- concerns MUST be an array of strings
- recommendations MUST be an array of strings

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
            required_keys=REQUIRED_DECISION_FIELDS,
        )

        return build_agent_decision(self.name, data)