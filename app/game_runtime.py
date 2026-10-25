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
    return source


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
