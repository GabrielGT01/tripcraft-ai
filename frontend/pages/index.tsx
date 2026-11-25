import Head from "next/head";
import Link from "next/link";
import {
  ArrowRight,
  Globe2,
  MapPinned,
  Plane,
  Sparkles,
} from "lucide-react";

export default function Home() {
  return (
    <>
      <Head>
        <title>
          TripCraft AI — AI Travel Planner
        </title>

        <meta
          name="description"
          content="Next.js, FastAPI, LangGraph and MCP travel planner."
        />
      </Head>

      <main className="landing-page">
        <nav className="landing-nav">
          <Link
            href="/"
            className="brand-link"
          >
            <span className="brand-icon">
              <Plane size={20} />
            </span>

            <span>TripCraft AI</span>
          </Link>

          <div className="landing-actions">
            <Link
              href="/product/"
              className="primary-link-button"
            >
              Open planner
              <ArrowRight size={17} />
            </Link>
          </div>
        </nav>

        <section className="landing-hero">
          <div className="hero-kicker">
            <Sparkles size={15} />
            LANGGRAPH · MCP · FASTAPI
          </div>

          <h1>
            One conversation.
            <br />
            <span>Your whole trip.</span>
          </h1>

          <p>
            TripCraft combines live travel
            research, LangGraph workflows
            and human approval into one clean
            planning experience.
          </p>

          <div className="hero-buttons">
            <Link
              href="/product/"
              className="primary-link-button large-button"
            >
              Start planning
              <ArrowRight size={18} />
            </Link>
          </div>

          <div className="hero-preview">
            <div className="preview-top">
              <span className="preview-dot red" />
              <span className="preview-dot amber" />
              <span className="preview-dot green" />
            </div>

            <div className="preview-content">
              <div className="preview-sidebar">
                <span className="mini-logo">
                  <Plane size={17} />
                </span>

                <div className="preview-line short" />
                <div className="preview-line" />
                <div className="preview-line" />
              </div>

              <div className="preview-main">
                <span className="preview-eyebrow">
                  YOUR TRIP
                </span>

                <h3>
                  Cologne → Lisbon
                </h3>

                <p>
                  12 Nov — 18 Nov · 2 travellers
                </p>

                <div className="preview-cards">
                  <div>
                    <Plane size={17} />
                    Flights
                  </div>

                  <div>
                    <MapPinned size={17} />
                    Hotels
                  </div>

                  <div>
                    <Globe2 size={17} />
                    Things to do
                  </div>
                </div>

                <div className="preview-plan">
                  <span />
                  <span />
                  <span />
                  <span className="small" />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="feature-strip">
          <div>
            <Plane size={22} />
            <h3>Live travel tools</h3>
            <p>
              Flight and destination research
              through your MCP toolchain.
            </p>
          </div>

          <div>
            <Globe2 size={22} />
            <h3>Conversation memory</h3>
            <p>
              A browser-generated thread ID
              connects this browser to its
              LangGraph thread.
            </p>
          </div>

          <div>
            <Sparkles size={22} />
            <h3>Human-in-the-loop</h3>
            <p>
              Clarify, revise, approve and
              download your final travel plan.
            </p>
          </div>
        </section>
      </main>
    </>
  );
}
