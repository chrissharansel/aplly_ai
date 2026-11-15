import { useEffect, useState } from "react";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function Status({ item }) {
  const state = item?.ok === true ? "good" : item?.ok === false ? "bad" : "pending";
  return <div className="status-row">
    <span className={`dot ${state}`} />
    <div><strong>{item?.message || "Checking…"}</strong></div>
    <span className={`status-label ${state}`}>{state === "good" ? "Ready" : state === "bad" ? "Action needed" : "Pending"}</span>
  </div>;
}

export default function App() {
  const [status, setStatus] = useState(null);
  const [statusError, setStatusError] = useState("");
  const [prompt, setPrompt] = useState("Introduce yourself as my job application assistant in one short paragraph.");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [agentError, setAgentError] = useState("");
  const [profile, setProfile] = useState({ full_name: "", email: "", phone: "", location: "", target_role: "" });
  const [profileMessage, setProfileMessage] = useState("");

  async function refreshStatus() {
    try {
      const response = await fetch(`${API}/api/system/status`);
      if (!response.ok) throw new Error("API returned an error");
      setStatus(await response.json());
      setStatusError("");
    } catch {
      setStatusError("Cannot reach FastAPI. Start the backend on port 8000.");
      setStatus(null);
    }
  }

  async function loadProfile() {
    try {
      const response = await fetch(`${API}/api/profile`);
      if (response.ok) setProfile(await response.json());
    } catch { /* status panel already reports backend connectivity */ }
  }

  useEffect(() => { refreshStatus(); loadProfile(); }, []);

  async function testAgent(e) {
    e.preventDefault();
    setBusy(true); setAnswer(""); setAgentError("");
    try {
      const response = await fetch(`${API}/api/agent/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Agent request failed");
      setAnswer(data.answer);
    } catch (err) { setAgentError(err.message); }
    finally { setBusy(false); }
  }

  async function saveProfile(e) {
    e.preventDefault(); setProfileMessage("");
    try {
      const response = await fetch(`${API}/api/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save profile");
      setProfileMessage("Profile saved to MongoDB Atlas.");
    } catch (err) { setProfileMessage(err.message); }
  }

  return <main className="shell">
    <header className="topbar">
      <div className="brand-mark">A</div>
      <div><div className="brand">ApplyAI</div><div className="subbrand">Your personal job application agent</div></div>
      <div className="top-right"><span className="phase-pill">PHASE 1 · FOUNDATION</span></div>
    </header>

    <section className="hero">
      <div>
        <p className="eyebrow">LOCAL AI · PERSISTENT MEMORY · HUMAN REVIEW</p>
        <h1>One URL. A smarter way<br/>to apply for jobs.</h1>
        <p className="hero-copy">We’re setting up your private application assistant. First, verify the services and test the local Llama model.</p>
      </div>
      <div className="hero-icon"><div className="orbit">✳</div><div className="core">AI</div></div>
    </section>

    <section className="section">
      <div className="section-heading"><div><p className="eyebrow">SYSTEM CHECK</p><h2>Your environment</h2></div><button className="secondary" onClick={refreshStatus}>↻ Refresh</button></div>
      {statusError && <div className="alert">{statusError}</div>}
      <div className="status-grid">
        <article className="panel"><div className="panel-kicker">01 / API</div><h3>FastAPI backend</h3><Status item={status?.api}/></article>
        <article className="panel"><div className="panel-kicker">02 / DATABASE</div><h3>MongoDB Atlas</h3><Status item={status?.mongodb}/></article>
        <article className="panel"><div className="panel-kicker">03 / LANGUAGE MODEL</div><h3>Ollama · Llama</h3><Status item={status?.ollama}/></article>
        <article className="panel"><div className="panel-kicker">04 / ORCHESTRATION</div><h3>LangGraph</h3><Status item={status?.agent}/></article>
        <article className="panel"><div className="panel-kicker">05 / BROWSER</div><h3>Google Chrome</h3><Status item={status?.browser}/></article>
      </div>
    </section>

    <section className="two-col section">
      <article className="panel large-panel">
        <p className="eyebrow">AGENT PLAYGROUND</p><h2>Test Llama + LangGraph</h2>
        <p className="muted">This sends your prompt through the Phase 1 LangGraph workflow to your local Ollama model.</p>
        <form onSubmit={testAgent}>
          <label htmlFor="prompt">Your prompt</label>
          <textarea id="prompt" rows="4" value={prompt} onChange={e=>setPrompt(e.target.value)} minLength="3" maxLength="2000"/>
          <button className="primary" disabled={busy || prompt.trim().length < 3}>{busy ? "Thinking…" : "Run agent →"}</button>
        </form>
        {agentError && <div className="alert">{agentError}</div>}
        {answer && <div className="answer"><div className="answer-label">LLAMA RESPONSE</div>{answer}</div>}
      </article>

      <article className="panel large-panel">
        <p className="eyebrow">PERSISTENT MEMORY</p><h2>Starter profile</h2>
        <p className="muted">Save basic profile fields to MongoDB Atlas. You can edit them later.</p>
        <form onSubmit={saveProfile} className="profile-form">
          {[
            ["full_name","Full name"],["email","Email"],["phone","Phone"],["location","Location"],["target_role","Target role"]
          ].map(([key,label])=><div className="field" key={key}><label htmlFor={key}>{label}</label><input id={key} value={profile[key] || ""} onChange={e=>setProfile({...profile,[key]:e.target.value})} /></div>)}
          <button className="primary" type="submit">Save profile →</button>
        </form>
        {profileMessage && <p className="feedback">{profileMessage}</p>}
      </article>
    </section>

    <footer><span>ApplyAI · Phase 1</span><span>Chrome automation and application review arrive in later phases.</span></footer>
  </main>;
}
