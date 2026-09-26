"""Build the Hugging Face dataset release (huggingface.co/datasets/Hangtao/JevAdvBench).

Offline, standard library only. Needs the restored evidence:
  python evidence/restore_and_verify.py
  python tools/build_hf.py --out hf
  huggingface-cli upload Hangtao/JevAdvBench hf . --repo-type dataset

Every row stores nested fields (state, question, answers) as JSON strings so that the
three configs have a fixed schema for the dataset viewer and `datasets.load_dataset`.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_analysis"))
from common import NAMES, FAMILY, load, decision, flipped  # noqa: E402


def js(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "hf")
    out = ap.parse_args().out
    if out.exists():
        shutil.rmtree(out)

    data = json.loads((ROOT / "data" / "ADbeta1.0.json").read_text(encoding="utf-8"))
    clean_rows, attack_rows = [], []
    for sc in data["scenarios"]:
        for qtype, qs in sc["questions"].items():
            for q in qs:
                ad = q["adversarial"]
                lab = q["standard_answer"]
                clean_rows.append({
                    "scenario_id": sc["scenario_id"], "question_id": q["question_id"], "type": qtype,
                    "state": js(sc["state"]), "question": ad["original_question_text"],
                    "label_kind": lab["kind"], "label": js(lab["value"]), "label_source": lab["source"],
                })
                for v in ad["samples"]:
                    attack_rows.append({
                        "scenario_id": sc["scenario_id"], "question_id": q["question_id"], "type": qtype,
                        "attack_id": v["id"], "attack": NAMES[v["id"]], "family": FAMILY[v["id"]],
                        "method": v["method"], "target_path": v["target_path"],
                        "injected_text": v["injected_text"],
                        "target_answer": None if v["target_answer"] is None else js(v["target_answer"]),
                        "state": js(v["perturbed_state"]), "question": v["perturbed_question_text"],
                    })

    Q = load()
    resp_rows = []
    for q in Q.values():
        base = {"scenario_id": q["scenario"], "question_id": q["qid"], "type": q["type"]}
        resp_rows.append({**base, "request": "clean", "attack_id": None, "answer": js(q["clean"]),
                          "decision": js(decision(q["clean"])), "flipped": None, "input_tokens": q["clean_tokens"]})
        resp_rows.append({**base, "request": "rerun", "attack_id": None, "answer": js(q["rerun"]),
                          "decision": js(decision(q["rerun"])), "flipped": flipped(q["clean"], q["rerun"]),
                          "input_tokens": q["rerun_tokens"]})
        for a, rec in sorted(q["attacks"].items()):
            resp_rows.append({**base, "request": "attack", "attack_id": a, "answer": js(rec["ans"]),
                              "decision": js(decision(rec["ans"])), "flipped": flipped(q["clean"], rec["ans"]),
                              "input_tokens": rec["tokens"]})

    n = {
        "clean": write_jsonl(out / "data" / "clean.jsonl", clean_rows),
        "attacks": write_jsonl(out / "data" / "attacks.jsonl", attack_rows),
        "responses": write_jsonl(out / "jev" / "responses.jsonl", resp_rows),
    }
    assert n == {"clean": 812, "attacks": 9744, "responses": 11368}, n
    (out / "raw").mkdir()
    for f in ("beta1.0.json", "ADbeta1.0.json"):
        shutil.copy2(ROOT / "data" / f, out / "raw" / f)
    shutil.copy2(ROOT / "tools" / "hf_card.md", out / "README.md")
    manifest = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(out.rglob("*")) if p.is_file() and p.name != "SHA256SUMS"}
    (out / "SHA256SUMS").write_text("".join(f"{h}  {k}\n" for k, h in manifest.items()))
    print(json.dumps({"out": str(out), **n}, indent=1))


if __name__ == "__main__":
    main()
