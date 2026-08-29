# MAGI

A multi-agent AI debate system that examines questions from three different perspectives, challenges those perspectives through structured debate, and produces a final synthesis and consensus.

> One question. Three perspectives. A debate between minds, distilled into consensus.

## What is MAGI?

MAGI is designed to make AI reasoning feel less like receiving an answer from a single model and more like observing a panel of independent minds reason through a problem.

A user submits a question. Three MAGI units independently form their positions, challenge one another, respond to criticism, and reconsider their views before the system produces a final result.

The goal is not simply to generate three answers. It is to create **interaction, disagreement, reconsideration, and convergence**.

## How It Works

MAGI processes each question through four debate rounds:

### 1. Initial Positions

Each MAGI unit independently analyzes the question and establishes an initial position.

### 2. Directed Challenges

The units challenge the reasoning of another MAGI unit, creating direct disagreement rather than three isolated responses.

### 3. Responses

Agents respond to the challenges directed toward their positions and defend or refine their reasoning.

### 4. Reconsideration

Each agent reviews the debate and determines whether its original position should remain unchanged or be revised.

After the debate, MAGI produces:

- Final agent positions
- Debate transcript
- MAGI synthesis
- Final verdict
- Confidence score
- Consensus statement

## The MAGI Units

MAGI currently consists of three independent reasoning units:

- **MELCHIOR**
- **BALTHASAR**
- **CASPER**

Each unit is intended to approach questions from a distinct perspective, allowing genuine disagreement and cooperation to emerge during the debate.

## Features

- Multi-agent AI debate
- Three independent MAGI units
- Four-stage debate process
- Directed agent-to-agent challenges
- Agent reconsideration
- Real-time backend streaming
- Server-Sent Events (SSE)
- Live debate log
- Live agent status updates
- Agent verdict indicators
- Confidence scoring
- Animated typewriter-style output
- MAGI synthesis
- Final consensus
- Keyboard navigation for long logs and synthesis
- Hidden scrollbars
- Responsive mobile interface
- OpenRouter LLM integration

## Architecture

```text
                         USER
                           │
                           ▼
                    ┌─────────────┐
                    │   NEXT.JS   │
                    │  FRONTEND   │
                    └──────┬──────┘
                           │
                           │ HTTP / SSE
                           ▼
                    ┌─────────────┐
                    │   FASTAPI   │
                    │   BACKEND   │
                    └──────┬──────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │ Streaming Debate Engine │
              └────────────┬────────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        ┌─────────┐   ┌─────────┐   ┌─────────┐
        │MELCHIOR │   │BALTHASAR│   │  CASPER │
        └────┬────┘   └────┬────┘   └────┬────┘
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                    ┌─────────────┐
                    │  OpenRouter │
                    │     LLM     │
                    └─────────────┘