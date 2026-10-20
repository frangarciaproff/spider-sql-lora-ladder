"""README figure from results/ only: Spider test EX (C1, C2, C3) and BIRD dev EX (C1, C3).

Bars: share of questions whose SQL returns the reference rows; C3 is the mean of 3 training
seeds. Error bars: 95% db-cluster bootstrap interval of each bar (SPEC 7.2 code). They are
per-condition intervals; differences between conditions are tested paired (README table).
Needs matplotlib (not a project dependency):
  uv run --with matplotlib python scripts/make_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

from spider_sql.stats import Key, load_rows, paired_cluster_bootstrap, seed_average  # noqa: E402

RESULTS = Path("results")
OUT = Path("docs/figures/results.png")
SIZES = (("qwen05b", "Qwen2.5-Coder 0.5B"), ("qwen15b", "Qwen2.5-Coder 1.5B"))
SEEDS = (0, 1, 2)
# navy, wine, olive (Fran's choice; CVD and contrast checks pass, navy and wine are darker
# than the recommended lightness band)
COLORS = {"C1": "#000080", "C2": "#800000", "C3": "#808000"}
NAMES = {
    "C1": "Zero-shot (no examples)",
    "C2": "Three examples in the prompt",
    "C3": "LoRA fine-tuned (mean of 3 seeds)",
}
SURFACE, INK, MUTED, GRID, WHISKER = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#8a8984"


def runs(tag: str, cond: str) -> list[str]:
    if cond == "C1":
        return [f"{tag}_c1_zero_shot"]
    if cond == "C2":
        return [f"{tag}_c2_three_shot"]
    return [f"{tag}_c3_lr0.0002_ep2_seed{s}" for s in SEEDS]


def scores(run_names: list[str], split: str) -> tuple[dict[Key, float], dict[Key, str]]:
    rows = [load_rows(RESULTS / r / f"{split}.jsonl") for r in run_names]
    return seed_average(rows, "ex"), {k: str(v["db_id"]) for k, v in rows[0].items()}


def panel(ax: Axes, split: str, conds: tuple[str, ...], title: str) -> None:
    width = 0.8 / len(conds)
    for i, (tag, _) in enumerate(SIZES):
        for j, cond in enumerate(conds):
            acc, clusters = scores(runs(tag, cond), split)
            ci = paired_cluster_bootstrap(dict.fromkeys(acc, 0.0), acc, clusters)
            mean, lo, hi = 100 * ci["point"], 100 * ci["lo"], 100 * ci["hi"]
            x = i + (j - (len(conds) - 1) / 2) * width
            ax.bar(x, mean, width - 0.03, color=COLORS[cond], label=NAMES[cond] if i == 0 else None)
            ax.errorbar(x, mean, yerr=[[mean - lo], [hi - mean]], color=WHISKER, capsize=2, lw=0.8)
            ax.text(x, hi + 1.2, f"{mean:.1f}", ha="center", va="bottom", fontsize=9, color=INK)
    ax.set_xticks(range(len(SIZES)), [label for _, label in SIZES])
    ax.set_title(title, loc="center", fontsize=11, color=INK)
    ax.set_ylabel("questions answered correctly (%)", color=MUTED, fontsize=11)
    ax.set_ylim(0, 88)
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED, length=0)


def main() -> int:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), facecolor=SURFACE, width_ratios=(3, 2))
    panel(axes[0], "test", ("C1", "C2", "C3"), "Spider test: 2,147 questions / 40 databases")
    panel(
        axes[1],
        "bird_dev",
        ("C1", "C3"),
        "Does it transfer to other databases?\n(BIRD: 1,534 questions / 11 databases)",
    )
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=9,
        bbox_to_anchor=(0.5, 0.045),
    )
    fig.text(
        0.5,
        0.005,
        "Correct = the generated SQL returns the same rows as the reference answer.",
        ha="center",
        fontsize=8,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=160, facecolor=SURFACE)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
