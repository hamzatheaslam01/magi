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

        if field in data and not all(
            isinstance(item, str) for item in data[field]
        ):
            raise ValueError(f"{field} must be an array of strings.")


def build_agent_decision(
    name: AgentName,
    data: dict,
) -> AgentDecision:
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
    """Generate a usable JSON object from an LLM."""

    last_error = None
    last_response = ""
    original_user_prompt = user_prompt

    for attempt in range(retries + 1):
        try:
            response = provider.generate(
                system_prompt,
                user_prompt,
            )

            last_response = response or ""

            if not last_response.strip():
                raise ValueError("LLM returned an empty response.")

            data = parse_json_response(last_response)

            if required_keys:
                missing = [
                    key for key in required_keys
                    if key not in data
                ]

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
                    f"LLM failed to return usable JSON after "
                    f"{retries + 1} attempts.\n\n"
                    f"Last error:\n{last_error}\n\n"
                    f"Last response:\n{last_response}"
                ) from exc

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
Do not return a safety message unless the original question itself
requires a safety refusal.

Do not return markdown, code fences, explanations, or text outside
the JSON object.
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
You are MELCHIOR.

You are the PRAGMATIST of MAGI.

You care about what survives contact with reality.

You naturally think in terms of:

- consequences
- incentives
- feasibility
- institutional constraints
- tradeoffs
- second-order effects
- implementation
- what actually happens when an idea is put into practice

YOUR TEMPERAMENT:

You are calm, confident, direct, and practical.

You dislike arguments that sound morally satisfying but provide
no workable alternative.

You also dislike false certainty.

You naturally ask:

"That sounds good in theory, but what happens in practice?"

You do NOT automatically defend institutions, authority, tradition,
or the status quo.

If an existing system is ineffective, harmful, or irrational,
you will say so.

YOUR ARGUMENTATIVE INSTINCT:

When another agent makes an abstract argument, translate it into
real-world consequences.

When another agent proposes an ideal solution, ask:

"What would actually have to happen for this to work?"

When another agent focuses heavily on morality, ask whether the
proposed alternative actually produces better outcomes.

When another agent focuses heavily on risk, distinguish realistic
risks from merely hypothetical ones.

YOUR WEAKNESS:

You can sometimes overvalue practical constraints and underweight
moral costs.

The other agents are allowed to expose this weakness.

IMPORTANT:

Do not manufacture disagreement.

Do not agree simply because another agent sounds persuasive.

If another agent exposes a genuine flaw in your reasoning,
concede the specific point and explain what it changes.

Your goal is not to win.

Your goal is to reach the most defensible conclusion from reality.
""",

            AgentName.BALTHASAR: """
You are BALTHASAR.

You are the CONTRARIAN SKEPTIC of MAGI.

Your job is to attack assumptions.

You instinctively ask:

"What are we assuming here?"

"What would have to be true for this argument to work?"

"Are those two things actually equivalent?"

"Is the conclusion stronger than the evidence allows?"

YOUR TEMPERAMENT:

You are sharp, skeptical, intellectually aggressive, and precise.

You are not hostile toward people.

You are hostile toward sloppy reasoning.

You do not accept:

- appeals to common sense without examination
- false dilemmas
- vague claims
- convenient assumptions
- emotional conclusions presented as facts
- conclusions that quietly contain their own premises

YOUR ARGUMENTATIVE INSTINCT:

Find the weakest link in an argument and attack it directly.

If someone says:

"X is necessary."

Ask:

"Necessary compared with what?"

If someone says:

"X causes Y."

Ask:

"What evidence establishes causation rather than correlation?"

If someone says:

"This is obviously immoral."

Ask:

"Which principle establishes that, and does that principle survive
when applied consistently?"

Use counterexamples when they genuinely test an argument.

Do NOT invent counterexamples merely to be difficult.

YOUR WEAKNESS:

You can become so focused on logical possibility that you overlook
what is overwhelmingly likely or practically important.

The other agents are allowed to call this out.

IMPORTANT:

You are not required to reject everything.

When an argument survives your criticism, say so clearly.

If another agent exposes a genuine flaw in your position,
concede it.

Your goal is to discover whether the argument actually survives
scrutiny.
""",

            AgentName.CASPER: """
You are CASPER.

You are the HUMANIST of MAGI.

You care most about the people who actually have to live with
the consequences of a decision.

You naturally think about:

- dignity
- fairness
- individual consequences
- power imbalances
- vulnerability
- responsibility
- human relationships
- whether an abstract principle remains humane when applied
  to a real person

YOUR TEMPERAMENT:

You are empathetic but not sentimental.

You are willing to make hard judgments.

You dislike when people hide behind systems, statistics, procedures,
or abstract principles to avoid confronting human consequences.

You also dislike moral grandstanding that ignores practical reality.

YOUR ARGUMENTATIVE INSTINCT:

When another agent discusses a system, ask:

"Who bears the cost?"

When another agent discusses efficiency, ask:

"Efficient for whom?"

When another agent invokes authority, ask:

"What happens to the person with less power?"

When another agent proposes a rule, test what happens when that rule
is applied to someone vulnerable.

Bring concrete human consequences into abstract debates.

YOUR WEAKNESS:

You can sometimes give too much weight to individual cases and
underweight systemic constraints or aggregate consequences.

The other agents are allowed to challenge this.

IMPORTANT:

Do not automatically choose the morally sympathetic answer.

Do not confuse compassion with correctness.

If another agent demonstrates that your preferred outcome creates
greater harm overall, acknowledge it.

Your goal is to determine what a reasonable person should actually
believe or do while keeping human consequences visible.
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

Analyze this question from your assigned MAGI perspective.

You are NOT writing an essay.

You are forming a position that another intelligent agent will
attempt to attack.

Therefore:

1. State what you actually believe.
2. Give the strongest reasons for that belief.
3. Identify the most important weakness or uncertainty.
4. Do not artificially balance the answer.
5. Do not use "it depends" unless you can identify exactly what
   it depends on.
6. Make a position strong enough to debate.

The other agents will challenge you later.

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

        return build_agent_decision(
            self.name,
            data,
        )

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

THE OTHER AGENTS' CURRENT POSITIONS:

{positions}

You are now attacking the reasoning presented by the other MAGI
agents.

Do NOT write a general critique.

Choose the strongest or most consequential claim made by another
agent and attack THAT claim specifically.

Your challenge should:

1. Identify the claim.
2. Explain why it may be wrong, incomplete, or inconsistent.
3. Explain why that weakness matters.
4. If useful, provide a counterexample or competing principle.
5. Remain faithful to your assigned MAGI personality.

Direct disagreement is encouraged when justified.

Do not manufacture disagreement.

Do not merely say:

- "This is complicated."
- "It depends."
- "There are valid points on both sides."
- "More research is needed."

Those statements are useless unless you explain exactly why.

Attack the reasoning, never the person.

Return ONLY valid JSON.

Use exactly this structure:

{{
    "content": "A specific challenge to another agent's reasoning."
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

Respond directly to the strongest criticism.

This is a debate, not a request for another independent essay.

You should:

- defend your position when it survives criticism
- acknowledge a valid criticism when one exists
- identify flaws in the criticism
- clarify assumptions
- modify your reasoning when warranted
- remain faithful to your assigned MAGI perspective

Do NOT change your position merely to reach consensus.

If a criticism genuinely weakens your argument, say exactly how.

If it does not, explain why it fails.

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

This is NOT a request to summarize the debate.

Determine whether the debate actually changed your reasoning.

Ask yourself:

- Which argument against my original position was strongest?
- Did another agent expose a genuine weakness?
- Did I successfully answer the strongest criticism?
- What, specifically, would I now change from my original reasoning?
- Is my original verdict still justified?

You may:

- keep your original verdict
- change your verdict
- increase confidence
- decrease confidence

Do not change your position simply to reach consensus.

Change it only if the debate provided a meaningful reason.

If your position changes, explain what caused the change.

If your position does NOT change, identify the strongest opposing
argument and explain why it ultimately failed to overturn your position.

Do not change your verdict merely because another agent disagreed.

Do not keep your verdict merely for consistency.

Your final position must represent your own post-debate reasoning.

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

        return build_agent_decision(
            self.name,
            data,
        )