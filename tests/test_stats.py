import pytest

from spider_sql.stats import mcnemar_exact, paired_cluster_bootstrap, seed_average


def keys(n: int) -> list[tuple[str, int]]:
    return [("dev", i) for i in range(n)]


def test_identical_runs_give_zero_difference() -> None:
    k = keys(40)
    a = {x: float(i % 2) for i, x in enumerate(k)}
    clusters = {x: f"db{i % 5}" for i, x in enumerate(k)}
    res = paired_cluster_bootstrap(a, dict(a), clusters, n_boot=500)
    assert res["point"] == 0.0
    assert res["lo"] == 0.0 and res["hi"] == 0.0
    assert res["n_clusters"] == 5


def test_uniform_improvement_has_interval_above_zero() -> None:
    k = keys(50)
    a = {x: 0.0 for x in k}
    b = {x: 1.0 if i % 2 else 0.0 for i, x in enumerate(k)}
    clusters = {x: f"db{i % 10}" for i, x in enumerate(k)}
    res = paired_cluster_bootstrap(a, b, clusters, n_boot=1000)
    assert res["point"] == pytest.approx(0.5)
    assert res["lo"] > 0


def test_bootstrap_is_deterministic_for_a_seed() -> None:
    k = keys(30)
    a = {x: float(i % 3 == 0) for i, x in enumerate(k)}
    b = {x: float(i % 2 == 0) for i, x in enumerate(k)}
    clusters = {x: f"db{i % 6}" for i, x in enumerate(k)}
    assert paired_cluster_bootstrap(a, b, clusters, n_boot=300, seed=1) == paired_cluster_bootstrap(
        a, b, clusters, n_boot=300, seed=1
    )


def test_seed_average() -> None:
    k = keys(2)
    runs = [{k[0]: {"ts": 1}, k[1]: {"ts": 0}}, {k[0]: {"ts": 0}, k[1]: {"ts": 0}}]
    assert seed_average(runs, "ts") == {k[0]: 0.5, k[1]: 0.0}
    with pytest.raises(ValueError):
        seed_average([runs[0], {k[0]: {"ts": 1}}], "ts")


def test_mcnemar_exact_known_value() -> None:
    k = keys(12)
    a = {x: 0 for x in k}
    b = {x: 1 if i < 10 else 0 for i, x in enumerate(k)}
    res = mcnemar_exact(a, b)
    assert (res["a_only"], res["b_only"]) == (0, 10)
    assert res["p_value"] == pytest.approx(2 / 1024)
    assert mcnemar_exact(a, dict(a))["p_value"] == 1.0
