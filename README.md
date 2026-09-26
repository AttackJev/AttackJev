# JevAdvBench: A Benchmark and Black-Box Attacks for Reinforcement Learning for Calibrated Decisions Models

[![Project page](https://img.shields.io/badge/Project-page-green)](https://jevadvbench.github.io/JevAdvBench/)
[![arXiv](https://img.shields.io/badge/arXiv-coming%20soon-b31b1b)](#citation)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Dataset-JevAdvBench-yellow)](https://huggingface.co/datasets/Hangtao/JevAdvBench)
[![Code license: MIT](https://img.shields.io/badge/code-MIT-lightgrey)](LICENSE)
[![Data license: CC BY-NC 4.0](https://img.shields.io/badge/data-CC%20BY--NC%204.0-lightgrey)](https://creativecommons.org/licenses/by-nc/4.0/)

This repository holds **JevAdvBench** and the code behind the paper.
Models trained with reinforcement learning for calibrated decisions (RLCD), such as Jev, answer a typed question about an input, the *state*, with a probability (Noul), a choice (Choice) or a score (Score), and software acts on the answer without a person reading it.
JevAdvBench is, to our knowledge, the first adversarial benchmark for such models: **812 typed questions** over **66 scenarios** and a black-box attack suite of **9,744 single-edit variants**, each editing one part of a request, with billed input tokens confirming that the edit reached the model.

The key idea is to score each attacked decision against the model's **own clean decision** rather than against labels, and to read it against the change caused by an **identical re-run**.
On `jev-1.13.0`, rewording stays within 1.2 percentage points of the re-run baseline, and fields outside the schema never reach the model.
In contrast, one unverified opinion appended to the state flips 12.1% of decisions, statistically tied with the strongest injected command (10.1%), and pushes 38% of confident answers below the 0.8 confidence threshold that routes them to human review.

<p align="center"><img src="figs/fig1_overview.png" width="92%" alt="JevAdvBench overview: attack surfaces and decision flips"></p>

## Citation

```bibtex
@misc{hu2026jevadvbench,
      title={JevAdvBench: A Benchmark and Black-Box Attacks for Reinforcement Learning for Calibrated Decisions Models},
      author={Jianyi Hu and Hangtao Zhang and Yi Liu and Yeqi Zeng and Li Zeng and Xianlong Wang and Rui Wang and Leo Yu Zhang},
      year={2026},
      note={Preprint}
}
```

## Data

Everything is in this repository, and the same data is on Hugging Face at [`Hangtao/JevAdvBench`](https://huggingface.co/datasets/Hangtao/JevAdvBench) in three flat configs:

```python
from datasets import load_dataset

clean     = load_dataset("Hangtao/JevAdvBench", "clean", split="test")      # 812 questions
attacks   = load_dataset("Hangtao/JevAdvBench", "attacks", split="test")    # 9,744 variants
responses = load_dataset("Hangtao/JevAdvBench", "responses", split="test")  # 11,368 Jev answers
```

[`tools/build_hf.py`](tools/build_hf.py) builds that release from the files below.

| File | Contents |
|---|---|
| [`data/beta1.0.json`](data/beta1.0.json) | The clean benchmark: 66 scenarios, 812 questions (314 Noul, 337 Choice, 161 Score) with labels and their provenance |
| [`data/ADbeta1.0.json`](data/ADbeta1.0.json) | The attack suite: for every question, the 12 single-edit variants (9,744 in total) with the edited slot, inserted text, attack target and generation metadata |
| [`evidence/`](evidence) | All 11,368 raw API responses (10,556 evaluation requests and 812 identical re-runs) with billing, timing and the SHA-256 of every request body, as a split, checksummed archive |

Both JSON files follow `scenarios → questions → {noul, choice, score} → [question]`.
Each question has a `question` (the typed request: `type`, `instructions`, `criteria`), a `standard_answer` with its `source` (`human_review` for 143 questions, `jev_default` for the 669 whose label is the model's own five-run consensus) and, in ADbeta1.0, an `adversarial.samples` list with one record per attack (`id`, `target_path`, `injected_text`, `target_answer`, `perturbed_question_text`, `perturbed_state`, ...).
Because 82.4% of labels are model-derived, the paper's primary metric does not use labels at all.

| Domain | Scenarios | Questions | Noul | Choice | Score | Human-reviewed |
|---|---:|---:|---:|---:|---:|---:|
| Customer-support triage | 21 | 212 | 84 | 85 | 43 | 45 |
| Information extraction and document parsing | 10 | 185 | 58 | 107 | 20 | 33 |
| Finance-assistant command parsing | 13 | 130 | 52 | 52 | 26 | 5 |
| Classification and entity judgment | 6 | 96 | 33 | 24 | 39 | 17 |
| Grounding, citation and policy QA | 5 | 55 | 24 | 20 | 11 | 1 |
| Agent and tool-use verification | 4 | 47 | 22 | 17 | 8 | 2 |
| Safety and security moderation | 4 | 47 | 19 | 20 | 8 | 20 |
| Claims and hiring decisions | 3 | 40 | 22 | 12 | 6 | 20 |
| **Total** | **66** | **812** | **314** | **337** | **161** | **143** |

### Attacks

Each variant applies exactly one reversible edit to the clean request. Templates are fixed and shared by all scenarios; no attack uses gradients, search or repeated queries.

| Family | ID | Attack | Slot edited | Targeted |
|---|---|---|---|:---:|
| Question | Q1 | Word/spacing edits | `instructions` / `criteria` | |
| | Q2 | Paraphrasing | `instructions` / `criteria` | |
| | Q3 | Unrelated sentences | `instructions` / `criteria` | |
| State | T1 | Unrelated state note | `state` | |
| | T2 | Observer opinion | `state` | ✓ |
| | T3 | Opinion via analogy | `state` | ✓ |
| Injection | P1 | Direct override | one question string | ✓ |
| | P2 | Authority impersonation | one question string | ✓ |
| | P3 | Fake validation note | one question string | ✓ |
| Structure (delivery control) | S1 | Unrelated extra field | extra question key | |
| | S2 | Escaped field names | key names | |
| | S3 | Opinion in extra field | extra question key | ✓ |

[`results/twelve-method-example.json`](results/twelve-method-example.json) shows all twelve edits on one question; the [project page](https://jevadvbench.github.io/JevAdvBench/#attacks) lets you step through them.

## Code

| Component | Location |
|---|---|
| Offline analysis: flips, noise floor, bootstrap CIs, tests, delivery, targeting, shifts, confidence gate, human labels | [`data_analysis/`](data_analysis) |
| One command that regenerates every table and checks it against the paper | [`data_analysis/run_all.sh`](data_analysis/run_all.sh) |
| Evidence restore and checksum verification | [`evidence/restore_and_verify.py`](evidence/restore_and_verify.py) |
| Attack generator and API evaluator used for the run | [`code/`](code) ([details](code/README.md)) |
| Perturbation specification | [`spec/perturbation_prompt_en.md`](spec/perturbation_prompt_en.md) |

The analysis needs Python 3.10 or newer and only the standard library.

### Reproduce the paper's numbers offline

This sends no requests and needs no key. Every number is recomputed from the released responses.

```bash
git clone https://github.com/JevAdvBench/JevAdvBench && cd JevAdvBench
bash data_analysis/run_all.sh
```

The script restores and verifies the 11,737 evidence files, writes the tables below to [`results/`](results) and compares 256 reported values with the paper:

```
256/256 values match the paper (24 bootstrap CI endpoints differ by <= 0.5 pp).
```

Point estimates, counts and test outcomes match exactly. Bootstrap confidence-interval endpoints can differ by a few tenths of a point from the printed ones because the resampling stream differs (66 scenario clusters, 2,000 resamples, seed 0).

| Output | Paper |
|---|---|
| [`flip_rates.csv`](results/flip_rates.csv) | Flip rates by attack and primitive with 95% scenario-cluster CIs (Table 17, Figure 1c) |
| [`excess_tests.csv`](results/excess_tests.csv) | Excess over the identical re-run, sign-flip permutation and McNemar tests with Holm correction (Tables 2, 18) |
| [`union.csv`](results/union.csv) | Questions flipped by at least one attack in each set (Table 19) |
| [`delivery.csv`](results/delivery.csv) | Added characters and billed-token increase per attack (Table 1) |
| [`injection_slot.csv`](results/injection_slot.csv) | Commands in `instructions` vs `criteria` (Figure 3) |
| [`target_hit.csv`](results/target_hit.csv), [`shift.csv`](results/shift.csv) | Target hits and shifts without a flip (Figure 4a, 4b) |
| [`confidence_gate.csv`](results/confidence_gate.csv) | Confident answers pushed below the 0.8 gate (Figure 4c) |
| [`human_label_accuracy.csv`](results/human_label_accuracy.csv) | Consistency with the 143 human-reviewed labels (Table 3) |
| [`headline.json`](results/headline.json), [`paper_check.json`](results/paper_check.json) | Scalars quoted in the text and the full comparison with the paper |

### Rerun against the API

```bash
pip install -r code/requirements.txt
export TYPESAFE_API_KEY=...        # never written to disk
```

The scripts in [`code/`](code) regenerate the attack variants and query `jev-1.13.0` one question per request; see [`code/README.md`](code/README.md) for the workspace layout they expect. A fresh run reproduces the protocol, not the exact answers, since the hosted model is not deterministic.

## Repository structure

```
JevAdvBench/
├── data/
│   ├── beta1.0.json         812 clean typed questions over 66 scenarios
│   └── ADbeta1.0.json       9,744 single-edit attack variants
├── evidence/                11,368 raw responses (split archive) + restore/verify script
├── data_analysis/           offline analysis; run_all.sh regenerates results/
├── results/                 paper-level tables and the comparison with the paper
├── code/                    attack generator and API evaluator used for the run
├── spec/                    perturbation specification
├── figs/                    paper figures
├── tools/                   Hugging Face release builder and dataset card
└── docs/                    project page (GitHub Pages)
```

## Ethics

JevAdvBench is dual-use: the templates that measure how far a typed decision can be steered can also be used to steer one.
We release them because the attacks are cheap, fixed texts of the kind a user can already write into a ticket or a post, and because a builder needs the same templates, together with the delivery check and the confidence-gate measurements, to test a deployment before an attacker does.
All requests went to the public API of `jev-1.13.0`; we attacked no third-party deployment and collected no personal data.
The scenarios are the vendor's published examples, extended with questions we wrote.

## License

Code: [MIT](LICENSE). Data: our questions, labels, attack variants, Jev outputs and metadata are under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Scenarios derived from the vendor's published examples keep their original terms.
