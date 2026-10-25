"""Snapshot game configs after removing preload entries absent from the source tree."""
import asyncio
import copy
import json
import posixpath
from pathlib import Path
from urllib.parse import urlsplit
import httpx

ROOT = Path(__file__).resolve().parents[1]


async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get("https://api.github.com/repos/sausi-7/games/git/trees/main?recursive=1")
        response.raise_for_status()
        tree = response.json()
        assert not tree.get("truncated"), "incomplete source tree"
        files = {item["path"] for item in tree["tree"] if item["type"] == "blob"}
        catalog = json.loads((ROOT / "data/registry.json").read_text(encoding="utf-8"))
        configs = [posixpath.dirname(game["path"]) + "/config.json" for game in catalog["games"]]
        semaphore = asyncio.Semaphore(4)
        fixes, removed, skipped = {}, {}, []

        async def check(path):
            if path not in files:
                return
            async with semaphore:
                res = await client.get("https://sausi-7.github.io/games/" + path)
                res.raise_for_status()
                try:
                    config = res.json()
                except ValueError:
                    skipped.append(path)
                    return
                if not isinstance(config, dict):
                    skipped.append(path)
                    return
            original = copy.deepcopy(config)
            missing = []
            for section in ["images1", "images2", "images", "ui", "audio", "spritesheets"]:
                entries = config.get(section)
                if not isinstance(entries, dict):
                    continue
                for key, value in list(entries.items()):
                    asset = value.get("path") if isinstance(value, dict) else value
                    if not isinstance(asset, str) or urlsplit(asset).scheme or asset.startswith("data:"):
                        continue
                    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), asset))
                    if resolved not in files:
                        missing.append({"section": section, "key": key, "path": asset})
                        del entries[key]
            if config != original:
                fixes[path] = config
                removed[path] = missing

        await asyncio.gather(*(check(path) for path in configs))
    result = {"source_tree": tree["sha"], "source": "sausi-7/games", "configs": dict(sorted(fixes.items()))}
    (ROOT / "data/config-overrides.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    (out / "upstream-config-repairs.json").write_text(json.dumps(removed, indent=2), encoding="utf-8")
    print(json.dumps({"configs_repaired": len(fixes), "missing_preloads_removed": sum(map(len, removed.values())), "source_tree": tree["sha"], "non_json_configs": skipped}))


if __name__ == "__main__":
    asyncio.run(main())
