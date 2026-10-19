import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "evaluate_hypotheses", Path(__file__).parents[1] / "scripts" / "evaluate_hypotheses.py"
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_success_needs_threshold_and_positive_lower_bound() -> None:
    assert mod.decide({"point": 0.06, "lo": 0.01, "hi": 0.1}, 0.05, 3) == "SUCCESS"
    assert mod.decide({"point": 0.04, "lo": 0.01, "hi": 0.1}, 0.05, 3) == "NOT MET"
    assert mod.decide({"point": 0.08, "lo": -0.01, "hi": 0.2}, 0.05, 3) == "NOT MET"
    assert mod.decide({"point": 0.08, "lo": 0.02, "hi": 0.2}, 0.05, 2) == "EXPLORATORY"


def test_thresholds_match_spec() -> None:
    assert mod.HYPOTHESES == {"H1": ("qwen05b", 0.05), "H2": ("qwen15b", 0.03)}
    assert mod.c3_runs("qwen05b")[0] == "qwen05b_c3_lr0.0002_ep2_seed0"
