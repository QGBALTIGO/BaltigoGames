"""Validate the deployed routing table against authoritative replacement metadata.

Actual Nginx body/range/conditional/traversal behavior has an isolated VPS probe.
"""
from pathlib import Path
import re

import pytest

from scripts.render_nginx_assets import BINARY_PATTERN, END, ROOT, START, render_maps, replacements, update_maps


def test_embedded_nginx_replacements_match_metadata_for_all_public_aliases():
    config = (ROOT / "deploy/nginx.conf").read_text(encoding="utf-8")
    assets = replacements()
    assert config[config.index(START):config.index(END) + len(END)] == render_maps(assets)
    maps = re.findall(r"map \$uri \$(baltigo_asset_\w+) \{\n(.*?)\n\}", config, re.S)
    assert len(maps) == 2
    for variable, body in maps:
        entries = re.findall(r"^\s+~(\S+) (\S+);$", body, re.M)
        assert len(entries) == len(assets)
        for source, target in assets.items():
            for prefix in ["play", "play-v2", "play-v3"]:
                matches = [value for pattern, value in entries if re.fullmatch(pattern, "/" + prefix + "/" + source)]
                assert matches == ["/opt/baltigogames/current/web" if variable == "baltigo_asset_root" else target]
                assert not any(re.fullmatch(pattern, "/" + prefix + "/" + source + ".extra") for pattern, _ in entries)


def test_fastpath_accepts_binary_assets_and_excludes_adapted_text_and_unsafe_names():
    pattern = re.compile(BINARY_PATTERN.replace("(?<baltigo_game_relative>", "(?P<baltigo_game_relative>"))
    for prefix in ["play", "play-v2", "play-v3"]:
        for filename in ["obj1.png", "music.mp3", "font.ttf", "panel.svg", "Object 1.PNG"]:
            path = "/" + prefix + "/games/arcade/proof/assets/" + filename
            assert pattern.fullmatch(path).group("baltigo_game_relative") == path.split("/", 2)[2]
        for filename in ["index.html", "main.js", "config.json", "styles.css", "secret.env", "x\\evil.png", 'x".png']:
            assert not pattern.fullmatch("/" + prefix + "/games/arcade/proof/" + filename)
    assert not pattern.fullmatch("/play-v3/private/secret.png")
    config = (ROOT / "deploy/nginx.conf").read_text(encoding="utf-8")
    assert re.findall(r'location ~ "([^"]*\(\?<baltigo_game_relative>[^"]*)" \{', config) == [BINARY_PATTERN]
    assert config.index("location ~ /\\.") < config.index("(?<baltigo_game_relative>")
    assert "disable_symlinks on from=$baltigo_asset_root;" in config


def test_generated_map_updates_are_bounded_and_idempotent():
    maps = render_maps(replacements())
    original = "http {\nproxy_cache_path /private-cache keys_zone=x:1m;\nserver {}\n}\n"
    updated = update_maps(original, maps)
    assert update_maps(updated, maps) == updated
    assert updated.endswith("proxy_cache_path /private-cache keys_zone=x:1m;\nserver {}\n}\n")
    with pytest.raises(ValueError):
        update_maps(updated + START, maps)
    with pytest.raises(ValueError):
        render_maps(replacements(), web="/opt/root; arbitrary")
