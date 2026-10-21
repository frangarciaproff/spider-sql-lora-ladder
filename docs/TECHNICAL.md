# Technical report: Spider SQL LoRA ladder

Plain-language summary: [README](../README.md). This page has the full numbers, methods and reproduction steps.

Does LoRA fine-tuning make small open models better at text-to-SQL, and does the gain survive on a harder benchmark it was not trained on? Qwen2.5-Coder 0.5B and 1.5B Instruct, fine-tuned on Spider with LoRA on a free T4 GPU, evaluated against pre-registered success criteria with three training seeds and database-level confidence intervals.

![Execution accuracy on Spider test and BIRD dev](figures/results.png)

*Error bars: 95% interval of each bar (bootstrap over databases). Conditions are compared on the same questions, so a difference can be clear even where error bars overlap; the paired tests are in the table below.*

## Results at a glance

| Hypothesis (fixed before any result) | Model | Gain of LoRA over zero-shot, 95% CI | Threshold | Outcome |
|---|---|---|---|---|
| H1, Spider test | 0.5B | **+15.2 pp** [+11.9, +18.8] | >= 5 pp, lower bound > 0 | met |
| H2, Spider test | 1.5B | **+9.0 pp** [+7.3, +10.7] | >= 3 pp, lower bound > 0 | met |
| O1 transfer, BIRD dev | 0.5B | **+5.5 pp** [+1.5, +9.8] | >= 2 pp, lower bound > 0 | met |
| O1 transfer, BIRD dev | 1.5B | **+2.7 pp** [-1.3, +6.7] | >= 2 pp, lower bound > 0 | **not met** |
| O2 no harm, BIRD dev | 0.5B | lower bound +1.5 | lower bound >= -2 pp | met |
| O2 no harm, BIRD dev | 1.5B | lower bound -1.3 | lower bound >= -2 pp | met |

What the numbers say, and what they do not:

- **Fine-tuning helps a lot on Spider.** Execution accuracy goes from 48.3% to 63.5% (0.5B) and from 66.4% to 75.4% (1.5B). Much of it comes from fewer queries that fail to run: the share of queries that execute without error rises from 70.7% to 82.4% (0.5B) and from 85.3% to 92.5% (1.5B).
- **Size still beats fine-tuning.** The fine-tuned 0.5B stays below the zero-shot 1.5B on Spider test: -3.0 pp [-4.9, -1.0].
- **Few-shot prompting is not a free baseline.** Three fixed examples in the prompt do nothing for the 0.5B (-0.3 pp [-2.6, +2.2]) and hurt the 1.5B (-3.2 pp [-5.4, -1.1]).
- **Transfer to BIRD is partial.** The 0.5B transfers. For the 1.5B the gain depends on the database: from -7.3 pp to +13.9 pp across the 11 BIRD databases, 5 of them negative, so the pre-registered interval includes zero. A per-question interval would exclude zero; the pre-registered method decides, so the result is reported as not met and not robust.
- **The BIRD gain is on easy questions.** For the 0.5B, simple questions go from 19.1% to about 26%; challenging questions stay around 4%.
- **The gain shrinks with size on both benchmarks** (Spider +15.2 to +9.0 pp, BIRD +5.5 to +2.7 pp). This pattern was not pre-registered or tested and is an observation only.

## Full results

Spider test, execution accuracy (EX), 2,147 questions on 40 databases never used in training or tuning. C3 is the mean of 3 seeds (seed standard deviation in brackets).

| Condition | 0.5B EX | 0.5B EX strict | 1.5B EX | 1.5B EX strict |
|---|---|---|---|---|
| B0b trivial baseline (overlap count) | 5.1 | 3.8 | 5.1 | 3.8 |
| C1 zero-shot | 48.3 | 47.6 | 66.4 | 66.0 |
| C2 three-shot | 48.0 | 47.5 | 63.2 | 62.9 |
| C3 LoRA | 63.5 (1.4) | 62.5 | 75.4 (0.4) | 74.5 |

Spider dev, test-suite accuracy (TS, the stricter official metric; its databases exist for dev only), 1,034 questions on 20 databases:

| Condition | 0.5B TS | 1.5B TS |
|---|---|---|
| C1 zero-shot | 40.8 | 56.7 |
| C2 three-shot | 39.9 | 57.3 |
| C3 LoRA | 53.9 | 69.2 |
| C3 minus C1, 95% CI | +13.1 [+9.3, +16.7] | +12.6 [+8.4, +16.3] |

BIRD dev, official execution accuracy, 1,534 questions on 11 databases, with the BIRD evidence hint in the prompt. No training on BIRD.

| Condition | 0.5B EX | 1.5B EX |
|---|---|---|
| C1 zero-shot | 13.4 | 26.2 |
| C3 LoRA (seeds) | 18.9 (18.4 / 20.1 / 18.3) | 28.9 (29.3 / 29.1 / 28.2) |
| Evidence effect for C3, with minus without hint | +7.9 pp | +10.8 pp |

EX strict keeps DISTINCT in both queries (the standard comparison removes it); it is reported as a sensitivity check. Spider and BIRD numbers use different comparison rules and should not be read side by side.

## How it was done

**Rules first.** [SPEC.md](../SPEC.md) fixed the data split, metrics, hypotheses and thresholds before any model was run. Every later change, null result and lost run is in the append-only [DECISIONS.md](DECISIONS.md), with the evidence and the previous state. The test set was run exactly once per condition, after the configuration was frozen, and the adapters used on test were checked against fingerprints taken before the run.

**Data.** Spider train (8,659 questions) split by database into fit (131 databases) and validation (15 databases), so validation measures unseen schemas. 25 training pairs whose question and SQL also appear in dev or test were removed before fitting (results/decontamination.json). 82 examples longer than 2,048 tokens were dropped from training only.

**Conditions.** B0a and B0b are trivial baselines that must be beaten. C1 is zero-shot with the schema as `CREATE TABLE` statements. C2 adds three fixed examples. C3 is LoRA fine-tuning. Prompt, extraction and greedy decoding are identical across conditions.

**Training.** LoRA r 16, alpha 32, all linear projections, AdamW, cosine schedule, fp16, effective batch 16, loss on the SQL answer only. Learning rate and epochs were chosen on validation with one seed of the 0.5B (4 runs, pre-registered tie rule), then frozen and reused for the 1.5B. Three fresh seeds per size. One seed takes about 32 minutes (0.5B, 2.3 GB peak memory) or 90 minutes (1.5B, 4.6 GB) on a single T4, with Unsloth.

**Evaluation.** Execution-based comparison vendored from the official test-suite evaluator (Apache-2.0), with a working timeout and read-only databases added; our wrapper agrees with the upstream code on 370 of 370 checked comparisons. BIRD uses its official rule (set equality of result rows), re-implemented and documented in src/spider_sql/bird.py.

**Statistics.** Per-question correctness is paired across conditions and averaged over seeds; 95% intervals come from a bootstrap that resamples whole databases (10,000 draws), because questions on the same database are correlated. Exact McNemar tests per seed are in results/.

## Limitations

- Test-suite accuracy is not available on Spider test, so test numbers are EX only, which accepts some queries that are right for the wrong reason.
- BIRD has only 11 databases, so its intervals are uncertain however many questions there are.
- Part of the measured error is the benchmark: the prompt shows the schema but no data, so some failures need stored values the model cannot see (spelling, case, codes), and some gold answers are debatable. The manual error analysis (below) counts these.
- Zero-shot accuracy is much higher on Spider than on BIRD (C1 47.8 vs 13.4 for 0.5B, 65.3 vs 26.2 for 1.5B, different metrics). Prior exposure of the base models to Spider-style data cannot be ruled out and is not corrected.
- Two model sizes, one model family, one LoRA configuration; nothing here says how 3B+ models or other families behave.

## Error analysis

Where do the remaining mistakes come from, and what did fine-tuning fix? 100 Spider dev failures of the zero-shot model and 100 of the fine-tuned model (1.5B, seed 0) were drawn at random, pooled, shuffled and labeled by hand without knowing which model produced each one, into six classes fixed before labeling. Shares are of all 1,034 dev questions (failure share times the class share in the sample), with 95% Wilson intervals.

| Error class | Zero-shot | LoRA |
|---|---|---|
| Invented column or table | **16.3%** [13.0, 19.7] | **5.8%** [4.0, 8.1] |
| Wrong join or set operation | 8.0% [5.5, 11.2] | 7.1% [5.1, 9.5] |
| Wrong filter or value | 3.8% [2.2, 6.5] | 2.8% [1.6, 4.7] |
| Wrong aggregation or grouping | 2.8% [1.4, 5.2] | 2.8% [1.6, 4.7] |
| SQL syntax error | 1.4% [0.5, 3.4] | 1.3% [0.5, 2.8] |
| Other (wrong selected column, ordering, valid answer) | 2.4% [1.2, 4.8] | 5.6% [3.8, 7.9] |
| All failures | 34.7% | 25.3% |

- **Fine-tuning mainly stops the model from inventing schema.** Invented columns and tables drop from 16.3% to 5.8% of questions, about 10 pp, which is more than the whole drop in failures (9.4 pp).
- **Query logic does not improve.** Join, filter, aggregation and syntax errors stay at about the same level.
- **Some failures are not model errors.** In 12 of the 100 sampled LoRA failures (3 of 100 zero-shot) the prediction is a valid answer that the reference does not accept: duplicates in the gold, grouping by first name instead of by person, a code instead of its description. Another 5 per model need a stored value that the prompt does not show. As the model improves, more of what remains is disagreement with the benchmark.

Limits of this analysis: one labeler (the author), one seed, failures defined by EX on the original database, and blinding only partial (style cues remain). Protocol, labeling guide and the rows discussed during labeling: docs/DECISIONS.md; labels: results/error_analysis/.

## Reproduce

Requirements: Python 3.13, [uv](https://docs.astral.sh/uv/), the Spider release and test-suite databases (not redistributed). GPU steps run on a free Colab or Kaggle T4.

```bash
uv sync --group dev
cp .env.example .env                      # set SPIDER_DIR, TESTSUITE_DIR, BIRD_DIR, BIRD_DB_DIR
uv run --env-file .env python scripts/prepare_split.py
uv run --env-file .env python scripts/run_baselines.py
# GPU: notebooks/kaggle_runner.ipynb (generation, training, test, BIRD)
uv run python scripts/evaluate_hypotheses.py   # H1, H2 -> results/hypotheses.json
uv run python scripts/evaluate_bird.py         # O1, O2 -> results/bird_hypotheses.json
uv run --with matplotlib python scripts/make_figures.py
```

All predictions, per-question scores, run metadata (library versions, model revision, adapter fingerprints) and comparisons are in results/. The LoRA adapters are not published: whether an adapter trained on CC BY-SA data must carry that license is an open question (docs/DECISIONS.md).

## Repository layout

```
SPEC.md                 pre-registered plan, frozen sections, outcomes
docs/DECISIONS.md       append-only log of every change and result
docs/TECHNICAL.md       this report
src/spider_sql/         data, split, leakage, prompts, execution, training, statistics, BIRD
scripts/                one entry point per step
notebooks/              Colab and Kaggle runners
results/                every number in this report
tests/                  unit tests, upstream-equivalence test
```

## Licenses and citations

Code: MIT. Spider and BIRD: CC BY-SA 4.0, not redistributed here. Qwen2.5-Coder: Apache-2.0. Vendored comparison code from taoyds/test-suite-sql-eval: Apache-2.0 (src/spider_sql/_vendor).

- Yu et al. 2018. Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task. EMNLP. arXiv:1809.08887
- Finegan-Dollak et al. 2018. Improving Text-to-SQL Evaluation Methodology. ACL. (Source of the databases in train_others.json.)
- Original datasets behind train_others.json: Restaurants, GeoQuery, Scholar, Academic, IMDB and Yelp. BibTeX for all Spider-required entries, as given in the Spider release: [spider_citations.bib](spider_citations.bib)
- Zhong, Yu and Klein 2020. Semantic Evaluation for Text-to-SQL with Distilled Test Suites. EMNLP. arXiv:2010.02840
- Li et al. 2023. Can LLM Already Serve as A Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs (BIRD). NeurIPS. arXiv:2305.03111
- Hui et al. 2024. Qwen2.5-Coder Technical Report. arXiv:2409.12186
- Yang et al. 2024. Qwen2 Technical Report. arXiv:2407.10671
- Hu et al. 2021. LoRA: Low-Rank Adaptation of Large Language Models. arXiv:2106.09685

Built with AI assistance (Claude) for code and documentation. The experimental design, decisions, runs and manual labels are the author's.

Author: Francisco García Soriano
