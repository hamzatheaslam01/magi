"use client";

import { useEffect, useRef, useState, type RefObject } from "react";

type AgentState = "idle" | "thinking" | "approve" | "conditional" | "reject";

type Agent = {
  name: string;
  number: string;
  state: AgentState;
};

const AGENT_JP: Record<string, string> = {
  BALTHASAR: "バルタザール",
  CASPER: "カスパル",
  MELCHIOR: "メルキオール",
};

const STATUS_TEXT: Record<AgentState, string> = {
  idle: "STANDBY",
  thinking: "THINKING",
  approve: "AGREE",
  conditional: "CONDITIONAL",
  reject: "DISAGREE",
};

const STATUS_JP: Record<AgentState, string> = {
  idle: "待機中",
  thinking: "思考中",
  approve: "同意",
  conditional: "条件付",
  reject: "拒否",
};

const initialAgents: Agent[] = [
  { name: "BALTHASAR", number: "2", state: "idle" },
  { name: "CASPER", number: "3", state: "idle" },
  { name: "MELCHIOR", number: "1", state: "idle" },
];

function AgentBlock({
  name,
  number,
  state,
  position,
}: {
  name: string;
  number: string;
  state: AgentState;
  position: "top" | "bottom-left" | "bottom-right";
}) {
  return (
    <div className={`agent-block agent-block--${position} state-${state}`}>
      <div className="agent-chip">
        <div className="agent-chip-name">
          {name}
          <span className="agent-chip-number"> {number}</span>
        </div>
        <div className="agent-chip-jp">{AGENT_JP[name]}</div>
      </div>

      <div className="agent-readout">
        <span className="agent-readout-label">
          {STATUS_TEXT[state]}
          <br />
          {STATUS_JP[state]}
        </span>
        <span className="agent-readout-hatch" />
      </div>
    </div>
  );
}

function EqBars({ active }: { active: boolean }) {
  const bars = Array.from({ length: 10 });

  return (
    <div className={`eq-bars ${active ? "is-active" : ""}`}>
      {bars.map((_, index) => (
        <span
          key={index}
          className="eq-bar"
          style={{ animationDelay: `${index * 80}ms` }}
        />
      ))}
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
      current.map((agent) => (agent.name === name ? { ...agent, state } : agent))
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

  // The backend already streams events progressively. Rendering each event
  // immediately keeps the SSE reader responsive instead of blocking it behind
  // a frontend typing animation.
  const logQueueRef = useRef<string[]>([]);
  const logTypingRef = useRef(false);
  const synthesisAnimationRef = useRef(0);

  function typeLogEntry(entry: string) {
    logQueueRef.current.push(entry);
    processLogQueue();
  }

  async function processLogQueue() {
    if (logTypingRef.current) return;

    logTypingRef.current = true;

    try {
      while (logQueueRef.current.length > 0) {
        const entry = logQueueRef.current.shift();

        if (!entry) continue;

        setDebateLog((current) => [...current, ""]);

        let index = 0;

        while (index < entry.length) {
          index = Math.min(index + 4, entry.length);

          const partial = entry.slice(0, index);

          setDebateLog((current) => {
            if (!current.length) return current;

            const updated = [...current];
            updated[updated.length - 1] = partial;
            return updated;
          });

          await new Promise((resolve) => setTimeout(resolve, 4));
        }
      }
    } finally {
      logTypingRef.current = false;
    }
  }

  function typeSynthesis(value: string) {
    const animationId = ++synthesisAnimationRef.current;

    setSynthesis("");

    let index = 0;

    const typeNext = () => {
      if (animationId !== synthesisAnimationRef.current) {
        return;
      }

      if (index >= value.length) {
        return;
      }

      index += 1;

      setSynthesis(value.slice(0, index));

      window.setTimeout(typeNext, 4);
    };

    typeNext();
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
    setDebateLog([]);
    setAgents(initialAgents.map((agent) => ({ ...agent, state: "thinking" })));

    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "/api";

      const response = await fetch(`${apiBaseUrl}/debate/stream`, {
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
            typeLogEntry("MAGI CORE INITIALIZED");
            typeLogEntry(
              `AGENTS ONLINE: ${event.agents?.join(" / ") ?? "MELCHIOR / BALTHASAR / CASPER"}`
            );
            break;

          case "round_started":
            typeLogEntry(`ROUND ${event.round}: ${event.label ?? "PROCESSING"}`);
            setAgents((current) => current.map((agent) => ({ ...agent, state: "thinking" })));
            break;

          case "decision":
            setAgentState(String(event.agent).toUpperCase(), verdictToState(event.verdict));
            typeLogEntry(
              `${String(event.agent).toUpperCase()} \u2192 ${String(event.verdict).toUpperCase()} (${Math.round(
                Number(event.confidence ?? 0) * 100
              )}%)`
            );
            if (event.summary) {
              typeLogEntry(
                `${String(event.agent).toUpperCase()}: ${String(event.summary)}`
              );
            }
            break;

          case "message":
            typeLogEntry(
              `${String(event.sender).toUpperCase()}${
                event.target ? ` \u2192 ${String(event.target).toUpperCase()}` : ""
              }: ${event.content ?? ""}`
            );
            break;

          case "agent_thinking":
            setAgentState(String(event.agent).toUpperCase(), "thinking");
            break;

          case "agent_error":
            typeLogEntry(`${String(event.agent).toUpperCase()} ERROR: ${event.message ?? "UNKNOWN ERROR"}`);
            break;

          case "round_completed":
            typeLogEntry(`ROUND ${event.round} COMPLETE`);

            if (event.round === 1) {
              // Give the UI time to display all three Round 1 verdict colours
              // before Round 2 begins.
              await new Promise((resolve) => setTimeout(resolve, 1500));
            } else if (event.round < 4) {
              await new Promise((resolve) => setTimeout(resolve, 500));
            }

            break;

          case "synthesis_started":
            typeLogEntry("MAGI CENTRAL SYNTHESIS");
            break;

          case "synthesis_chunk":
            if (typeof event.content === "string") {
              setSynthesis((current) => current + event.content);
            }
            break;

          case "completed": {
            const finalVerdict = String(event.final_verdict ?? "").toLowerCase();

            if (finalVerdict === "approve" || finalVerdict === "conditional" || finalVerdict === "reject") {
              setVerdict(finalVerdict);
            }

            const finalDecisions = Array.isArray(event.decisions) ? event.decisions : [];

            const finalConfidence =
              typeof event.final_confidence === "number"
                ? Math.max(0, Math.min(1, event.final_confidence))
                : finalDecisions.length
                  ? finalDecisions.reduce(
                      (sum: number, decision: { confidence?: number }) => sum + Number(decision.confidence ?? 0),
                      0
                    ) / finalDecisions.length
                  : null;

            setConfidence(finalConfidence !== null ? Math.round(finalConfidence * 100) : null);

            const verdictText =
              finalVerdict === "approve"
                ? "AGREE"
                : finalVerdict === "reject"
                  ? "DISAGREE"
                  : finalVerdict === "conditional"
                    ? "CONDITIONAL"
                    : "UNRESOLVED";

            const agreeingAgents = finalDecisions.filter(
              (decision: { verdict?: string }) => String(decision.verdict ?? "").toLowerCase() === finalVerdict
            ).length;

            setConsensus(
              finalDecisions.length
                ? `${verdictText}. ${agreeingAgents} OF ${finalDecisions.length} MAGI UNITS CONVERGED ON THE FINAL POSITION.`
                : "NO CONSENSUS REACHED."
            );

            typeLogEntry("MAGI SYNTHESIS COMPLETE");
            typeLogEntry(`FINAL VERDICT: ${verdictText}`);

            break;
          }

          case "synthesis":
            if (typeof event.content === "string") {
              typeSynthesis(event.content);
            }
            break;

          case "synthesis_error":
            typeLogEntry(`SYNTHESIS ERROR: ${event.message ?? "UNKNOWN ERROR"}`);
            setSynthesis("synthesis unavailable");
            break;

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
      typeLogEntry(`SYSTEM ERROR: ${message}`);
      setSynthesis("analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  }

  const verdictLabel = verdict
    ? ({
        approve: "AGREE",
        conditional: "CONDITIONAL",
        reject: "DISAGREE",
      } as const)[verdict]
    : "---";

  return (
    <>
      <div className="crt-overlay" />

      <main className="magi-app">
        {/* ============================= HEADER ============================= */}
        <header className="app-header">
          <div className="header-brand">
            <div className="header-warning">
              <span className="header-warning-text">NERV ONLY</span>
              <span className="header-warning-marks">
                <span className="header-warning-mark" />
                <span className="header-warning-mark" />
                <span className="header-warning-mark" />
                <span className="header-warning-mark" />
              </span>
            </div>

            <div className="header-title-row">
              <h1 className="header-title">MAGI SYSTEM</h1>
              <span className="header-version">VER.1.0</span>
            </div>
          </div>

          <div className="header-center">
            <div className="header-center-jp">内部管理システム</div>
            <div className="header-center-sub">MAGI - MELCHIOR / BALTHASAR / CASPER</div>
          </div>

          <div className="header-status">
            <span className="header-status-text">ONLINE</span>
          </div>
        </header>

        {/* ============================== MAIN =============================== */}
        <section className="app-main">
          {/* -------------------------- QUESTION -------------------------- */}
          <aside className="panel question-panel">
            <div className="panel-header">
              <span className="panel-title">QUESTION</span>
              <span className="panel-deco">///</span>
            </div>

            <div className="question-body">
              <img
                src="/nerv-logo.png"
                alt=""
                className="question-watermark-logo"
              />
              <span className="question-prompt">&gt;</span>
              <textarea
                className="question-textarea"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="ENTER QUERY PARAMETERS..."
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
              className={`analyze-button ${isAnalyzing ? "is-analyzing" : ""}`}
              onClick={analyze}
              disabled={isAnalyzing || !question.trim()}
            >
              {isAnalyzing ? "ANALYZING" : "ANALYZE"}
            </button>

            <div className={`analyzing-box ${isAnalyzing ? "is-active" : "is-idle"}`}>
              <div className="analyzing-row">
                <span className="analyzing-label">{isAnalyzing ? "ANALYZING..." : "STANDBY"}</span>
                <span className="analyzing-jp">{isAnalyzing ? "分析中" : "待機中"}</span>
              </div>
              <div className="analyzing-divider" />
              <EqBars active={isAnalyzing} />
            </div>
          </aside>

          {/* --------------------------- MAGI CORE -------------------------- */}
          <section className="panel core-panel">
            <div className="core-frame">
              <div className="core-divider" />

              <AgentBlock name={agents[0].name} number={agents[0].number} state={agents[0].state} position="top" />

              <div className="agent-block--bottom">
                <AgentBlock
                  name={agents[1].name}
                  number={agents[1].number}
                  state={agents[1].state}
                  position="bottom-left"
                />
                <AgentBlock
                  name={agents[2].name}
                  number={agents[2].number}
                  state={agents[2].state}
                  position="bottom-right"
                />
              </div>

              <div className="magi-diamond-wrap">
                <span className="magi-tick magi-tick-top" />
                <span className="magi-tick magi-tick-bottom" />
                <div className="magi-diamond" />
                <div className="magi-diamond-inner" />
                <div className="magi-diamond-label">
                  <span className="magi-diamond-text">MAGI</span>
                  <span className="magi-diamond-jp">マギ</span>
                </div>
              </div>
            </div>
          </section>

          {/* --------------------------- RIGHT SIDE -------------------------- */}
          <aside className="right-column">
            <div className="panel status-panel">
              <div className="panel-header">
                <span className="panel-title">SYSTEM STATUS</span>
                <span className="panel-deco">///</span>
              </div>

              <div className="status-lines">
                <p className="status-line">
                  <span>&gt; MAGI CORE SYSTEM:</span>
                  <span className="status-line-value">ONLINE</span>
                </p>
                <p className="status-line">
                  <span>&gt; ALL MODULES:</span>
                  <span className="status-line-value">NOMINAL</span>
                </p>
                <p className="status-line">
                  <span>&gt; LINK STATUS:</span>
                  <span className="status-line-value">STABLE</span>
                </p>
              </div>
            </div>

            <div className="panel debate-panel">
              <div className="debate-watermark">
                <img src="/nerv-logo.png" alt="" />
              </div>
              <div className="panel-header">
                <span className="panel-title">DEBATE LOG</span>
                <span className="panel-deco">///</span>
              </div>

              <div
                className="debate-log"
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
                {debateLog.map((entry, index) => {
                  const isIdleMessage =
                    entry === "awaiting analysis" ||
                    entry === "analysis pending";

                  return (
                    <p
                      key={`${entry}-${index}`}
                      className={isIdleMessage ? "debate-idle-message" : ""}
                    >
                      &gt; {entry}
                      {isIdleMessage && (
                        <span className="idle-dots" aria-hidden="true">
                          <span>.</span>
                          <span>.</span>
                          <span>.</span>
                        </span>
                      )}

                      {index === debateLog.length - 1 && isAnalyzing && !isIdleMessage && (
                        <span className="debate-cursor">_</span>
                      )}
                    </p>
                  );
                })}
              </div>
            </div>
          </aside>
        </section>

        {/* ============================= BOTTOM ============================== */}
        <section className="app-bottom">
          <div className={`panel verdict-panel state-${verdict ?? "idle"}`}>
            <div className="panel-header">
              <span className="panel-title">FINAL VERDICT</span>
              <span className="panel-deco">///</span>
            </div>

            <div className={`verdict-box ${verdict ? `state-${verdict}` : ""}`}>
              <span className="verdict-value-text">{verdictLabel}</span>
            </div>

            <div className="confidence-row">
              <span className="confidence-label">
                CONFIDENCE LEVEL
                <span className="confidence-jp">信頼度</span>
              </span>
              <span className="confidence-value">{confidence !== null ? `${confidence}%` : "--%"}</span>
            </div>

            <div className="confidence-bar-track">
              <div
                className="confidence-bar-fill"
                style={{ width: confidence !== null ? `${confidence}%` : "0%" }}
              />
            </div>
          </div>

          <div className="panel synthesis-panel">
            <div className="panel-header">
              <span className="panel-title">MAGI SYNTHESIS</span>
              <span className="panel-deco">///</span>
            </div>

            <div className="synthesis-watermark">
              <img
                src="/nerv-logo.png"
                alt="NERV"
                className="synthesis-watermark-logo"
              />
            </div>

            <div
              className="synthesis-body"
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
              <p className={synthesis === "analysis pending" ? "synthesis-idle-message" : ""}>
                &gt; {synthesis}

                {synthesis === "analysis pending" && (
                  <span className="idle-dots" aria-hidden="true">
                    <span>.</span>
                    <span>.</span>
                    <span>.</span>
                  </span>
                )}

                {isAnalyzing && synthesis !== "analysis pending" && (
                  <span className="debate-cursor">_</span>
                )}
              </p>
            </div>
          </div>

          <div className="panel consensus-panel">
            <div className="panel-header">
              <span className="panel-title">CONSENSUS</span>
              <span className="panel-deco">///</span>
            </div>

            <div className="consensus-body">
              <span
                className={`consensus-main ${
                  consensus === "AWAITING DEBATE" ? "consensus-idle-message" : ""
                }`}
              >
                {consensus}

                {consensus === "AWAITING DEBATE" && (
                  <span className="idle-dots" aria-hidden="true">
                    <span>.</span>
                    <span>.</span>
                    <span>.</span>
                  </span>
                )}
              </span>
            </div>

            <div className="consensus-dots">
              <span className="consensus-dot" />
              <span className="consensus-dot" />
              <span className="consensus-dot" />
            </div>
          </div>
        </section>

        {/* ============================= FOOTER =============================== */}
        <footer className="app-footer">
          <span>
            <span className="footer-dot" />
            MAGI CONNECTED
          </span>
          <span>AUTHORIZED PERSONNEL ONLY ////////</span>
        </footer>
      </main>
    </>
  );
}