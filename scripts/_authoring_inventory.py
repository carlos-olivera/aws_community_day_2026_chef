# One-off authoring helper for data/inventory.seed.json (checked in after).
# Convention: 'ingredients' on dishes list main components only, so pantry
# basics like salt and oil are not modelled.
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

VEG = ["vegan", "vegetarian", "gluten_free", "lactose_free"]
VEG_GLUTEN = ["vegan", "vegetarian", "lactose_free"]          # wheat & friends
LACTO_VEG = ["vegetarian", "gluten_free"]                     # dairy
OVO_VEG = ["vegetarian", "gluten_free", "lactose_free"]       # egg
MEAT = ["gluten_free", "lactose_free"]                        # animal protein

# (id, name, category, qty, unit, allergens, flags, bolivian, notes)
ITEMS = [
    ("quinoa", "Quinoa Real", "grain", 35, "kg", [], VEG, True, "Altiplano Sur"),
    ("amaranth", "Amaranth", "grain", 12, "kg", [], VEG, True, ""),
    ("canahua", "Canahua", "grain", 8, "kg", [], VEG, True, ""),
    ("rice", "Rice", "grain", 60, "kg", [], VEG, False, ""),
    ("corn", "Choclo Corn", "grain", 40, "kg", [], VEG, True, "large Andean kernels"),
    ("purple_corn", "Purple Corn", "grain", 15, "kg", [], VEG, True, "for api"),
    ("corn_flour", "Corn Flour", "grain", 20, "kg", [], VEG, True, ""),
    ("wheat_flour", "Wheat Flour", "grain", 30, "kg", [], VEG_GLUTEN, False, "contains gluten"),
    ("oats", "Oats", "grain", 10, "kg", [], VEG_GLUTEN, False, "possible gluten traces"),
    ("potato", "Native Potatoes", "tuber", 90, "kg", [], VEG, True, "mixed varieties"),
    ("chuno", "Chuno", "tuber", 18, "kg", [], VEG, True, "freeze-dried potato"),
    ("sweet_potato", "Camote", "tuber", 20, "kg", [], VEG, True, ""),
    ("yuca", "Yuca", "tuber", 35, "kg", [], VEG, True, "Santa Cruz lowlands"),
    ("tarwi", "Tarwi", "legume", 14, "kg", [], VEG, True, "Andean lupin, pre-soaked"),
    ("broad_beans", "Broad Beans", "legume", 16, "kg", [], VEG, True, "habas"),
    ("black_beans", "Black Beans", "legume", 12, "kg", [], VEG, False, ""),
    ("lentils", "Lentils", "legume", 10, "kg", [], VEG, False, ""),
    ("peanut", "Peanuts", "legume", 25, "kg", ["peanut"], VEG, True, "Bolivian-grown"),
    ("tomato", "Tomatoes", "vegetable", 45, "kg", [], VEG, True, ""),
    ("onion", "Onions", "vegetable", 40, "kg", [], VEG, True, ""),
    ("garlic", "Garlic", "vegetable", 6, "kg", [], VEG, True, ""),
    ("carrot", "Carrots", "vegetable", 30, "kg", [], VEG, True, ""),
    ("spinach", "Spinach", "vegetable", 12, "kg", [], VEG, True, ""),
    ("bell_pepper", "Bell Peppers", "vegetable", 15, "kg", [], VEG, True, ""),
    ("squash", "Zapallo Squash", "vegetable", 25, "kg", [], VEG, True, ""),
    ("locoto", "Locoto Chilli", "spice", 5, "kg", [], VEG, True, "hot"),
    ("aji_amarillo", "Aji Amarillo", "spice", 7, "kg", [], VEG, True, "mild-fruity"),
    ("cinnamon", "Cinnamon", "spice", 3, "kg", [], VEG, False, ""),
    ("banana", "Bananas", "fruit", 50, "kg", [], VEG, True, "Chapare"),
    ("papaya", "Papayas", "fruit", 30, "kg", [], VEG, True, ""),
    ("mango", "Mangoes", "fruit", 25, "kg", [], VEG, True, ""),
    ("pineapple", "Pineapples", "fruit", 28, "kg", [], VEG, True, ""),
    ("chirimoya", "Chirimoyas", "fruit", 12, "kg", [], VEG, True, ""),
    ("achachairu", "Achachairu", "fruit", 15, "kg", [], VEG, True, "Santa Cruz native"),
    ("lime", "Limes", "fruit", 10, "kg", [], VEG, True, ""),
    ("orange", "Oranges", "fruit", 20, "kg", [], VEG, True, ""),
    ("milk", "Milk", "dairy", 60, "l", [], LACTO_VEG, True, ""),
    ("cheese", "Quesillo Cheese", "dairy", 22, "kg", [], LACTO_VEG, True, "valley quesillo"),
    ("butter", "Butter", "dairy", 8, "kg", [], LACTO_VEG, False, ""),
    ("yogurt", "Yogurt", "dairy", 15, "l", [], LACTO_VEG, False, ""),
    ("egg", "Eggs", "protein", 600, "units", ["egg"], OVO_VEG, True, ""),
    ("beef", "Beef", "protein", 55, "kg", [], MEAT, True, ""),
    ("chicken", "Chicken", "protein", 45, "kg", [], MEAT, True, ""),
    ("llama_meat", "Llama Meat", "protein", 20, "kg", [], MEAT, True, "highland charque cut"),
    ("trout", "Titicaca Trout", "protein", 18, "kg", ["fish"], MEAT, True, ""),
    ("honey", "Honey", "other", 6, "kg", [],
     ["vegetarian", "gluten_free", "lactose_free"], True, ""),
    ("sugar", "Sugar", "other", 30, "kg", [], VEG, True, "Santa Cruz cane"),
    ("chocolate", "Bolivian Chocolate", "other", 10, "kg", [], VEG, True, "Alto Beni cacao"),
    ("coffee", "Coffee", "other", 8, "kg", [], VEG, True, "Yungas"),
]

inventory = [
    {
        "ingredient_id": iid, "name": name, "category": cat,
        "quantity": qty, "unit": unit, "allergens": allergens,
        "dietary_flags": flags, "is_bolivian": bolivian, "notes": notes,
    }
    for (iid, name, cat, qty, unit, allergens, flags, bolivian, notes) in ITEMS
]

out = ROOT / "data" / "inventory.seed.json"
out.write_text(json.dumps(inventory, indent=2) + "\n")
print(f"wrote {len(inventory)} items to {out}")
