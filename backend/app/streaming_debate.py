"""Streaming adapter for the MAGI debate engine.

This module preserves the existing DebateEngine protocol while exposing
each completed backend operation as soon as it finishes so a web client
can render real MAGI activity instead of simulating it.
"""

import asyncio
import time
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

        print("[SYNTHESIS] Starting MAGI Central...")

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
You are MAGI CENTRAL, the final reasoning layer of the MAGI system.

You are NOT a debate participant.

Your job is to produce a concise FINAL VERDICT SUMMARY from the completed
debate.

Do NOT write separate sections for MELCHIOR, BALTHASAR, or CASPER.
Do NOT mention the agents by name.

The output must read like the conclusion of a serious expert panel.

Structure the synthesis around:

1. FINAL JUDGMENT
   State clearly what MAGI ultimately concludes.

2. WHY
   Give the 2-3 strongest reasons that survived the debate.

3. WHAT CHANGED
   Briefly identify the most important argument, assumption, or piece of
   reasoning that was weakened, conceded, or refined during the debate.

4. DECISIVE CONDITION
   If the conclusion depends on a specific condition, state it clearly.
   If it does not, do not invent one.

IMPORTANT:

- Do NOT simply concatenate the agents' summaries.
- Do NOT write one paragraph per agent.
- Do NOT repeat every argument from the debate.
- Do NOT produce meeting notes.
- Do NOT invent facts or arguments.
- Do NOT treat majority vote as automatically correct.
- Resolve disagreements where the debate actually resolves them.
- Preserve meaningful uncertainty where it remains.
- Directly answer the original question.
- Be concise and decisive.

Return ONLY the final verdict summary.

Use approximately 120-180 words.
Use 2-3 short paragraphs.
"""

        synthesis_user_prompt = f"""
QUESTION:

{question}

FINAL AGENT POSITIONS:

{decision_text}

FULL DEBATE:

{debate_text}

Produce the final MAGI verdict summary.
"""

        try:
            synthesis_provider = next(
                iter(self.agents.values())
            ).provider

            synthesis_start = time.perf_counter()

            synthesis = await asyncio.to_thread(
                synthesis_provider.generate,
                synthesis_system_prompt,
                synthesis_user_prompt,
            )

            print(
                f"[TIMING] MAGI CENTRAL synthesis: "
                f"{time.perf_counter() - synthesis_start:.2f}s"
            )

            synthesis = synthesis.strip()

            if not synthesis:
                raise ValueError(
                    "MAGI synthesis returned an empty response."
                )

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