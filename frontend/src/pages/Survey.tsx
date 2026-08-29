import { useState } from "react";
import { submitResponse } from "../api";
import { PREFERRED_INGREDIENTS, type Allergen, type SurveySubmission } from "../types";

const ALLERGENS: Allergen[] = ["peanut", "tree_nuts", "shellfish", "fish", "egg", "soy"];
const LABELS: Record<string, string> = {
  none: "Sin restricción", vegetarian: "Vegetariana", vegan: "Vegana",
  peanut: "Maní", tree_nuts: "Frutos secos", shellfish: "Mariscos", fish: "Pescado", egg: "Huevo", soy: "Soya",
  mild: "Suave", medium: "Medio", hot: "Picante",
  traditional_bolivian: "Boliviana tradicional", andean_fusion: "Fusión andina", international: "Internacional", no_preference: "Sin preferencia",
  quinoa: "Quinua", potato: "Papa", corn: "Maíz", aji_amarillo: "Ají amarillo", llama_meat: "Carne de llama",
  trout: "Trucha", chuno: "Chuño", broad_beans: "Habas", amaranth: "Amaranto",
};

const INITIAL: SurveySubmission = {
  diet: "none",
  lactose_intolerant: false,
  gluten_free: false,
  allergies: [],
  spice_level: "medium",
  cuisine_preference: "no_preference",
  preferred_ingredients: [],
  consent: false,
};

export default function Survey() {
  const [form, setForm] = useState<SurveySubmission>(INITIAL);
  const [status, setStatus] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [error, setError] = useState("");

  function toggle<T>(list: T[], value: T, max?: number): T[] {
    if (list.includes(value)) return list.filter((item) => item !== value);
    if (max !== undefined && list.length >= max) return list;
    return [...list, value];
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setStatus("sending");
    try {
      await submitResponse(form);
      setStatus("done");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
      setStatus("error");
    }
  }

  if (status === "done") {
    return (
      <main className="center-stage">
        <div className="chef-mark">✓</div>
        <h1>¡Gracias!</h1>
        <p className="subtitle">Tu respuesta anónima ya forma parte de la demostración. Esta misma página mostrará el menú final.</p>
      </main>
    );
  }

  return (
    <form onSubmit={submit}>
      <p className="eyebrow">Demostración educativa · AWS Community Day</p>
      <h1>Ayuda a Chef Andino a cocinar para ti</h1>
      <p className="subtitle">Toma 30 segundos. No pedimos nombre, correo ni texto libre.</p>

      <fieldset>
        <legend>Alimentación</legend>
        {(["none", "vegetarian", "vegan"] as const).map((diet) => (
          <label key={diet}><input type="radio" name="diet" checked={form.diet === diet} onChange={() => setForm({ ...form, diet })} /> {LABELS[diet]}</label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Intolerancias</legend>
        <label><input type="checkbox" checked={form.lactose_intolerant} onChange={(event) => setForm({ ...form, lactose_intolerant: event.target.checked })} /> Intolerancia a la lactosa</label>
        <label><input type="checkbox" checked={form.gluten_free} onChange={(event) => setForm({ ...form, gluten_free: event.target.checked })} /> Evito el gluten</label>
      </fieldset>

      <fieldset>
        <legend>Alergias declaradas</legend>
        <p className="field-help">Solo categorías. En una situación real consulta al equipo de catering.</p>
        {ALLERGENS.map((allergen) => (
          <label key={allergen}><input type="checkbox" checked={form.allergies.includes(allergen)} onChange={() => setForm({ ...form, allergies: toggle(form.allergies, allergen) })} /> {LABELS[allergen]}</label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Nivel máximo de picante</legend>
        {(["mild", "medium", "hot"] as const).map((spice_level) => (
          <label key={spice_level}><input type="radio" name="spice" checked={form.spice_level === spice_level} onChange={() => setForm({ ...form, spice_level })} /> {LABELS[spice_level]}</label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Preferencia culinaria</legend>
        {(["traditional_bolivian", "andean_fusion", "international", "no_preference"] as const).map((cuisine_preference) => (
          <label key={cuisine_preference}><input type="radio" name="cuisine" checked={form.cuisine_preference === cuisine_preference} onChange={() => setForm({ ...form, cuisine_preference })} /> {LABELS[cuisine_preference]}</label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Ingredientes favoritos — máximo 3</legend>
        {PREFERRED_INGREDIENTS.map((ingredient) => (
          <label key={ingredient}><input type="checkbox" checked={form.preferred_ingredients.includes(ingredient)} onChange={() => setForm({ ...form, preferred_ingredients: toggle(form.preferred_ingredients, ingredient, 3) })} /> {LABELS[ingredient]}</label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Consentimiento</legend>
        <label><input type="checkbox" checked={form.consent} onChange={(event) => setForm({ ...form, consent: event.target.checked })} /> Acepto que mis respuestas anónimas y estructuradas se usen únicamente en esta demostración educativa.</label>
      </fieldset>

      {status === "error" && <p className="error">{error}</p>}
      <button type="submit" disabled={!form.consent || status === "sending"}>{status === "sending" ? "Enviando…" : "Enviar a Chef Andino"}</button>
    </form>
  );
}
