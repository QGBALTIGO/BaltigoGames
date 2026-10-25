import json
import re
from collections import Counter
from pathlib import Path

from app.game_runtime import prepare_game_response, word_games

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_precedes_engine_and_corrects_mobile_viewport():
    original = b'<html lang="en"><head><meta name="viewport" content="width=980"><script src="phaser.js"></script></head><body>How to Play</body></html>'
    rendered = prepare_game_response('games/arcade/snake/index.html', original, 'text/html').decode()
    assert rendered.count('name="viewport"') == 1
    assert 'width=device-width,initial-scale=1,viewport-fit=cover' in rendered
    assert 'lang="pt-BR"' in rendered
    assert rendered.index('game-runtime.js') < rendered.index('src="phaser.js"')
    assert 'Cobrinha' in rendered


def test_localization_preserves_scene_asset_and_config_identifiers():
    script = b"scene.start('play'); const url='assets/next.png'; const next='next'; add.text(1,2,'Game Over');"
    rendered = prepare_game_response('games/arcade/snake/mechanics.js', script, 'application/javascript').decode()
    assert "scene.start('play')" in rendered
    assert "'assets/next.png'" in rendered
    assert "const next='next'" in rendered
    assert "'Fim de jogo'" in rendered
    source = {'gameplay': {'state': 'play'}, 'images': {'next': 'assets/next.png'}, 'texts': {'instructions': 'How to Play'}}
    config = json.loads(prepare_game_response('games/puzzle/test/config.json', json.dumps(source).encode()))
    assert config['gameplay'] == source['gameplay']
    assert config['images'] == source['images']
    assert config['texts']['instructions'] == 'Como jogar'


def test_binary_assets_are_never_decoded_or_changed():
    binary = b'\x89PNG\x00\xff\x01Game Over'
    assert prepare_game_response('games/a/assets/play.png', binary, 'image/png') == binary


def test_archer_vector_result_words_are_portuguese_and_keep_animation_targets():
    original = b'''<html><head></head><body><svg>
<g id="target" transform="translate(900 249.5) scale(1.8)"><path d="M0 0"/></g>
<g class="miss" fill="#aaa" opacity="0" transform="translate(0, 100)"><path d="M358 194L363 118"/></g>
<g class="bullseye" fill="#F4531C" opacity="0"><path d="M322 159L337 138"/></g>
<g class="hit" fill="#ffcc00" opacity="0" transform="translate(180, -80) rotate(12)"><path d="M383 114L385 195"/></g>
</svg></body></html>'''
    rendered = prepare_game_response('games/sports/archer/index.html', original, 'text/html').decode()
    for group, label in [('miss', 'ERROU!'), ('bullseye', 'NO CENTRO!'), ('hit', 'ACERTOU!')]:
        match = re.search(r'<g\b[^>]*class="' + group + r'"[^>]*>(.*?)</g>', rendered, re.S)
        assert match and '<text ' in match[1] and label in match[1]
        assert '<path' not in match[1]
    assert 'id="target" transform="translate(900 249.5)' in rendered
    assert '<path d="M0 0"/>' in rendered
    assert 'class="hit" fill="#ffcc00" opacity="0" transform="translate(180, -80) rotate(12)"' in rendered
    source = b'TweenMax.staggerFromTo(selector + " path", .5, before, after, .05); TweenMax.staggerTo(selector + " path", .3, after, .03);'
    adapted = prepare_game_response('games/sports/archer/script.js', source).decode()
    assert adapted.count('selector + " text"') == 2
    assert '.5, before, after, .05' in adapted and '.3, after, .03' in adapted


def test_wordle_display_fix_preserves_native_keyboard_action_codes():
    source = b'''const label = t.special ? t.code === "ENTER"
            ? "ENTER"
            : "DEL" : t.code;
const style={fontSize: (t.special ? 44 : 54) + "px"};
this.keyRects.push({code:t.code});this._pressKey("ENTER");this._pressKey("DEL");'''
    fixed = prepare_game_response('games/word-quiz/wordle/Scenes/GameScene.js', source).decode()
    assert '? "Enviar"' in fixed and ': "Apagar"' in fixed
    assert 't.code === "ENTER"' in fixed and 'code:t.code' in fixed
    assert 'this._pressKey("ENTER")' in fixed and 'this._pressKey("DEL")' in fixed


def test_result_spacing_fix_is_scoped_to_observed_games_not_shooter_category():
    source = b'this.add.text(cx,cy,title + this.finalScore,style);'
    assert prepare_game_response('games/shooter/bird-shooter/Scenes/WinScene.js', source) == source
    fixed = prepare_game_response('games/shooter/shooter/Scenes/WinScene.js', source).decode()
    assert "title.trim() + '\\nPontos: ' + this.finalScore" in fixed


def test_screw_replay_keeps_real_loss_without_adding_victory_or_next():
    source = b'''this.gameOver = true;
const tps=(this.score/Math.max(this.elapsed,1)).toFixed(3);
this.add.text(540,960,`Score: ${tps} tiles/sec`);
overlay.on("pointerdown", () => {
      this.scene.restart();
    });'''
    fixed = prepare_game_response('games/puzzle/screw-master/Scenes/GameScene.js', source).decode()
    assert 'this.gameOver = true' in fixed
    assert '`Acertos por segundo:\\n${tps}`' in fixed
    assert 'WinScene' not in fixed and 'next' not in fixed.lower()
    assert "completeAndRestart({result: 'lose', score: this.score})" in fixed
    assert 'WinScene' not in fixed and 'next' not in fixed.lower()


def test_portuguese_wordle_retains_five_letter_logic_and_clues():
    source = {'words': {'answerPool': ['APPLE']}, 'gameplay': {'fixedAnswer': 'APPLE'}, 'texts': {}}
    game = json.loads(prepare_game_response('games/word-quiz/wordle/config.json', json.dumps(source).encode()))
    words = game['words']
    assert 'APPLE' not in words['answerPool']
    assert game['gameplay']['fixedAnswer'] == ''
    assert game['texts']['score_label'] == 'Tentativa'
    assert 'sem acentos' in game['texts']['how_to_play']
    assert set(words['answerPool']) <= set(words['validGuesses'])
    assert set(words['answerPool']) <= set(words['clues'])
    assert all(len(word) == 5 and word.isascii() and word.isupper() for word in words['validGuesses'])


def test_portuguese_crosswords_are_solvable_and_crossing_letters_agree():
    puzzles = word_games()['words-of-wonder']['puzzles']
    assert len(puzzles) >= 2
    for puzzle in puzzles:
        used = {}
        letters = Counter(puzzle['letters'])
        for entry in puzzle['crossword']['words']:
            assert len(entry['word']) == len(entry['slots'])
            assert not (Counter(entry['word']) - letters)
            for letter, slot in zip(entry['word'], entry['slots'], strict=True):
                coordinate = slot['r'], slot['c']
                assert coordinate not in used or used[coordinate] == letter
                used[coordinate] = letter
        for bonus in puzzle['bonusWords']:
            assert not (Counter(bonus) - letters)


def test_portuguese_metadata_covers_every_catalog_identifier():
    catalog = json.loads((ROOT / 'data/registry.json').read_text(encoding='utf-8'))
    metadata = json.loads((ROOT / 'data/catalog-pt.json').read_text(encoding='utf-8'))
    assert set(metadata) == {game['slug'] for game in catalog['games']}
    assert all(item['tutorial'] and item['language'] == 'pt-BR' for item in metadata.values())


def test_embedded_games_refresh_canvas_instead_of_forcing_fullscreen():
    original = b"this.scale.startFullscreen(); scene.scale.startFullscreen(); scene.start('play');"
    rendered = prepare_game_response('games/arcade/flappy/mechanics.js', original).decode()
    assert rendered == "this.scale.refresh(); scene.scale.refresh(); scene.start('play');"


def test_source_comments_cannot_consume_later_template_translations():
    source = "// It's the player's turn.\nconst hint=`Swipe to control the snake.\\nEat food to grow longer and\\nscore points. Hitting a wall or\\nbiting yourself ends the game.\\n Target:${this.targetScore}`;\nconst key='ENTER';"
    rendered = prepare_game_response('games/arcade/snake/mechanics.js', source.encode()).decode()
    assert 'Swipe to control' not in rendered
    assert 'Deslize para guiar a cobra.' in rendered
    assert '${this.targetScore}' in rendered
    assert "const key='ENTER'" in rendered


def test_desert_wordwheel_has_only_reachable_portuguese_grid_targets():
    game = json.loads(prepare_game_response('games/puzzle/6oct/config.json', b'{"gameplay":{}}'))
    for puzzle in game['gameplay']['puzzles']:
        letters = Counter(puzzle['bank'])
        for target in puzzle['targets']:
            assert not (Counter(target) - letters)
            assert any(target in row for row in puzzle['grid']['cells'])
        assert all(len(row) == puzzle['grid']['cols'] for row in puzzle['grid']['cells'])


def test_legacy_final_confirmation_uses_runtime_but_preserves_real_phase_changes():
    original = b"next.on('pointerdown',()=>this.notifyParent('sceneComplete',{result:'win'})); this.scene.start('Level2'); state.level++; notifyParent('sceneComplete', {result:'fail'}); this.events.emit('sceneComplete');"
    rendered = prepare_game_response('games/arcade/test/mechanics.js', original).decode()
    assert "next.on('pointerdown',()=>window.__baltigo.completeAndRestart({result:'win'}))" in rendered
    assert "this.scene.start('Level2'); state.level++" in rendered
    assert "window.__baltigo.completeAndRestart({result:'fail'})" in rendered
    assert "this.events.emit('sceneComplete')" not in rendered


def test_transition_policy_covers_all_games_and_keeps_authored_campaigns():
    policies=json.loads((ROOT/'data/game-transitions.json').read_text(encoding='utf-8'))
    registry=json.loads((ROOT/'data/registry.json').read_text(encoding='utf-8'))
    assert set(policies)=={game['slug'] for game in registry['games']}
    campaigns={slug for slug,policy in policies.items() if policy['mode']=='campaign'}
    assert campaigns=={'crowd-control','cut-rope','demon','gunman','perfect-square','road-cross','penalty'}
    assert all(policies[slug]['replay_policy']=='source' for slug in campaigns)
    assert sum(policy['replay_policy']=='document' for policy in policies.values())==122
