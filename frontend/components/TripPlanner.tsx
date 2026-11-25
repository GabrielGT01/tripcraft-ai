import {
  FormEvent,
  useMemo,
  useState,
} from "react";

import {
  ArrowRight,
  Check,
  Download,
  LoaderCircle,
  MapPin,
  Plane,
  RefreshCcw,
  Sparkles,
  Users,
  WalletCards,
} from "lucide-react";

import MarkdownPlan from "./MarkdownPlan";

import {
  resumeTrip,
  startTrip,
} from "../lib/api";

import {
  createFreshThreadId,
  getOrCreateThreadId,
} from "../lib/session";

import type {
  ClarifyInterrupt,
  DecisionInterrupt,
  ResumePayload,
  TripResponse,
} from "../lib/types";


const samplePrompts = [
  {
    label: "Lisbon",
    value:
      "Cologne to Lisbon, 2026-11-12 to 2026-11-18, 2 adults, budget 1500 EUR, I like food and history, hotel near the city centre.",
  },
  {
    label: "Rome",
    value:
      "Cologne to Rome, 2026-12-03 to 2026-12-08, 1 adult, budget 1200 EUR, I like museums, food and history.",
  },
  {
    label: "Mallorca",
    value:
      "Cologne to Mallorca, 2026-12-15 to 2026-12-25, 1 adult, budget 1500 EUR, I like museums, food, nightlife and history.",
  },
];


function formatDate(
  value?: string | null,
) {
  if (!value) {
    return "Not set";
  }

  const date = new Date(
    `${value}T00:00:00`,
  );

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    "en",
    {
      day: "numeric",
      month: "short",
      year: "numeric",
    },
  ).format(date);
}


export default function TripPlanner() {
  const [question, setQuestion] =
    useState("");

  const [
    clarification,
    setClarification,
  ] = useState("");

  const [revision, setRevision] =
    useState("");

  const [result, setResult] =
    useState<TripResponse | null>(null);

  const [loading, setLoading] =
    useState(false);

  const [
    loadingMessage,
    setLoadingMessage,
  ] = useState(
    "Planning your trip",
  );

  const [error, setError] =
    useState<string | null>(null);


  const details =
    result?.travel_details;

  const flight =
    details?.flight;


  const routeTitle = useMemo(() => {
    if (
      !flight?.origin &&
      !flight?.destination
    ) {
      return "Your trip";
    }

    return (
      `${flight?.origin || "Origin"} → ` +
      `${flight?.destination || "Destination"}`
    );
  }, [
    flight?.origin,
    flight?.destination,
  ]);


  async function onStart(
    event: FormEvent,
  ) {
    event.preventDefault();

    const value = question.trim();

    if (!value) {
      return;
    }

    setError(null);

    setLoadingMessage(
      "Researching your trip",
    );

    setLoading(true);

    try {
      const threadId =
        getOrCreateThreadId();

      const response =
        await startTrip(
          threadId,
          value,
        );

      setResult(response);

    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not start the trip.",
      );

    } finally {
      setLoading(false);
    }
  }


  async function onResume(
    payload: ResumePayload,
    message: string,
  ) {
    setError(null);
    setLoadingMessage(message);
    setLoading(true);

    try {
      const threadId =
        getOrCreateThreadId();

      const response =
        await resumeTrip(
          threadId,
          payload,
        );

      setResult(response);
      setClarification("");
      setRevision("");

    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not continue the trip.",
      );

    } finally {
      setLoading(false);
    }
  }


  function resetUi() {
    setResult(null);
    setQuestion("");
    setClarification("");
    setRevision("");
    setError(null);
  }


  function startFreshConversation() {
    createFreshThreadId();
    resetUi();
  }


  function downloadPlan() {
    const content =
      result?.saved_file_content ||
      result?.plan;

    if (!content) {
      return;
    }

    const blob = new Blob(
      [content],
      {
        type:
          "text/plain;charset=utf-8",
      },
    );

    const url =
      URL.createObjectURL(blob);

    const link =
      document.createElement("a");

    link.href = url;

    link.download =
      result?.saved_filename ||
      "trip-plan.txt";

    document.body.appendChild(link);

    link.click();
    link.remove();

    URL.revokeObjectURL(url);
  }


  const clarify: ClarifyInterrupt | null =
    result?.interrupt_type === "clarify"
      ? (result.interrupt as ClarifyInterrupt)
      : null;


  const decision: DecisionInterrupt | null =
    result?.interrupt_type === "decision"
      ? (result.interrupt as DecisionInterrupt)
      : null;


  return (
    <main className="planner-shell">
      <nav className="app-nav">
        <button
          className="brand-button"
          type="button"
          onClick={resetUi}
        >
          <span className="brand-icon">
            <Plane size={20} />
          </span>

          <span>TripCraft AI</span>
        </button>

        <div className="nav-right">
          <div className="signed-user">
            <span className="signed-dot" />

            <span>
              Browser conversation
            </span>
          </div>

          <button
            className="ghost-button"
            type="button"
            onClick={
              startFreshConversation
            }
          >
            New conversation
          </button>
        </div>
      </nav>


      {!result ? (
        <section className="planner-hero">
          <div className="hero-kicker">
            <Sparkles size={15} />
            LANGGRAPH · MCP · FASTAPI
          </div>

          <h1>
            Your trip, researched
            <span> in one place.</span>
          </h1>

          <p className="hero-description">
            Tell TripCraft where you want
            to go. It researches live
            flight options, places to stay
            and things worth doing, then
            lets you revise the plan
            before you approve it.
          </p>

          <form
            className="trip-composer"
            onSubmit={onStart}
          >
            <label htmlFor="trip-question">
              Describe your trip
            </label>

            <textarea
              id="trip-question"
              value={question}
              onChange={(event) =>
                setQuestion(
                  event.target.value,
                )
              }
              rows={6}
              placeholder="Example: Cologne to Lisbon, 12–18 November 2026, 2 adults, budget €1,500. We like food and history."
            />

            <div className="prompt-row">
              {samplePrompts.map(
                (prompt) => (
                  <button
                    key={prompt.label}
                    type="button"
                    className="prompt-chip"
                    onClick={() =>
                      setQuestion(
                        prompt.value,
                      )
                    }
                  >
                    {prompt.label}
                  </button>
                ),
              )}
            </div>

            <div className="composer-footer">
              <div className="research-note">
                <span className="live-indicator" />
                Live flight + destination
                research
              </div>

              <button
                className="primary-button"
                type="submit"
              >
                Plan my trip
                <ArrowRight size={18} />
              </button>
            </div>
          </form>

          {error && (
            <div className="error-banner">
              {error}
            </div>
          )}

          <div className="trust-grid">
            <div>
              <Plane size={19} />

              <strong>
                Live flights
              </strong>

              <span>
                Flight research through
                MCP tools
              </span>
            </div>

            <div>
              <MapPin size={19} />

              <strong>
                Local research
              </strong>

              <span>
                Hotels, food, activities
                and events
              </span>
            </div>

            <div>
              <RefreshCcw size={19} />

              <strong>
                Human control
              </strong>

              <span>
                Revise before approving
                the final plan
              </span>
            </div>
          </div>
        </section>

      ) : (
        <section className="workspace">
          <div className="workspace-heading">
            <div>
              <span className="workspace-label">
                YOUR TRIP
              </span>

              <h1>{routeTitle}</h1>

              <p>
                {formatDate(
                  flight?.departure_date,
                )}

                {flight?.return_date
                  ? ` — ${formatDate(
                      flight.return_date,
                    )}`
                  : ""}
              </p>
            </div>

            <button
              className="secondary-button"
              onClick={resetUi}
              type="button"
            >
              <RefreshCcw size={16} />
              New request
            </button>
          </div>


          <div className="summary-grid">
            <div className="summary-card">
              <Plane size={18} />
              <span>Trip type</span>

              <strong>
                {flight?.trip_type
                  ?.replaceAll(
                    "_",
                    " ",
                  ) || "Unknown"}
              </strong>
            </div>

            <div className="summary-card">
              <Users size={18} />
              <span>Travellers</span>

              <strong>
                {details?.adults ?? 1}
              </strong>
            </div>

            <div className="summary-card">
              <WalletCards size={18} />
              <span>Budget</span>

              <strong>
                {details?.budget_amount
                  ? (
                      `${details.budget_amount.toLocaleString()} ` +
                      `${details.budget_currency || ""}`
                    )
                  : "Not specified"}
              </strong>
            </div>

            <div className="summary-card">
              <Sparkles size={18} />
              <span>Interests</span>

              <strong>
                {details?.interests?.length
                  ? details.interests.join(
                      ", ",
                    )
                  : "Open"}
              </strong>
            </div>
          </div>


          {error && (
            <div className="error-banner">
              {error}
            </div>
          )}


          {clarify && (
            <section className="interaction-card">
              <div className="interaction-icon">
                ?
              </div>

              <div>
                <span className="workspace-label">
                  A FEW MORE DETAILS
                </span>

                <h2>
                  {clarify.question ||
                    "I need a little more information."}
                </h2>

                <ul className="missing-list">
                  {(
                    clarify.missing || []
                  ).map((item) => (
                    <li key={item}>
                      {item}
                    </li>
                  ))}
                </ul>

                <form
                  className="inline-form"
                  onSubmit={(event) => {
                    event.preventDefault();

                    const value =
                      clarification.trim();

                    if (!value) {
                      return;
                    }

                    void onResume(
                      {
                        message: value,
                      },
                      "Checking your details",
                    );
                  }}
                >
                  <input
                    value={
                      clarification
                    }
                    onChange={(event) =>
                      setClarification(
                        event.target.value,
                      )
                    }
                    placeholder="Type the missing information…"
                  />

                  <button
                    className="primary-button"
                    type="submit"
                  >
                    Continue
                    <ArrowRight size={17} />
                  </button>
                </form>
              </div>
            </section>
          )}


          {result.plan && (
            <section className="plan-card">
              <div className="plan-header">
                <div>
                  <span className="workspace-label">
                    RESEARCHED PLAN
                  </span>

                  <h2>
                    Your travel options
                  </h2>
                </div>

                <span className="researched-badge">
                  <span className="live-indicator" />
                  Researched
                </span>
              </div>

              <MarkdownPlan
                content={result.plan}
              />
            </section>
          )}


          {decision && (
            <section className="interaction-card">
              <div className="interaction-icon">
                <Check size={20} />
              </div>

              <div>
                <span className="workspace-label">
                  YOUR DECISION
                </span>

                <h2>
                  {decision.question ||
                    "What would you like to do?"}
                </h2>

                <label
                  className="revision-label"
                  htmlFor="revision"
                >
                  Want anything changed?
                </label>

                <textarea
                  id="revision"
                  className="revision-box"
                  value={revision}
                  onChange={(event) =>
                    setRevision(
                      event.target.value,
                    )
                  }
                  rows={4}
                  placeholder="Example: Make the trip cheaper, or find a hotel closer to the airport."
                />

                <div className="decision-row">
                  <button
                    className="success-button"
                    type="button"
                    onClick={() =>
                      void onResume(
                        {
                          action: "approve",
                        },
                        "Saving your travel plan",
                      )
                    }
                  >
                    <Check size={17} />
                    Approve & save
                  </button>

                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => {
                      const value =
                        revision.trim();

                      if (!value) {
                        setError(
                          "Describe what you want changed first.",
                        );

                        return;
                      }

                      void onResume(
                        {
                          action: "revise",
                          message: value,
                        },
                        "Researching your changes",
                      );
                    }}
                  >
                    <RefreshCcw size={16} />
                    Revise
                  </button>

                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() =>
                      void onResume(
                        {
                          action: "inquire",
                        },
                        "Finishing your trip",
                      )
                    }
                  >
                    Keep & finish
                  </button>
                </div>
              </div>
            </section>
          )}


          {result.status === "finished" && (
            <section className="complete-card">
              <div className="complete-icon">
                <Check size={22} />
              </div>

              <div>
                <span className="workspace-label">
                  TRIP COMPLETE
                </span>

                <h2>
                  Your plan is ready.
                </h2>

                <p>
                  {result.saved_filename
                    ? (
                        `Saved as ` +
                        `${result.saved_filename}.`
                      )
                    : (
                        "The planning workflow " +
                        "is complete."
                      )}
                </p>
              </div>

              {(
                result.saved_file_content ||
                result.plan
              ) && (
                <button
                  className="primary-button"
                  onClick={downloadPlan}
                  type="button"
                >
                  <Download size={17} />
                  Download .txt
                </button>
              )}
            </section>
          )}
        </section>
      )}


      {loading && (
        <div className="loading-overlay">
          <div className="loading-card">
            <span className="loading-icon">
              <LoaderCircle size={27} />
            </span>

            <h2>
              {loadingMessage}
            </h2>

            <p>
              TripCraft is calling the
              travel tools and continuing
              your workflow.
            </p>

            <div className="loading-line">
              <span />
            </div>
          </div>
        </div>
      )}
    </main>
  );
}