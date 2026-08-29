# One-off authoring helper used to write the initial data/corpus files.
# The corpus files it writes are checked in and hand-edited afterwards;
# re-running this will overwrite them. Kept for transparency.
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"

VEG_ALL = ["vegan", "vegetarian", "gluten_free", "lactose_free"]

DISHES = [
    # --- breakfast (buffet items) ---
    ("api_morado", "Api Morado", "breakfast", ["breakfast"],
     ["purple_corn", "sugar", "cinnamon", "lime"], [], VEG_ALL, "mild", True, 1,
     "A warm, thick purple-corn drink spiced with cinnamon, served at Bolivian "
     "breakfast tables and street stalls at dawn.",
     "Naturally vegan and gluten-free, api holds temperature well in urns, which "
     "makes it an easy anchor for a breakfast buffet station."),
    ("bunuelos", "Bunuelos", "breakfast", ["breakfast"],
     ["wheat_flour", "egg", "sugar"], ["egg"], ["vegetarian", "lactose_free"], "mild", True, 2,
     "Airy fried dough rings dusted with sugar, the classic companion of api "
     "morado on Bolivian winter mornings.",
     "Best fried in batches close to service; they lose their crispness if held "
     "too long, so plan a live station or short rotations."),
    ("cunape", "Cunape", "breakfast", ["breakfast", "santa cruz"],
     ["yuca", "cheese", "egg"], ["egg"], ["vegetarian", "gluten_free"], "mild", True, 2,
     "Santa Cruz's beloved cheese bread made from yuca starch, naturally "
     "gluten-free with a chewy centre and golden crust.",
     "Cunapes bake in under fifteen minutes and are eaten warm, ideal for a "
     "rolling buffet where trays come out in waves."),
    ("fruit_platter_tropical", "Tropical Fruit Platter", "breakfast", ["breakfast", "fruit"],
     ["banana", "papaya", "pineapple", "achachairu"], [], VEG_ALL, "mild", True, 1,
     "A seasonal platter of banana, papaya, pineapple and achachairu, the "
     "small tangy fruit native to the Santa Cruz lowlands.",
     "Zero cooking and universally safe for vegan, gluten-free and lactose-free "
     "guests - every large breakfast buffet should include one."),
    ("humintas", "Humintas al Horno", "breakfast", ["breakfast", "corn"],
     ["corn", "cheese", "sugar"], [], ["vegetarian", "gluten_free"], "mild", True, 2,
     "Fresh ground corn and cheese wrapped in corn husks and baked - a "
     "vegetarian staple across the Bolivian valleys.",
     "They can be steamed or baked ahead in quantity and served warm from the "
     "husk, which doubles as a natural, waste-free plate."),
    ("quinoa_porridge", "Quinoa Breakfast Porridge", "breakfast", ["breakfast", "quinoa", "buffet"],
     ["quinoa", "banana", "sugar", "cinnamon"], [], VEG_ALL, "mild", True, 1,
     "Creamy quinoa simmered with cinnamon and topped with banana - an Andean "
     "grain reimagined for a breakfast buffet.",
     "Cooked in a single kettle and held in a hot well, it scales to hundreds "
     "of servings and covers vegan and gluten-free needs at once."),
    # --- starters ---
    ("chairo_vegetariano", "Chairo Vegetariano", "starter", ["soup", "andean"],
     ["chuno", "potato", "broad_beans", "carrot", "onion"], [], VEG_ALL, "mild", True, 2,
     "A vegetarian take on the highland chairo: chuno, potato and broad beans "
     "in a hearty vegetable broth.",
     "Chuno's deep, earthy flavour gives the broth body without any meat, and "
     "the soup only improves when made hours ahead."),
    ("ensalada_de_choclo", "Ensalada de Choclo", "starter", ["salad", "corn"],
     ["corn", "tomato", "onion", "lime"], [], VEG_ALL, "mild", True, 1,
     "A bright salad of large-kernel Andean choclo corn, tomato and onion "
     "dressed with lime.",
     "Served cold, it needs no holding equipment and adds colour and acidity "
     "to a menu heavy on warm dishes."),
    ("sopa_de_mani", "Sopa de Mani", "starter", ["soup", "classic"],
     ["peanut", "potato", "carrot", "onion"], ["peanut"],
     ["vegetarian", "gluten_free", "lactose_free"],
     "mild", True, 2,
     "Bolivia's iconic creamy peanut soup, blended smooth and finished with "
     "crisp potato batons.",
     "A guaranteed crowd-pleaser - but it is, of course, entirely built on "
     "peanuts, so check declared allergies before it goes anywhere near a menu."),
    ("sopa_de_quinua", "Sopa de Quinua", "starter", ["soup", "quinoa"],
     ["quinoa", "potato", "carrot", "onion"], [], VEG_ALL, "mild", True, 1,
     "A light highland soup of quinoa and vegetables, the everyday starter of "
     "the Altiplano kitchen.",
     "Quinoa thickens the broth naturally as it rests, and the soup is vegan "
     "and gluten-free without any substitution."),
    # --- mains ---
    ("majadito_vegetal", "Majadito Vegetal", "main", ["santa cruz", "rice", "events"],
     ["rice", "tomato", "onion", "bell_pepper", "garlic"], [], VEG_ALL, "mild", True, 2,
     "A plant-based version of Santa Cruz's majadito: toasted rice simmered "
     "with tomato, pepper and garlic until deeply savoury.",
     "One-pot, ladle-friendly and safe for every dietary group, it is the kind "
     "of universal main a single-option dinner service needs."),
    ("papas_rellenas_verdura", "Papas Rellenas de Verduras", "main", ["potato", "street food"],
     ["potato", "carrot", "spinach", "onion"], [], VEG_ALL, "mild", True, 2,
     "Golden mashed-potato croquettes with a spiced vegetable heart, a "
     "meat-free spin on the street-corner classic.",
     "They fry ahead and reheat well, and the all-vegetable filling keeps them "
     "vegan and gluten-free by construction."),
    ("pique_a_lo_macho", "Pique a lo Macho", "main", ["beef", "cochabamba", "events"],
     ["beef", "potato", "tomato", "onion", "locoto"], [], ["gluten_free", "lactose_free"],
     "medium", True, 3,
     "Cochabamba's mountain of beef strips, fried potato, tomato and locoto "
     "chilli - festive, generous and unapologetically bold.",
     "Great for crowds that enjoy some heat; the locoto brings genuine medium "
     "spice, so it should never be the only main on offer."),
    ("quinua_tarwi_guiso", "Guiso de Quinua y Tarwi", "main",
     ["quinoa", "tarwi", "andean", "events"],
     ["quinoa", "tarwi", "tomato", "onion", "aji_amarillo"], [], VEG_ALL, "mild", True, 2,
     "A gentle stew of quinoa and tarwi - the protein-rich Andean lupin - "
     "with tomato and mild aji amarillo.",
     "Tarwi delivers complete plant protein, making this a nutritionally "
     "serious universal main rather than a token vegetarian option."),
    ("silpancho_tradicional", "Silpancho Tradicional", "main", ["beef", "cochabamba"],
     ["beef", "wheat_flour", "egg", "rice", "potato", "tomato"], ["egg"], ["lactose_free"],
     "mild", True, 2,
     "The Cochabamba classic: breaded flattened beef over rice and potato, "
     "crowned with a fried egg and fresh salsa.",
     "Beloved and filling, though its breading and egg keep it off gluten-free "
     "and vegetarian plates - pair it with a universal option."),
    ("trucha_al_horno", "Trucha del Titicaca al Horno", "main", ["fish", "titicaca"],
     ["trout", "potato", "lime", "garlic"], ["fish"], ["gluten_free", "lactose_free"],
     "mild", True, 2,
     "Lake Titicaca trout baked with lime and garlic over a bed of native "
     "potatoes.",
     "A lighter protein choice that showcases highland aquaculture; remember "
     "fish is a declared allergen category for some guests."),
    # --- desserts ---
    ("arroz_con_leche", "Arroz con Leche", "dessert", ["classic", "creamy"],
     ["rice", "milk", "sugar", "cinnamon"], [], ["vegetarian", "gluten_free"], "mild", True, 1,
     "Slow-simmered rice pudding perfumed with cinnamon, the dessert every "
     "Bolivian grandmother keeps on the stove.",
     "Made in one pot and served warm or cold, it is comfortably scalable but "
     "dairy-based - keep a lactose-free alternative alongside."),
    ("chocolate_con_frutas", "Chocolate Boliviano con Frutas", "dessert", ["chocolate", "fruit"],
     ["chocolate", "banana", "mango"], [], VEG_ALL, "mild", True, 1,
     "Skewers of banana and mango draped in melted Bolivian single-origin "
     "chocolate from the Alto Beni.",
     "Assembled cold with no baking, vegan and gluten-free, it doubles as the "
     "safe dessert for nearly every dietary restriction on the list."),
    ("flan_de_chirimoya", "Flan de Chirimoya", "dessert", ["custard", "fruit"],
     ["chirimoya", "egg", "milk", "sugar"], ["egg"], ["vegetarian", "gluten_free"], "mild", True, 2,
     "A silky caramel flan folded with chirimoya, the custard-apple of the "
     "Andean valleys.",
     "Elegant on a plated menu, but it carries both egg and dairy - always "
     "offer a fruit-based dessert next to it."),
    ("helado_de_canela", "Helado de Canela", "dessert", ["frozen", "la paz"],
     ["sugar", "cinnamon", "lime"], [], VEG_ALL, "mild", True, 1,
     "La Paz's striking scarlet cinnamon sorbet, churned from a spiced syrup "
     "and served in tall scoops.",
     "Water-based rather than dairy-based, it is vegan by accident of "
     "tradition and refreshes after a rich main course."),
]

INGREDIENTS = [
    ("quinoa", "Quinoa", "The mother grain of the Andes: complete protein, naturally "
     "gluten-free, and grown across the Bolivian Altiplano.",
     "Use it in soups, stews, porridges and salads; it cooks in fifteen minutes "
     "and absorbs any broth it meets."),
    ("tarwi", "Tarwi", "An Andean lupin bean domesticated on the shores of Lake "
     "Titicaca, exceptionally rich in plant protein.",
     "After soaking away its natural bitterness it behaves like a firm bean, "
     "excellent in stews and salads for vegan menus."),
    ("chuno", "Chuno", "Freeze-dried potato made by exposing tubers to Altiplano "
     "night frost and daytime sun - ancient food preservation technology.",
     "Rehydrated chuno adds an earthy depth to soups like chairo and keeps "
     "for years without refrigeration."),
    ("achachairu", "Achachairu", "A small orange fruit with bright, tangy white flesh, "
     "native to the Santa Cruz lowlands and harvested in the southern summer.",
     "Serve it fresh on fruit platters or as juice; its acidity balances rich "
     "buffet dishes."),
    ("aji_amarillo", "Aji Amarillo", "The yellow Andean chilli that provides fruity, "
     "gentle warmth rather than aggressive heat.",
     "Blended into sauces and stews it gives colour and mild spice suitable "
     "for mixed audiences."),
    ("locoto", "Locoto", "The fiery highland chilli eaten fresh in llajua salsa and "
     "cooked into piques.",
     "Genuinely hot - dishes built on locoto should be flagged medium or hot "
     "and never be the only option."),
    ("purple_corn", "Purple Corn", "Deep violet Andean maize, prized for the colour and "
     "gentle sweetness it releases when simmered.",
     "The base of api morado and refreshing coloured drinks; it is a grain, "
     "so treat it like corn in dietary terms."),
    ("yuca", "Yuca", "The starchy lowland root that anchors Santa Cruz cooking, from "
     "boiled sides to cunape cheese bread.",
     "Its starch is gluten-free, which makes yuca doughs the natural base for "
     "celiac-friendly baking."),
]

TECHNIQUES = [
    ("buffet_planning", "Buffet Planning for Large Events",
     "Planning a buffet for hundreds means choosing dishes that hold "
     "temperature, serve themselves and fail gracefully.",
     "Favour one-pot dishes and cold platters, label every station with "
     "allergens, and always position the universal (vegan, gluten-free) "
     "options first in line so they are not picked over."),
    ("vegetarian_substitutions", "Vegetarian Substitutions in Bolivian Cooking",
     "Most Bolivian classics adapt to vegetarian versions by swapping the "
     "protein while keeping the seasoning that defines the dish.",
     "Tarwi and quinoa replace beef in stews, chuno keeps broths deep without "
     "bones, and eggs or cheese can bridge dishes for lacto-ovo guests - but "
     "a truly universal menu needs fully vegan anchors."),
    ("single_option_service", "Designing a Single-Option Course",
     "When a course offers exactly one dish, that dish must satisfy every "
     "guest at once - the constraint flips from variety to universality.",
     "Choose a naturally vegan, gluten-free preparation with broad appeal and "
     "put richness in optional toppings served on the side."),
]


def write_doc(folder: str, slug: str, meta: dict, title: str, p1: str, p2: str) -> None:
    d = CORPUS / folder
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.md").write_text(f"# {title}\n\n{p1}\n\n{p2}\n")
    (d / f"{slug}.meta.json").write_text(json.dumps(meta, indent=2) + "\n")


for (slug, name, course, tags, ingredients, allergens, flags,
     spice, bolivian, complexity, p1, p2) in DISHES:
    meta = {
        "type": "dish",
        "name": name,
        "course": course,
        "tags": tags + ["bolivian"],
        "ingredients": ingredients,
        "allergens": allergens,
        "dietary_flags": flags,
        "spice_level": spice,
        "bolivian_origin": bolivian,
        "complexity": complexity,
    }
    write_doc("dishes", slug, meta, name, p1, p2)

for slug, name, p1, p2 in INGREDIENTS:
    meta = {"type": "ingredient", "name": name, "ingredient_id": slug,
            "tags": ["bolivian", "ingredient"]}
    write_doc("ingredients", slug, meta, name, p1, p2)

for slug, name, p1, p2 in TECHNIQUES:
    meta = {"type": "technique", "name": name, "tags": ["technique", "events"]}
    write_doc("techniques", slug, meta, name, p1, p2)

print(f"wrote {len(DISHES)} dishes, {len(INGREDIENTS)} ingredients, "
      f"{len(TECHNIQUES)} techniques under {CORPUS}")
