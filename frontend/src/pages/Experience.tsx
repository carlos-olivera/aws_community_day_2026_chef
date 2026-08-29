import { useEffect, useState } from "react";
import { fetchEvent } from "../api";
import type { EventSummary } from "../types";
import Menu from "./Menu";
import Survey from "./Survey";

export default function Experience() {
  const [event, setEvent] = useState<EventSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const next = await fetchEvent();
        if (active) {
          setEvent(next);
          setError("");
        }
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : String(caught));
      }
    }
    void poll();
    const timer = window.setInterval(poll, 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  if (!event) {
    return <p className={error ? "error" : "subtitle"}>{error || "Conectando con la demo…"}</p>;
  }
  if (event.state === "OPEN") return <Survey key={event.cycle} />;
  if (event.state === "PUBLISHED") return <Menu key={event.cycle} />;

  return (
    <main className="center-stage">
      <div className="chef-mark">CA</div>
      <h1>{event.state === "FROZEN" ? "La encuesta terminó" : "Chef Andino está cocinando"}</h1>
      <p className="subtitle">
        {event.state === "FROZEN"
          ? "Las preferencias ya fueron agregadas. El presentador iniciará al agente en un momento."
          : "El agente consulta conocimiento culinario, evalúa restricciones y valida antes de publicar."}
      </p>
      {event.state === "GENERATING" && <div className="loader" aria-label="Generando" />}
      {event.run?.steps?.length ? (
        <ol className="trace public-trace">
          {event.run.steps.slice(-5).map((step, index) => (
            <li key={`${step.at ?? index}-${index}`}>
              {step.tool ? `Herramienta: ${step.tool}` : step.message ?? step.reason ?? step.type}
              {step.status ? ` — ${step.status}` : ""}
            </li>
          ))}
        </ol>
      ) : null}
      <p className="cycle">Ciclo {event.cycle} · actualización automática cada 2 segundos</p>
    </main>
  );
}
