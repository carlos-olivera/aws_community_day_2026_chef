export type Diet = "none" | "vegetarian" | "vegan";
export type Allergen = "peanut" | "tree_nuts" | "shellfish" | "fish" | "egg" | "soy";
export type SpiceLevel = "mild" | "medium" | "hot";
export type EventState = "OPEN" | "FROZEN" | "GENERATING" | "PUBLISHED";
export type CuisinePreference =
  | "traditional_bolivian"
  | "andean_fusion"
  | "international"
  | "no_preference";

export const PREFERRED_INGREDIENTS = [
  "quinoa", "potato", "corn", "aji_amarillo", "llama_meat",
  "trout", "chuno", "broad_beans", "amaranth", "peanut",
] as const;
export type PreferredIngredient = (typeof PREFERRED_INGREDIENTS)[number];

export interface SurveySubmission {
  diet: Diet;
  lactose_intolerant: boolean;
  gluten_free: boolean;
  allergies: Allergen[];
  spice_level: SpiceLevel;
  cuisine_preference: CuisinePreference;
  preferred_ingredients: PreferredIngredient[];
  consent: boolean;
}

export interface RunStep {
  type: string;
  tool?: string;
  status?: string;
  reason?: string;
  message?: string;
  at?: string;
}

export interface Run {
  run_id: string;
  cycle: number;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  started_at: string;
  finished_at?: string;
  error?: string;
  steps: RunStep[];
}

export interface EventSummary {
  event_id: string;
  cycle: number;
  state: EventState;
  menu_available: boolean;
  run?: Run;
}

export interface Stats extends EventSummary {
  total_responses: number;
  diet_counts?: Record<Diet, number>;
  lactose_intolerant_count?: number;
  gluten_free_count?: number;
  allergen_counts?: Record<string, number>;
  spice_counts?: Record<SpiceLevel, number>;
  derived_constraints?: {
    must_exclude_allergens: string[];
    require_vegetarian_lunch_main: boolean;
    require_vegan_option_per_meal: boolean;
    require_gluten_free_option_per_meal: boolean;
    require_lactose_free_option_per_meal: boolean;
    max_default_spice: SpiceLevel;
  };
  top_preferred_ingredients?: { ingredient: string; count: number }[];
}

export interface MenuItem {
  dish_id: string;
  name: string;
  description: string;
  ingredients: string[];
  allergens: Allergen[];
  dietary_flags: string[];
  spice_level: SpiceLevel;
  bolivian_origin: boolean;
  complexity: number;
}

export interface Menu {
  menu_id: string;
  event_id: string;
  cycle: number;
  run_id?: string;
  generation_mode: "live_agentcore" | "fallback_last_good";
  snapshot_version: number;
  disclaimer: string;
  meals: {
    breakfast: { style: "buffet"; items: MenuItem[] };
    lunch: { starter: MenuItem; mains: MenuItem[]; dessert: MenuItem };
    dinner: { main: MenuItem; dessert: MenuItem };
  };
  coverage?: {
    vegetarian_lunch_main: boolean;
    vegan_option_per_meal: boolean;
    gluten_free_option_per_meal: boolean;
    lactose_free_option_per_meal: boolean;
    preferred_ingredients_used: string[];
    bolivian_ingredient_ratio: number;
  };
  warnings: string[];
}
