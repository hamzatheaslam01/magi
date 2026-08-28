import asyncio

from app.models import (
    AgentDecision,
    AgentName,
    DebateMessage,
    DebateState,
    MessageType,
)
from app.real_agents import RealAgent
from app.llm import LLMProvider


class DebateEngine:

    def __init__(self, provider: LLMProvider):

        self.agents = {
            name: RealAgent(
                name=name,
                provider=provider,
            )
            for name in AgentName
        }

    async def _initial_positions(
        self,
        question: str,
    ) -> list[AgentDecision]:

        tasks = [
            asyncio.to_thread(
                agent.initial_position,
                question,
            )
            for agent in self.agents.values()
        ]

        return await asyncio.gather(*tasks)

    async def _challenges(
        self,
        question: str,
        decisions: list[AgentDecision],
    ):

        # Each agent challenges the next agent.
        #
        # MELCHIOR → BALTHASAR
        # BALTHASAR → CASPER
        # CASPER → MELCHIOR

        targets = {
            AgentName.MELCHIOR: AgentName.BALTHASAR,
            AgentName.BALTHASAR: AgentName.CASPER,
            AgentName.CASPER: AgentName.MELCHIOR,
        }

        async def create_challenge(agent_name):

            agent = self.agents[agent_name]

            target = targets[agent_name]

            target_decision = next(
                d for d in decisions
                if d.agent == target
            )

            challenge = agent.challenge(
                question,
                [target_decision],
            )

            return (
                agent_name,
                target,
                challenge,
            )

        tasks = [
            create_challenge(agent_name)
            for agent_name in self.agents
        ]

        return await asyncio.gather(*tasks)

    async def _responses(
        self,
        question: str,
        decisions: list[AgentDecision],
        challenges,
    ):

        async def create_response(agent_name):

            agent = self.agents[agent_name]

            # Find the challenge aimed at this agent.
            incoming = [
                challenge
                for sender, target, challenge
                in challenges
                if target == agent_name
            ]

            response = agent.respond(
                question,
                incoming,
                decisions,
            )

            return agent_name, response

        tasks = [
            create_response(agent_name)
            for agent_name in self.agents
        ]

        return await asyncio.gather(*tasks)

    async def _reconsider(
        self,
        question: str,
        decisions: list[AgentDecision],
        messages: list[DebateMessage],
    ):

        async def reconsider_agent(agent):

            revised = agent.reconsider(
                question,
                decisions,
                messages,
            )

            return revised

        tasks = [
            reconsider_agent(agent)
            for agent in self.agents.values()
        ]

        return await asyncio.gather(*tasks)

    async def run(
        self,
        question: str,
    ) -> DebateState:

        state = DebateState(
            question=question
        )

        # ==============================================
        # ROUND 1
        # INITIAL POSITIONS
        # ==============================================

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

        # ==============================================
        # ROUND 2
        # DIRECTED CHALLENGES
        # ==============================================

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

        # ==============================================
        # ROUND 3
        # RESPONSES
        # ==============================================

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

        # ==============================================
        # ROUND 4
        # RECONSIDERATION
        # ==============================================

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

        state.decisions = revised

        return state

    def start(
        self,
        question: str,
    ) -> DebateState:

        return asyncio.run(
            self.run(question)
        )