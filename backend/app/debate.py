import asyncio

from app.models import (
    AgentDecision,
    AgentName,
    DebateMessage,
    DebateState,
    MessageType,
)
from app.real_agents import RealAgent


class DebateEngine:

    def __init__(self, agents: list[RealAgent]):

        self.agents = {
            agent.name: agent
            for agent in agents
        }

    # ========================================================
    # ROUND 1
    # ========================================================

    async def _initial_positions(
        self,
        question: str,
    ) -> list[AgentDecision]:

        async def run_agent(agent):

            try:
                return await asyncio.to_thread(
                    agent.initial_position,
                    question,
                )

            except Exception as exc:

                print(
                    f"[WARNING] {agent.name.value.upper()} "
                    f"failed during initial position: {exc}"
                )

                return None

        results = await asyncio.gather(
            *[
                run_agent(agent)
                for agent in self.agents.values()
            ]
        )

        return [
            result
            for result in results
            if result is not None
        ]

    # ========================================================
    # ROUND 2
    # ========================================================

    async def _challenges(
        self,
        question: str,
        decisions: list[AgentDecision],
    ):

        targets = {
            AgentName.MELCHIOR: AgentName.BALTHASAR,
            AgentName.BALTHASAR: AgentName.CASPER,
            AgentName.CASPER: AgentName.MELCHIOR,
        }

        async def create_challenge(agent_name):

            agent = self.agents[agent_name]
            target = targets[agent_name]

            target_decision = next(
                (
                    decision
                    for decision in decisions
                    if decision.agent == target
                ),
                None,
            )

            if target_decision is None:

                print(
                    f"[INFO] {agent_name.value.upper()} "
                    f"cannot challenge "
                    f"{target.value.upper()} because "
                    f"the target has no decision."
                )

                return None

            try:

                challenge = await asyncio.to_thread(
                    agent.challenge,
                    question,
                    [target_decision],
                )

                return (
                    agent_name,
                    target,
                    challenge,
                )

            except Exception as exc:

                print(
                    f"[WARNING] {agent_name.value.upper()} "
                    f"failed during challenge: {exc}"
                )

                return None

        results = await asyncio.gather(
            *[
                create_challenge(agent_name)
                for agent_name in self.agents
            ]
        )

        return [
            result
            for result in results
            if result is not None
        ]

    # ========================================================
    # ROUND 3
    # ========================================================

    async def _responses(
        self,
        question: str,
        decisions: list[AgentDecision],
        challenges,
    ):

        async def create_response(agent_name):

            agent = self.agents[agent_name]

            incoming = [
                challenge
                for sender, target, challenge in challenges
                if target == agent_name
            ]

            if not incoming:

                print(
                    f"[INFO] {agent_name.value.upper()} "
                    f"received no usable challenge."
                )

                return None

            try:

                response = await asyncio.to_thread(
                    agent.respond,
                    question,
                    incoming,
                    decisions,
                )

                return (
                    agent_name,
                    response,
                )

            except Exception as exc:

                print(
                    f"[WARNING] {agent_name.value.upper()} "
                    f"failed during response: {exc}"
                )

                return None

        results = await asyncio.gather(
            *[
                create_response(agent_name)
                for agent_name in self.agents
            ]
        )

        return [
            result
            for result in results
            if result is not None
        ]

    # ========================================================
    # ROUND 4
    # ========================================================

    async def _reconsider(
        self,
        question: str,
        decisions: list[AgentDecision],
        messages: list[DebateMessage],
    ):

        async def reconsider_agent(agent):

            try:

                return await asyncio.to_thread(
                    agent.reconsider,
                    question,
                    decisions,
                    messages,
                )

            except Exception as exc:

                print(
                    f"[WARNING] {agent.name.value.upper()} "
                    f"failed during reconsideration: {exc}"
                )

                return None

        results = await asyncio.gather(
            *[
                reconsider_agent(agent)
                for agent in self.agents.values()
            ]
        )

        return [
            result
            for result in results
            if result is not None
        ]

    # ========================================================
    # FULL DEBATE
    # ========================================================

    async def run(
        self,
        question: str,
    ) -> DebateState:

        state = DebateState(
            question=question
        )

        # ====================================================
        # ROUND 1
        # ====================================================

        decisions = await self._initial_positions(
            question
        )

        for decision in decisions:

            state.messages.append(
                DebateMessage(
                    sender=decision.agent,
                    message_type=MessageType.INITIAL_POSITION,
                    content=decision.summary,
                    round_number=1,
                )
            )

        state.decisions = decisions

        # ====================================================
        # ROUND 2
        # ====================================================

        challenges = await self._challenges(
            question,
            decisions,
        )

        for sender, target, content in challenges:

            state.messages.append(
                DebateMessage(
                    sender=sender,
                    message_type=MessageType.CHALLENGE,
                    content=(
                        f"To {target.value.upper()}: "
                        f"{content}"
                    ),
                    round_number=2,
                )
            )

        # ====================================================
        # ROUND 3
        # ====================================================

        responses = await self._responses(
            question,
            decisions,
            challenges,
        )

        for sender, content in responses:

            state.messages.append(
                DebateMessage(
                    sender=sender,
                    message_type=MessageType.RESPONSE,
                    content=content,
                    round_number=3,
                )
            )

        # ====================================================
        # ROUND 4
        # ====================================================

        revised = await self._reconsider(
            question,
            decisions,
            state.messages,
        )

        for decision in revised:

            state.messages.append(
                DebateMessage(
                    sender=decision.agent,
                    message_type=MessageType.REVISION,
                    content=decision.summary,
                    round_number=4,
                )
            )

        if revised:
            state.decisions = revised

        return state

    # ========================================================
    # SYNCHRONOUS ENTRY POINT
    # ========================================================

    def start(
        self,
        question: str,
    ) -> DebateState:

        return asyncio.run(
            self.run(question)
        )