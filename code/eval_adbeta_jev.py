#!/usr/bin/env python3
"""Run ADbeta1.0 through the pinned Jev API and score against adopted labels.

The S2 question is inserted into the HTTP JSON body as raw text so its Unicode
escapes reach the endpoint. Credentials are loaded privately by the existing
ref1.2 runner and are never written to output files.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import datetime as dt
import hashlib
import importlib.util
import json
import math
import pathlib
import random
import threading
import time
import urllib.error
import urllib.request


HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "exports/ADbeta1.0.json"
OUT = HERE / "exports/ADbeta1.0-jev-eval"
RESPONSES = OUT / "responses"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"  # Pin to the model used for the beta1.0 baseline.
MAX_QUESTIONS = 20
MAX_QUESTION_BYTES = 60_000
WORKERS = 6
RETRYABLE = {429, 500, 502, 503, 504, 529}
STOP = threading.Event()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_json(path: pathlib.Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def credential() -> str:
    spec = importlib.util.spec_from_file_location("ref12_run", HERE / "run.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.credential()


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def load_items():
    source_bytes = SOURCE.read_bytes()
    dataset = json.loads(source_bytes)
    items = []
    groups = collections.OrderedDict()
    for scenario in dataset["scenarios"]:
        sid = scenario["scenario_id"]
        state = scenario["state"]
        for records in scenario["questions"].values():
            for record in records:
                qid = record["question_id"]
                pkg = record["adversarial"]
                assert len(pkg["samples"]) == 12
                entries = [("clean", pkg["original_question_text"], state, None)]
                entries.extend((sample["id"], sample["perturbed_question_text"],
                                sample["perturbed_state"], sample["method"])
                               for sample in pkg["samples"])
                for category, raw_question, actual_state, method in entries:
                    if category != "clean":
                        sample = next(s for s in pkg["samples"] if s["id"] == category)
                        assert sample["status"] == "candidate"
                    question = json.loads(raw_question)
                    assert question["type"] == record["question_type"]
                    item_id = f"i{len(items):05d}"
                    items.append({"item_id": item_id, "scenario_id": sid,
                                  "question_id": qid, "category": category,
                                  "type": record["question_type"], "method": method,
                                  "label": record["standard_answer"]})
                    state_text = compact(actual_state)
                    state_hash = digest(state_text.encode())
                    group_key = (sid, state_hash)
                    if group_key not in groups:
                        groups[group_key] = {"state": actual_state, "items": []}
                    groups[group_key]["items"].append((item_id, raw_question))
    assert len(items) == 812 * 13
    assert sum(i["category"] == "clean" for i in items) == 812
    assert sum(i["category"] != "clean" for i in items) == 812 * 12
    return dataset, digest(source_bytes), items, groups


def chunks(group):
    current = []
    nbytes = 0
    for item_id, raw in group["items"]:
        raw_bytes = len(raw.encode())
        if current and (len(current) >= MAX_QUESTIONS or nbytes + raw_bytes > MAX_QUESTION_BYTES):
            yield current
            current, nbytes = [], 0
        current.append((item_id, raw))
        nbytes += raw_bytes
    if current:
        yield current


def build_jobs(groups):
    jobs = []
    for (scenario_id, state_hash), group in groups.items():
        for part in chunks(group):
            jobs.append({"job_id": f"job-{len(jobs):05d}", "scenario_id": scenario_id,
                         "state_hash": state_hash, "state": group["state"], "items": part})
    return jobs


def request_bytes(state, items):
    # Do not parse and reserialize raw questions: doing so removes S2 escapes.
    body = ('{"model":' + compact(MODEL) + ',"state":' + compact(state)
            + ',"questions":{' + ','.join(compact(item_id) + ':' + raw for item_id, raw in items)
            + '}}')
    parsed = json.loads(body)
    assert set(parsed["questions"]) == {item_id for item_id, _ in items}
    return body.encode("utf-8")


def one_request(body: bytes, key: str):
    request = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)
        request_id = response.headers.get("x-request-id")
    return result, request_id, time.monotonic() - start


def evaluate_part(state, items, key: str, depth: int = 0):
    body = request_bytes(state, items)
    expected = {item_id for item_id, _ in items}
    last = None
    for attempt in range(1, 8):
        if STOP.is_set():
            raise RuntimeError("Evaluation stopped after an authentication or billing error")
        try:
            answer, request_id, elapsed = one_request(body, key)
            if answer.get("model") != MODEL or set(answer.get("answers", {})) != expected:
                raise ValueError("Resolved model or returned answer IDs differ from the request")
            for item_id, raw in items:
                if answer["answers"][item_id].get("type") != json.loads(raw)["type"]:
                    raise ValueError("Returned question type differs from the request")
            return {"answers": answer["answers"], "model": answer["model"],
                    "usage": answer.get("usage", {}), "request_ids": [request_id],
                    "http_calls": 1, "elapsed_seconds": elapsed}
        except urllib.error.HTTPError as exc:
            status = exc.code
            detail = exc.read().decode("utf-8", errors="replace")[:500].replace(key, "[REDACTED]")
            last = f"HTTP {status}: {detail}"
            if status in {401, 402, 403}:
                STOP.set()
                raise RuntimeError(f"API authentication/billing error: HTTP {status}") from None
            if status in {413, 422} and len(items) > 1 and depth < 8:
                mid = len(items) // 2
                left = evaluate_part(state, items[:mid], key, depth + 1)
                right = evaluate_part(state, items[mid:], key, depth + 1)
                usage = {k: left["usage"].get(k, 0) + right["usage"].get(k, 0)
                         for k in set(left["usage"]) | set(right["usage"])}
                return {"answers": {**left["answers"], **right["answers"]},
                        "model": MODEL, "usage": usage,
                        "request_ids": left["request_ids"] + right["request_ids"],
                        "http_calls": left["http_calls"] + right["http_calls"],
                        "elapsed_seconds": left["elapsed_seconds"] + right["elapsed_seconds"]}
            if status not in RETRYABLE:
                break
            retry_after = exc.headers.get("Retry-After")
            try:
                delay = min(float(retry_after), 60.0) if retry_after else min(2 ** attempt, 30)
            except ValueError:
                delay = min(2 ** attempt, 30)
        except Exception as exc:
            last = f"{type(exc).__name__}: {str(exc)[:500]}".replace(key, "[REDACTED]")
            delay = min(2 ** attempt, 30)
        if attempt < 7:
            time.sleep(delay + random.random())
    raise RuntimeError(last or "Unknown API error")


def job_file(job):
    return RESPONSES / (job["job_id"] + ".json")


def run_job(job, key):
    body = request_bytes(job["state"], job["items"])
    body_sha = digest(body)
    path = job_file(job)
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("body_sha256") != body_sha:
            raise RuntimeError(f"Checkpoint payload mismatch: {job['job_id']}")
        if old.get("status") == "ok":
            return old, True
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        response = evaluate_part(job["state"], job["items"], key)
        result = {"job_id": job["job_id"], "body_sha256": body_sha,
                  "item_ids": [item_id for item_id, _ in job["items"]],
                  "status": "ok", "started_at": started_at,
                  "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(), **response}
    except Exception as exc:
        result = {"job_id": job["job_id"], "body_sha256": body_sha,
                  "item_ids": [item_id for item_id, _ in job["items"]],
                  "status": "error", "started_at": started_at,
                  "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "error": f"{type(exc).__name__}: {exc}".replace(key, "[REDACTED]")}
    atomic_json(path, result)
    return result, False


def score(item, answer):
    typ = item["type"]
    label = item["label"]
    value = label["value"]
    if typ == "noul":
        measured = answer["noul"]
        assert 0 <= measured <= 1
        strict = (value["lower"] <= measured <= value["upper"]) if label["kind"] == "interval" else ((measured >= 0.5) is value)
        supplemental = strict
    elif typ == "choice":
        measured = answer["choice"]
        strict = measured == value
        supplemental = strict
    else:
        measured = answer["score"]
        assert isinstance(measured, (float, int)) and math.isfinite(measured)
        if label["kind"] == "interval":
            strict = value["lower"] <= measured <= value["upper"]
            supplemental = strict
        else:
            strict = math.isclose(measured, value, rel_tol=0, abs_tol=1e-9)
            supplemental = abs(measured - value) <= 0.25 + 1e-9
    return measured, bool(strict), bool(supplemental)


def rate(rows):
    total = len(rows)
    errors = sum(not row["strict_correct"] for row in rows)
    sensitivity_errors = sum(not row["score_tolerance_0_25_correct"] for row in rows)
    return {"answered": total, "strict_errors": errors,
            "strict_error_rate": errors / total if total else None,
            "score_tolerance_0_25_errors": sensitivity_errors,
            "score_tolerance_0_25_error_rate": sensitivity_errors / total if total else None}


def summarize(items, jobs):
    by_item = {item["item_id"]: item for item in items}
    rows = []
    failures = []
    models = set()
    usage = collections.Counter()
    for job in jobs:
        path = job_file(job)
        if not path.exists():
            failures.append({"job_id": job["job_id"], "reason": "missing"})
            continue
        result = json.loads(path.read_text(encoding="utf-8"))
        if result["status"] != "ok":
            failures.append({"job_id": job["job_id"], "reason": result.get("error", "error")})
            continue
        models.add(result["model"])
        usage.update(result.get("usage", {}))
        for item_id, answer in result["answers"].items():
            item = by_item[item_id]
            measured, strict, supplemental = score(item, answer)
            rows.append({"item_id": item_id, "scenario_id": item["scenario_id"],
                         "question_id": item["question_id"], "category": item["category"],
                         "type": item["type"], "method": item["method"],
                         "answer_kind": item["label"]["kind"],
                         "label_value": item["label"]["value"],
                         "label_source": item["label"]["source"],
                         "jev_answer": answer, "measured_value": measured,
                         "strict_correct": strict,
                         "score_tolerance_0_25_correct": supplemental,
                         "response_job_id": job["job_id"]})
    rows.sort(key=lambda row: int(row["item_id"][1:]))
    by_id = {row["item_id"]: row for row in rows}
    by_category = {category: rate([row for row in rows if row["category"] == category])
                   for category in ["clean", "Q1", "Q2", "Q3", "S1", "S2", "S3", "T1", "T2", "T3", "P1", "P2", "P3"]}
    adversarial = [row for row in rows if row["category"] != "clean"]
    clean = {row["question_id"]: row for row in rows if row["category"] == "clean"}
    new_errors = {}
    for category in by_category:
        if category == "clean":
            continue
        paired = [(clean[row["question_id"]], row)
                  for row in rows if row["category"] == category and row["question_id"] in clean]
        eligible = [(baseline, attack) for baseline, attack in paired if baseline["strict_correct"]]
        introduced = sum(not attack["strict_correct"] for _, attack in eligible)
        new_errors[category] = {"baseline_correct_count": len(eligible),
                                "new_errors": introduced,
                                "new_error_rate": introduced / len(eligible) if eligible else None}
    summary = {"dataset": "ADbeta1.0", "source_sha256": digest(SOURCE.read_bytes()),
               "model_requested": MODEL, "models_returned": sorted(models),
               "expected_adversarial_answers": 9744, "adversarial_answers": len(adversarial),
               "expected_clean_answers": 812, "clean_answers": len(clean),
               "complete": len(adversarial) == 9744 and len(clean) == 812 and not failures,
               "jobs": len(jobs), "failed_or_missing_jobs": failures,
               "usage": dict(usage), "overall_adversarial": rate(adversarial),
               "clean": rate(list(clean.values())), "by_category": by_category,
               "by_type": {typ: rate([row for row in adversarial if row["type"] == typ])
                           for typ in ("noul", "choice", "score")},
               "score_exact_only": rate([row for row in adversarial
                                         if row["type"] == "score" and row["answer_kind"] == "exact"]),
               "by_label_source": {source: rate([row for row in adversarial if row["label_source"] == source])
                                   for source in ("human_review", "jev_default")},
               "new_errors_given_correct_clean": new_errors,
               "scoring": {"noul_exact": "noul >= 0.5 means true; value 0.5 is true",
                           "noul_interval": "inclusive on raw noul probability",
                           "choice_exact": "choice option key equality",
                           "score_exact": "continuous score equality, absolute tolerance 1e-9 for floating-point representation only",
                           "score_interval": "inclusive on raw continuous score",
                           "sensitivity": "for exact Score only, absolute difference <= 0.25; not part of the adopted benchmark label"}}
    OUT.mkdir(parents=True, exist_ok=True)
    atomic_json(OUT / "summary.json", summary)
    with (OUT / "results.jsonl.tmp").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (OUT / "results.jsonl.tmp").replace(OUT / "results.jsonl")
    lines = ["# ADbeta1.0 Jev API 评测", "",
             f"模型：`{MODEL}`；实际返回：{', '.join(sorted(models)) or '无'}。",
             f"完成：{len(adversarial):,}/9,744 条对抗样本，{len(clean)}/812 条原题对照。",
             "", "## 严格按标注计分", "",
             "Noul 固定布尔标签用 P(true)≥0.5；Noul/Score 区间按原始数值与闭区间比较；Choice 比较选项键；Score 固定小数按连续值严格相等比较（仅容许 1e-9 浮点误差）。",
             "Score ±0.25 是单独的敏感性统计，不是数据库定义的正确标准。", "",
             "| 类别 | 返回数 | 严格错误数 | 严格错误率 | Score±0.25 敏感性错误率 |", 
             "| --- | ---: | ---: | ---: | ---: |"]
    for category, stats in by_category.items():
        e = stats["strict_error_rate"]
        s = stats["score_tolerance_0_25_error_rate"]
        lines.append(f"| {category} | {stats['answered']} | {stats['strict_errors']} | "
                     f"{e:.2%} | {s:.2%} |" if e is not None else f"| {category} | 0 | — | — | — |")
    overall = summary["overall_adversarial"]
    if overall["answered"]:
        lines += [f"| **对抗合计** | **{overall['answered']}** | **{overall['strict_errors']}** | "
                  f"**{overall['strict_error_rate']:.2%}** | **{overall['score_tolerance_0_25_error_rate']:.2%}** |"]
    lines += ["", "## 题型与标签来源", "",
              "| 分组 | 返回数 | 严格错误数 | 严格错误率 | Score±0.25 敏感性错误率 |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for label, stats in list(summary["by_type"].items()) + list(summary["by_label_source"].items()):
        lines.append(f"| {label} | {stats['answered']} | {stats['strict_errors']} | "
                     f"{stats['strict_error_rate']:.2%} | {stats['score_tolerance_0_25_error_rate']:.2%} |")
    exact_score = summary["score_exact_only"]
    lines += ["", f"固定小数标注的 Score 严格错误为 {exact_score['strict_errors']}/{exact_score['answered']} "
              f"（{exact_score['strict_error_rate']:.2%}）；其中很多偏差来自连续值不完全相等。", "",
              "## 原题答对后的新增偏离", "",
              "| 类别 | 原题答对数 | 扰动后偏离数 | 比例 |",
              "| --- | ---: | ---: | ---: |"]
    for category, stats in new_errors.items():
        lines.append(f"| {category} | {stats['baseline_correct_count']} | "
                     f"{stats['new_errors']} | {stats['new_error_rate']:.2%} |")
    total_new = sum(stats["new_errors"] for stats in new_errors.values())
    total_baseline_correct = sum(stats["baseline_correct_count"] for stats in new_errors.values())
    lines.append(f"| **合计** | **{total_baseline_correct}** | **{total_new}** | "
                 f"**{total_new / total_baseline_correct:.2%}** |")
    lines += ["", "## 判读边界", "",
              "这是一轮 API 调用的原标注一致性检查。669 道题使用 `jev_default` 标签，来源于此前 Jev 共识，不能视为独立人工真值。",
              "S3 改写了判定规则，因此偏离原标注不自动构成模型错误或攻击成功。Q1/Q2 的语义等价性仍需人工审核。",
              "S2 的 Unicode 转义已保留在 HTTP 请求原始字节里；JSON 解析后字段名与原题相同，模型是否实际接触原始转义形式由服务端实现决定。",
              "`confidence` 只按 API 原值保存，没有用于计分。每个样本在本次统计中只采用一次正式返回，结果会受随机性影响。",
              "若有失败请求，错误率仅以成功返回的答案为分母，不把服务失败计为模型错误。", ""]
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--limit-jobs", type=int)
    args = parser.parse_args()
    dataset, source_sha, items, groups = load_items()
    jobs = build_jobs(groups)
    manifest = {"dataset": dataset["dataset"], "source_sha256": source_sha,
                "model": MODEL, "endpoint": ENDPOINT,
                "max_questions_per_request": MAX_QUESTIONS,
                "max_question_bytes_per_request": MAX_QUESTION_BYTES,
                "items": items,
                "jobs": [{"job_id": j["job_id"], "scenario_id": j["scenario_id"],
                          "state_hash": j["state_hash"],
                          "item_ids": [item_id for item_id, _ in j["items"]]}
                         for j in jobs]}
    print(json.dumps({"items": len(items), "adversarial": 9744, "clean": 812,
                      "jobs": len(jobs), "state_groups": len(groups),
                      "max_items_in_job": max(len(j["items"]) for j in jobs)}, ensure_ascii=False), flush=True)
    if args.plan:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous != manifest:
            raise RuntimeError("Existing evaluation manifest differs; refusing to mix runs")
    else:
        atomic_json(manifest_path, manifest)
    key = credential()
    pending = jobs if args.limit_jobs is None else jobs[:args.limit_jobs]
    done = 0
    errors = 0
    reused = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(run_job, job, key) for job in pending]
        for future in concurrent.futures.as_completed(futures):
            result, from_cache = future.result()
            done += 1
            reused += int(from_cache)
            errors += result["status"] != "ok"
            if done % 25 == 0 or done == len(pending) or result["status"] != "ok":
                print(json.dumps({"completed_jobs": done, "planned_jobs": len(pending),
                                  "reused": reused, "errors": errors,
                                  "last_job": result["job_id"],
                                  "last_status": result["status"]}), flush=True)
    summary = summarize(items, jobs)
    print(json.dumps({"complete": summary["complete"],
                      "adversarial_answers": summary["adversarial_answers"],
                      "clean_answers": summary["clean_answers"],
                      "strict_error_rate": summary["overall_adversarial"]["strict_error_rate"],
                      "failed_jobs": len(summary["failed_or_missing_jobs"])},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
