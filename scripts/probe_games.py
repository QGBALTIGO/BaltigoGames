"""Bounded live check of every catalog entry, keeping results as evidence."""
import asyncio
import json
import os
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8186").rstrip("/")


async def main():
    catalog = json.loads((ROOT / "data/registry.json").read_text(encoding="utf-8"))
    semaphore = asyncio.Semaphore(4)
    async with httpx.AsyncClient(timeout=45) as client:
        async def check(game):
            async with semaphore:
                try:
                    response = await client.get(BASE + "/play/" + game["path"])
                    html = "text/html" in response.headers.get("content-type", "")
                    return {"slug": game["slug"], "status": response.status_code,
                            "bytes": len(response.content), "ok": response.status_code == 200 and html and len(response.content) > 100}
                except httpx.HTTPError as exc:
                    return {"slug": game["slug"], "ok": False, "error": type(exc).__name__}
        results = await asyncio.gather(*(check(game) for game in catalog["games"]))
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    (out / "catalog-probe.json").write_text(json.dumps({"base": BASE, "results": results}, indent=2), encoding="utf-8")
    failures = [result for result in results if not result["ok"]]
    print(json.dumps({"base": BASE, "passed": len(results) - len(failures), "failed": failures}))
    assert not failures, "some game entries failed"


if __name__ == "__main__":
    asyncio.run(main())
