# SPEC: spider-sql-lora-ladder

Status: AGREED v1.0 (2026-10-15, Fran: "Let's start"). Metrics and thresholds in sections 7 are frozen; no result existed at agreement. BIRD hypotheses O1/O2 (section 8) remain PROPOSED until review point 4.

## 1. Problem

Does LoRA fine-tuning on Spider improve text-to-SQL accuracy of small instruct code models, how large is the gain at two model sizes, and does it transfer to a different benchmark (BIRD)?

Purpose: portfolio project. No production task. The value of the project is the evaluation rigor, not the absolute number.

## 2. Models

| ID | Model | License (verify on card, record here) |
|---|---|---|
| S | Qwen/Qwen2.5-Coder-0.5B-Instruct | Apache-2.0 (LICENSE file from the model card, Copyright 2024 Alibaba Cloud) |
| M | Qwen/Qwen2.5-Coder-1.5B-Instruct | Apache-2.0 (LICENSE file from the model card, confirmed by Fran) |

- Full-precision weights, LoRA in fp16 (T4 has no bf16). No 4-bit quantization at these sizes.
- Exact model revision (commit hash) is recorded in `results/` for every run.
- Requires `transformers` >= 4.37.0 (model card); the pinned version is recorded in `pyproject.toml`.
- Citations required: Hui et al. 2024 (Qwen2.5-Coder Technical Report, arXiv:2409.12186) and Yang et al. 2024 (Qwen2 Technical Report, arXiv:2407.10671).
- Larger sizes (3B) and other families are non-goals.

## 3. Data

### 3.1 Spider (primary)
- Source: official Spider 1.0 release, local copy `spider_data.zip`.
- Archive sha256: `00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b` (205,800,266 bytes).
- License: CC BY-SA 4.0 (confirmed on yale-lily.github.io/spider, 2026-10-15).
- Colab bundle (`dist/spider_bundle.zip`, built 2026-10-15 by `scripts/make_colab_bundle.py`): 1,241 files plus MANIFEST.json, 4.47 GB uncompressed, 0.95 GB zipped, sha256 `aacfdd35b1a6afc369ef028cff59c39ac8639fd813c3b092fb7e5a1615e2b44f`. Contents: Spider JSON/SQL files, all 166 train/dev databases, the 40 test databases, and the test-suite folders of the 20 dev databases (675 variant files). Every Colab run verifies this checksum.
- Citations required: Yu et al. 2018 (Spider), Finegan-Dollak et al. 2018, and the original datasets behind `train_others.json` (Restaurants, GeoQuery, Scholar, Academic, IMDB, Yelp). Full BibTeX goes in README.md.
- Raw data is never committed. `scripts/get_data.py` documents the source; the archive is provided locally.

| Split | Source | Examples | DBs |
|---|---|---|---|
| train (full) | `train_spider.json` + `train_others.json` | 8,659 | 146 |
| validation | carved from train by `db_id` (section 3.3) | tbd | tbd |
| train (fit) | train minus validation minus pair-overlap removals (3.4) | tbd | tbd |
| dev | `dev.json` | 1,034 | 20 |
| test | `test.json` (gold in `test_gold.sql`, public since Feb 2024) | 2,147 | 40 |

### 3.2 Roles of each split
- train (fit): the only data the model is fitted on.
- validation: hyperparameter and checkpoint selection. Nothing else.
- dev: development-phase reporting and error analysis. Never used to select anything.
- test: confirmatory evaluation. Run once per condition, after all hyperparameters and prompts are frozen. Success criteria (section 7) are evaluated here.

### 3.3 Validation split
- Hold out whole databases, never individual examples.
- Fraction: 10% of train databases (15 of 146), chosen with split seed 1234 (constant for the whole project; not varied with training seeds).
- Databases from `train_others` (6 DBs, 1,659 examples) are assigned to fit, to keep validation on Spider-native databases. This is a decision, logged in docs/DECISIONS.md.

### 3.4 Leakage checks
Unit tests on synthetic data run in CI. Real-data checks run with `scripts/prepare_split.py` and `pytest -m data`, and write `results/leakage_report.json` and `results/decontamination.json`.
- Hard rule: no `db_id` shared between fit, validation, dev, test. Any violation fails the run.
- Exact (question, gold SQL) pairs, compared after lowercasing and whitespace normalization: fit examples whose pair also occurs in validation, dev or test are removed from fit. Removed examples are listed in `results/decontamination.json`. After cleaning, no pair may overlap (checked).
- Question-only duplicates (same question text, different SQL or database) are not removed. Counts are reported in `leakage_report.json`.
- Basis (dry run 2026-10-15, official run pending): question overlap with fit was 5 dev, 27 test, 2 validation; question+SQL pair overlap was 2 dev, 17 test, 1 validation, always on a different database.

### 3.5 Execution evaluation data
- Test-suite accuracy needs the distilled test-suite databases from `taoyds/test-suite-sql-eval` (Apache-2.0, 12 commits, last commit 2022-08-02, 19 open issues at check time). Frozen codebase (verified: HEAD e97acc5 is the 2022-08-02 commit). Only its result-comparison functions are vendored into `src/spider_sql/_vendor` (Apache-2.0, license file included); the evaluation script itself is not run, because its timeout is ineffective (see 7.1).
- CHECKED 2026-10-15 on the local copy (`data/testsuitedatabases`, 29 database folders, 3,889 SQLite files): covers Spider dev (20 of 20 DBs, 675 variant files), covers 0 of the 40 Spider test DBs. Test-suite accuracy is therefore unavailable on test. DECIDED 2026-10-15 (option A, docs/DECISIONS.md): success criteria use EX on Spider test; TS on dev is a secondary robustness check.

## 4. Conditions

| ID | Condition | Seeds |
|---|---|---|
| B0a | Trivial: `SELECT * FROM <first table in schema>` | n/a |
| B0b | Trivial: `SELECT count(*) FROM <table with highest token overlap with the question>`; tokens are lowercase alphanumerics, `_` splits words, a trailing `s` is dropped on words longer than 3 characters, ties go to the earlier table (`src/spider_sql/baselines.py`) | n/a |
| C1 | Zero-shot instruct model | n/a (greedy, deterministic) |
| C2 | 3-shot instruct model, 3 fixed examples from train (fit), chosen by seed 1234, same for all questions | n/a |
| C3 | LoRA fine-tuned | 3 training seeds: 0, 1, 2 |

- A model that does not beat the better of B0a/B0b is not a result.
- Same prompt template and same decoding across C1, C2, C3.

## 5. Prompt and decoding

- Prompt: model chat template; system message fixed; user message = schema as `CREATE TABLE` statements taken from the SQLite files (`sqlite_master`, tables only, creation order), then the question. No sample rows (sample-row ablation is deferred, see non-goals). Exact text: `src/spider_sql/prompt.py`.
- Target: the gold SQL only. Loss on completion tokens only.
- Decoding: greedy, `max_new_tokens` 256, no sampling, identical across all conditions.
- Post-processing: take the first fenced code block if present, otherwise the whole output; keep the first SQL statement (`sqlparse.split`), strip the trailing semicolon. Same function (`extract_sql`) for every condition.
- Execution timeout per query is fixed once (default 30 s) and recorded.
- Training examples exceeding `max_seq_length` are dropped and counted. Evaluation prompts are never truncated; over-length eval prompts count as incorrect and are reported.

## 6. Training configuration (frozen starting point)

- LoRA r = 16, alpha = 32, dropout 0, all linear projection modules.
- Optimizer AdamW, lr 2e-4, cosine schedule, warmup 3%, effective batch size 16, max length 2048, fp16.
- Tuning budget, on validation only, with seed 0 only, on S only: lr in {1e-4, 2e-4} x epochs in {2, 3} (4 runs maximum). The winning config is used for S and M. No further tuning. Any change to this plan is a logged deviation.
- Library: Unsloth + TRL SFTTrainer. The Unsloth speedup is measured by us (wall clock per epoch), not assumed.
- Adapter and checkpoints are saved to Drive; sessions may die and runs are rerun, not skipped.
- Every run logs: git commit, package versions, model revision, data checksum, seed, config, GPU, wall clock, peak VRAM.

## 7. Metrics and success criteria (frozen at agreement)

### 7.1 Metrics
- Primary: execution accuracy (EX) on Spider test: the predicted SQL and the gold SQL return the same result on the original database, compared with the test-suite comparison rules below.
- Secondary: test-suite accuracy (TS) on Spider dev (databases available only for dev), EX on dev, valid-SQL rate (executes without error) on dev and test.
- TS is stricter than EX and is the official Spider metric; its absence on test is stated as a limitation in the README.
- Comparison rules (test-suite-sql-eval defaults, `src/spider_sql/execution.py`): bag semantics; row order ignored unless the gold SQL contains ORDER BY; column order ignored (column permutations are tried); DISTINCT keywords removed from both queries before execution (so COUNT(DISTINCT x) equals COUNT(x)); no value plugging, the model predicts values.
- Execution safeguards: databases opened read-only; 60 s timeout enforced by a SQLite progress handler (upstream's asyncio timeout does not interrupt a running query: with timeout 1 s it returned after 10.7 s, measured 2026-10-15); result cap of 1,000,000 rows; empty or unparsable prediction counts as wrong; a failing gold query aborts the run.
- Verification: `tests/test_upstream_equivalence.py` compares our `exec_match` with upstream `eval_exec_match` (same commit) on mutated dev queries against the test-suite databases. 370 comparisons (37 dev questions x 10 query variants each, 2026-10-15): 0 disagreements. Rerun after any change to execution.py.
- Secondary metric, approved by Fran 2026-10-15: the same comparison with `keep_distinct = True` (DISTINCT kept, stricter) on dev (TS) and test (EX), reported next to every primary number as a sensitivity check on the DISTINCT leniency. No threshold; it is not part of the success criteria.
- Efficiency: wall clock per epoch, peak VRAM, tokens/s.

### 7.2 Statistics
- Unit of analysis: question. Per-question correctness is paired across conditions.
- Resampling: cluster bootstrap over `db_id` (questions within one database are correlated), 10,000 resamples, 95% percentile intervals.
- For C3, per-question correctness is averaged over the 3 seeds before bootstrapping. Seed-to-seed sd of the accuracy is reported separately.
- McNemar test on discordant pairs reported per seed as a secondary check.
- Differences are reported in percentage points (pp).

### 7.3 Pre-registered hypotheses (Spider test, EX)
- H1 (size S): C3 beats C1.
  SUCCESS if mean gain >= 5 pp and the lower bound of the 95% CI > 0.
- H2 (size M): C3 beats C1.
  SUCCESS if mean gain >= 3 pp and the lower bound of the 95% CI > 0.
- The two hypotheses concern different models and are tested separately at 95%, no multiplicity correction, declared here.
- If M has fewer than 3 completed seeds, H2 is labeled exploratory and not reported as a finding.
- Secondary comparisons (reported, no threshold): C3 vs C2, C2 vs C1, S vs M.
- Outcomes are recorded whether met or not. Null and negative results go to docs/DECISIONS.md.

## 8. OOD evaluation: BIRD (separate, pre-registered)

Run only after Spider test results are final.

- Data: BIRD dev (1,534 questions), official release. License and redistribution terms to be verified before use (OPEN).
- Models: C1 and C3 (Spider-trained, all seeds) for S and M. No training on BIRD in this section.
- Prompt: same template plus the BIRD `evidence` field appended to the question, because BIRD questions are not answerable without it. Variant without evidence reported as secondary.
- Metric: BIRD execution accuracy with the official evaluation script. Same statistics as 7.2.
- Hypotheses (PROPOSED, need Fran's confirmation before freezing):
  - O1 (transfer): C3 gain over C1 on BIRD dev >= 2 pp with lower CI bound > 0.
  - O2 (no harm): lower CI bound of the C3 minus C1 difference >= -2 pp.
- Contamination probe: report C1 accuracy on Spider dev vs BIRD dev. A large gap is evidence of exposure to Spider-style data, noted as a limitation, not corrected.

## 9. Error analysis

- Performed on Spider dev failures only (never on test).
- Sample 100 failures of C1 and 100 of C3 (size M, seed 0), seeded random sample, labeled manually into: wrong join, wrong aggregation, hallucinated column/table, syntax error, wrong filter/value, other. Taxonomy fixed before labeling.

## 10. Non-goals

3B+ models, Qwen3, base-vs-instruct comparison, 4-bit QLoRA, DPO/RL, schema linking, value linking, retrieval, sample-row and schema-format ablations (candidate follow-ups after the main results), training on BIRD, production deployment.

## 11. Review points (SPEC may change here, each change logged)

1. After baselines (B0a, B0b, C1, C2) on validation and dev: feasibility and sanity.
2. After the tuning runs: frozen config.
3. Before the first test run: freeze check.
4. Before BIRD: confirm O1/O2 thresholds and verify the BIRD license.

## 12. Deliverables

- Repo `spider-sql-lora-ladder` (code MIT, no data). Layout per Working Agreement.
- Results tables in `results/`; README written last, only from results.
- LoRA adapters with model card on Hugging Face. Publication is held until the CC BY-SA ShareAlike question for adapters is decided (docs/DECISIONS.md).
- Short failure-analysis write-up.

## 13. Environment

- Python 3.13.15 pinned in `.python-version` (verify against Colab).
- Compute: free Colab T4, budget 0. Interrupted runs are rerun. Time per epoch for S is measured first; M gets 3 seeds only if the measured time allows, otherwise M is exploratory.

## 14. Open items

- [x] Model license recorded for S (Apache-2.0)
- [x] Model license recorded for M (Apache-2.0)
- [x] Test-suite databases: coverage checked (dev yes, test no)
- [x] Decide metric/split for confirmatory evaluation (A: EX on test)
- [x] Comparison code runs on Python 3.13.15 and agrees with upstream (370 comparisons)
- [x] keep_distinct secondary metric approved (7.1)
- [ ] BIRD license and download verified
- [ ] BIRD hypotheses O1/O2 confirmed by Fran
- [x] Colab Python version matches 3.13.15
- [x] SPEC agreed by Fran (date: 2026-10-15)
