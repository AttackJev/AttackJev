---
license: cc-by-nc-4.0
language:
- en
pretty_name: JevAdvBench
size_categories:
- 10K<n<100K
task_categories:
- text-classification
tags:
- adversarial-robustness
- prompt-injection
- benchmark
- calibrated-decisions
- typed-decisions
configs:
- config_name: clean
  data_files:
  - split: test
    path: data/clean.jsonl
- config_name: attacks
  data_files:
  - split: test
    path: data/attacks.jsonl
- config_name: responses
  data_files:
  - split: test
    path: jev/responses.jsonl
---

# JevAdvBench

[Project page](https://jevadvbench.github.io/JevAdvBench/) · [Code](https://github.com/JevAdvBench/JevAdvBench)

**JevAdvBench** is, to our knowledge, the first adversarial benchmark for models trained with reinforcement
learning for calibrated decisions (RLCD), such as Jev. These models answer a typed question about an input,
the *state*, with a probability (Noul), a choice (Choice) or a score (Score), and software acts on the answer
without a person reading it.

The benchmark has **812 typed questions** over **66 scenarios** and a black-box attack suite of
**9,744 single-edit variants** (12 attacks × 812 questions). It also releases all **11,368 answers** of
`jev-1.13.0`: the clean run, an identical re-run that gives the noise floor, and every attacked request.
On `jev-1.13.0`, one unverified opinion appended to the state flips 12.1% of decisions, statistically tied with
the strongest injected command (10.1%).

## Configs

```python
from datasets import load_dataset

clean     = load_dataset("Hangtao/JevAdvBench", "clean", split="test")      # 812 questions
attacks   = load_dataset("Hangtao/JevAdvBench", "attacks", split="test")    # 9,744 variants
responses = load_dataset("Hangtao/JevAdvBench", "responses", split="test")  # 11,368 Jev answers
```

Nested values (`state`, `label`, `target_answer`, `answer`, `decision`) are JSON strings; parse them with
`json.loads`. `question` is the raw JSON text of the typed question exactly as sent to the API.

### `clean`

| Field | Description |
|---|---|
| `scenario_id`, `question_id` | Identifiers; questions in a scenario share one state |
| `type` | `noul`, `choice` or `score` |
| `state` | The content under evaluation (string or JSON object) |
| `question` | The typed question: `type`, `instructions`, `criteria` |
| `label_kind`, `label` | `exact` value or inclusive `interval` |
| `label_source` | `human_review` (143) or `jev_default` (669, the model's own five-run consensus) |

### `attacks`

| Field | Description |
|---|---|
| `attack_id`, `attack`, `family` | Q1–Q3 Question, T1–T3 State, P1–P3 Injection, S1–S3 Structure (delivery control) |
| `method` | Generator sub-method |
| `target_path` | The edited slot, e.g. `state.supplementary_text`, `question.instructions` |
| `injected_text` | The inserted text, where the edit inserts one |
| `target_answer` | The answer a targeted attack names (T2, T3, P1–P3) |
| `state`, `question` | The full edited request |

### `responses`

| Field | Description |
|---|---|
| `request` | `clean`, `rerun` (identical second call) or `attack` |
| `attack_id` | Set for attacked requests |
| `answer` | The API answer: `noul`; or `choice`/`score` with `probabilities` and `confidence` |
| `decision` | Benchmark decision: P(true) ≥ 0.5, the returned option, or the most likely level |
| `flipped` | Whether the decision differs from the clean decision on the same question |
| `input_tokens` | Billed input tokens; an edit that adds characters at +0 tokens was not delivered |

`raw/` holds the original nested files `beta1.0.json` and `ADbeta1.0.json`. `SHA256SUMS` lists every file's hash.

## Attacks

| Family | ID | Attack | Slot | Flip rate |
|---|---|---|---|---:|
| — | — | Identical re-run (noise floor) | — | 1.0% |
| Question | Q1 | Word/spacing edits | instructions / criteria | 1.0% |
| | Q2 | Paraphrasing | instructions / criteria | 1.5% |
| | Q3 | Unrelated sentences | instructions / criteria | 4.6% |
| State | T1 | Unrelated state note | state | 2.2% |
| | T2 | Observer opinion | state | 12.1% |
| | T3 | Opinion via analogy | state | 6.9% |
| Injection | P1 | Direct override | one question string | 8.9% |
| | P2 | Authority impersonation | one question string | 10.1% |
| | P3 | Fake validation note | one question string | 8.1% |
| Structure | S1 | Unrelated extra field | extra question key | 1.2% (not delivered) |
| | S2 | Escaped field names | key names | 0.9% (no-op) |
| | S3 | Opinion in extra field | extra question key | 0.7% (not delivered) |

The offline analysis in the [GitHub repository](https://github.com/JevAdvBench/JevAdvBench) regenerates every
table in the paper from these files.

## Intended use and limitations

JevAdvBench is for measuring and improving the robustness of typed decision models. It is dual-use: the fixed
templates that measure how far a decision can be steered can also be used to steer one. All results are for
one model version, `jev-1.13.0`, queried on 2026-09-25. Most labels (82.4%) are the model's own consensus
answers, which is why the primary metric compares each attacked decision with the model's own clean decision.
The variants are designed, not verified, to preserve the correct answer. Some label-review notes are in Chinese.

## License

Our questions, labels, attack variants, Jev outputs and metadata are released under
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Scenarios derived from the vendor's published
examples keep their original terms. Code in the GitHub repository is MIT.

## Citation

```bibtex
@misc{hu2026jevadvbench,
      title={JevAdvBench: A Benchmark and Black-Box Attacks for Reinforcement Learning for Calibrated Decisions Models},
      author={Jianyi Hu and Hangtao Zhang and Yi Liu and Yeqi Zeng and Li Zeng and Xianlong Wang and Rui Wang and Leo Yu Zhang},
      year={2026},
      note={Preprint}
}
```
