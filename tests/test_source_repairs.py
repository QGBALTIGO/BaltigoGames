import json

from app.source_repairs import DREAM_WEAVER_CONFIG, apply_source_repairs


def repaired_json(path, data):
    return json.loads(apply_source_repairs(path, json.dumps(data).encode(), "application/json"))


def test_unknown_game_and_binary_assets_are_byte_identical():
    for path in ["games/arcade/snake/index.html", "games/arcade/dream-weaver/assets/images/player.png"]:
        original = b"\xff\xd8\x00original bytes"
        assert apply_source_repairs(path, original, "image/png") == original


def test_dream_manifest_recovers_empty_invalid_source_and_preserves_valid_config():
    path = "games/arcade/dream-weaver/config.json"
    for invalid in [b"", b"not JSON", b"\xff"]:
        assert json.loads(apply_source_repairs(path, invalid)) == DREAM_WEAVER_CONFIG
    original = b'{"mechanics":{"bridgeAfterMs":900}}'
    assert apply_source_repairs(path, original) == original
    assert set(DREAM_WEAVER_CONFIG["assets"]) == {"player", "music", "jump", "morph"}


def test_dream_source_repair_enables_real_sprite_controls_failure_and_clean_restart():
    source = b"""class DreamWeaverScene extends Phaser.Scene {
  preload() {
    this.load.image('background', 'assets/images/background.png');
    this.load.image('player',     'assets/images/player.png');
    this.load.image('platform',   'assets/images/platform.png');
    this.load.image('spike',      'assets/images/spike.png');
    this.load.image('gate',       'assets/images/gate.png');
  }
  create() {
    const W = this.scale.width, H = this.scale.height;

    // Background
    this.physics.world.setBounds(0, 0, W, H);
    this.gate.displayHeight = 160; this.gate.displayWidth = 80;
      this.player.setScale(s);
    this.input.keyboard.on('keydown-SPACE', () => { if (this.started) this.queueJump(); });
    this.makeEndOverlay();
  }
  makeStartOverlay() {}
  startGame() {
    this.started = true;
  }
  showEnd() {}
  tryDoJump(onFloor) {
    if ((this.jumpQueued || withinBuffer) && (onFloor || withinCoyote)) {}
  }
}"""
    path = "games/arcade/dream-weaver/index.html"
    repaired = apply_source_repairs(path, source).decode()
    assert "this.load.spritesheet('player'" in repaired
    assert "frameWidth:100, frameHeight:155, endFrame:8" in repaired
    assert "createDreamTextures(this)" in repaired
    for texture in ["background", "platform", "spike", "gate", "dream-spark"]:
        assert f"draw('{texture}'" in repaired
    for missing in ["background", "platform", "spike", "gate"]:
        assert f"// this.load.image('{missing}'," in repaired
    assert "checkCollision.down = false" in repaired
    assert "this.gate.body.updateFromGameObject()" in repaired
    assert "keydown-UP" in repaired
    assert "makeTouchControls()" in repaired
    assert "this.physics.world.pause()" in repaired
    assert "this.physics.world.resume()" in repaired
    assert "this.platforms = []; this._platformByGO = new Map();" in repaired
    assert "const requestedJump = this.jumpQueued;" in repaired
    assert "if ((requestedJump || withinBuffer) && (onFloor || withinCoyote))" in repaired
    assert apply_source_repairs(path, repaired.encode()).decode() == repaired
    assert apply_source_repairs("/play/" + path, source).decode() == repaired
    # The pinned upstream HTML uses CRLF. Multi-line repairs must still insert
    # texture creation before the scene starts using those textures.
    assert apply_source_repairs(path, source.replace(b"\n", b"\r\n")).decode() == repaired


def test_bird_preserves_core_player_enemy_and_existing_particle_explosion():
    config = {"spritesheets": {"bird_flap": {"url": "assets/hero.png"},
                              "shard_break": {"url": "assets/spritesheets/shard_break.png"}},
              "images1": {"player": "assets/player.png", "enemy": "assets/shard.png"},
              "gameplay": {"targetScore": 100}}
    repaired = repaired_json("games/shooter/bird-shooter/config.json", config)
    assert repaired["spritesheets"] == {}
    assert repaired["images1"] == config["images1"]
    assert repaired["gameplay"] == config["gameplay"]


def test_color_dash_reuses_shipped_character_and_keeps_color_state_visible():
    config = {"spritesheets": {"player_colors": {"url": "assets/player_colors.png", "frameWidth": 64, "frameHeight": 64}},
              "gameplay": {"startColor": "blue"}}
    repaired = repaired_json("games/arcade/color-dash/config.json", config)
    assert repaired["spritesheets"]["player_colors"] == {
        "url": "assets/hero.png", "frameWidth": 100, "frameHeight": 155, "frames": 9}
    assert repaired["gameplay"] == config["gameplay"]
    source = b"this.player = this.physics.add.sprite(x, y, 'player_colors', 0);\n    this.playerColor = colorName;"
    patched = apply_source_repairs("games/arcade/color-dash/Scenes/GameScene.js", source)
    assert b".setScale(0.65)" in patched
    assert b"setTint(this.colors[colorName]" in patched
    assert apply_source_repairs("games/arcade/color-dash/Scenes/GameScene.js", patched) == patched


def test_demon_uses_valid_frame_dimensions_and_real_final_boss_variant():
    config = {"spritesheets": {"akaza_boss": {"url": "assets/akaza.png", "frameWidth": 165, "frameHeight": 228, "frames": 4},
                              "akaza14_boss": {"url": "assets/akaza14.png", "frameWidth": 172, "frameHeight": 413},
                              "akaza15_boss": {"url": "assets/akaza15.png"}}}
    patched = repaired_json("games/arcade/demon/config.json", config)
    first = patched["spritesheets"]["akaza_boss"]
    assert first["frameHeight"] <= 226 and first["frameWidth"] <= 192
    assert first["frames"] == 1
    assert patched["spritesheets"]["akaza15_boss"] == patched["spritesheets"]["akaza14_boss"]
    path = "games/arcade/demon/Scenes/GameScene.js"
    source = b"const ft = tex.frameTotal || 1;\nconst ft = tex?.frameTotal || 1;"
    repaired = apply_source_repairs(path, source)
    assert repaired.count(b"-1)") == 2
    assert apply_source_repairs(path, repaired) == repaired


def test_flip_jump_uses_shipped_soundtrack_and_audio_failure_does_not_abort_game():
    config = {"audio": {"bgm": "https://expired.example/temporary.mp3", "bomb": "assets/bomb.mp3"}, "game": {"playerSpeed": 300}}
    repaired = repaired_json("games/platformer/flip-jump/config.json", config)
    assert repaired["audio"] == {"bgm": "assets/bgm.mp3", "bomb": "assets/bomb.mp3"}
    assert repaired["game"] == config["game"]
    source = b"    if (!this.bgmSound) {\n      this.bgmSound = this.sound.add('bgm', { loop: true, volume: 0.5 });\n    }\n    this.bgmSound.play();\n    this.initSceneFromConfig();"
    repaired_source = apply_source_repairs("games/platformer/flip-jump/mechanics.js", source)
    assert b"if (this.cache.audio.exists('bgm'))" in repaired_source
    assert b"this.initSceneFromConfig();" in repaired_source


def test_fruit_basket_removes_invalid_listener_without_removing_real_drag_input():
    path = "games/casual/fruit-basket/mechanics.js"
    source = b"this.input.on('pointerdown', pointer => { this.touchPointer = pointer; });\n    this.input.once('pointerdown', null);\n        this.setupInput();\n    this.scene.restart = () => { window.game.scene.keys['GameScene'].scene.restart(); };"
    repaired = apply_source_repairs(path, source)
    assert b"once('pointerdown', null)" not in repaired
    assert b"this.touchPointer = pointer" in repaired
    assert b"removeAllListeners" not in repaired
    assert b"this.setupInput();" not in repaired
    assert b"this.scene.restart =" not in repaired
    assert apply_source_repairs(path, repaired) == repaired


def test_math_quest_keeps_actual_character_and_drops_only_unused_eve_loader():
    source = b'''      this.load.spritesheet("eve", sheetUrl, {
        frameWidth: frameW,
        frameHeight: frameH,
      });
      this.load.spritesheet("character", `${basePath}/${charSheet.url}`, {frameWidth:100,frameHeight:158});'''
    patched = apply_source_repairs("games/word-quiz/math-quest/mechanics.js", source)
    assert b'this.load.spritesheet("eve"' not in patched
    assert b'this.load.spritesheet("character"' in patched


def test_orbital_removes_unreferenced_solar_asset_and_keeps_spaceship():
    source = b'''            solar: "assets/solar.png",
            spaceship: "assets/spaceship.png",
    this.station = this.add.image(540,960,'spaceship');'''
    patched = apply_source_repairs("games/3d/orbital-outpost/mechanics.js", source)
    assert b"assets/solar.png" not in patched
    assert b"assets/spaceship.png" in patched
    assert b"this.station =" in patched


def test_signal_circuit_removed_widget_is_optional_and_real_win_still_runs():
    source = b"if (visited[key]) { this.winGame(); } else {\n      this.winText.setText('');\n}"
    patched = apply_source_repairs("games/puzzle/signal-circuit/mechanics.js", source)
    assert b"this.winText?.setText('');" in patched
    assert b"this.winGame();" in patched


def test_penalty_configuration_is_passed_before_scene_creation():
    source = b'''<script type="module">
const phaserConfig = {
        scene: [GameScene, WinScene, GameOverScene]
};
const game = new Phaser.Game(phaserConfig);
      game.scene.getScene('GameScene').events.once('create', function(){
        this.registry.set('cfg', cfg);
      });
</script>'''
    path = "games/sports/penalty/index.html"
    patched = apply_source_repairs(path, source)
    assert b"callbacks: { preBoot:" in patched
    assert b"game.scene.getScene('GameScene').events.once" not in patched
    assert apply_source_repairs(path, patched) == patched


def test_swipe_assassin_player_elimination_reuses_real_elimination_audio():
    config = {"audio": {"bgm": "assets/bgm.mp3", "kill": "assets/kill.mp3"}, "gameplay": {"grid": 6}}
    repaired = repaired_json("games/arcade/swipe-assassin/config.json", config)
    assert repaired["audio"]["gameover"] == "assets/kill.mp3"
    assert repaired["gameplay"] == config["gameplay"]


def test_sudoku_fits_both_orientations_and_accepts_real_sudoku_solutions():
    path = "games/puzzle/sudoku/index.html"
    source = b"<head></head><script>function checkWin(){if(JSON.stringify(grid)===JSON.stringify(solutionA)||JSON.stringify(grid)===JSON.stringify(solutionB)){triggerWin();}}</script>"
    repaired = apply_source_repairs(path, source)
    assert b"repeat(9,minmax(0,1fr))" in repaired
    assert b"calc(100dvh - 24px)" in repaired
    assert b"grid-template-columns:repeat(3,minmax(0,1fr))" in repaired
    assert b"validPlacement(r,c,value)" in repaired
    assert b"JSON.stringify(grid)===JSON.stringify(solutionA)" not in repaired
    assert apply_source_repairs(path, repaired) == repaired


def test_sudoku_exposes_a_real_new_round_action_after_win_or_timeout():
    path="games/puzzle/sudoku/index.html"
    source=b'<head></head><div class="controls"><div class="btn" id="clearBtn">Clear Cell</div></div>'
    repaired=apply_source_repairs(path,source)
    assert b'id="newGameBtn" onclick="location.reload()"' in repaired
    assert b'flex-wrap:wrap' in repaired
    assert apply_source_repairs(path,repaired)==repaired


def test_crossy_end_controls_fit_width_without_clipping_buttons():
    path = "games/arcade/crossy-road/index.html"
    repaired = apply_source_repairs(path, b"<head></head><body></body>")
    assert b"width:min(92vw,560px)" in repaired
    assert b"min-width:0;max-width:100%" in repaired
    assert b"overflow-wrap:anywhere" in repaired
    assert b"pointer-events:auto" in repaired
    assert apply_source_repairs(path, repaired) == repaired


def test_shadow_runner_mobile_action_spends_real_charge_and_preserves_button_fit():
    source = b"""      this.btnAction.setDisplaySize(100, 100);
      // this.btnAction.on('pointerdown', () => { this.btnAction.setScale(0.9); this.btnAction.setAlpha(0.85); this._lightBlast(); });
      this.btnAction.on('pointerup', () => { this.btnAction.setScale(1); this.btnAction.setAlpha(1); });"""
    path = "games/racing/shadow-runner/Scenes/GameScene.js"
    repaired = apply_source_repairs(path, source)
    assert b"// this.btnAction.on('pointerdown'" not in repaired
    assert b"this.btnAction.on('pointerdown'" in repaired
    assert b"this._lightBlast();" in repaired
    assert b"setScale(1)" not in repaired
    assert b"Math.ceil(44*this.W/(this.game.canvas.getBoundingClientRect().width||this.W))" in repaired
    assert b"setDisplaySize(actionSize,actionSize)" in repaired
    assert apply_source_repairs(path, repaired) == repaired


def test_train_simulator_track_uses_the_actual_shipped_artwork():
    config = {"images": {"train": "assets/train.png", "platform": "assets/platform2.png"},
              "gameplay": {"targetStations": 5}}
    repaired = repaired_json("games/sports/cricket-123/config.json", config)
    assert repaired["images"]["track"] == "assets/track.png"
    assert repaired["images"]["train"] == config["images"]["train"]
    assert repaired["gameplay"] == config["gameplay"]


def test_link_palette_matches_real_level_pairs_and_keeps_their_shipped_images():
    pairs = [{"color": "red", "a": [0,0], "b": [2,0]}, {"color": "green", "a": [0,1], "b": [2,1]}]
    config = {"gameplay": {"levels": [{"colors": {"red": "#ff0000", "green": "#00ff00", "blue": "#0000ff"}, "pairs": pairs}]},
              "images1": {"red": "assets/red.png", "green": "assets/green.png"}}
    repaired = repaired_json("games/puzzle/link/config.json", config)
    level = repaired["gameplay"]["levels"][0]
    assert level["colors"] == {"red": "#ff0000", "green": "#00ff00"}
    assert level["pairs"] == pairs
    assert repaired["images1"] == config["images1"]


def test_ludo_waits_for_human_roll_and_has_real_victory_and_restart():
    source = b'''<head></head><script>
async function turn(){
    await performMove(p,m.t,d);
}
async function performMove(p,t,d){
  renderTokens();
  return true;
}

function rollDice(){return 6;}
function humanChoose(p,t){
  awaitingHuman=false;
  performMove(p,t,lastDice).then(()=>{
    if (lastDice===6) turn();
    else endTurn();
  });
}
renderTokens();
turn();
</script>'''
    path = "games/board/ludo/index.html"
    repaired = apply_source_repairs(path, source)
    assert b"async function takeLudoTurn()" in repaired
    assert b"rollButton.addEventListener('click'" in repaired
    assert b"tokens[p].every(token=>token.steps===FINAL_STEP)" in repaired
    assert b"function finishLudo(winner)" in repaired
    assert b"function resetLudo()" in repaired
    assert b"gameOver || !awaitingHuman" in repaired
    assert b"if(gameOver)return;" in repaired
    assert b"baltigo-ludo-layout" in repaired
    assert apply_source_repairs(path, repaired) == repaired


def test_tic_tac_toe_reserves_one_human_turn_during_the_ai_delay_and_resets():
    source = b"""  resetState() {
    this.gameOver = false;
    this.state = 'start';
  }
  startGame() {
    this.state = 'playing';
  }
  handlePointerDown(pointer) {
    if (this.gameOver || this.state !== 'playing') return;
    if (!this.board[row][col]) {
      this.makeMove(row, col, 'X');
      if (!this.gameOver) {
        this.time.delayedCall(300, () => this.computerMove());
      }
    }
  }
  checkWinner(player) { return 'unchanged'; }
"""
    path = "games/board/tic-tac-toe/mechanics.js"
    repaired = apply_source_repairs(path, source).decode()
    assert "this.state !== 'playing' || this.isComputerTurn" in repaired
    assert repaired.index("this.isComputerTurn = true;") < repaired.index("this.makeMove(row, col, 'X');")
    assert "this.computerMove();\n          this.isComputerTurn = false;" in repaired
    assert "} else {\n        this.isComputerTurn = false;" in repaired
    assert "resetState() {\n    this.isComputerTurn = false;" in repaired
    assert "this.state = 'playing';\n    this.isComputerTurn = false;" in repaired
    assert "checkWinner(player) { return 'unchanged'; }" in repaired
    assert apply_source_repairs(path, repaired.encode()) == repaired.encode()


def test_demon_replay_resets_actual_wave_and_mobile_exit_is_a_large_guarded_button():
    path="games/arcade/demon/Scenes/GameScene.js"
    source=b"""class GameScene {
  init() {
    // track timers / delayed calls so we can clean them on restart
    this._scheduled=[];
  }
  _spawnStairs() { this.oldHint='tiny, keyboard only'; }
  _nextFloor() {
    this.state.floor++;
  }
}
"""
    repaired=apply_source_repairs(path,source).decode()
    assert "this.state={floor:1,kills:0,cleared:false" in repaired
    assert "this.akazaIsActive=false;this.playerIsDead=false;" in repaired
    assert "oldHint" not in repaired
    assert "Math.ceil(50/Math.max(.05,ratio))" in repaired
    assert "setName('next-wave').setInteractive" in repaired
    assert "this.nextFloorHint.on('pointerdown'" in repaired
    assert "this.cursors.up.isDown||this.keyW.isDown" in repaired
    assert "_nextFloor() {\n    if(!this.state.cleared)return;" in repaired
    assert apply_source_repairs(path,repaired.encode())==repaired.encode()


def test_road_cross_next_uses_authored_level_callback_and_loss_replay_resets():
    path="games/arcade/road-cross/mechanics.js"
    source=b"""    _reallyCreate() {
    }
    _showWinScreen(onNext) {
                this.notifyParent('sceneComplete', { result: 'win' });
    }
    _showEndScreen(message, color, onRestart) {
        btn.once('pointerup', () => {
            this.input.enabled = false;
            this._preRestartCleanup();
            this.time.delayedCall(0, () => this.scene.restart());
        });
    }
"""
    repaired=apply_source_repairs(path,source).decode()
    assert "this.input.enabled = true;" in repaired
    assert "typeof onNext==='function')onNext()" in repaired
    assert "typeof onRestart==='function')onRestart()" in repaired
    assert "this.notifyParent('sceneComplete'" not in repaired
    assert apply_source_repairs(path,repaired.encode())==repaired.encode()


def test_penalty_completed_cpu_kick_does_not_start_another_and_replay_resets_match():
    path="games/sports/penalty/gamescene.js"
    source=b"""  create() {
    const gcfg = this.sys.game.config;
  }
          this._setTurn('CPU_SHOT'); // reset to shot will handle end-of-round in _nextTurn
          this._nextTurn(650);
"""
    repaired=apply_source_repairs(path,source).decode()
    assert "this._setTurn('CPU_SHOT')" not in repaired
    assert "this.turn = 'CPU_SHOT';\n          this.busy = true;" in repaired
    assert "this._nextTurn(650)" in repaired
    assert "this.playerScore=0;this.cpuScore=0;this.round=1;this.inSuddenDeath=false;" in repaired
    assert "this.inputFlags={left:false,right:false,action:false};" in repaired
    assert apply_source_repairs(path,repaired.encode())==repaired.encode()


def test_perfect_square_allows_time_for_its_actual_three_level_animations():
    path="games/puzzle/perfect-square/config.json"
    config={"mechanics":{"timeLimit":2,"totalLevels":3,"holeWidthRange":[40,240]}}
    repaired=repaired_json(path,config)
    assert repaired["mechanics"]=={"timeLimit":60,"totalLevels":3,"holeWidthRange":[40,240]}
    config["mechanics"]["timeLimit"]=90
    assert repaired_json(path,config)==config


def test_alien_battle_freezes_once_and_replay_leaves_teardown_to_phaser():
    path="games/shooter/alien-battle/mechanics.js"
    source=b"""function win(scene) {
  scene.input.off('pointerdown');
    scene.scene.restart();
    scene.children.list.forEach(child => child.destroy());
}
function gameovr(scene) {}
function startGame(scene) {}
  create() {
    const levelData = this.cache.json.get('levelConfig');
  }
"""
    repaired=apply_source_repairs(path,source).decode()
    assert "if(scene.hasEnded)return;" in repaired
    assert "scene.physics.pause();scene.input.off('pointerdown');scene.input.off('pointerup');" in repaired
    assert "scene.children.list.forEach" not in repaired
    assert "scene.hasEnded=false;scene.isGameStarted=true;scene.physics.resume();" in repaired
    assert "this.hasEnded=false;this.isGameStarted=false;this.input.removeAllListeners();" in repaired
    assert apply_source_repairs(path,repaired.encode())==repaired.encode()


def test_penalty_vector_fallback_is_drawn_once_and_has_native_visible_touch_bounds():
    path="games/sports/penalty/gamescene.js"
    source=b"""    const g = this.add.graphics();
    g.fillStyle(color, 1);
    g.fillRoundedRect(x - w * 0.5, y - h * 0.5, w, h, Math.min(12, w * 0.1));

    // Emulate size props expected elsewhere, without touching methods
    g.x = x;
    g.y = y;
    g.displayWidth = w;
    g.displayHeight = h;

    // Important: leave g.setDepth and g.destroy as-is to avoid recursion
    return g;
      const hit = new Phaser.Geom.Rectangle(-size / 2, -size / 2, size, size);
      s.setInteractive({
        hitArea: hit,
        hitAreaCallback: Phaser.Geom.Rectangle.Contains,
        useHandCursor: true
      });
"""
    repaired=apply_source_repairs(path,source).decode()
    assert "g.fillRoundedRect" not in repaired
    assert "this.add.circle(x,y,w/2,color)" in repaired
    assert "this.add.rectangle(x,y,w,h,color)" in repaired
    assert "s.setInteractive({useHandCursor:true})" in repaired
    assert "'ESQ.':key===rightKey?'DIR.':'AÇÃO'" in repaired
    assert apply_source_repairs(path,repaired.encode())==repaired.encode()


def test_chess_button_child_gesture_relays_to_shared_container_action_once():
    path="games/board/chess/index.html"
    source=b"""<script type="module">
            img.setScale(scale).setInteractive({ useHandCursor: true });
            group.setInteractive(new Phaser.Geom.Rectangle(-50,-30,100,60),Phaser.Geom.Rectangle.Contains);
            rect.setStrokeStyle(2, 0x24355f, 1).setInteractive({ useHandCursor: true });
          playBtn.list.forEach(ch => ch.setInteractive?.({ useHandCursor: true }).on?.('pointerdown', () => this.startGame()));
            replayBtn.on('pointerdown',()=>{this.resetGame(false);this.startGame();});
          return group;
    </script>"""
    repaired=apply_source_repairs(path,source)
    assert b"img.setScale(scale).setInteractive" not in repaired
    assert b"setStrokeStyle(2, 0x24355f, 1).setInteractive" not in repaired
    assert b"group.setInteractive" in repaired
    assert b"playBtn.list.forEach" not in repaired
    assert b"child.setInteractive({useHandCursor:true}).on('pointerdown',(...args)=>group.emit('pointerdown',...args))" in repaired
    assert b"this.resetGame(false);this.startGame();" in repaired
    assert apply_source_repairs(path,repaired)==repaired


def test_swipe_assassin_real_next_restarts_round_instead_of_alerting_a_placeholder():
    path="games/arcade/swipe-assassin/index.html"
    source=b'''<script type="module">
function nextLevel(){alert("Next level JSON hook");}
document.querySelector("#winOverlay .secondary").textContent=texts.next_button;
</script>'''
    repaired=apply_source_repairs(path,source)
    assert b"alert(" not in repaired
    assert b"completeAndRestart({result:'win'})" in repaired
    assert b'textContent="Nova partida"' in repaired
    assert apply_source_repairs(path,repaired)==repaired


def test_stack_tower_consumes_only_the_game_gesture_without_touching_overlay_actions():
    path="games/3d/stack-tower/index.html"
    source=b'''<script type="module">
    window.addEventListener("pointerdown", () => {
      if (playing) {
        playDrop();
        drop();
      }
    });
    </script>'''
    repaired=apply_source_repairs(path,source)
    assert b'event.target.closest?.("button,.overlay")' in repaired
    assert b'event.preventDefault()' in repaired
    assert b'setPointerCapture(event.pointerId)' in repaired
    assert b'event.detail>0' in repaired
    assert b'event.stopImmediatePropagation()' in repaired
    assert b'if(event.target.closest?.(".overlay button"))baltigoCanvasGesture=false;' in repaired
    assert b'{passive:false}' in repaired
    assert apply_source_repairs(path,repaired)==repaired


def test_fighter_jet_final_collision_stops_timers_before_destroyed_jet_is_reused():
    path="games/shooter/fighter-jet/mechanics.js"
    source=b"""        callback: () => {
            if (!scene.jet.active) return;
        }
            this.gameEnded = true;
            this.physics.world.pause();
            this.jet.destroy();this.jet=null;
"""
    repaired=apply_source_repairs(path,source)
    assert b"scene.gameEnded || !scene.jet?.active" in repaired
    assert b"this.gameEnded = true;\n            this.time.removeAllEvents();" in repaired
    assert apply_source_repairs(path,repaired)==repaired


def test_parkour_shutdown_does_not_clear_groups_already_destroyed_by_phaser():
    path="games/platformer/parkour/Scenes/GameScene.js"
    source=b"""_onShutdown() {
  if (this.fireballs) { this.fireballs.clear(true, true); this.fireballs = null; }
  if (this.platforms) { this.platforms.clear(true, true); this.platforms = null; }
  this.ready = false;
}
"""
    repaired=apply_source_repairs(path,source)
    assert b"if(this.fireballs.children)this.fireballs.clear(true, true)" in repaired
    assert b"if(this.platforms.children)this.platforms.clear(true, true)" in repaired
    assert b"this.fireballs = null" in repaired and b"this.platforms = null" in repaired
    assert apply_source_repairs(path,repaired)==repaired


def test_tee_shooter_overlay_gestures_stop_phaser_before_gameplay_listener_runs():
    path="games/shooter/tee-shooter/mechanics.js"
    callback=b""".on('pointerdown', (pointer) => {
      pointer.event.stopPropagation();
      this.gameState = 'playing';
      this.startGame();
    });
"""
    source=callback*4+b"this.input.on('pointerdown', pointer => this.handleTap(pointer));"
    repaired=apply_source_repairs(path,source)
    assert repaired.count(b"eventData?.stopPropagation();")==4
    assert repaired.count(b"pointer.event.stopPropagation();")==4
    assert b"this.input.on('pointerdown', pointer => this.handleTap(pointer));" in repaired
    assert apply_source_repairs(path,repaired)==repaired


def test_screw_master_next_confirms_inside_actual_callback_not_registration_context():
    path="games/puzzle/screw-master/Scenes/WinScene.js"
    source=b"""    next.on('pointerdown', () => this.bgm && this.bgm.stop(),
      this.notifyParent('sceneComplete', { result: 'win' }));
"""
    repaired=apply_source_repairs(path,source)
    assert b"next.on('pointerdown', () => {" in repaired
    assert b"this.notifyParent('sceneComplete', { result: 'win' });\n    });" in repaired
    assert b"if(this.bgm)this.bgm.stop();" in repaired
    assert apply_source_repairs(path,repaired)==repaired


def test_vaccine_shooter_cleanup_skips_only_phaser_groups_already_destroyed():
    path="games/shooter/vaccine-shooter/Scenes/GameScene.js"
    source=b"""    const safeWipe = (grp) => {
      if (!grp?.getChildren) return;
      const kids = grp.getChildren().slice();
      for (const k of kids) k.destroy();
    };
"""
    repaired=apply_source_repairs(path,source)
    assert b"if (!grp?.getChildren || !grp.children) return;" in repaired
    assert b"const kids = grp.getChildren().slice();" in repaired
    assert b"for (const k of kids) k.destroy();" in repaired
    assert apply_source_repairs(path,repaired)==repaired


def test_flappy_terminal_gestures_cannot_restart_destroyed_bird_or_append_defeat():
    path="games/arcade/flappy/mechanics.js"
    source=b"""function handleClick(scene) {
  if (!scene.isGameStarted) startGame(scene,scene.config);
}
function updateScore(scene,config) {
  if(scene.score>=scene.targetscore) {
    scene.levelClearedTriggered = true;
    scene.time.delayedCall(500,()=>levelcleared(scene,config));
  }
}
function gameOverHandler(scene, config) {
  if (scene.gameOver) return;
  destroyPlayer(scene);
}
"""
    repaired=apply_source_repairs(path,source)
    assert b"scene.gameOver || scene.levelClearedTriggered || !scene.bird?.body" in repaired
    assert b"scene.levelClearedTriggered = true;\n    scene.physics.pause();" in repaired
    assert b"if (scene.gameOver || scene.levelClearedTriggered) return;" in repaired
    assert b"delayedCall(500" in repaired
    assert apply_source_repairs(path,repaired)==repaired
