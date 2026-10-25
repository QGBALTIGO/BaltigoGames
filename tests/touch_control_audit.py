"""Read-only source evidence inventory for each game, not a playability pass gate.

Regenerates artifacts/touch-control-audit.json from the pinned mirror and current
Portuguese metadata. Manual notes record the actual handlers and update paths
reviewed during QA. Raw-source findings may already be repaired by response-time
adapters; final browser testing must verify the effective served game separately.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIRROR = ROOT / ".deploy" / "mirror"
KEYBOARD = re.compile(r"keyboard|addEventListener\(\s*['\"]key(?:down|up)|\.on\(\s*['\"]key(?:down|up)|createCursorKeys|KeyCodes|Arrow(?:Left|Right|Up|Down)", re.I)
TOUCH = re.compile(r"pointer(?:down|up|move|cancel)|touch(?:start|end|move)|POINTER_(?:DOWN|UP|MOVE)|addEventListener\(\s*['\"](?:click|mousedown)|onpointer(?:down|up)|activePointer\.isDown", re.I)
LIBRARY = re.compile(r"phaser|three|babylon|cannon|jquery|gsap|TweenMax", re.I)

MANUAL_NOTES = dict(line.split("|", 1) for line in """
2048|Swipes from pointerdown/up select the same move(dx,dy) function as arrow keydown.
6oct|Letter wheel taps build words; on-screen submit/clear/shuffle mirror Enter/Backspace/Space shortcuts.
sudoku|DOM cells and numeric buttons use click handlers; keyboard mention does not imply keyboard-only gameplay.
alien-battle|Gameplay pointerdown/up implements held jump/fire zones; Space is an additional input.
antigravity|Left/right buttons set moveLeft/moveRight used alongside cursors; up button calls gravity flip.
archer|Touchstart/move/end performs bow aiming and release; occurrences of Arrow predominantly name projectiles.
bird-shooter|Three mobile flags left/right/action are consumed alongside keyboard movement and shooting in update.
bomb-blast|Mobile lane/action flags and swipe handlers are consumed alongside arrows/A/D/Space.
breakoid|Gameplay pointermove positions the paddle; keyboard arrows offer the alternative movement path.
bubble-shooter|Pointer down/move sets aiming, pointerup shoots; keyboard Space and arrow aiming are alternatives.
buttermilk|Phaser POINTER_DOWN/UP/MOVE handlers operate objects and swipe actions; not limited to menu buttons.
cargo-stack|GameScene pointerdown directly calls dropCargo, same action as keyboard Space.
car-race|Touchstart/end computes horizontal swipe lane changes; arrows and A/D change the same lane variable.
carrom|Gameplay pointerdown/move/up handles aiming, charge, release and the player turn.
catch-me-if-you-can|Gameplay pointer handlers feed drag movement; keyboard vectors are an alternative input path.
collector|Joystick X steers horizontally; actionHeld from mobile action button is consumed alongside Space/Up/W.
color-dash|Mobile buttons call laneLeft/laneRight/tryAction, the same functions as A/D/arrows/Space.
cool-platformer|Update reads effective keyboard OR touch flags; button handlers explicitly preserve independent held flags.
cosmic-cleaner|Gameplay pointer handlers steer and operate the beam; menu pointer handlers are not the only touch input.
cricket-123|Actual train game: mobile accelerate/brake plus vertical lane swipe; action flag maps to Space.
crossy-road|Four DOM click buttons call move(forward/backward/left/right); global pointerdown only starts the game.
curve-snake|Canvas touchstart toggles turnDir in the 0,1,-1,0 cycle; Space is the desktop equivalent.
demon|Touch left/right/jump/attack flags feed movement, floor transition and attack alongside keyboard state.
dodge-enemy|Gameplay pointerdown/up/move feeds movement; keyboard is explicitly the fallback update path.
doodle-jump|Gameplay left/right screen touch zones set moveLeft/moveRight consumed with cursor keys.
dream-weaver|Raw source originally lacked mobile movement; source repair adds explicit left/right/jump buttons. Verify served version.
endless-mafia|Virtual joystick handlers move the hero and mobile shoot button calls shooting; keyboard also supports actions.
endless-runner|Pointer down/up measures swipe direction and calls jump/slide; Up/Down are alternatives.
fighter-jet|Gameplay joystick knob drag updates movement; menu/replay are not the only pointer handlers.
football|Touch buttons press/release virtual ArrowLeft/Right/Up keys; update reads those virtual keys.
forest-runner|Gameplay pointer handler provides double jump and sliding actions; keyboard remains additional support.
fruit-basket|Dragging while pointer is held updates basket position; arrows are the alternative steering method.
luma-bounce|Left/right/jump touch flags and releaseBounce implement the same bounce mechanic as keyboard press/release.
gunman|Gameplay pointerdown calls onShoot; the action button offers an additional touch target.
gun-run|Joystick pointermove sets hero velocity; update deliberately avoids resetting keyboard velocity while joystick.dragging.
hungry-player|Gameplay pointermove controls the player; keyboard mentions are listener cleanup rather than required movement.
kaiju-krush|Mobile leftHeld/rightHeld and punch button call actual movement and tryPunch, alongside cursors/Space.
mario|Mobile flags set left/right/jump; update preserves them and consumes jump taps while grounded.
one-car|Gameplay pointerdown calls moveCar; keyboard provides discrete lane changes through JustDown.
pacman|Four held mobile direction flags are used in the same update branches as cursor keys.
parkour|Mobile left/right/action flags feed horizontal velocity and grounded jump alongside cursors.
pathfinder|Four held touch buttons set heldDir, consumed by the same directional update as cursor keys.
pirates|Virtual joystick feeds movement and touchAction feeds shooting alongside cursor/Ctrl fallbacks.
planet-war|Joystick direction feeds horizontal movement and jump/fire/shield buttons supply actual actions.
projectile-enemy|Right-half tap shoots; left-side touch movement and pointer release coexist with keyboard vertical movement.
red-light-green-light|Pointer hold sets touchActive, consumed with Space to move while held.
road-cross|Four touch buttons directly call tryMovePlayer with the appropriate tile delta.
road-fighter|Mobile buttons provide lane snaps and dash; keyboard Q/E shortcuts are additional lane controls.
robot-destruction|JoystickActive/direction feed movement and mobile jump flag is consumed alongside cursor Up.
shadow-runner|Confirmed missing action: the only pointerdown-to-lightBlast binding is commented out; Space is the only live call.
shadow-shooter|Mobile up/down/shoot flags are consumed by update; held pointer movement also aims.
shape-collector|Mobile left/right flags feed the same horizontal movement branches as keyboard; action is intentionally unused.
shoot-enemy|Gameplay joystick down/move/up controls aiming and charge/release; keyboard Space/arrows are alternatives.
shooter|Held mobile left/right/shoot plus jump button call movement/fire/jump; pointer hold can also fire.
sky-high|Joystick forceX moves and negative forceY jumps; shield button calls activateShield alongside Space.
snake-and-ladder|Dice sprite pointerdown rolls the dice; Space/Enter are only shortcuts.
sniper|Game buttons and drag/hold controls operate actual gameplay; D is a keyboard debug shortcut.
space-fighter|Gameplay pointer down/move/up controls movement and shooting; cursor/Space bindings are alternatives.
spaceman|Gameplay pointer swipe direction feeds the same movement branch as cursor keys.
space-waves|Active pointer isDown is consumed directly alongside Space/W/Up; absence of gameplay pointer listeners is not a blocker.
stick-game|Gameplay pointerdown/up implements the held action and release; keyboard mention is not required movement.
stick-toss|Gameplay pointerdown operates the timing mechanic; menus are not the only touch input.
straight-rush|Gameplay pointerdown calls charge and pointerup calls fire; later switching the listeners implements the cycle.
survival-run|Joystick movement and action button flags are consumed alongside keyboard directions/Space.
survivor|Joystick X moves and upward joystick threshold triggers a one-shot jump; action button shoots. Down/S quick-turn is extra.
table-tennis|Mobile buttons move the paddle up/down. Space stored-power handler is a no-op because powers apply on pickup.
tetris|Touch swipes and five screen controls move/rotate/drop pieces; keyboard arrows/Space are alternatives.
that-level-again-1|Touch buttons set held left/right and jump directly; keyboard jump is an additional update path.
that-level-again-2|Touch buttons set held left/right and jump directly; keyboard jump is an additional update path.
that-level-again-3|Touch jump is handled on pointerdown; the update comment explicitly identifies keyboard-only branch as fallback.
that-level-again-4|Touch jump is handled on pointerdown; left/right held flags are consumed alongside keyboard states.
that-level-again-5|Touch buttons set held left/right and jump directly; the keyboard branch is not the only jump path.
thunder-god|Mobile directional flags feed four-way movement; touch action and gesture controls supplement keyboard Shift dash.
tower-shooter|Mobile left/right/action flags feed update movement and the action path alongside cursor keys.
vaccine-shooter|Mobile left/right steer and held action fires; action double tap bursts. Keyboard-only up/down is an asymmetry.
wordle|On-screen keyboard hit areas feed handleKeyboardTap; physical keyboard listener is an alternative.
penalty|Screen left/right/action buttons call the same press methods as cursor/Space JustDown.
swipe-assassin|Canvas pointerdown/up measures the swipe vector; mobile is the primary interaction.
level-devil|Confirmed raw blocker: only keydown/up writes keys; animate reads ArrowLeft/Right/A/D for camera X. No touch handler.
""".strip().splitlines())

RAW_FINDINGS = [
    {"slug": "level-devil", "kind": "missing_mobile_movement", "status": "reported_to_runtime_owner",
     "evidence": "index.html keydown/up stores keys; animate reads ArrowLeft/Right/A/D for camera X; no touch/pointer listeners.",
     "metadata_mismatch": "Actual auto-forward 3D tunnel with distance and torus obstacles; original metadata describes platform traps."},
    {"slug": "shadow-runner", "kind": "missing_mobile_action", "status": "reported_to_source_repairs_owner",
     "evidence": "Scenes/GameScene.js:130 Space calls _lightBlast; :462 equivalent pointerdown is commented; :463-464 only reset visuals.",
     "impact": "Mobile action button cannot spend a charge to clear shadows."},
    {"slug": "vaccine-shooter", "kind": "partial_input_asymmetry", "status": "metadata_clarification_reported",
     "evidence": "Scenes/GameScene.js:275-278 mobile flags exist only for left/right, while keyboard supports vertical movement too; double-tap action burst exists."},
]


def evidence(source: Path):
    raw = source.read_bytes()
    lines = raw.decode("utf-8", errors="replace").splitlines()
    keyboard, touch = [], []
    for index, line in enumerate(lines):
        trimmed = line.strip()
        # Record commented candidate separately: it must never count as a live handler.
        commented = trimmed.startswith("//")
        record = {"line": index + 1, "code": trimmed[:500], "commented": commented,
                  "context": "\n".join(lines[max(0, index-1):min(len(lines), index+4)])}
        if KEYBOARD.search(line):
            keyboard.append(record)
        if TOUCH.search(line):
            touch.append(record)
    return {"path": str(source.relative_to(ROOT)), "sha256": hashlib.sha256(raw).hexdigest(),
            "keyboard_evidence": keyboard, "touch_evidence": touch}


def snapshot_english():
    observed = {
        "chess": ["Flip Board"],
        "dream-weaver": ["Stand still", "Overstay"],
        "snake": ["Swipe to control the snake.", "Eat food to grow longer"],
        "sudoku": ["Limpar Cell"],
    }
    results = []
    for slug, needles in observed.items():
        path = ROOT / "artifacts" / "adapted-second" / f"{slug}-mobile.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        hits = []
        for phase in ["before", "after"]:
            for text in data.get(phase, {}).get("text", []):
                if any(needle in text for needle in needles):
                    hits.append({"phase": phase, "text": text})
        if hits:
            results.append({"slug": slug, "snapshot": str(path.relative_to(ROOT)), "hits": hits,
                            "status": "old_adapter_snapshot_reported_to_translation_owner_not_live_retested"})
    return results


def main():
    catalog = json.loads((ROOT / "data" / "registry.json").read_text(encoding="utf-8"))
    metadata = json.loads((ROOT / "data" / "catalog-pt.json").read_text(encoding="utf-8"))
    games = []
    for game in catalog["games"]:
        entry = MIRROR / game["path"]
        sources = sorted({entry, *entry.parent.rglob("*.js")})
        sources = [source for source in sources if source.exists() and source.stat().st_size < 500_000
                   and not LIBRARY.search(source.name)]
        records = [evidence(source) for source in sources]
        note = MANUAL_NOTES.get(game["slug"])
        games.append({"slug": game["slug"], "name_pt": metadata.get(game["slug"], {}).get("name"),
                      "controls_pt": metadata.get(game["slug"], {}).get("controls_pt"),
                      "manual_control_path_review": note,
                      "assessment": "manual_source_trace" if note else "source_inventory_only_no_playability_claim",
                      "sources": records})
    report = {"scope": "Pinned raw source and old adapted-second snapshots. Not a live mobile playthrough or a pass/fail release gate.",
              "games_scanned": len(games), "manual_source_traces": sum(bool(game["manual_control_path_review"]) for game in games),
              "raw_findings": RAW_FINDINGS, "old_snapshot_english": snapshot_english(), "games": games}
    output = ROOT / "artifacts" / "touch-control-audit.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"games_scanned": len(games), "manual_source_traces": report["manual_source_traces"],
                      "raw_findings": len(RAW_FINDINGS), "old_english_leaks": len(report["old_snapshot_english"]),
                      "report": str(output)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
