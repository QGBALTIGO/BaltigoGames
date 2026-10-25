"""Local Portuguese presentation adapter for pinned upstream games.

Only public, human-readable text is changed. Asset URLs, identifiers, scene keys,
physics, scoring and saved game data retain their original values.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = '20261025-7'


@lru_cache(maxsize=1)
def translations() -> dict[str, str]:
    path = ROOT / 'data/localization-pt.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


@lru_cache(maxsize=1)
def metadata() -> dict:
    path = ROOT / 'data/catalog-pt.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


@lru_cache(maxsize=1)
def transition_policies() -> dict:
    path = ROOT / 'data/game-transitions.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def _translate(value: str) -> str:
    return translations().get(value, value)


def _json_text(value, active=False):
    if isinstance(value, dict):
        return {key: _json_text(item, active or key in {
            'texts', 'text', 'questions', 'question', 'options', 'answers',
            'instructions', 'description', 'hint', 'hints', 'events', 'recipes',
            'labels', 'strings', 'uiText', 'textContent',
        } or bool(re.search(r'title|label|instruction|message|caption|hint|^howto', key, re.I))) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_text(item, active) for item in value]
    if active and isinstance(value, str):
        return _translate(value)
    return value


@lru_cache(maxsize=1)
def word_games() -> dict:
    return json.loads((ROOT / 'data/word-games-pt.json').read_text(encoding='utf-8'))


def _word_game_config(path: str, config: dict) -> dict:
    if '/wordle/' in path:
        words = word_games()['wordle']
        config.setdefault('words', {}).update({key: words[key] for key in ['answerPool', 'validGuesses', 'clues']})
        config['words']['validGuesses'] = sorted({word.upper() for word in config['words']['validGuesses'] if len(word) == 5 and word.isascii() and word.isalpha()})
        config.setdefault('gameplay', {})['titleText'] = words['titleText']
        config['gameplay']['fixedAnswer'] = ''
        config.setdefault('texts', {})['how_to_play'] = words['instructions']
        config['texts']['score_label'] = 'Tentativa'
    if '/words-of-wonder/' in path:
        config.setdefault('gameplay', {})['puzzles'] = word_games()['words-of-wonder']['puzzles']
    if '/6oct/' in path:
        puzzles = []
        for bank, targets in [
            ('PORTAS', ['PORTA', 'PRATO', 'PATO', 'RATO', 'ROTA', 'ATO']),
            ('LIVROS', ['LIVRO', 'VIRO', 'VIR', 'RIO', 'VIL', 'ROL']),
            ('PEDRAS', ['PEDRA', 'PERDA', 'PRESA', 'PARES', 'PARE', 'SER']),
        ]:
            cells = ['.' * 8] + [('.' * ((8-len(word))//2) + word).ljust(8, '.') for word in targets] + ['.' * 8]
            puzzles.append({'bank': bank, 'targets': targets, 'grid': {'rows':len(cells), 'cols':8, 'cells':cells}})
        config.setdefault('gameplay', {})['puzzles'] = puzzles
    return config


# Quoted string literals are replaced in place without reserializing code. Only
# multiword phrases or uppercase labels are eligible: lowercase identifiers such
# as 'play', 'score', 'next', 'white' are also scene/asset/event keys upstream.
@lru_cache(maxsize=1)
def _literal_replacements():
    replacements = {}
    semantic_keys = {'ENTER', 'DEL', 'LEFT', 'RIGHT', 'UP', 'DOWN', 'SPACE', 'WASD', 'FIRE', 'ACTION', 'ATTACK', 'JUMP'}
    for english, portuguese in translations().items():
        if english == portuguese or english in semantic_keys or not (' ' in english.strip() or english.isupper()):
            continue
        for quote in ('"', "'", '`'):
            def encode(text):
                return text.replace('\\', '\\\\').replace(quote, '\\' + quote).replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            replacements[quote + encode(english) + quote] = quote + encode(portuguese) + quote
            if quote == '`' and '\n' in english:
                replacements[quote + english + quote] = quote + portuguese + quote
    # Match only complete, reviewed literals. Tokenizing all JavaScript with a
    # quote regex consumes apostrophes in source comments and misses later text.
    # Literal alternatives also preserve identifiers and unrelated JS exactly.
    pattern = re.compile('|'.join(re.escape(key) for key in sorted(replacements, key=len, reverse=True)))
    return pattern, replacements


def _localize_literals(source: str) -> str:
    pattern, replacements = _literal_replacements()
    return pattern.sub(lambda match: replacements[match[0]], source)


def _adapt_legacy_handoffs(source: str) -> str:
    # The old host was meant to replace the document after a final-screen Next.
    # Keep internal scene.start()/level increments untouched. The runtime records
    # the result, and reloads only after an actual confirmation-button gesture.
    source = re.sub(
        r"(?<![\w$.])(?:this\.)?notifyParent\(\s*(['\"])sceneComplete\1\s*,\s*",
        'window.__baltigo.completeAndRestart(', source,
    )
    source = re.sub(
        r"\bthis\.events\.emit\(\s*(['\"])sceneComplete\1\s*\)",
        "window.__baltigo.completeAndRestart({result:'win'})", source,
    )
    return source


def _localize_archer_result_art(source: str) -> str:
    # These authored SVG paths spell English words; they cannot be translated
    # by DOM/Canvas text hooks. Keep the groups that source hit/miss animations
    # address, replacing only their word artwork with accessible SVG text.
    for group, label in {'miss': 'ERROU!', 'bullseye': 'NO CENTRO!', 'hit': 'ACERTOU!'}.items():
        pattern = r'(<g\b[^>]*\bclass="' + group + r'"[^>]*>)[\s\S]*?(</g>)'
        text = '<text x="500" y="190" text-anchor="middle" font-family="Arial Black,Arial,sans-serif" font-size="72" font-weight="900" letter-spacing="2" paint-order="stroke fill" stroke="#101824" stroke-width="2">' + label + '</text>'
        source = re.sub(pattern, lambda match: match[1] + text + match[2], source, count=1)
    return source


# This helper is copied only into the five reviewed sources below. The game
# keeps its native values and visibility; the pill follows the measured text
# instead of assuming English captions have the same width as Portuguese.
_PILL_LAYOUT_JS = '''
function __baltigoPill(scene, plate, labels, baseFont = 50) {
  const originalWidth = plate.displayWidth, originalHeight = plate.displayHeight;
  let previous = '';
  const layout = () => {
    if (!plate.scene || labels.some(label => !label.scene)) return;
    const ratio = scene.game.canvas.getBoundingClientRect().width / scene.scale.width;
    if (!(ratio > 0)) return;
    const size = Math.max(baseFont, 14 / ratio), gap = 8 / ratio, padding = 10 / ratio;
    const signature = [ratio, ...labels.map(label => label.text)].join('|');
    if (signature === previous) return;
    previous = signature;
    labels.forEach(label => label.setFontSize(size).setOrigin(.5).setScrollFactor(0));
    const total = labels.reduce((sum, label) => sum + label.width, 0) + gap * (labels.length - 1);
    const height = Math.max(...labels.map(label => label.height));
    plate.setScrollFactor(0).setDisplaySize(Math.max(originalWidth, total + padding * 2), Math.max(originalHeight, height + padding));
    plate.x = Math.max(plate.displayWidth / 2 + padding, Math.min(scene.scale.width - plate.displayWidth / 2 - padding, plate.x));
    plate.y = Math.max(plate.y, plate.displayHeight / 2 + 6 / ratio);
    let x = plate.x - total / 2;
    labels.forEach(label => { label.setPosition(x + label.width / 2, plate.y); x += label.width + gap; });
  };
  scene.events.on('postupdate', layout);
  scene.events.once('shutdown', () => scene.events.off('postupdate', layout));
  layout();
}
'''


_HUD_ROW_JS = '''
function __baltigoHUDRow(scene, labels, options = {}) {
  const plates = labels.map(() => scene.add.rectangle(0, 0, 1, 1, 0x081824, .84).setDepth(100).setScrollFactor(0).setVisible(options.background !== false));
  scene.__baltigoHudGroups = labels.map((label, i) => ({plate: plates[i], labels: [label]}));
  let previous = '';
  const layout = () => {
    if (labels.some(label => !label.scene)) return;
    const ratio = scene.game.canvas.getBoundingClientRect().width / scene.scale.width;
    if (!(ratio > 0)) return;
    const signature = [ratio, ...labels.map(label => label.text)].join('|');
    if (signature === previous) return;
    previous = signature;
    const pad = 3 / ratio, size = Math.max(36, 14 / ratio);
    const width = (scene.scale.width - (options.reserveRight || 0)) / labels.length;
    labels.forEach(label => label.setFontSize(size).setOrigin(.5, 0).setScrollFactor(0).setDepth(101).setAlign('center').setWordWrapWidth(width - pad * 4, true));
    const height = Math.max(...labels.map(label => label.height)) + pad * 2;
    labels.forEach((label, index) => {
      label.setPosition(width * (index + .5), pad);
      plates[index].setPosition(label.x, height / 2).setSize(width - pad, height);
    });
  };
  scene.events.on('postupdate', layout);
  scene.events.once('shutdown', () => scene.events.off('postupdate', layout));
  layout();
}
'''


def _reviewed_small_hud_fixes(path: str, source: str) -> str:
    rows = {
        '/6oct/Scenes/GameScene.js': ("this._timerText.setShadow(0, 2, '#0b1222', 4, true, true);", '[this._scoreText, this._progressText, this._timerText]'),
        '/pacman/Scenes/GameScene.js': ('this.state.lastThinkAt = this.time.now;', '[this.ui.scoreText, this.ui.livesText, this.ui.levelText]'),
        '/shadow-runner/Scenes/GameScene.js': ('// Audio\n    this._playBgm();', '[this.ui.score, this.ui.charges, this.ui.timer]'),
        '/shooter/Scenes/GameScene.js': ('// Timers\n    this.state.timeLeft', '[this.hud.hp, this.hud.kills, this.hud.timer, this.hud.weapon]'),
        '/tower-shooter/Scenes/GameScene.js': ('this.refreshHealthBar();', '[this.ui.scoreText, this.ui.timerText], {reserveRight: 320, background: false}'),
        '/vaccine-shooter/Scenes/GameScene.js': ('// Controls\n    this.keys', '[this.ui.score, this.ui.timer, this.ui.health, this.ui.charges]'),
        '/cooking/Scenes/GameScene.js': ('// Audio wiring', '[this.scoreText, this.timerText, this.mistakeText, this.recipeTitleText]'),
        '/kaiju-krush/index.html': ('this.survivalTimerEvent = this.time.addEvent({', '[this.scoreText, this.timeText], {background: false}'),
    }
    for suffix, (anchor, labels) in rows.items():
        if path.endswith(suffix):
            pattern = r'\s+'.join(re.escape(part) for part in re.split(r'\s+', anchor))
            source = re.sub(pattern, lambda match: '__baltigoHUDRow(this, ' + labels + ');\n    ' + match[0], source, count=1)
            # Function declarations inside an HTML script are needed before its
            # closing tag; placing JS before <!doctype> would turn it into text.
            if path.endswith('.html'):
                source = re.sub(r'(<script\b[^>]*>)', lambda match: match[0] + _HUD_ROW_JS, source, count=1) if '<script src=' not in source else source.replace('class GameScene extends Phaser.Scene', _HUD_ROW_JS + '\nclass GameScene extends Phaser.Scene', 1)
            else:
                source = _HUD_ROW_JS + source
            break
    if path.endswith('/cooking/Scenes/GameScene.js'):
        source = re.sub(r'this\._hover\(this\.recipeTitleText,\s*3,\s*1600\);', '', source, count=1)
    if path.endswith('/cosmic-cleaner/mechanics.js'):
        source = _PILL_LAYOUT_JS + source
        source = source.replace("this.add.image(960, 50, 'scorebar')", "this.__baltigoHudPlate = this.add.image(960, 50, 'scorebar')", 1)
        source = source.replace('this.createUI();', 'this.createUI();\n        __baltigoPill(this, this.__baltigoHudPlate, [this.batteryBar, this.scoreText, this.shieldBar], 36);', 1)
        source = source.replace('this.batteryBar.setText(`Shield:', 'this.batteryBar.setText(`Battery:')
    if path.endswith('/collector/Scenes/GameScene.js'):
        source = source.replace("String(label) + ':'", r"String(label).replace(/:\s*$/, '') + ':'")
        source = source.replace('this._buildHud();', '''this._buildHud();
    const __layoutHud = () => {
      const ratio = this.game.canvas.getBoundingClientRect().width / this.scale.width;
      if (!(ratio > 0)) return;
      const pad = 6 / ratio, gap = 5 / ratio, width = this.scale.width / 3;
      const chips = [this.timerChip, this.scoreChip, this.altChip];
      chips.forEach((chip, i) => {
        const font = Math.max(28, 14 / ratio);
        [chip.lbl, chip.val].forEach(label => { if (parseFloat(label.style.fontSize) !== font) label.setFontSize(font); label.setOrigin(0, 0); });
        const height = Math.max(chip.lbl.height, chip.val.height) + pad * 2;
        chip.baseY = pad; chip.setPosition(width * i + pad, chip.baseY);
        chip.bg.setDisplaySize(width - pad * 2, height);
        chip.lbl.setPosition(pad, pad);
        chip.val.setPosition(pad + chip.lbl.width + gap, pad);
      });
      const cont = this.scoreBarContainer, track = cont.list[0], target = cont.list.find(o => typeof o.text === 'string');
      const barWidth = this.scoreChip.bg.displayWidth;
      this.scoreBarBaseY = this.scoreChip.baseY + this.scoreChip.bg.displayHeight + pad;
      cont.setPosition(this.scoreChip.x, this.scoreBarBaseY);
      track.setDisplaySize(barWidth, 6 / ratio);
      cont._maxW = barWidth - 8;
      cont._fill.setPosition(4, 2).setSize(Math.max(1, cont._maxW * Math.min(1, this.score / this.TARGET_SCORE)), Math.max(2, track.displayHeight - 4));
      const targetFont = Math.max(20, 14 / ratio);
      if (parseFloat(target.style.fontSize) !== targetFont) target.setFontSize(targetFont);
      target.setOrigin(0, 0).setPosition(0, track.displayHeight + gap);
      this.__baltigoHudGroups = chips.map(chip => ({plate: chip.bg, labels: [chip.lbl, chip.val]}));
    };
    this.events.on('postupdate', __layoutHud);
    this.events.once('shutdown', () => this.events.off('postupdate', __layoutHud));
    __layoutHud();''', 1)
    if path.endswith('/cricket-123/Scenes/GameScene.js'):
        source = source.replace("this._lastStationPrompt = '';", '''this._lastStationPrompt = '';
    const __hudPlate = this.add.rectangle(0, 0, 1, 1, 0x081824, .84).setOrigin(0).setDepth(49);
    let __previousHud = '';
    const __layoutHud = () => {
      const ratio = this.game.canvas.getBoundingClientRect().width / this.scale.width;
      if (!(ratio > 0)) return;
      const pad = 6 / ratio, gap = 3 / ratio, font = Math.max(28, 14 / ratio);
      const stats = [this.ui.speed, this.ui.time, this.ui.stat, this.ui.hp, this.ui.pax];
      const signature = [ratio, ...Object.values(this.ui).map(label => label.text)].join('|');
      if (signature === __previousHud) return;
      __previousHud = signature;
      let leftY = pad, rightY = pad;
      stats.forEach(label => { label.setFontSize(font).setOrigin(0).setPosition(pad, leftY); leftY += label.height + gap; });
      [this.ui.hint, this.ui.stationHint, this.ui.doorMsg].forEach(label => {
        label.setFontSize(Math.max(24, 14 / ratio)).setWordWrapWidth(this.W * .52 - pad * 2, true).setAlign('left').setOrigin(0).setPosition(this.W * .48, rightY);
        if (label.text) rightY += label.height + gap;
      });
      __hudPlate.setSize(this.W, Math.max(leftY, rightY) + pad);
      this.__baltigoHudGroups = stats.map(label => ({plate: __hudPlate, labels: [label]}));
    };
    this.events.on('postupdate', __layoutHud);
    this.events.once('shutdown', () => this.events.off('postupdate', __layoutHud));
    __layoutHud();''', 1)
    return source


def _reviewed_hud_fixes(path: str, source: str) -> str:
    if path.endswith('/antigravity/mechanics.js'):
        source = _PILL_LAYOUT_JS + source
        source = source.replace('// collisions & overlaps', '__baltigoPill(this, this.scorebar, [this.coreText]);\n        // collisions & overlaps', 1)
    elif path.endswith('/endless-runner/mechanics.js'):
        source = _PILL_LAYOUT_JS + source
        source = source.replace('this.timerEvent = null;', '__baltigoPill(this, this.pointBox, [this.coinText]);\n    __baltigoPill(this, this.timeBox, [this.timerText]);\n    this.timerEvent = null;', 1)
    elif path.endswith('/table-tennis/Scenes/GameScene.js'):
        source = _PILL_LAYOUT_JS + source
        source = source.replace("this.add.image(960, 100, 'scoreback')", "this.__baltigoScorePlate = this.add.image(960, 100, 'scoreback')", 1)
        source = source.replace('// --- Audio ---', '__baltigoPill(this, this.__baltigoScorePlate, [this.ui.scoreText]);\n    // --- Audio ---', 1)
    elif path.endswith('/sniper/Scenes/GameScene.js'):
        source = _PILL_LAYOUT_JS + source
        source = source.replace("this.add.image(960, 70, 'timerbar')", "this.__baltigoTimerPlate = this.add.image(960, 70, 'timerbar')", 1)
        source = source.replace('this.add.text(830, 40,', 'this.__baltigoTimerLabel = this.add.text(830, 40,', 1)
        source = source.replace('this._refreshTimerUI();', '__baltigoPill(this, this.__baltigoTimerPlate, [this.__baltigoTimerLabel, this.ui.timer], 40);\n    this._refreshTimerUI();', 1)
    elif path.endswith('/trench-defence/mechanics.js'):
        source = _PILL_LAYOUT_JS + source
        source = source.replace('// Config-driven variables', '__baltigoPill(this, this.scorebar, [this.scoreText, this.timerText]);\n    // Config-driven variables', 1)
    elif path.endswith('/planet-visitor/mechanics.js'):
        # Three fixed columns replace the overlapping tiny captions. Preserve
        # the native health fill and all health/photo/timer updates.
        source = source.replace('Pictures Taken:', 'Fotos:').replace('Health:', 'Vida:')
        source = source.replace('  createUI() {', '''  createUI() {
    const plates = [0, 1, 2].map(() => this.add.rectangle(0, 0, 1, 1, 0x081824, .88).setDepth(99).setScrollFactor(0));
    let previous = '';
    const layout = () => {
      if (!this.healthText?.scene || !this.timerText?.scene || !this.pictureCounterText?.scene) return;
      const ratio = this.game.canvas.getBoundingClientRect().width / this.scale.width;
      if (!(ratio > 0)) return;
      const labels = [this.healthText, this.pictureCounterText, this.timerText];
      const signature = [ratio, ...labels.map(label => label.text)].join('|');
      if (signature === previous) return;
      previous = signature;
      const font = Math.max(40, 14 / ratio), pad = 6 / ratio, width = this.scale.width / 3;
      labels.forEach(label => label.setFontSize(font).setOrigin(.5, 0).setScrollFactor(0));
      const height = Math.max(...labels.map(label => label.height)) + 34 + pad * 3;
      labels.forEach((label, index) => {
        const x = width * (index + .5);
        label.setPosition(x, pad * 2);
        plates[index].setPosition(x, pad + height / 2).setSize(width - pad, height);
      });
      const x = width / 2, y = this.healthText.y + this.healthText.height + pad + 17;
      [this.healthBarBg, this.healthBarBorder].forEach(bar => bar.setPosition(x, y));
      this.healthBarFill.setPosition(x - 110 + this.healthBarFill.width / 2, y);
    };
    this.events.on('postupdate', layout);
    this.events.once('shutdown', () => this.events.off('postupdate', layout));''', 1)
    elif path.endswith('/football/index.html'):
        source = source.replace('#overlay {', '#overlay {\n      width: max-content;\n      max-width: calc(100vw - 24px);', 1)
        source = source.replace('function resizeCanvas() {', 'let __footballHud = {};\n    function resizeCanvas() {', 1)
        source = source.replace('canvas.style.height = ch + "px";', '''canvas.style.height = ch + "px";
      const ratio = cw / GAME_WIDTH;
      __footballHud = {score: Math.max(32, 16 / ratio), time: Math.max(22, 14 / ratio), names: Math.max(16, 14 / ratio)};
      __footballHud.timerY = 16 + __footballHud.score + 8 / ratio;
      const bounds = canvas.getBoundingClientRect();
      overlayEl.style.top = (bounds.top + (__footballHud.timerY + __footballHud.time) * ratio + 6) + "px";
      overlayEl.style.maxWidth = Math.max(160, cw - 24) + "px";''', 1)
        start = source.index('function drawHUD() {') if 'function drawHUD() {' in source else -1
        end = source.index('function drawGoalFX()', start) if start >= 0 and 'function drawGoalFX()' in source[start:] else -1
        if end >= 0:
            hud = source[start:end]
            for size, field in [('32', 'score'), ('22', 'time'), ('16', 'names')]:
                hud = hud.replace('"' + size + 'px system-ui, sans-serif"', '`' + '${__footballHud.' + field + '}' + 'px system-ui, sans-serif`')
            hud = hud.replace('GAME_WIDTH / 2, 56)', 'GAME_WIDTH / 2, __footballHud.timerY)')
            source = source[:start] + hud + source[end:]
    elif path.endswith('/penalty/gamescene.js'):
        source = source.replace('this._createGameplayUI();', '''this._createGameplayUI();
    let __previousHud = '';
    const __layoutHud = () => {
      const ratio = this.game.canvas.getBoundingClientRect().width / this.scale.width;
      if (!(ratio > 0)) return;
      const signature = [ratio, ...Object.values(this.ui).map(label => label.text)].join('|');
      if (signature === __previousHud) return;
      __previousHud = signature;
      const pad = 6 / ratio, gap = 3 / ratio, font = Math.max(40, 14 / ratio);
      this.ui.scoreText.setFontSize(font).setOrigin(.5, 0).setPosition(this.W / 2, pad);
      const rowY = pad + this.ui.scoreText.height + gap;
      this.ui.roundText.setFontSize(font).setOrigin(0, 0).setPosition(pad, rowY);
      this.ui.timerText.setFontSize(font).setOrigin(1, 0).setPosition(this.W - pad, rowY);
      this.ui.statusText.setFontSize(Math.max(44, 14 / ratio)).setWordWrapWidth(this.W - pad * 2, true).setAlign('center').setOrigin(.5, 0)
        .setPosition(this.W / 2, this.goal.getBounds().bottom + pad * 2);
    };
    this.events.on('postupdate', __layoutHud);
    this.events.once('shutdown', () => this.events.off('postupdate', __layoutHud));
    __layoutHud();''', 1)
    elif path.endswith('/penalty/index.html'):
        # The native aim/defense instruction and portal tutorial replace this
        # duplicated HTML footer, which crossed all three touch buttons.
        source = source.replace('.hint {', '.hint { display: none;', 1)
    return _reviewed_small_hud_fixes(path, source)


def _reviewed_visual_fixes(path: str, source: str) -> str:
    """Scoped presentation fixes verified in the final screenshot inventory."""
    if path.endswith('/fruit-cosmics/mechanics.js'):
        for label in ['Time: 00:60', 'Tempo: 00:60']:
            source = source.replace('"' + label + '"', '`Tempo: ${this.formatTime(this.timeLeft)}`')
    if path.endswith('/wordle/Scenes/GameScene.js'):
        source = source.replace('? "ENTER"\n            : "DEL"', '? "Enviar"\n            : "Apagar"')
        source = source.replace('(t.special ? 44 : 54) + "px"', '(t.special ? 36 : 54) + "px"')
    if path.endswith('/doodle-jump/mechanics.js'):
        source = re.sub(
            r"(scene\.highScoreText\s*=\s*scene\.add\s*\.text\()20,\s*60,\s*'',\s*\{\s*fontSize:\s*'32px'",
            r"\g<1>650, 70, '', { fontSize: '40px'", source, count=1,
        )
    if path.endswith('/tic-tac-toe/mechanics.js'):
        source = source.replace('lineStyle: { width: 8, color: 0x2c3e50 }', 'lineStyle: { width: 8, color: 0x9ce7ff }')
    if path.endswith('/dodge-master/mechanics.js'):
        source = source.replace('this.add.text(470, 33,', 'this.add.text(200, 108,')
    if path.endswith('/boom-dots/mechanics.js'):
        source = source.replace('Win at ${this.targetScore} hits.', 'Alcance ${this.targetScore} pontos.')
        source = source.replace('Win at 3 hits.', 'Alcance 3 pontos.')
    if path.endswith('/penalty/index.html'):
        # Both authored result screens restart on a real touch or Space. Wait
        # for that scene transition before announcing another activity round.
        source = source.replace("()=> this.scene.start('GameScene')", "()=> { this.scene.start('GameScene'); window.__baltigo.resumePenaltyRound(); }")
    if path.endswith('/ellars/mechanics.js'):
        # Text is centered in the authored button art, with enough room for its
        # Portuguese caption. Custom hit areas keep the full visible button
        # tappable even when the runtime changes the Next caption afterward.
        helper = '''const __baltigoEllarsButton = (button, width, height) => {
  button.input.customHitArea = true;
  button.input.hitArea = new Phaser.Geom.Rectangle(0, 0, width, height);
  button.input.hitAreaCallback = (area, x, y) => Phaser.Geom.Rectangle.Contains(area,
    x + (width - button.width) / 2, y + (height - button.height) / 2);
};
'''
        source = helper + source
        source = source.replace('"Reshuffle"', '"Misturar"')
        source = re.sub(r'(add\.text\(145, topY, [^\n]+\{\s*font: ")bold 50px Arial', r'\g<1>bold 40px Arial', source)
        source = source.replace('add.text(285, topY,', 'add.text(315, topY,')
        source = re.sub(r'(scene\.partsLabel = scene\.add\.text\(730, topY, [^\n]+font: ")bold 50px Arial', r'\g<1>bold 46px Arial', source)
        source = source.replace('font: "bold 70px Arial", fill: "#000000"', 'font: "bold 40px Arial", fill: "#000000"')
        source = source.replace('scene.shuffleText.on("pointerdown",', '__baltigoEllarsButton(scene.shuffleText, shuffleBg.displayWidth, Math.max(124, shuffleBg.displayHeight));\n    scene.shuffleText.on("pointerdown",')
        source = source.replace('nextBtn.on("pointerdown",', '__baltigoEllarsButton(nextBtn, nextBtnBg.displayWidth, nextBtnBg.displayHeight);\n    nextBtn.on("pointerdown",')
        source = source.replace('replayBtn.on("pointerdown",', '__baltigoEllarsButton(replayBtn, replayBtnBg.displayWidth, replayBtnBg.displayHeight);\n    replayBtn.on("pointerdown",')
    if path.endswith('/Scenes/WinScene.js') and path.split('/')[-3] in {'bomb-blast', 'parkour', 'shooter', 'tower-shooter'}:
        source = source.replace('title + this.finalScore', "title.trim() + '\\nPontos: ' + this.finalScore")
    if path.endswith('/screw-master/Scenes/GameScene.js'):
        # Preserve the real error/timeout result. Only its actual replay gesture
        # adopts the existing clean-document policy; no victory/Next is added.
        source = source.replace('`Score: ${tps} tiles/sec`', '`Acertos por segundo:\\n${tps}`')
        source = source.replace('`Pontos: ${tps} tiles/sec`', '`Acertos por segundo:\\n${tps}`')
        source = re.sub(r'(`Acertos por segundo:\\n\$\{tps\}`\s*,\s*\{)', r'\g<1> align: "center",', source, count=1)
        source = source.replace('''overlay.on("pointerdown", () => {
      this.scene.restart();
    });''', '''overlay.name = 'Replay';
    overlay.on("pointerdown", () => {
      window.__baltigo.completeAndRestart({result: 'lose', score: this.score});
    });''')
    return _reviewed_hud_fixes(path, source)


def prepare_game_response(path: str, content: bytes, media_type: str = '') -> bytes:
    """Return adapted response bytes; media type remains the caller's value.

    Call for HTML, JS and JSON (including normalized config overrides). The
    runtime must be inserted synchronously before any source engine script.
    """
    extension = Path(path).suffix.lower()
    if extension not in {'.html', '.js', '.json'}:
        return content
    try:
        source = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        return content
    if extension == '.json':
        try:
            config = _json_text(json.loads(source))
            if isinstance(config, dict) and path.endswith('/config.json'):
                config = _word_game_config(path, config)
            return json.dumps(config, ensure_ascii=False).encode('utf-8')
        except (ValueError, TypeError):
            return content
    source = _localize_literals(source)
    source = _adapt_legacy_handoffs(source)
    source = _reviewed_visual_fixes(path, source)
    if '/sports/archer/' in path:
        if extension == '.html':
            source = _localize_archer_result_art(source)
        elif extension == '.js':
            source = source.replace('selector + " path"', 'selector + " text"')
    # Embedded Mini Apps are expanded by the parent shell. Upstream attempts
    # fullscreen during Scene.create(), without a gesture, caused rejected
    # promises in WebViews and did not improve canvas sizing.
    source = re.sub(r'((?:(?:this|scene)\.)?scale)\.startFullscreen\(\s*\)', r'\1.refresh()', source)
    if '/arcade/abhita/' in path and extension == '.js':
        source = source.replace("const bg = this.add.image(0, -50, 'dialog_bg_start');", "const bg = this.add.image(0, -50, 'dialog_bg_start').setDisplaySize(1120, 900);")
        source = source.replace('this.add.text(-55, -165,', 'this.add.text(0, -330,')
        source = source.replace('const desc = this.add.text(0, 30,', 'const desc = this.add.text(0, -40,')
    # This source rendered nothing until Start. Show the real first 3D frame
    # behind the tutorial and read the same configured target as the HUD.
    if '/car-race/' in path and extension == '.html':
        source = source.replace('animate();', 'animate(); renderer.render(scene, camera);')
        source = source.replace('Collect 100 coins to win.', 'Recolha as moedas indicadas na meta para vencer.')
        source = source.replace('Recolha 100 moedas para vencer.', 'Recolha as moedas indicadas na meta para vencer.')
    if '/board/chess/' in path and extension == '.html':
        # The source stacked 60px + 100vh + a fixed 64px footer, leaving the
        # canvas taller than its actual embedded viewport and clipping controls.
        source = source.replace('</style>', '''
html,body{width:100%;height:100%;overflow:hidden!important}
body{display:grid;grid-template-rows:42px minmax(0,1fr) 38px}
.topbar{height:42px;box-sizing:border-box;min-width:0;padding:0 10px}
.topbar .btn{margin-top:0;padding:7px 12px;font-size:12px;white-space:nowrap}
#game{width:100%;height:100%;min-width:0;min-height:0;overflow:hidden}
.bottom{position:static;height:38px;min-width:0;box-sizing:border-box;padding:0 10px;font-size:12px;text-align:center}
#status{overflow-wrap:anywhere;max-width:100%}
</style>''', 1)
        source = source.replace('playBtn.y = 550;', 'playBtn.y = boxH * 0.36;')
        source = source.replace("'PLAY', boxW * 1, boxH * 1", "'PLAY', boxW * 0.7, 150")
        source = source.replace("'JOGAR', boxW * 1, boxH * 1", "'JOGAR', boxW * 0.7, 150")
        source = source.replace("'REPLAY', boxW * 1, boxH * 1", "'REPLAY', boxW * 0.7, 150")
        source = source.replace("'JOGAR NOVAMENTE', boxW * 1, boxH * 1", "'JOGAR NOVAMENTE', boxW * 0.7, 150")
    if extension != '.html':
        return source.encode('utf-8')
    slug = path.split('/')[-2] if '/' in path else ''
    game = {'slug': slug, **metadata().get(slug, {}), 'transitions':transition_policies().get(slug, {})}
    config = json.dumps(game, ensure_ascii=False).replace('</', '<\\/')
    injection = (
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,user-scalable=no">'
        '<meta name="baltigo-adapter" content="' + VERSION + '">'
        '<script>window.__BALTIGO_GAME=' + config + ';</script>'
        '<script src="/static/game-localization.js?v=' + VERSION + '"></script>'
        '<script src="/static/game-runtime.js?v=' + VERSION + '"></script>'
        '<style data-baltigo>html,body{overscroll-behavior:none!important;-webkit-text-size-adjust:100%;}'
        'body{margin:0}canvas{touch-action:none}button{touch-action:manipulation;cursor:pointer}'
        '@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}</style>'
    )
    source = re.sub(r'<meta\b[^>]*\bname\s*=\s*["\']viewport["\'][^>]*>', '', source, flags=re.I)
    source = re.sub(r'(<html\b[^>]*\blang\s*=\s*)["\'][^"\']*["\']', r'\1"pt-BR"', source, count=1, flags=re.I)
    if re.search(r'<head\b[^>]*>', source, re.I):
        source = re.sub(r'(<head\b[^>]*>)', lambda m: m[0] + injection, source, count=1, flags=re.I)
    else:
        source = injection + source
    return source.encode('utf-8')
