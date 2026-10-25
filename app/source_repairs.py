"""Narrow repairs for reproducible defects in the pinned source game builds.

These edits precede the presentation/localization adapter. They preserve the
actual game and its shipped character/audio assets instead of replacing it with
an unrelated game or hiding broken asset requests.
"""
from __future__ import annotations

import json
import copy
from pathlib import PurePosixPath


DREAM_WEAVER_CONFIG = {
    "title": "Tecelão dos sonhos",
    "entry": "index.html",
    "assets": {
        "player": "assets/images/player.png",
        "music": "assets/audio/dream_music.mp3",
        "jump": "assets/audio/jump.mp3",
        "morph": "assets/audio/morph.mp3",
    },
    "generated_textures": ["background", "platform", "spike", "gate", "dream-spark"],
    "mechanics": {"bridgeAfterMs": 1000, "spikesAfterMs": 1900, "crumbleAfterMs": 2600},
    "controls": {"move": ["ArrowLeft", "ArrowRight"], "jump": ["ArrowUp", "Space"]},
}


_DREAM_HELPERS = r"""
// BALTIGO_SOURCE_REPAIR_DREAM_WEAVER_V1
// The upstream source explicitly designed vector fallbacks. Its repository
// ships only the character sheet and audio, so make the missing scenery into
// intentional, reusable game-specific textures before creating physics bodies.
function createDreamTextures(scene) {
  const draw = (key, width, height, paint) => {
    if (scene.textures.exists(key)) return;
    const graphics = scene.make.graphics({x: 0, y: 0, add: false});
    paint(graphics, width, height);
    graphics.generateTexture(key, width, height);
    graphics.destroy();
  };
  draw('background', 1080, 1920, (g,w,h) => {
    for (let y=0; y<h; y+=30) {
      const ratio=y/h;
      const color=(Math.round(8+ratio*11)<<16)|(Math.round(14+ratio*21)<<8)|Math.round(35+ratio*32);
      g.fillStyle(color,1); g.fillRect(0,y,w,30);
    }
    for (let i=0; i<150; i++) {
      const x=(i*173+61)%w, y=(i*347+103)%h;
      g.fillStyle(i%4 ? 0x8fb8df : 0xd9f9ff, i%3 ? 0.55 : 0.9);
      g.fillCircle(x,y,i%5 ? 1.5 : 3);
    }
    g.fillStyle(0x7df9ff,0.045); g.fillCircle(850,330,270);
    g.fillStyle(0x9f83ff,0.055); g.fillCircle(190,1240,330);
  });
  draw('platform',240,24,(g,w,h) => {
    g.fillStyle(0x233b58,1); g.fillRoundedRect(0,0,w,h,6);
    g.fillStyle(0x426780,1); g.fillRoundedRect(2,2,w-4,h-5,4);
    g.fillStyle(0xa7ffff,1); g.fillRect(5,2,w-10,3);
    g.fillStyle(0x132338,1); g.fillRect(8,h-5,w-16,3);
  });
  draw('spike',80,18,(g,w,h) => {
    for (let x=0; x<w; x+=16) {
      g.fillStyle(0xff5074,1); g.fillTriangle(x,h,x+8,0,x+16,h);
      g.fillStyle(0xffbed0,1); g.fillTriangle(x+8,0,x+8,h,x+12,h);
    }
  });
  draw('gate',80,160,(g,w,h) => {
    g.fillStyle(0x30d8ed,0.14); g.fillEllipse(w/2,h/2,w,h);
    g.fillStyle(0x7a6cf5,0.32); g.fillEllipse(w/2,h/2,w-20,h-22);
    g.lineStyle(5,0x7df9ff,1); g.strokeEllipse(w/2,h/2,w-10,h-10);
    g.lineStyle(2,0xe2ffff,0.9); g.strokeEllipse(w/2,h/2,w-22,h-22);
    g.fillStyle(0xb8ffff,0.85); g.fillCircle(w/2,h/2,5);
  });
  draw('dream-spark',12,12,(g) => {
    g.fillStyle(0x7df9ff,0.25); g.fillCircle(6,6,6);
    g.fillStyle(0xe2ffff,1); g.fillCircle(6,6,2.5);
  });
}
"""


_DREAM_INIT = r"""
  init() {
    // Phaser reuses a Scene instance when scene.restart() is called.
    this.player = null; this.cursors = null;
    this.moveLeft = false; this.moveRight = false; this.jumpQueued = false;
    this.started = false; this.gameOver = false; this.won = false;
    this.platforms = []; this._platformByGO = new Map();
    this.currentSurface = null; this.stillnessMs = 0; this.activeBridge = null;
    this.bridgeCollider = null; this.coyoteTimer = 9999;
    this.lastJumpRequest = -9999; this.pointerDown = false;
    this.sound?.stopByKey?.('music');
  }

"""


_DEMON_STAIRS = r"""
  _spawnStairs() {
    if (this.stairs || this.nextFloorHint) return;
    const gconf = this.sys.config || this.sys.game.config;
    const width = Number(gconf.width) || 1080;
    const height = Number(gconf.height) || 1920;
    const sKey = this._ensureTexture('stairs', 120, 64, 0x66ffaa);
    const stairs = this.physics.add.staticSprite(width - 120, height - 120, sKey).setDepth(2);
    stairs.setDisplaySize(140, 80).refreshBody();
    this.stairs = stairs;

    // The authored exit required standing on a tiny stair and holding Jump.
    // Keep that keyboard route, and expose an explicit mobile action above
    // the movement controls. Its hit area follows the real rendered canvas.
    const ratio=(this.game.canvas.getBoundingClientRect().width||width)/width;
    const buttonWidth=Math.max(420,Math.ceil(178/Math.max(.05,ratio)));
    const buttonHeight=Math.max(140,Math.ceil(50/Math.max(.05,ratio)));
    const buttonY=height-Math.max(350,buttonHeight/2+240);
    this.nextFloorHint=this.add.text(width/2,buttonY,'PRÓXIMA ONDA',{
      fontFamily:'Arial,sans-serif',fontStyle:'bold',color:'#07251c',
      backgroundColor:'#78e7bc',align:'center',
      fontSize:Math.ceil(16/Math.max(.05,ratio))+'px',
      fixedWidth:buttonWidth,fixedHeight:buttonHeight,
      padding:{top:Math.ceil((buttonHeight-20/Math.max(.05,ratio))/2)}
    }).setOrigin(.5).setDepth(50).setScrollFactor(0)
      .setName('next-wave').setInteractive({useHandCursor:true});
    this.nextFloorHint.on('pointerdown',(_pointer,_x,_y,event)=>{
      event.stopPropagation();
      if(this.state.cleared)this._nextFloor();
    });
    this.physics.add.overlap(this.player,stairs,()=>{
      if(this.state.cleared && (this.inputState.jump||this.cursors.up.isDown||this.keyW.isDown))this._nextFloor();
    });
  }
"""


_DREAM_CONTROLS = r"""
  makeTouchControls() {
    const W=this.scale.width, H=this.scale.height;
    this.input.addPointer(2);
    const button=(x,width,label,onDown,onUp) => {
      const box=this.add.rectangle(x,H-74,width,136,0x112a42,0.94)
        .setStrokeStyle(2,0x7df9ff,0.65).setScrollFactor(0).setDepth(100)
        .setInteractive({useHandCursor:true});
      this.add.text(x,H-74,label,{fontSize:'38px',fontFamily:'Arial',color:'#ddffff'})
        .setOrigin(0.5).setScrollFactor(0).setDepth(101);
      box.on('pointerdown',(pointer,localX,localY,event) => {
        event.stopPropagation();
        if (!this.started) this.startGame();
        if (this.gameOver || this.won) return;
        box.setFillStyle(0x21627c,1); onDown();
      });
      const release=() => {box.setFillStyle(0x112a42,0.94);onUp?.();};
      box.on('pointerup',release); box.on('pointerout',release);
    };
    button(118,192,'ESQUERDA',()=>{this.moveLeft=true;},()=>{this.moveLeft=false;});
    button(326,192,'DIREITA',()=>{this.moveRight=true;},()=>{this.moveRight=false;});
    button(W-160,270,'SALTAR',()=>this.queueJump());
    this.game.events.once('blur',()=>{this.moveLeft=false;this.moveRight=false;this.jumpQueued=false;});
  }

"""


_SUDOKU_LAYOUT = """
<style id="baltigo-sudoku-layout">
  .container{box-sizing:border-box;width:min(500px,94vw,calc(100dvh - 172px));max-height:100dvh;padding:8px 0}
  .sudoku{width:100%;max-width:100%;flex:none;grid-template-columns:repeat(9,minmax(0,1fr));grid-template-rows:repeat(9,minmax(0,1fr))}
  .cell{min-width:0;font-size:clamp(1rem,4.2vw,1.6rem);box-sizing:border-box}
  .timer{font-size:clamp(1rem,3vw,1.3rem);margin-bottom:8px}
  .num-pad{box-sizing:border-box;width:100%;max-width:100%;grid-template-columns:repeat(9,minmax(0,1fr));gap:clamp(2px,.8vw,8px);margin-top:clamp(6px,2vh,16px)}
  .num{box-sizing:border-box;min-width:0;padding:clamp(7px,2vh,12px) 0;font-size:clamp(.75rem,3.8vw,1.2rem);touch-action:manipulation}
  .controls{box-sizing:border-box;width:100%;justify-content:center;margin-top:8px;flex-wrap:wrap;gap:6px}
  .btn{font-size:clamp(.8rem,3.5vw,1rem);padding:10px 14px;touch-action:manipulation}
  #winMessage{font-size:clamp(1.5rem,6vw,3rem);max-width:90vw;text-align:center}
  @media(max-height:500px) and (min-width:600px){
    .container{display:grid;grid-template-columns:min(calc(100dvh - 24px),50vw) minmax(170px,1fr);grid-template-rows:auto 1fr auto;width:min(800px,96vw);height:calc(100dvh - 16px);padding:0;gap:8px 18px}
    .sudoku{grid-column:1;grid-row:1/4;width:min(calc(100dvh - 24px),50vw);align-self:center}
    .timer{grid-column:2;grid-row:1;margin:0;text-align:center}
    .num-pad{grid-column:2;grid-row:2;grid-template-columns:repeat(3,minmax(0,1fr));align-self:center;margin:0;gap:8px}
    .num{padding:10px 0;font-size:1.15rem}
    .controls{grid-column:2;grid-row:3;margin:0}
  }
  @media(max-height:320px) and (min-width:600px){
    .timer{font-size:1rem}
    .num-pad{gap:6px}
    .num{padding:5px 0;font-size:1rem}
    .btn{padding:8px 12px;font-size:.875rem}
  }
</style>
"""


_CROSSY_LAYOUT = """
<style id="baltigo-crossy-layout">
  body{font-size:clamp(18px,3vw,28px)}
  #counter{font-size:clamp(18px,3vw,26px);top:16px;right:16px}
  #end{position:fixed;inset:0;min-width:0;min-height:0;width:100%;height:100dvh;box-sizing:border-box;z-index:20}
  .end-panel{box-sizing:border-box;width:min(92vw,560px);max-width:100%;max-height:calc(100dvh - 32px);overflow:auto;padding:clamp(16px,4vw,28px)}
  .end-buttons{display:flex;gap:10px;width:100%;min-width:0;align-items:stretch}
  #end button{box-sizing:border-box;flex:1;min-width:0;max-width:100%;font-size:clamp(12px,2.7vw,18px);padding:14px 10px;white-space:normal;overflow-wrap:anywhere;line-height:1.4}
  #end-message{font-size:clamp(16px,3vw,24px);line-height:1.5}
  #howToPlay .msg,.htp-panel{box-sizing:border-box;width:min(90vw,540px);max-width:90vw;font-size:clamp(16px,3vw,24px);line-height:1.5;padding:20px}
  #controlls{position:fixed;inset:0;min-width:0;min-height:0;pointer-events:none;z-index:4}
  #controlls div{pointer-events:auto;grid-template-columns:56px 56px 56px;grid-template-rows:48px 48px;gap:8px;margin-bottom:max(20px,env(safe-area-inset-bottom))}
  @media(max-height:500px){#controlls div{grid-template-columns:48px 48px 48px;grid-template-rows:42px 42px;gap:6px;margin-bottom:10px}}
</style>
"""


_LUDO_CONTROLLER = r"""
// BALTIGO_SOURCE_REPAIR_LUDO_TURNS_V1
const rollButton=document.getElementById('rollBtn');
const turnStatus=document.createElement('div');
turnStatus.id='turnStatus';turnStatus.setAttribute('aria-live','polite');
document.getElementById('ui').appendChild(turnStatus);
let turnBusy=false;

function finishLudo(winner) {
  gameOver=true;awaitingHuman=false;selectableTokens=[];turnBusy=false;
  turnStatus.id='result-title';
  turnStatus.textContent=winner===0 ? 'Você venceu a partida!' : `Você perdeu. O computador ${winner} venceu a partida.`;
  rollButton.disabled=false;rollButton.textContent='Jogar novamente';
  renderTokens();
}

function resetLudo() {
  for(const playerTokens of tokens)for(const token of playerTokens)token.steps=-1;
  currentPlayer=0;lastDice=0;gameOver=false;awaitingHuman=false;
  selectableTokens=[];turnBusy=false;
  turnStatus.id='turnStatus';
  document.getElementById('dice').textContent='—';
  renderTokens();turn();
}

async function turn() {
  if(gameOver)return;
  awaitingHuman=false;selectableTokens=[];turnBusy=false;
  renderTokens();
  const computer=players[currentPlayer].isAI;
  rollButton.disabled=computer;
  rollButton.textContent=computer ? 'Aguarde' : 'Lançar dado';
  turnStatus.textContent=computer ? `Vez do computador ${currentPlayer}` : 'Sua vez: lance o dado.';
  if(computer) {
    turnBusy=true;
    return takeLudoTurn();
  }
}

rollButton.addEventListener('click',()=>{
  if(gameOver){resetLudo();return;}
  if(players[currentPlayer].isAI || turnBusy || awaitingHuman)return;
  turnBusy=true;rollButton.disabled=true;
  turnStatus.textContent='Escolha uma peça destacada.';
  takeLudoTurn();
});
"""


_LUDO_LAYOUT = """
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<style id="baltigo-ludo-layout">
  html{display:block;width:100%;height:100%}
  body{box-sizing:border-box;width:100%;height:100dvh;display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:minmax(0,1fr) auto;padding:12px;gap:12px}
  #game{box-sizing:border-box;width:min(92vw,calc(100dvh - 130px));height:min(92vw,calc(100dvh - 130px));justify-self:center;align-self:center}
  #ui{box-sizing:border-box;position:static;width:100%;display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:center}
  #dice{font-size:20px;padding:8px 12px;min-width:44px;text-align:center}
  #rollBtn{min-height:44px;font-size:18px;padding:10px 16px}
  #rollBtn:disabled{opacity:.65;cursor:default}
  #turnStatus,#result-title{flex-basis:100%;font-size:14px;color:#cbd5e1;text-align:center;line-height:1.5}
  @media(max-height:500px) and (min-width:600px){
    body{grid-template-columns:minmax(0,1fr) minmax(170px,220px);grid-template-rows:minmax(0,1fr);gap:16px}
    #game{grid-column:1;grid-row:1;width:min(calc(100dvh - 24px),calc(100vw - 280px));height:min(calc(100dvh - 24px),calc(100vw - 280px))}
    #ui{grid-column:2;grid-row:1;flex-direction:column;justify-content:center}
    #turnStatus,#result-title{flex-basis:auto}
  }
</style>
"""


def _repair_dream_weaver(source: str) -> str:
    if "BALTIGO_SOURCE_REPAIR_DREAM_WEAVER_V1" in source:
        return source
    if "class DreamWeaverScene extends Phaser.Scene" not in source:
        return source
    source = source.replace("\r\n", "\n")
    source = source.replace("class DreamWeaverScene extends Phaser.Scene", _DREAM_HELPERS + "\nclass DreamWeaverScene extends Phaser.Scene", 1)
    for key in ("background", "platform", "spike", "gate"):
        source = source.replace(f"    this.load.image('{key}',", f"    // Procedural {key} texture replaces the unshipped file:\n    // this.load.image('{key}',")
    source = source.replace("this.load.image('player',     'assets/images/player.png');",
                            "this.load.spritesheet('player', 'assets/images/player.png', {frameWidth:100, frameHeight:155, endFrame:8});")
    source = source.replace("  preload() {", _DREAM_INIT + "  preload() {", 1)
    source = source.replace("    const W = this.scale.width, H = this.scale.height;\n\n    // Background",
                            "    const W = this.scale.width, H = this.scale.height;\n    createDreamTextures(this);\n\n    // Background", 1)
    source = source.replace("this.physics.world.setBounds(0, 0, W, H);",
                            "this.physics.world.setBounds(0, 0, W, H);\n    this.physics.world.checkCollision.down = false;", 1)
    source = source.replace("this.gate.displayHeight = 160; this.gate.displayWidth = 80;",
                            "this.gate.displayHeight = 160; this.gate.displayWidth = 80;\n      this.gate.body.updateFromGameObject();", 1)
    source = source.replace("      this.player.setScale(s);", """      this.player.setScale(s).setFrame(3);
      this.player.body.setSize(70,130).setOffset(15,15);
      if (!this.anims.exists('dream-run')) this.anims.create({key:'dream-run',frames:this.anims.generateFrameNumbers('player',{start:0,end:8}),frameRate:12,repeat:-1});""", 1)
    source = source.replace("this.input.keyboard.on('keydown-SPACE', () => { if (this.started) this.queueJump(); });", """this.input.keyboard.on('keydown-SPACE', () => { if (this.started) this.queueJump(); else this.startGame(); });
    this.input.keyboard.on('keydown-UP', () => { if (this.started) this.queueJump(); else this.startGame(); });""", 1)
    source = source.replace("    this.makeEndOverlay();", "    this.makeEndOverlay();\n    this.makeTouchControls();\n    this.physics.world.pause();", 1)
    source = source.replace("      this.sound.add('music', { loop: true, volume: 0.33 }).play();",
                            "      this.dreamMusic = this.sound.add('music', { loop: true, volume: 0.33 });", 1)
    source = source.replace("  makeStartOverlay() {", _DREAM_CONTROLS + "  makeStartOverlay() {", 1)
    source = source.replace("    this.started = true;", "    this.started = true;\n    this.physics.world.resume();\n    this.dreamMusic?.play();", 1)
    source = source.replace("  showEnd() {", "  showEnd() {\n    this.physics.world.pause();\n    this.moveLeft = this.moveRight = false;", 1)
    source = source.replace("const stars = this.add.particles(0,0,'');", "const stars = this.add.particles('dream-spark');")
    source = source.replace("this.add.particles(this.player.x, this.player.y + (this.player.displayHeight/2||30), '')",
                            "this.add.particles('dream-spark').setPosition(this.player.x, this.player.y + (this.player.displayHeight/2||30))")
    source = source.replace("    if ((this.jumpQueued || withinBuffer) && (onFloor || withinCoyote)) {",
                            "    const requestedJump = this.jumpQueued;\n    this.jumpQueued = false;\n    if ((requestedJump || withinBuffer) && (onFloor || withinCoyote)) {", 1)
    source = source.replace("    // jump with coyote/buffer", """    if (this.player.anims) {
      if (moving) this.player.anims.play('dream-run',true);
      else {this.player.anims.stop();this.player.setFrame(3);}
    }

    // jump with coyote/buffer""", 1)
    source = source.replace("this.sound?.play?.('morph', { volume: 0.45 });",
                            "if (this.cache.audio?.exists('morph')) this.sound.play('morph', { volume: 0.45 });")
    # The original 20px tutorial rendered at 7px on a 390px-wide screen. Keep
    # this game's logical canvas while giving its real controls readable text
    # and touch targets, with the full tutorial inside the start panel.
    source = source.replace("W*0.86, 360,", "W*0.86, 600,")
    source = source.replace("H/2 - 120", "H/2 - 200").replace("H/2 + 120", "H/2 + 200")
    source = source.replace("fontSize: '44px'", "fontSize: '52px'")
    source = source.replace("fontSize: '20px', color: '#cfe7ff', align: 'center', lineSpacing: 6",
                            "fontSize: '40px', color: '#cfe7ff', align: 'center', lineSpacing: 12, wordWrap: {width:W*0.76}")
    source = source.replace("fontSize: '22px'", "fontSize: '44px'")
    source = source.replace("fontSize: '46px'", "fontSize: '64px'")
    source = source.replace("W*0.8, 280,", "W*0.8, 420,")
    source = source.replace("220, 56, 0x7df9ff", "380, 120, 0x7df9ff")
    source = source.replace('  <div class="hint">Stand still ≈1s → bridge grows toward next platform • Overstay → spikes → crumble</div>', "")
    return source


def apply_source_repairs(path: str, source: bytes, media_type: str = "") -> bytes:
    path = str(PurePosixPath(path.replace("\\", "/"))).lstrip("/")
    if path.startswith("play/"):
        path = path[5:]
    if path == "games/board/ludo/index.html":
        try:
            text = source.decode("utf-8-sig").replace("\r\n", "\n")
        except UnicodeDecodeError:
            return source
        if "BALTIGO_SOURCE_REPAIR_LUDO_TURNS_V1" in text:
            return source
        text = text.replace("</head>", _LUDO_LAYOUT + "</head>", 1)
        text = text.replace("async function turn(){", "async function takeLudoTurn(){", 1)
        text = text.replace("    await performMove(p,m.t,d);", "    await performMove(p,m.t,d);\n    if(gameOver)return;", 1)
        text = text.replace("  renderTokens();\n  return true;\n}\n\nfunction rollDice(){",
                            "  renderTokens();\n  if(tokens[p].every(token=>token.steps===FINAL_STEP))finishLudo(p);\n  return true;\n}\n\nfunction rollDice(){", 1)
        text = text.replace("function humanChoose(p,t){\n  awaitingHuman=false;\n  performMove(p,t,lastDice).then(()=>{\n    if (lastDice===6) turn();\n    else endTurn();\n  });\n}",
                            "function humanChoose(p,t){\n  if(gameOver || !awaitingHuman || p!==currentPlayer || !selectableTokens.some(move=>move.p===p && move.t===t))return;\n  const dice=lastDice;\n  awaitingHuman=false;\n  performMove(p,t,dice).then(()=>{\n    if(gameOver)return;\n    if(dice===6)turn();else endTurn();\n  });\n}", 1)
        text = text.replace("\nrenderTokens();\nturn();", "\n" + _LUDO_CONTROLLER + "\nrenderTokens();\nturn();", 1)
        return text.encode("utf-8")
    if path in {"games/puzzle/sudoku/index.html", "games/arcade/crossy-road/index.html"}:
        try:
            text = source.decode("utf-8-sig")
        except UnicodeDecodeError:
            return source
        if "/sudoku/" in path:
            if 'id="baltigo-sudoku-layout"' not in text:
                text = text.replace("</head>", _SUDOKU_LAYOUT + "</head>", 1)
            if 'id="newGameBtn"' not in text:
                # The source locked the solved/timed-out board permanently.
                # A full document restart also resets its const timer and the
                # continuously scheduled confetti animation without leaks.
                text = text.replace('<div class="btn" id="clearBtn">Clear Cell</div>',
                                    '<div class="btn" id="clearBtn">Clear Cell</div>\n      <button type="button" class="btn" id="newGameBtn" onclick="location.reload()">Nova partida</button>', 1)
            # The supplied solutionA contains the impossible number 53. Compare
            # the filled board with Sudoku's real constraints, so any legal
            # solution of the given puzzle can win.
            text = text.replace("if(JSON.stringify(grid)===JSON.stringify(solutionA)||JSON.stringify(grid)===JSON.stringify(solutionB)){",
                                "if(grid.every((row,r)=>row.every((value,c)=>Number.isInteger(value)&&value>=1&&value<=9&&validPlacement(r,c,value)))){")
        elif 'id="baltigo-crossy-layout"' not in text:
            text = text.replace("</head>", _CROSSY_LAYOUT + "</head>", 1)
        return text.encode("utf-8")
    if path == "games/arcade/dream-weaver/config.json":
        try:
            json.loads(source)
            return source
        except (ValueError, UnicodeDecodeError):
            return json.dumps(DREAM_WEAVER_CONFIG, ensure_ascii=False).encode("utf-8")
    if path in {
        "games/shooter/bird-shooter/config.json",
        "games/arcade/color-dash/config.json",
        "games/arcade/demon/config.json",
        "games/platformer/flip-jump/config.json",
        "games/arcade/swipe-assassin/config.json",
        "games/sports/cricket-123/config.json",
        "games/puzzle/link/config.json",
        "games/puzzle/perfect-square/config.json",
    }:
        try:
            config = json.loads(source)
            sheets = config.get("spritesheets", {})
            if "/bird-shooter/" in path:
                # The actual game uses static player.png and shard.png. The
                # unshipped bird animation is never referenced; shard hits have
                # real source-defined sparks/smoke/ring effects without a sheet.
                sheets.pop("bird_flap", None)
                sheets.pop("shard_break", None)
            elif "/color-dash/" in path and "player_colors" in sheets:
                # The character sheet is really named hero.png. Its first row
                # contains nine poses, not nine pre-tinted 64px tiles.
                sheets["player_colors"].update(url="assets/hero.png", frameWidth=100, frameHeight=155, frames=9)
            elif "/demon/" in path:
                if "akaza_boss" in sheets:
                    sheets["akaza_boss"].update(frameWidth=192, frameHeight=226, frames=1)
                if "akaza15_boss" in sheets and "akaza14_boss" in sheets:
                    # Floor 15 retains its existing stronger HP/speed mechanics
                    # and uses the final real boss variant shipped by the game.
                    sheets["akaza15_boss"] = copy.deepcopy(sheets["akaza14_boss"])
            elif "/flip-jump/" in path:
                # The exact shipped soundtrack replaces an expired third-party
                # temporary-sound URL that leaves Phaser's audio cache empty.
                config.setdefault("audio", {})["bgm"] = "assets/bgm.mp3"
            elif "/swipe-assassin/" in path:
                audio = config.setdefault("audio", {})
                # A player elimination uses the existing elimination effect.
                # Never assign undefined to Audio.src (it requests /undefined).
                if not audio.get("gameover") and audio.get("kill"):
                    audio["gameover"] = audio["kill"]
            elif "/cricket-123/" in path:
                # This source is a train simulator. Its real rail artwork is
                # shipped in assets/, but the config omitted the track key and
                # Phaser interpreted undefined as a request for ./track.png.
                config.setdefault("images", {})["track"] = "assets/track.png"
            elif "/link/" in path:
                # This 3x3 level contains three real red/yellow/green pairs.
                # Six unused entries copied from a nine-color template made
                # preload guess filenames for nonexistent, unused art. Keep
                # the palette aligned with the level's actual endpoint data.
                for level in config.get("gameplay", {}).get("levels", []):
                    active = {pair.get("color") for pair in level.get("pairs", [])}
                    if active and isinstance(level.get("colors"), dict):
                        level["colors"] = {color: value for color, value in level["colors"].items() if color in active}
            elif "/perfect-square/" in path:
                # The source is explicitly a 60-second game. The pinned JSON
                # accidentally allows only two seconds, shorter than even one
                # successful drop's 2000ms resolution plus its setup animation.
                mechanics = config.setdefault("mechanics", {})
                if mechanics.get("timeLimit") == 2:
                    mechanics["timeLimit"] = 60
            return json.dumps(config, ensure_ascii=False).encode("utf-8")
        except (ValueError, UnicodeDecodeError, AttributeError, TypeError):
            return source
    text_repairs = {
        "games/arcade/flappy/mechanics.js": [
            # A Replay resets bird=null before Phaser's queued scene restart.
            # Its same pointer event also reaches the global gameplay handler;
            # a terminal screen gesture must never start the destroyed bird.
            ("function handleClick(scene) {", "function handleClick(scene) {\n  if(scene.gameOver || scene.levelClearedTriggered || !scene.bird?.body)return;"),
            # The final scoring collision is authoritative. Freeze immediately
            # during the authored 500ms result delay so a fall cannot append a
            # contradictory defeat overlay before the victory screen appears.
            ("    scene.levelClearedTriggered = true;", "    scene.levelClearedTriggered = true;\n    scene.physics.pause();"),
            ("function gameOverHandler(scene, config) {\n  if (scene.gameOver) return;", "function gameOverHandler(scene, config) {\n  if (scene.gameOver || scene.levelClearedTriggered) return;"),
        ],
        "games/shooter/vaccine-shooter/Scenes/GameScene.js": [
            # Scene shutdown follows Phaser Group shutdown. getChildren exists
            # on its prototype even after the internal children Set is gone.
            ("      if (!grp?.getChildren) return;", "      if (!grp?.getChildren || !grp.children) return;"),
        ],
        "games/puzzle/screw-master/Scenes/WinScene.js": [
            # notifyParent was evaluated immediately as EventEmitter.on's
            # context argument. The visible Next only stopped music and never
            # confirmed anything when actually pressed.
            ("    next.on('pointerdown', () => this.bgm && this.bgm.stop(),\n      this.notifyParent('sceneComplete', { result: 'win' }));",
             "    next.on('pointerdown', () => {\n      if(this.bgm)this.bgm.stop();\n      this.notifyParent('sceneComplete', { result: 'win' });\n    });"),
        ],
        "games/shooter/tee-shooter/mechanics.js": [
            # DOM stopPropagation does not stop Phaser's gameobjectdown ->
            # pointerdown dispatch. Start/retry could shoot the new hostage
            # beneath the button in the same gesture and immediately lose.
            ("(pointer) => {\n      pointer.event.stopPropagation();",
             "(pointer,localX,localY,eventData) => {\n      eventData?.stopPropagation();\n      pointer.event.stopPropagation();"),
        ],
        "games/platformer/parkour/Scenes/GameScene.js": [
            # Phaser registers its Group shutdown before this scene's custom
            # shutdown handler. Those groups may already have no children set;
            # a second clear then aborts the real exit-door scene transition.
            ("  if (this.fireballs) { this.fireballs.clear(true, true); this.fireballs = null; }",
             "  if (this.fireballs) { if(this.fireballs.children)this.fireballs.clear(true, true); this.fireballs = null; }"),
            ("  if (this.platforms) { this.platforms.clear(true, true); this.platforms = null; }",
             "  if (this.platforms) { if(this.platforms.children)this.platforms.clear(true, true); this.platforms = null; }"),
        ],
        "games/shooter/fighter-jet/mechanics.js": [
            # The real final collision destroys jet=null, but its repeating
            # missile timer kept dereferencing jet.active on the result screen.
            ("            if (!scene.jet.active) return;", "            if (scene.gameEnded || !scene.jet?.active) return;"),
            ("            this.gameEnded = true;\n            this.physics.world.pause();",
             "            this.gameEnded = true;\n            this.time.removeAllEvents();\n            this.physics.world.pause();"),
        ],
        "games/3d/stack-tower/index.html": [
            # A winning canvas touch could reveal Replay under the same finger;
            # its compatibility click then restarted the round immediately.
            # Browsers may retarget the compatibility click after pointerup,
            # even with capture. A new deliberate overlay pointerdown disarms
            # the guard, so immediate intentional Replay stays available.
            ('    window.addEventListener("pointerdown", () => {\n      if (playing) {\n        playDrop();\n        drop();\n      }\n    });',
             '''    let baltigoCanvasGesture=false;
    window.addEventListener("pointerdown",event=>{
      if(event.target.closest?.(".overlay button"))baltigoCanvasGesture=false;
    },true);
    window.addEventListener("click",event=>{
      if(baltigoCanvasGesture && event.detail>0 && event.target.closest?.(".overlay button")){
        baltigoCanvasGesture=false;
        event.preventDefault();event.stopImmediatePropagation();
      }
    },true);
    window.addEventListener("pointerdown", event => {
      if(!playing || event.target.closest?.("button,.overlay"))return;
      baltigoCanvasGesture=true;
      event.preventDefault();
      if(event.target instanceof HTMLCanvasElement)event.target.setPointerCapture(event.pointerId);
      playDrop();
      drop();
    },{passive:false});'''),
        ],
        "games/board/chess/index.html": [
            # makeButton registers callbacks on its Container, while its
            # visual children receive the actual pointer. Use one shared
            # action relay for Start, Replay and Next.
            ("img.setScale(scale).setInteractive({ useHandCursor: true });", "img.setScale(scale);"),
            (".setStrokeStyle(2, 0x24355f, 1).setInteractive({ useHandCursor: true });", ".setStrokeStyle(2, 0x24355f, 1);"),
            ("          playBtn.list.forEach(ch => ch.setInteractive?.({ useHandCursor: true }).on?.('pointerdown', () => this.startGame()));", ""),
            # Phaser's Container hit coordinates differ from its children's
            # display origin. Relay each real child gesture to the one shared
            # action; the source's special Start-only relay is removed above.
            ("          return group;", "          group.list.forEach(child=>child.setInteractive({useHandCursor:true}).on('pointerdown',(...args)=>group.emit('pointerdown',...args)));\n          return group;"),
        ],
        "games/arcade/swipe-assassin/index.html": [
            # The shipped Next was an alert('Next level JSON hook') placeholder.
            # There is one authored arena, so make its actual confirmation a
            # new round through the same gesture-gated host adapter.
            ('function nextLevel(){alert("Next level JSON hook");}',
             "function nextLevel(){window.__baltigo.completeAndRestart({result:'win'});}"),
            ('document.querySelector("#winOverlay .secondary").textContent=texts.next_button;',
             'document.querySelector("#winOverlay .secondary").textContent="Nova partida";'),
        ],
        "games/shooter/alien-battle/mechanics.js": [
            # A queued replay destroys the hero only on Phaser's next scene
            # step. Immediate manual destruction left the old jump-release
            # listener calling setVelocityY on its already removed body.
            ("  scene.input.off('pointerdown');", "  scene.input.off('pointerdown');\n  scene.input.off('pointerup');"),
            ("    scene.scene.restart();\n    scene.children.list.forEach(child => child.destroy());",
             "    scene.scene.restart(); // Phaser owns object/input teardown on its next scene step."),
            # The ordinary boss-dead update otherwise created result overlays
            # repeatedly. Freeze the real terminal round exactly once.
            ("function win(scene) {", "function win(scene) {\n  if(scene.hasEnded)return;\n  scene.hasEnded=true;scene.isGameStarted=false;\n  scene.physics.pause();scene.input.off('pointerdown');scene.input.off('pointerup');"),
            ("function gameovr(scene) {", "function gameovr(scene) {\n  if(scene.hasEnded)return;\n  scene.hasEnded=true;scene.isGameStarted=false;\n  scene.physics.pause();scene.input.off('pointerdown');scene.input.off('pointerup');"),
            ("function startGame(scene) {", "function startGame(scene) {\n  scene.hasEnded=false;scene.isGameStarted=true;scene.physics.resume();"),
            ("  create() {\n    const levelData", "  create() {\n    this.hasEnded=false;this.isGameStarted=false;this.input.removeAllListeners();\n    const levelData"),
        ],
        "games/arcade/road-cross/mechanics.js": [
            # Both overlays accepted a callback but never called it: Next
            # removed the UI without advancing, and a loss ignored its reset.
            ("    _reallyCreate() {\n", "    _reallyCreate() {\n        this.input.enabled = true;\n"),
            ("                this.notifyParent('sceneComplete', { result: 'win' });",
             "                this._preRestartCleanup();\n                if(typeof onNext==='function')onNext();else this.scene.restart();"),
            ("        btn.once('pointerup', () => {\n            this.input.enabled = false;\n            this._preRestartCleanup();\n            this.time.delayedCall(0, () => this.scene.restart());\n        });",
             "        btn.once('pointerup', () => {\n            this.input.enabled = false;\n            this._preRestartCleanup();\n            this.time.delayedCall(0, () => {if(typeof onRestart==='function')onRestart();else this.scene.restart();});\n        });"),
        ],
        "games/board/tic-tac-toe/mechanics.js": [
            # A second physical tap could place another human mark during the
            # computer's 300ms delay and queue a second computer move. Reserve
            # the turn before placing X, then unlock after the one AI callback.
            ("  resetState() {\n    this.gameOver = false;",
             "  resetState() {\n    this.isComputerTurn = false;\n    this.gameOver = false;"),
            ("    this.state = 'playing';",
             "    this.state = 'playing';\n    this.isComputerTurn = false;"),
            ("    if (this.gameOver || this.state !== 'playing') return;",
             "    if (this.gameOver || this.state !== 'playing' || this.isComputerTurn) return;"),
            ("      this.makeMove(row, col, 'X');\n      if (!this.gameOver) {\n        this.time.delayedCall(300, () => this.computerMove());\n      }",
             "      this.isComputerTurn = true;\n      this.makeMove(row, col, 'X');\n      if (!this.gameOver) {\n        this.time.delayedCall(300, () => {\n          this.computerMove();\n          this.isComputerTurn = false;\n        });\n      } else {\n        this.isComputerTurn = false;\n      }"),
        ],
        "games/casual/fruit-basket/mechanics.js": [
            # EventEmitter.once requires a callable. There is no obsolete
            # pointerdown restart handler here; the game's real drag handler
            # must remain registered.
            ("    this.input.once('pointerdown', null);", "    // Existing basket drag input remains registered."),
            ("        this.setupInput();", "        // Input is already registered by create(); preserve its drag handlers."),
            # This override recursively called itself through the same Scene
            # Plugin instance. Phaser's original restart correctly tears down
            # and recreates the scene and its input handlers.
            ("    this.scene.restart = () => { window.game.scene.keys['GameScene'].scene.restart(); };", ""),
        ],
        "games/platformer/flip-jump/mechanics.js": [
            ("    if (!this.bgmSound) {\n      this.bgmSound = this.sound.add('bgm', { loop: true, volume: 0.5 });\n    }\n    this.bgmSound.play();",
             "    if (this.cache.audio.exists('bgm')) {\n      if (!this.bgmSound) this.bgmSound = this.sound.add('bgm', { loop: true, volume: 0.5 });\n      this.bgmSound.play();\n    }"),
        ],
        "games/word-quiz/math-quest/mechanics.js": [
            # The actual player is the configured 'character' sheet. The unused
            # Eve loader below is a leftover from another template game.
            ('      this.load.spritesheet("eve", sheetUrl, {\n        frameWidth: frameW,\n        frameHeight: frameH,\n      });',
             "      // Actual character is loaded below from the shipped hero.png."),
        ],
        "games/3d/orbital-outpost/mechanics.js": [
            # No game object references 'solar'; station is the real spaceship.
            ('            solar: "assets/solar.png",\n', ""),
        ],
        "games/puzzle/signal-circuit/mechanics.js": [
            # winText belonged to the removed status widget. The current win
            # scene and circuit state remain responsible for victory.
            ("      this.winText.setText('');", "      this.winText?.setText('');"),
        ],
        "games/sports/penalty/index.html": [
            # Phaser scenes do not exist synchronously after new Game(). Pass
            # configuration before scene initialization instead of dereferencing
            # a missing GameScene in an eager create-event subscription.
            ("        scene: [GameScene, WinScene, GameOverScene]",
             "        callbacks: { preBoot: (game) => game.registry.set('cfg', cfg) },\n        scene: [GameScene, WinScene, GameOverScene]"),
            ("      game.scene.getScene('GameScene').events.once('create', function(){\n        this.registry.set('cfg', cfg);\n      });",
             "      // cfg is already in the shared registry before GameScene preload/create."),
        ],
        "games/sports/penalty/gamescene.js": [
            # _setTurn('CPU_SHOT') executes a new kick. Calling it from the
            # completed CPU kick recursively queued shots across later rounds.
            # Retain the completed turn only while _nextTurn's normal delay
            # advances the match, with input locked during that short interval.
            ("          this._setTurn('CPU_SHOT'); // reset to shot will handle end-of-round in _nextTurn",
             "          this.turn = 'CPU_SHOT';\n          this.busy = true; // completed kick waits for _nextTurn; never fire another kick here"),
            # Phaser reuses this Scene on Replay; constructor scores and round
            # fields otherwise survived into the next match.
            ("  create() {\n    const gcfg", "  create() {\n    this.playerScore=0;this.cpuScore=0;this.round=1;this.inSuddenDeath=false;\n    this.turn='PLAYER_AIM';this.aimIndex=0;this.diveIndex=0;this.busy=false;this.turnDeadline=0;\n    this.inputFlags={left:false,right:false,action:false};\n    const gcfg"),
            # No images are shipped for this source, which intentionally has
            # vector fallbacks. Graphics drawn at absolute x/y were then also
            # translated by x/y, placing the actual game and controls offscreen.
            ("    const g = this.add.graphics();\n    g.fillStyle(color, 1);\n    g.fillRoundedRect(x - w * 0.5, y - h * 0.5, w, h, Math.min(12, w * 0.1));\n\n    // Emulate size props expected elsewhere, without touching methods\n    g.x = x;\n    g.y = y;\n    g.displayWidth = w;\n    g.displayHeight = h;\n\n    // Important: leave g.setDepth and g.destroy as-is to avoid recursion\n    return g;",
             "    const shape=(w===90&&h===90) ? this.add.circle(x,y,w/2,color) : this.add.rectangle(x,y,w,h,color);\n    shape.setStrokeStyle(3,0xd8e9ed,0.75);\n    return shape;"),
            ("      const hit = new Phaser.Geom.Rectangle(-size / 2, -size / 2, size, size);\n      s.setInteractive({\n        hitArea: hit,\n        hitAreaCallback: Phaser.Geom.Rectangle.Contains,\n        useHandCursor: true\n      });",
             "      s.setInteractive({useHandCursor:true});\n      this.add.text(x,y,key===leftKey?'ESQ.':key===rightKey?'DIR.':'AÇÃO',{fontFamily:'Arial',fontSize:'44px',fontStyle:'bold',color:'#ffffff'}).setOrigin(.5).setDepth(21);"),
        ],
        "games/racing/shadow-runner/Scenes/GameScene.js": [
            # The only mobile action binding was commented out, so collected
            # charges could be spent only with a physical SPACE key. Changing
            # scale back to 1 also discarded the button's fitted display size.
            ("      // this.btnAction.on('pointerdown', () => { this.btnAction.setScale(0.9); this.btnAction.setAlpha(0.85); this._lightBlast(); });",
             "      this.btnAction.on('pointerdown', () => { this.btnAction.setAlpha(0.85); this._lightBlast(); });"),
            ("this.btnAction.setDisplaySize(100, 100);",
             "const actionSize=Math.max(140,Math.ceil(44*this.W/(this.game.canvas.getBoundingClientRect().width||this.W)));\n      this.btnAction.setDisplaySize(actionSize,actionSize);\n      this._positionActionButton();"),
            ("this.btnAction.setScale(1); this.btnAction.setAlpha(1);", "this.btnAction.setAlpha(1);"),
            ("    this.btnAction.setPosition(cam.width - 160, cam.height - 100);",
             "    const actionSize=Math.max(140,Math.ceil(44*this.W/(this.game.canvas.getBoundingClientRect().width||this.W)));\n    this.btnAction.setDisplaySize(actionSize,actionSize);\n    this.btnAction.setPosition(cam.width-Math.max(160,actionSize/2+24),cam.height-Math.max(100,actionSize/2+24));"),
        ],
    }
    if path in text_repairs:
        try:
            text = source.decode("utf-8-sig").replace("\r\n", "\n")
        except UnicodeDecodeError:
            return source
        marker = "// BALTIGO_SOURCE_REPAIR_" + path.split("/")[2].replace("-", "_").upper() + "_V1"
        if marker in text:
            return source
        for old, new in text_repairs[path]:
            text = text.replace(old, new)
        # Insert before source, outside any script only when the HTML case.
        if path.endswith(".html"):
            text = text.replace("<script type=\"module\">", "<script type=\"module\">\n    " + marker, 1)
        else:
            text = marker + "\n" + text
        return text.encode("utf-8")
    if path == "games/arcade/color-dash/Scenes/GameScene.js":
        try:
            text = source.decode("utf-8-sig")
        except UnicodeDecodeError:
            return source
        if "BALTIGO_SOURCE_REPAIR_COLOR_PLAYER_V1" in text:
            return source
        text = text.replace("this.player = this.physics.add.sprite(x, y, 'player_colors', 0);",
                            "// BALTIGO_SOURCE_REPAIR_COLOR_PLAYER_V1\n      this.player = this.physics.add.sprite(x, y, 'player_colors', 0).setScale(0.65);")
        text = text.replace("    this.playerColor = colorName;", "    this.playerColor = colorName;\n    this.player.setTint(this.colors[colorName] ?? 0xffffff);", 1)
        return text.encode("utf-8")
    if path == "games/arcade/demon/Scenes/GameScene.js":
        try:
            text = source.decode("utf-8-sig").replace("\r\n", "\n")
        except UnicodeDecodeError:
            return source
        if "BALTIGO_SOURCE_REPAIR_DEMON_PHASES_V1" in text:
            return source
        # Phaser frameTotal includes the special __BASE frame; it is not an
        # animation frame. Without subtracting it, boss loops request a frame
        # that does not exist (especially the shipped single-frame first boss).
        text = text.replace("const ft = tex.frameTotal || 1;", "const ft = Math.max(1,(tex.frameTotal || 1)-1);")
        text = text.replace("const ft = tex?.frameTotal || 1;", "const ft = Math.max(1,(tex?.frameTotal || 1)-1);")
        text = text.replace("  init() {\n    // track timers", "  init() {\n    this.state={floor:1,kills:0,cleared:false,invulnUntil:0,nextAttackAt:0,timerLeft:0};\n    this.akazaIsActive=false;this.playerIsDead=false;this._consumeTapAttack=false;\n    this.inputState={left:false,right:false,jump:false,attack:false};\n    this.stairs=null;this.nextFloorHint=null;\n    // track timers", 1)
        start = text.find("  _spawnStairs() {")
        end = text.find("\n  _nextFloor() {", start)
        if start >= 0 and end > start:
            text = text[:start] + _DEMON_STAIRS + text[end:]
        text = text.replace("  _nextFloor() {\n", "  _nextFloor() {\n    if(!this.state.cleared)return;\n", 1)
        text = "// BALTIGO_SOURCE_REPAIR_DEMON_PHASES_V1\n" + text
        return text.encode("utf-8")
    if path != "games/arcade/dream-weaver/index.html":
        return source
    try:
        text = source.decode("utf-8-sig")
    except UnicodeDecodeError:
        return source
    return _repair_dream_weaver(text).encode("utf-8")
