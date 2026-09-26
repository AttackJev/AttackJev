# Generation and evaluation code

These are the scripts that produced release `beta1.0-20260925`, kept exactly as they were run so that
the request hashes in `evidence/` stay verifiable. They were written inside the authors' research
workspace: paths such as `exports/`, `research/ref1.2/` and the prompt file name refer to that layout,
and some report headers are in Chinese. You do **not** need them to reproduce the paper; the offline
analysis in [`../data_analysis`](../data_analysis) works from the released responses alone.

| Script | Role |
|---|---|
| `generate_adbeta.py` | Generator: one reversible edit per question for each of the 12 attacks (templates in paper Appendix C) |
| `query_rewrite_v2.py`, `query_sentence_bank.py` | Lexicon and sentence banks for word edits (Q1) and paraphrasing (Q2) |
| `analogy_cases_v2.py` | The 66 hand-written hypothetical analogies used by opinion via analogy (T3) |
| `generate_corrected_attacks.py`, `regenerate_adbeta.py` | Fresh generation of the released variant set with a recorded seed |
| `finalize_corrected_attacks.py` | Structural checks and receipt for the generated set |
| `eval_adbeta_jev.py` | Evaluator: sends one question per request to `jev-1.13.0`, records responses, billing and request hashes |
| `eval_corrected_attacks.py` | Evaluation run of the 10,556 clean and attacked requests |
| `eval_clean_repeat.py` | The 812 identical re-runs that give the noise floor |
| `report_corrected_attacks.py` | Legacy strict-label report (superseded by `../data_analysis`) |
| `run.py` | Reads the API key from `TYPESAFE_API_KEY`; nothing is stored |

The perturbation specification the generator follows is [`../spec/perturbation_prompt_en.md`](../spec/perturbation_prompt_en.md)
(named `扰动生成prompt-en.md` in the original workspace). Dependencies: `pip install -r requirements.txt`.

A fresh run calls the paid API (about $0.41 at the listed price for all 11,368 requests) and will not
reproduce the released answers byte for byte, because the hosted model is not deterministic; the
noise floor in the paper quantifies how much identical requests vary.
