from spider_sql.baselines import first_table, overlap_count


def test_first_table() -> None:
    assert first_table(["singer", "concert"]) == 'SELECT * FROM "singer"'


def test_overlap_count_picks_best_match_with_plural_stripping() -> None:
    tables = ["stadium", "singer", "concert", "singer_in_concert"]
    assert overlap_count("How many concerts are there?", tables) == 'SELECT count(*) FROM "concert"'


def test_overlap_count_ties_go_to_first_table() -> None:
    assert overlap_count("Show everything", ["b", "a"]) == 'SELECT count(*) FROM "b"'


def test_quotes_are_escaped() -> None:
    assert first_table(['we"ird']) == 'SELECT * FROM "we""ird"'
