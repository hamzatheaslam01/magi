"use client";

import { useEffect, useRef, useState, type RefObject } from "react";

type AgentState =
  | "idle"
  | "thinking"
  | "approve"
  | "conditional"
  | "reject";

type Agent = {
  name: string;
  number: string;
  state: AgentState;
};

const initialAgents: Agent[] = [
  {
    name: "BALTHASAR",
    number: "2",
    state: "idle",
  },
  {
    name: "CASPER",
    number: "3",
    state: "idle",
  },
  {
    name: "MELCHIOR",
    number: "1",
    state: "idle",
  },
];

function AgentPanel({
  name,
  number,
  state,
}: {
  name: string;
  number: string;
  state: AgentState;
}) {
  const statusText = {
    idle: "STANDBY",
    thinking: "THINKING",
    approve: "AGREE",
    conditional: "CONDITIONAL",
    reject: "DISAGREE",
  }[state];

  return (
    <div className={`agent agent-${state}`}>
      <div className="agent-inner">
        <div className="agent-name">
          {name}
          <span> • {number}</span>
        </div>

        <div className="agent-status">
          <span>{statusText}</span>

        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [verdict, setVerdict] = useState<"approve" | "conditional" | "reject" | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [synthesis, setSynthesis] = useState("analysis pending");
  const [consensus, setConsensus] = useState("AWAITING DEBATE");
  const [debateLog, setDebateLog] = useState<string[]>(["awaiting analysis"]);

  const logRef = useRef<HTMLDivElement>(null);
  const synthesisRef = useRef<HTMLDivElement>(null);
  const logAutoScrollRef = useRef(true);
  const synthesisAutoScrollRef = useRef(true);

  function setAgentState(name: string, state: AgentState) {
    setAgents((current) =>
      current.map((agent) =>
        agent.name === name ? { ...agent, state } : agent
      )
    );
  }

  function scrollPanel(ref: RefObject<HTMLDivElement | null>, direction: number) {
    ref.current?.scrollBy({
      top: direction * 70,
      behavior: "smooth",
    });
  }

  function verdictToState(value: string | undefined): AgentState {
    const normalized = String(value ?? "").toLowerCase();
    if (["approve", "agree", "approved"].includes(normalized)) return "approve";
    if (["reject", "disagree", "rejected"].includes(normalized)) return "reject";
    if (normalized === "conditional") return "conditional";
    return "thinking";
  }

  async function typeLogEntry(entry: string) {
    setDebateLog((current) => [...current, ""]);
    for (let i = 1; i <= entry.length; i += 1) {
      setDebateLog((current) => {
        const next = [...current];
        next[next.length - 1] = entry.slice(0, i);
        return next;
      });
      if (i % 1 === 0) {
        await new Promise((resolve) => setTimeout(resolve, 12));
      }
    }
  }

  async function typeSynthesis(value: string) {
    setSynthesis("");
    for (let i = 1; i <= value.length; i += 1) {
      setSynthesis(value.slice(0, i));
      if (i % 1 === 0) {
        await new Promise((resolve) => setTimeout(resolve, 14));
      }
    }
  }

  useEffect(() => {
    if (logRef.current && logAutoScrollRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [debateLog]);

  useEffect(() => {
    if (synthesisRef.current && synthesisAutoScrollRef.current) {
      synthesisRef.current.scrollTop = synthesisRef.current.scrollHeight;
    }
  }, [synthesis]);

  async function analyze() {
    if (!question.trim() || isAnalyzing) return;

    setIsAnalyzing(true);
    setVerdict(null);
    setConfidence(null);
    setConsensus("AWAITING DEBATE");
    logAutoScrollRef.current = true;
    synthesisAutoScrollRef.current = true;
    setSynthesis("MAGI CORE PROCESSING");
    setDebateLog([]);
    setAgents(initialAgents.map((agent) => ({ ...agent, state: "thinking" })));

    try {
      const response = await fetch("http://localhost:8000/debate/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ question: question.trim() }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`MAGI backend returned HTTP ${response.status}.`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const processEvent = async (raw: string) => {
        const dataLines = raw
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim());

        if (!dataLines.length) return;

        let event: any;
        try {
          event = JSON.parse(dataLines.join("\n"));
        } catch {
          return;
        }

        switch (event.type) {
          case "analysis_started":
            await typeLogEntry("MAGI CORE INITIALIZED");
            await typeLogEntry(`AGENTS ONLINE: ${event.agents?.join(" / ") ?? "MELCHIOR / BALTHASAR / CASPER"}`);
            break;

          case "round_started":
            await typeLogEntry(`ROUND ${event.round}: ${event.label ?? "PROCESSING"}`);
            setAgents((current) => current.map((agent) => ({ ...agent, state: "thinking" })));
            break;

          case "decision":
            setAgentState(String(event.agent).toUpperCase(), verdictToState(event.verdict));
            await typeLogEntry(`${String(event.agent).toUpperCase()} → ${String(event.verdict).toUpperCase()} (${Math.round(Number(event.confidence ?? 0) * 100)}%)`);
            if (event.summary) {
              await typeLogEntry(`${String(event.agent).toUpperCase()}: ${event.summary}`);
            }
            break;

          case "message":
            await typeLogEntry(`${String(event.sender).toUpperCase()}${event.target ? ` → ${String(event.target).toUpperCase()}` : ""}: ${event.content ?? ""}`);
            break;

          case "agent_thinking":
            setAgentState(String(event.agent).toUpperCase(), "thinking");
            break;

          case "agent_error":
            await typeLogEntry(`${String(event.agent).toUpperCase()} ERROR: ${event.message ?? "UNKNOWN ERROR"}`);
            break;

          case "round_completed":
            await typeLogEntry(`ROUND ${event.round} COMPLETE`);
            if (event.round === 1) {
              // Keep all three Round 1 verdict colours visible before Round 2 starts.
              await new Promise((resolve) => setTimeout(resolve, 1200));
            } else if (event.round < 4) {
              await new Promise((resolve) => setTimeout(resolve, 500));
            }
            break;

          case "synthesis_started":
            await typeLogEntry("MAGI CENTRAL SYNTHESIS");
            setSynthesis("synthesizing...");
            break;

          case "synthesis_chunk":
            if (typeof event.content === "string") {
              setSynthesis((current) =>
                current === "synthesizing..." ? event.content : current + event.content
              );
            }
            break;

          case "synthesis":
            if (typeof event.content === "string") {
              await typeSynthesis(event.content);
            }
            break;

          case "synthesis_error":
            await typeLogEntry(`SYNTHESIS ERROR: ${event.message ?? "UNKNOWN ERROR"}`);
            setSynthesis("synthesis unavailable");
            break;

          case "completed": {
            const finalVerdict = String(event.final_verdict ?? "").toLowerCase();
            if (["approve", "conditional", "reject"].includes(finalVerdict)) {
              setVerdict(finalVerdict as "approve" | "conditional" | "reject");
            }
            const finalDecisions = Array.isArray(event.decisions) ? event.decisions : [];

            const finalConfidence =
              typeof event.final_confidence === "number"
                ? Math.max(0, Math.min(1, event.final_confidence))
                : finalDecisions.length
                  ? finalDecisions.reduce(
                      (sum: number, decision: { confidence?: number }) =>
                        sum + Number(decision.confidence ?? 0),
                      0
                    ) / finalDecisions.length
                  : null;

            setConfidence(
              finalConfidence !== null
                ? Math.round(finalConfidence * 100)
                : null
            );

            const verdictText =
              finalVerdict === "approve"
                ? "AGREE"
                : finalVerdict === "reject"
                  ? "DISAGREE"
                  : finalVerdict === "conditional"
                    ? "CONDITIONAL"
                    : "UNRESOLVED";

            const agreeingAgents = finalDecisions.filter(
              (decision: { verdict?: string }) =>
                String(decision.verdict ?? "").toLowerCase() === finalVerdict
            ).length;

            setConsensus(
              finalDecisions.length
                ? `${verdictText}. ${agreeingAgents} OF ${finalDecisions.length} MAGI UNITS CONVERGED ON THE FINAL POSITION.`
                : "NO CONSENSUS REACHED."
            );

            // The current backend returns the final agent summaries in the
            // completed event. Turn those real results into the synthesis.
            if (finalDecisions.length) {
              const synthesisText = finalDecisions
                .map(
                  (decision: { agent: string; summary: string }) =>
                    `${decision.agent}: ${decision.summary}`
                )
                .join(" | ");

              await typeSynthesis(synthesisText);
            } else {
              await typeSynthesis("MAGI synthesis unavailable.");
            }

            await typeLogEntry("MAGI SYNTHESIS COMPLETE");
            await typeLogEntry(`FINAL VERDICT: ${verdictText}`);
            break;
          }

          case "error":
            throw new Error(event.message ?? "Unknown MAGI backend error.");
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        for (const rawEvent of events) await processEvent(rawEvent);
      }

      if (buffer.trim()) await processEvent(buffer);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to reach MAGI backend.";
      await typeLogEntry(`SYSTEM ERROR: ${message}`);
      setSynthesis("analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  }

  const verdictLabel = verdict
    ? {
        approve: "AGREE",
        conditional: "CONDITIONAL",
        reject: "DISAGREE",
      }[verdict]
    : "---";

  return (
    <main className="magi-screen">
      {/* =========================================
          TOP BAR
      ========================================= */}

      <header className="topbar">
        <div className="brand">
          <span className="brand-name">
            MAGI SYSTEM
          </span>

          <span className="version">
            VER.1.0
          </span>
        </div>

        <div className="online">
          ONLINE
        </div>
      </header>

      {/* =========================================
          MAIN AREA
      ========================================= */}

      <section className="main-grid">
        {/* =====================================
            QUESTION
        ===================================== */}

        <aside className="question-section">
          <div className="section-title">
            QUESTION
          </div>

          <div className="question-box">
            <span className="prompt">
              &gt;
            </span>

            <textarea
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              placeholder="ENTER QUESTION..."
              spellCheck={false}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                  event.preventDefault();
                  event.currentTarget.scrollBy({
                    top: event.key === "ArrowDown" ? 100 : -100,
                    behavior: "smooth",
                  });
                }
              }}
            />
          </div>

          <button
            className={`analyze-button ${
              isAnalyzing ? "analyzing" : ""
            }`}
            onClick={analyze}
            disabled={
              isAnalyzing || !question.trim()
            }
          >
            <span>
              {isAnalyzing
                ? "ANALYZING"
                : "ANALYZE"}
            </span>

          </button>
        </aside>

        {/* =====================================
            MAGI CORE
        ===================================== */}

        <section className="core-section">
          {/* BALTHASAR */}

          <div className="agent-top">
            <AgentPanel
              name={agents[0].name}
              number={agents[0].number}
              state={agents[0].state}
            />
          </div>

          {/* CASPER + MELCHIOR */}

          <div className="agent-bottom">
            <AgentPanel
              name={agents[1].name}
              number={agents[1].number}
              state={agents[1].state}
            />

            <AgentPanel
              name={agents[2].name}
              number={agents[2].number}
              state={agents[2].state}
            />
          </div>

          {/* MAGI LABEL */}

          <div className="magi-core">
            <span>MAGI</span>
          </div>
        </section>

        {/* =====================================
            RIGHT SIDE
        ===================================== */}

        <aside className="right-section">
          {/* SYSTEM STATUS */}

          <div className="hud-panel status-panel">
            <div className="hud-title">
              SYSTEM STATUS
            </div>

            <div className="terminal-lines">
              <p>
                &gt; MAGI CORE SYSTEM :
                <span> ONLINE</span>
              </p>

              <p>
                &gt; ALL MODULES :
                <span> NOMINAL</span>
              </p>

              <p>
                &gt; LINK STATUS :
                <span> STABLE</span>
              </p>
            </div>
          </div>

          {/* DEBATE LOG */}

          <div className="hud-panel debate-panel">
            <div className="hud-title">
              DEBATE LOG
            </div>

            <div
              className="terminal-log keyboard-scroll"
              ref={logRef}
              tabIndex={0}
              onScroll={(event) => {
                const element = event.currentTarget;
                logAutoScrollRef.current =
                  element.scrollHeight - element.scrollTop - element.clientHeight < 8;
              }}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                  event.preventDefault();
                  logAutoScrollRef.current = false;
                  scrollPanel(logRef, event.key === "ArrowDown" ? 1 : -1);
                }
              }}
            >
              {debateLog.map((entry, index) => (
                <p key={`${entry}-${index}`}>
                  &gt; {entry}
                  {index === debateLog.length - 1 &&
                    isAnalyzing && (
                      <span className="cursor">
                        _
                      </span>
                    )}
                </p>
              ))}
            </div>
          </div>
        </aside>
      </section>

      {/* =========================================
          BOTTOM AREA
      ========================================= */}

      <section className="bottom-grid">
        {/* FINAL VERDICT */}

        <div
          className={`verdict-panel ${
            verdict
              ? `verdict-${verdict}`
              : ""
          }`}
        >
          <div className="hud-title">
            FINAL VERDICT
          </div>

          <div className="verdict-value">
            {verdictLabel}
          </div>

          <div className="confidence-label">
            CONFIDENCE
          </div>

          <div className="confidence-value">
            {confidence !== null
              ? `${confidence}%`
              : "--%"}
          </div>

          <div className="confidence-bar">
            <div
              style={{
                width:
                  confidence !== null
                    ? `${confidence}%`
                    : "0%",
              }}
            />
          </div>
        </div>

        {/* SYNTHESIS */}

        <div className="synthesis-panel">
          <div className="hud-title">
            MAGI SYNTHESIS
          </div>

          <div
            className="synthesis-content keyboard-scroll"
            ref={synthesisRef}
            tabIndex={0}
            onScroll={(event) => {
              const element = event.currentTarget;
              synthesisAutoScrollRef.current =
                element.scrollHeight - element.scrollTop - element.clientHeight < 8;
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                synthesisAutoScrollRef.current = false;
                scrollPanel(synthesisRef, event.key === "ArrowDown" ? 1 : -1);
              }
            }}
          >
            <p>
              &gt; {synthesis}
              {isAnalyzing && (
                <span className="cursor">
                  _
                </span>
              )}
            </p>
          </div>
        </div>

        {/* CONSENSUS */}

        <div className="legend-panel consensus-panel">
          <div className="hud-title">
            CONSENSUS
          </div>

          <div className="consensus-content">
            {consensus}
          </div>
        </div>

      </section>
      <style jsx global>{`
        .keyboard-scroll {
          scrollbar-width: none;
          -ms-overflow-style: none;
          overflow-y: auto;
        }

        .keyboard-scroll::-webkit-scrollbar {
          display: none;
          width: 0;
          height: 0;
        }

        .consensus-panel .consensus-content {
          color: #65ff65;
          line-height: 1.7;
          letter-spacing: 0.06em;
          font-size: 0.78rem;
          text-transform: uppercase;
          padding: 18px 20px;
          display: flex;
          align-items: center;
          min-height: 130px;
        }
      `}</style>
    </main>
  );
}