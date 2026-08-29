import { useEffect, useState } from "react";
import {
  clearPresenterKey,
  fetchStats,
  freezeEvent,
  generateMenu,
  hasPresenterKey,
  resetEvent,
  revealFallback,
  savePresenterKey,
} from "../api";
import type { Stats } from "../types";

export default function Presenter() {
  const [unlocked, setUnlocked] = useState(hasPresenterKey());
  const [passphrase, setPassphrase] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!unlocked) return;
    let active = true;
    async function poll() {
      try {
        const value = await fetchStats();
        if (active) setStats(value);
      } catch (caught) {
        if (active) setMessage(caught instanceof Error ? caught.message : String(caught));
      }
    }
    void poll();
    const timer = window.setInterval(poll, 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [unlocked]);

  function unlock(event: React.FormEvent) {
    event.preventDefault();
    savePresenterKey(passphrase);
    setUnlocked(true);
  }

  async function act(label: string, action: () => Promise<unknown>) {
    setBusy(true);
    setMessage(label);
    try {
      await action();
      setStats(await fetchStats());
      setMessage(`${label} — listo.`);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  if (!unlocked) {
    return (
      <form className="login" onSubmit={unlock}>
        <h1>Consola del presentador</h1>
        <p className="subtitle">
          La clave se conserva únicamente durante esta pestaña, en sessionStorage cuando está disponible.
        </p>
        <label htmlFor="passphrase">Clave compartida</label>
        <input
          id="passphrase"
          type="password"
          value={passphrase}
          onChange={(event) => setPassphrase(event.target.value)}
          autoComplete="current-password"
          required
        />
        <button type="submit">Abrir consola</button>
      </form>
    );
  }

  return (
    <main>
      <div className="presenter-heading">
        <div>
          <h1>Consola del presentador</h1>
          <p className="subtitle">Evento demo-event · ciclo {stats?.cycle ?? "…"}</p>
        </div>
        <button
          className="link-button"
          onClick={() => {
            clearPresenterKey();
            setUnlocked(false);
          }}
        >Cerrar sesión</button>
      </div>

      <div className="state-card">
        <span className={`state state-${stats?.state.toLowerCase()}`}>{stats?.state ?? "CARGANDO"}</span>
        <strong>{stats?.total_responses ?? 0} respuestas</strong>
      </div>
      <div className="grid">
        <div className="stat"><div className="value">{stats?.diet_counts?.vegetarian ?? 0}</div><div className="label">vegetarianas</div></div>
        <div className="stat"><div className="value">{stats?.diet_counts?.vegan ?? 0}</div><div className="label">veganas</div></div>
        <div className="stat"><div className="value">{stats?.lactose_intolerant_count ?? 0}</div><div className="label">sin lactosa</div></div>
        <div className="stat"><div className="value">{stats?.gluten_free_count ?? 0}</div><div className="label">sin gluten</div></div>
      </div>

      <h2>Controles</h2>
      <div className="controls">
        <button disabled={busy} onClick={() => void act("Restableciendo", () => resetEvent(false))}>Restablecer demo</button>
        <button disabled={busy} className="secondary" onClick={() => void act("Cargando respuestas sintéticas", () => resetEvent(true))}>Restablecer con datos</button>
        <button disabled={busy || stats?.state !== "OPEN"} onClick={() => void act("Congelando encuesta", freezeEvent)}>Congelar</button>
        <button disabled={busy || stats?.state !== "FROZEN"} onClick={() => void act("Iniciando AgentCore", generateMenu)}>Generar menú</button>
        <button disabled={busy} className="warning" onClick={() => void act("Revelando contingencia", revealFallback)}>Revelar fallback</button>
      </div>
      {message && <p className="notice">{message}</p>}

      {stats?.run && (
        <>
          <h2>Ejecución {stats.run.run_id}</h2>
          <p><span className="badge ok">{stats.run.status}</span>{stats.run.error && <span className="error"> {stats.run.error}</span>}</p>
          <ol className="trace">
            {stats.run.steps.map((step, index) => (
              <li key={`${step.at ?? index}-${index}`}>
                <b>{step.type}</b>{step.tool ? ` · ${step.tool}` : ""}{step.status ? ` · ${step.status}` : ""}{step.reason ? ` · ${step.reason}` : ""}{step.message ? ` · ${step.message}` : ""}
              </li>
            ))}
          </ol>
        </>
      )}
    </main>
  );
}
