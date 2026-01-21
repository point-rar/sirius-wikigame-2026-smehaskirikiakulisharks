from game.wiki_game_dumb import WikiGameDumb


def test_simple():
    path = WikiGameDumb().play("Software design pattern", "Software engineering", 2)
    assert len(path.page_names) == 2
    assert path.page_names[0] == "Software design pattern"
    assert path.page_names[1] == "Software engineering"
