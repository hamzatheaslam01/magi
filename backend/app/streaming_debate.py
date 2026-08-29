"""Streaming adapter for the MAGI debate engine.

This module preserves the existing DebateEngine protocol while exposing
each completed backend operation as soon as it finishes so a web client
can render real MAGI activity instead of simulating it.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

from app.debate import DebateEngine
from app.models import AgentName, DebateMessage, DebateState, MessageType


EventCallback = Callable[[dict[str, Any]], None]


class StreamingDebateEngine(DebateEngine):
    """Run the existing debate pipeline while emitting live events."""

    async def _stream_agent_calls(
        self,
        calls: list[tuple[AgentName, Any]],
    ) -> AsyncIterator[tuple[AgentName, Any, Exception | None]]:
        """Run independent backend calls concurrently and yield completions."""
        async def execute(
            agent_name: AgentName,
            awaitable: Any,
        ) -> tuple[AgentName, Any, Exception | None]:
            try:
                result = await awaitable
                return agent_name, result, None
            except Exception as exc:
                return agent_name, None, exc

        tasks = [
            asyncio.create_task(execute(agent_name, awaitable))
            for agent_name, awaitable in calls
        ]

        for task in asyncio.as_completed(tasks):
            yield await task

    async def stream(self, question: str) -> AsyncIterator[dict[str, Any]]:
        """Execute all four MAGI rounds and yield backend-owned events."""
        state = DebateState(question=question)

        yield {
            "type": "analysis_started",
            "question": question,
            "agents": [name.value.upper() for name in self.agents],
        }

        # ============================================================
        # ROUND 1: INITIAL POSITIONS
        # ============================================================
        yield {
            "type": "round_started",
            "round": 1,
            "label": "INITIAL POSITIONS",
        }

        initial_calls = [
            (
                agent_name,
                asyncio.to_thread(
                    agent.initial_position,
                    question,
                ),
            )
            for agent_name, agent in self.agents.items()
        ]

        decisions = []

        async for agent_name, decision, error in self._stream_agent_calls(
            initial_calls
        ):
            if error is not None:
                yield {
                    "type": "agent_error",
                    "round": 1,
                    "agent": agent_name.value.upper(),
                    "message": str(error),
                }
                continue

            decisions.append(decision)

            message = DebateMessage(
                sender=decision.agent,
                message_type=MessageType.INITIAL_POSITION,
                content=decision.summary,
                round_number=1,
            )
            state.messages.append(message)

            yield {
                "type": "decision",
                "round": 1,
                "agent": decision.agent.value.upper(),
                "verdict": decision.verdict.value,
                "confidence": decision.confidence,
                "severity": decision.severity.value,
                "summary": decision.summary,
            }

            yield {
                "type": "message",
                "round": 1,
                "sender": message.sender.value.upper(),
                "message_type": message.message_type.value.upper(),
                "content": message.content,
            }

        state.decisions = decisions

        if not decisions:
            yield {
                "type": "error",
                "message": "All agents failed during the initial position round.",
            }
            return

        yield {
            "type": "round_completed",
            "round": 1,
        }

        # ============================================================
        # ROUND 2: DIRECTED CHALLENGES
        # ============================================================
        yield {
            "type": "round_started",
            "round": 2,
            "label": "DIRECTED CHALLENGES",
        }

        targets = {
            AgentName.MELCHIOR: AgentName.BALTHASAR,
            AgentName.BALTHASAR: AgentName.CASPER,
            AgentName.CASPER: AgentName.MELCHIOR,
        }

        challenge_calls = []

        for agent_name, agent in self.agents.items():
            if not any(d.agent == agent_name for d in decisions):
                continue

            target = targets[agent_name]
            target_decision = next(
                (d for d in decisions if d.agent == target),
                None,
            )

            if target_decision is None:
                continue

            challenge_calls.append(
                (
                    agent_name,
                    asyncio.to_thread(
                        agent.challenge,
                        question,
                        [target_decision],
                    ),
                )
            )

        challenges = []

        async for agent_name, content, error in self._stream_agent_calls(
            challenge_calls
        ):
            if error is not None:
                yield {
                    "type": "agent_error",
                    "round": 2,
                    "agent": agent_name.value.upper(),
                    "message": str(error),
                }
                continue

            target = targets[agent_name]
            challenges.append((agent_name, target, content))

            message = DebateMessage(
                sender=agent_name,
                message_type=MessageType.CHALLENGE,
                content=f"To {target.value.upper()}: {content}",
                round_number=2,
            )
            state.messages.append(message)

            yield {
                "type": "message",
                "round": 2,
                "sender": agent_name.value.upper(),
                "target": target.value.upper(),
                "message_type": "CHALLENGE",
                "content": content,
            }

        yield {
            "type": "round_completed",
            "round": 2,
        }

        # ============================================================
        # ROUND 3: RESPONSES
        # ============================================================
        yield {
            "type": "round_started",
            "round": 3,
            "label": "RESPONSES",
        }

        response_calls = []

        for agent_name, agent in self.agents.items():
            incoming = [
                challenge
                for sender, target, challenge in challenges
                if target == agent_name
            ]

            if not incoming:
                continue

            response_calls.append(
                (
                    agent_name,
                    asyncio.to_thread(
                        agent.respond,
                        question,
                        incoming,
                        decisions,
                    ),
                )
            )

        responses = []

        async for agent_name, content, error in self._stream_agent_calls(
            response_calls
        ):
            if error is not None:
                yield {
                    "type": "agent_error",
                    "round": 3,
                    "agent": agent_name.value.upper(),
                    "message": str(error),
                }
                continue

            responses.append((agent_name, content))

            message = DebateMessage(
                sender=agent_name,
                message_type=MessageType.RESPONSE,
                content=content,
                round_number=3,
            )
            state.messages.append(message)

            yield {
                "type": "message",
                "round": 3,
                "sender": agent_name.value.upper(),
                "message_type": "RESPONSE",
                "content": content,
            }

        yield {
            "type": "round_completed",
            "round": 3,
        }

        # ============================================================
        # ROUND 4: RECONSIDERATION
        # ============================================================
        yield {
            "type": "round_started",
            "round": 4,
            "label": "RECONSIDERATION",
        }

        reconsider_calls = []

        for agent_name, agent in self.agents.items():
            if not any(d.agent == agent_name for d in decisions):
                continue

            reconsider_calls.append(
                (
                    agent_name,
                    asyncio.to_thread(
                        agent.reconsider,
                        question,
                        decisions,
                        state.messages,
                    ),
                )
            )

        revised = []

        async for agent_name, decision, error in self._stream_agent_calls(
            reconsider_calls
        ):
            if error is not None:
                yield {
                    "type": "agent_error",
                    "round": 4,
                    "agent": agent_name.value.upper(),
                    "message": str(error),
                }
                continue

            revised.append(decision)

            message = DebateMessage(
                sender=decision.agent,
                message_type=MessageType.REVISION,
                content=decision.summary,
                round_number=4,
            )
            state.messages.append(message)

            yield {
                "type": "decision",
                "round": 4,
                "agent": decision.agent.value.upper(),
                "verdict": decision.verdict.value,
                "confidence": decision.confidence,
                "severity": decision.severity.value,
                "summary": decision.summary,
            }

            yield {
                "type": "message",
                "round": 4,
                "sender": message.sender.value.upper(),
                "message_type": "REVISION",
                "content": message.content,
            }

        if revised:
            state.decisions = revised

        yield {
    "type": "round_completed",
    "round": 4,
}

# ============================================================
# MAGI CENTRAL SYNTHESIS
# ============================================================

        yield {
            "type": "synthesis_started",
        }

        final_decisions = state.decisions

        decision_text = "\n\n".join(
            (
                f"{decision.agent.value.upper()}:\n"
                f"Verdict: {decision.verdict.value}\n"
                f"Confidence: {decision.confidence:.2f}\n"
                f"Position: {decision.summary}\n"
                f"Arguments: {'; '.join(decision.arguments)}\n"
                f"Concerns: {'; '.join(decision.concerns)}\n"
                f"Recommendations: {'; '.join(decision.recommendations)}"
            )
            for decision in final_decisions
        )

        debate_text = "\n\n".join(
            (
                f"[ROUND {message.round_number}] "
                f"{message.sender.value.upper()} "
                f"{message.message_type.value.upper()}:\n"
                f"{message.content}"
            )
            for message in state.messages
        )

        synthesis_system_prompt = """
        You are MAGI CENTRAL, the final synthesis intelligence of the MAGI system.

        You are NOT another debate participant.

        Your job is to examine the complete debate and produce the final human-readable
        judgment.

        The three MAGI units have deliberately different perspectives:

        MELCHIOR = analytical, evidence-driven, rigorous.
        BALTHASAR = skeptical, adversarial, focused on risks and failure.
        CASPER = human-centered, contextual, pragmatic.

        Do not simply average their positions.

        Identify:
        - where they genuinely disagreed
        - which arguments survived the debate
        - which arguments were weakened
        - where one agent changed or strengthened another's reasoning
        - the strongest consideration on each side
        - the final conclusion

        The result should sound like an intelligent synthesis of an actual debate,
        not a generic "it depends" answer.

        Do not mention JSON, prompts, models, or being an AI.

        Return ONLY the synthesis text.
        """

        synthesis_user_prompt = f"""
        QUESTION:

        {question}

        FINAL AGENT POSITIONS:

        {decision_text}

        FULL DEBATE:

        {debate_text}

        Write the final MAGI synthesis.

        Give a clear conclusion. If the answer is conditional, explain precisely
        what the decisive conditions are rather than hiding behind vague nuance.

        Keep it to approximately 2-4 paragraphs.
        """

        try:
            # All agents share the same provider, so use the existing OpenRouter
            # connection rather than creating another API client.
            synthesis_provider = next(iter(self.agents.values())).provider

            synthesis = await asyncio.to_thread(
                synthesis_provider.generate,
                synthesis_system_prompt,
                synthesis_user_prompt,
            )

            synthesis = synthesis.strip()

            if not synthesis:
                raise ValueError("MAGI synthesis returned an empty response.")

            yield {
                "type": "synthesis",
                "content": synthesis,
            }

        except Exception as exc:
            yield {
                "type": "synthesis_error",
                "message": str(exc),
            }

        # ============================================================
        # FINAL STATE
        # ============================================================
        final_decisions = state.decisions

        counts: dict[str, int] = {
            "approve": 0,
            "conditional": 0,
            "reject": 0,
        }

        for decision in final_decisions:
            counts[decision.verdict.value] += 1

        final_verdict = max(
            counts,
            key=lambda verdict: (
                counts[verdict],
                sum(
                    decision.confidence
                    for decision in final_decisions
                    if decision.verdict.value == verdict
                ),
            ),
        )

        final_confidence = (
            sum(decision.confidence for decision in final_decisions)
            / len(final_decisions)
            if final_decisions
            else 0.0
        )

        yield {
            "type": "completed",
            "question": state.question,
            "decisions": [
                {
                    "agent": decision.agent.value.upper(),
                    "verdict": decision.verdict.value,
                    "confidence": decision.confidence,
                    "severity": decision.severity.value,
                    "summary": decision.summary,
                    "arguments": decision.arguments,
                    "concerns": decision.concerns,
                    "recommendations": decision.recommendations,
                }
                for decision in final_decisions
            ],
            "messages": [
                {
                    "sender": message.sender.value.upper(),
                    "message_type": message.message_type.value.upper(),
                    "content": message.content,
                    "round_number": message.round_number,
                }
                for message in state.messages
            ],
            "final_verdict": final_verdict,
            "final_confidence": final_confidence,
        }
