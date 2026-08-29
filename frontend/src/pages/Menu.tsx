import { useEffect, useState } from "react";
import { fetchMenu } from "../api";
import type { Menu as MenuType, MenuItem } from "../types";

const LABELS: Record<string, string> = {
  vegan: "vegano", vegetarian: "vegetariano", gluten_free: "sin gluten", lactose_free: "sin lactosa",
  peanut: "maní", tree_nuts: "frutos secos", shellfish: "mariscos", fish: "pescado", egg: "huevo", soy: "soya",
};

function Dish({ item }: { item: MenuItem }) {
  return (
    <article className="dish">
      <div className="name">{item.name}</div>
      <div className="desc">{item.description}</div>
      {item.dietary_flags.map((flag) => <span key={flag} className="badge ok">{LABELS[flag] ?? flag}</span>)}
      {item.allergens.map((allergen) => <span key={allergen} className="badge">contiene {LABELS[allergen] ?? allergen}</span>)}
    </article>
  );
}

export default function Menu() {
  const [menu, setMenu] = useState<MenuType | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchMenu().then(setMenu).catch((caught) => setError(caught instanceof Error ? caught.message : String(caught)));
  }, []);

  if (error) return <main><h1>Aún no hay menú</h1><p className="subtitle">{error}</p></main>;
  if (!menu) return <p className="subtitle">Cargando el menú…</p>;

  const fallback = menu.generation_mode === "fallback_last_good";
  return (
    <main>
      <p className="eyebrow">Chef Andino · ciclo {menu.cycle}</p>
      <h1>Menú de la jornada</h1>
      <p className="subtitle">Preparado a partir del snapshot {menu.snapshot_version} y verificado con reglas deterministas.</p>
      {fallback && <div className="fallback-banner"><b>Resultado de contingencia</b><br />No fue generado con las respuestas en vivo de este ciclo.</div>}

      <h2>Desayuno · buffet</h2>
      {menu.meals.breakfast.items.map((item) => <Dish key={item.dish_id} item={item} />)}

      <h2>Almuerzo</h2>
      <h3>Entrada</h3><Dish item={menu.meals.lunch.starter} />
      <h3>Platos principales</h3>{menu.meals.lunch.mains.map((item) => <Dish key={item.dish_id} item={item} />)}
      <h3>Postre</h3><Dish item={menu.meals.lunch.dessert} />

      <h2>Cena</h2>
      <h3>Plato principal</h3><Dish item={menu.meals.dinner.main} />
      <h3>Postre</h3><Dish item={menu.meals.dinner.dessert} />

      {menu.coverage && (
        <section>
          <h2>Cobertura verificada</h2>
          <p>
            {menu.coverage.vegetarian_lunch_main && <span className="badge ok">principal vegetariano</span>}
            {menu.coverage.vegan_option_per_meal && <span className="badge ok">opción vegana por comida</span>}
            {menu.coverage.gluten_free_option_per_meal && <span className="badge ok">opción sin gluten</span>}
            {menu.coverage.lactose_free_option_per_meal && <span className="badge ok">opción sin lactosa</span>}
            <span className="badge">{Math.round(menu.coverage.bolivian_ingredient_ratio * 100)}% ingredientes bolivianos</span>
          </p>
        </section>
      )}
      {menu.warnings.length > 0 && <div className="notice">{menu.warnings.join(" ")}</div>}
      <p className="disclaimer">{menu.disclaimer}</p>
    </main>
  );
}
