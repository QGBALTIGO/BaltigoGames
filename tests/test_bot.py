from app.bot import _game_link, _launch_url, _search_games


def test_sharing_without_main_mini_app():
    assert _game_link("BaltigoGamesBot", "snake") == "https://t.me/BaltigoGamesBot?start=game_snake"


def test_sharing_with_main_mini_app():
    assert _game_link("BaltigoGamesBot", "snake", True) == "https://t.me/BaltigoGamesBot?startapp=snake"


def test_launch_selected_game_preserves_other_query_params():
    assert _launch_url("https://games.example/?v=2", "snake") == "https://games.example/?v=2&startapp=snake"
    assert _launch_url("https://games.example/", None) == "https://games.example/"


def test_inline_empty_query_limit_and_no_matches():
    catalog = {"games": [{"slug": str(i), "name": str(i)} for i in range(60)]}
    assert len(_search_games(catalog, "")) == 25
    assert _search_games(catalog, "no-game-with-this-name") == []
