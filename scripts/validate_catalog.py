import json
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "data" / "registry.json"
data = json.loads(path.read_text(encoding="utf-8"))
games = data.get("games", [])
slugs = [g["slug"] for g in games]
paths = [g["path"] for g in games]
assert len(games) >= 140, f"expected >=140 games, got {len(games)}"
assert len(slugs) == len(set(slugs)), "duplicate game slugs"
assert all(p.startswith("games/") and p.endswith("index.html") for p in paths), "invalid game path"
print(f"OK: {len(games)} games, {len(data.get('categories', []))} categories, all slugs unique")
