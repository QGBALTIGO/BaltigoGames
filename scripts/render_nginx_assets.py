"""Keep the embedded public game-file maps synchronized with replacement art.

Default is a read-only check. --write replaces only the marked map block in the
selected local config; installation/reload is deliberately outside this script.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]
START = "# BEGIN GENERATED BALTIGO GAME ASSET MAPS"
END = "# END GENERATED BALTIGO GAME ASSET MAPS"
MIRROR = "/opt/baltigogames/upstream/c97ef8b"
WEB = "/opt/baltigogames/current/web"
BINARY_EXTENSIONS = "png|jpe?g|gif|webp|svg|avif|ico|bmp|ttf|otf|woff2?|mp3|ogg|wav|m4a|mp4|webm|bin|wasm|glb|fbx"
BINARY_PATTERN = r"^/play(?:-v[23])?/(?<baltigo_game_relative>games/[-A-Za-z0-9_./%+ @,()~]+[.](?i:" + BINARY_EXTENSIONS + r"))$"


def replacements(path: Path = ROOT / "data/asset-replacements.json") -> dict[str, str]:
    assets = json.loads(path.read_text(encoding="utf-8"))["assets"]
    for source, target in assets.items():
        for value, prefix in [(source, "games/"), (target, "game-art/")]:
            if not value.startswith(prefix) or not re.fullmatch(r"[-A-Za-z0-9_./]+", value):
                raise ValueError("Unsafe replacement path")
            if any(part in {".", ".."} or part.startswith(".") for part in PurePosixPath(value).parts):
                raise ValueError("Unsafe replacement segment")
        if not re.search(r"[.](?:" + BINARY_EXTENSIONS + r")$", source, re.I):
            raise ValueError("Replacement would bypass adapted text")
        resolved = (ROOT / "web" / target).resolve()
        if (ROOT / "web").resolve() not in resolved.parents or not resolved.is_file():
            raise ValueError("Replacement artwork unavailable")
    return assets


def render_maps(assets: dict[str, str], mirror: str = MIRROR, web: str = WEB) -> str:
    for base in [mirror, web]:
        if not re.fullmatch(r"/[-A-Za-z0-9_/]+", base) or ".." in PurePosixPath(base).parts:
            raise ValueError("Unsafe alias root")
    lines = [START, "# Regenerate with scripts/render_nginx_assets.py; do not bypass Portuguese art."]
    for variable, default in [("baltigo_asset_root", mirror), ("baltigo_asset_relative", "$baltigo_game_relative")]:
        lines.extend(["map $uri $" + variable + " {", "    default " + default + ";"])
        for source, target in sorted(assets.items()):
            # Values are validated as plain relative paths before rendering.
            pattern = "^/play(?:-v[23])?/" + re.escape(source) + "$"
            value = web if variable == "baltigo_asset_root" else target
            lines.append("    ~" + pattern + " " + value + ";")
        lines.append("}")
    return "\n".join(lines + [END])


def update_maps(config: str, maps: str) -> str:
    if START in config or END in config:
        if config.count(START) != 1 or config.count(END) != 1:
            raise ValueError("Ambiguous generated maps")
        start, end = config.index(START), config.index(END) + len(END)
        if end <= start:
            raise ValueError("Invalid generated map markers")
        return config[:start] + maps + config[end:]
    if "proxy_cache_path " not in config:
        raise ValueError("No HTTP-level cache anchor")
    return config.replace("proxy_cache_path ", maps + "\n\nproxy_cache_path ", 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "deploy/nginx.conf")
    parser.add_argument("--mirror-root", default=MIRROR)
    parser.add_argument("--web-root", default=WEB)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    assets = replacements()
    original = args.config.read_text(encoding="utf-8")
    result = update_maps(original, render_maps(assets, args.mirror_root, args.web_root))
    if args.write:
        args.config.write_text(result, encoding="utf-8", newline="\n")
    elif result != original:
        raise SystemExit("Embedded Nginx asset maps are stale; run with --write")
    print(json.dumps({"config": str(args.config), "replacement_paths": len(assets), "mode": "write" if args.write else "check"}))


if __name__ == "__main__":
    main()
