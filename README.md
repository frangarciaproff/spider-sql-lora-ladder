# Teaching small AI models to write SQL

[![CI](https://github.com/frangarciaproff/spider-sql-lora-ladder/actions/workflows/ci.yml/badge.svg)](https://github.com/frangarciaproff/spider-sql-lora-ladder/actions/workflows/ci.yml)

You ask a database a question in plain English, for example *"How many singers are older than 30?"*, and an AI model writes the query that answers it: `SELECT count(*) FROM singer WHERE age > 30`. Small open models can do this, but they make many mistakes.

This project asks three questions. Does a little extra training (fine-tuning) make small models better at it? By how much? And does the improvement carry over to databases the model has never seen?


## In short

- **Fine-tuning works.** The smaller model answers 63% of test questions correctly instead of 48%. The larger one answers 75% instead of 66%.
- **What it learned is to stop inventing things.** Before fine-tuning, the model often used columns or tables that do not exist. That kind of mistake fell from 16% to 6% of questions. Mistakes in the logic of the query did not decrease.
- **Size still matters more.** The larger model without any training beats the smaller model with training.
- **Showing examples in the prompt did not help.** Giving the model three solved examples changed nothing for the smaller model and made the larger one worse.
- **On a harder, different benchmark the gain shrinks.** The smaller model still improves by 5.5 points. For the larger model the improvement (2.7 points) is too uncertain to count.
- **Everything ran on a free cloud GPU.** Training one model takes 30 to 90 minutes.

## What was tested

Two open models from the same family, Qwen2.5-Coder, with 0.5 and 1.5 billion parameters. Each was used in three ways:

- **Zero-shot:** the model sees only the database structure and the question.
- **Three examples:** the same, plus three solved questions in the prompt.
- **Fine-tuned:** the model is trained on about 8,000 example questions with LoRA, a cheap method that trains a small add-on instead of the whole model.

Two benchmarks:

- **Spider:** questions over about 200 databases. The test set uses 40 databases the model never saw during training.
- **BIRD:** a harder benchmark with larger, messier databases, used only for testing, never for training.

## The goals, set before running anything

| Goal | Result | Met? |
|---|---|---|
| Smaller model gains at least 5 points on Spider | +15.2 points | yes |
| Larger model gains at least 3 points on Spider | +9.0 points | yes |
| Smaller model's gain carries over to BIRD (at least 2 points, reliably above zero) | +5.5 points | yes |
| Larger model's gain carries over to BIRD | +2.7 points, could be zero | **no** |
| Fine-tuning does not make either model worse on BIRD | no meaningful loss | yes |

"Points" are percentage points of questions answered correctly. "Reliably" means the 95% uncertainty interval stays above zero.

## Why the results can be trusted

- **The goals and thresholds were written down first,** in [SPEC.md](SPEC.md), before any model was run. They were not adjusted afterwards.
- **The final test set was used once.** All tuning happened on separate data.
- **Each fine-tuning was repeated three times** with different random starts, and every result comes with an uncertainty interval.
- **Every change, failed run and disappointing result is logged** in [DECISIONS.md](docs/DECISIONS.md), including the goal that was not met.
- **200 mistakes were checked by hand,** without knowing which model made them.

## What the mistakes look like

Checking 200 wrong answers by hand showed three things:

- **Fine-tuning mostly stopped the model from inventing columns and tables.** That one change explains the whole improvement.
- **Logic errors stayed the same.** Wrong joins between tables, wrong filters and wrong counts are as common after training as before.
- **Some "wrong" answers are not wrong.** In 12 of 100 checked failures of the fine-tuned model, the answer is reasonable but differs from the benchmark's reference answer: for example, listing each player separately instead of merging everyone called Anna. As models get better, more of what counts as an error is disagreement with the benchmark.

## More

- **Full results, methods, statistics and how to reproduce:** [docs/TECHNICAL.md](docs/TECHNICAL.md)
- **The plan as agreed before running:** [SPEC.md](SPEC.md)
- **Every decision and change:** [docs/DECISIONS.md](docs/DECISIONS.md)

Data: Spider (Yu et al. 2018) and BIRD (Li et al. 2023), both CC BY-SA 4.0, not redistributed. Models: Qwen2.5-Coder (Hui et al. 2024), Apache-2.0. Code: MIT. Full citations in the technical report.

Built with AI assistance (Claude) for code and documentation. The experimental design, decisions, runs and manual labels are the author's.

Author: Francisco J. García Soriano
