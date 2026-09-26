"""Compare the regenerated results with the numbers printed in the paper.

Point estimates must match to the printed precision. Bootstrap CIs use a different
random stream from the paper's run, so their endpoints may differ by a few tenths.
"""
import csv
import json
import sys
from common import RESULTS

CI_TOL = 0.5


def table(name, key="id"):
    with (RESULTS / name).open(encoding="utf-8") as f:
        return {r[key]: r for r in csv.DictReader(f)}


# Paper Table 17 / Table 2: flips per primitive and pooled rate with CI
PAPER_FLIPS = {
    "rerun": (1, 4, 3, 1.0, 0.3, 1.9), "Q1": (1, 3, 4, 1.0, 0.3, 1.9), "Q2": (4, 5, 3, 1.5, 0.6, 2.5),
    "Q3": (13, 11, 13, 4.6, 3.0, 6.4), "T1": (1, 11, 6, 2.2, 0.9, 3.6), "T2": (19, 62, 17, 12.1, 8.5, 15.5),
    "T3": (10, 30, 16, 6.9, 4.4, 9.2), "P1": (37, 31, 4, 8.9, 7.1, 10.8), "P2": (41, 36, 5, 10.1, 8.3, 12.0),
    "P3": (30, 29, 7, 8.1, 5.7, 10.3), "S1": (1, 5, 4, 1.2, 0.4, 2.1), "S2": (0, 4, 3, 0.9, 0.1, 1.5),
    "S3": (1, 2, 3, 0.7, 0.1, 1.6),
}
# Paper Table 18: excess (pp) with CI and attack-only / re-run-only flips
PAPER_EXCESS = {
    "Q1": (0.0, -0.6, 0.6, 4, 4), "Q2": (0.5, -0.2, 1.3, 7, 3), "Q3": (3.6, 2.3, 4.9, 32, 3),
    "T1": (1.2, 0.3, 2.1, 13, 3), "T2": (11.1, 7.8, 14.4, 92, 2), "T3": (5.9, 3.8, 7.7, 51, 3),
    "P1": (7.9, 5.7, 10.1, 68, 4), "P2": (9.1, 7.4, 11.1, 76, 2), "P3": (7.1, 5.0, 9.2, 64, 6),
    "S1": (0.2, 0.0, 0.6, 2, 0), "S2": (-0.1, -0.8, 0.5, 4, 5), "S3": (-0.2, -0.7, 0.0, 1, 3),
}
# Paper Table 1: median added characters and mean billed-token increase
PAPER_DELIVERY = {
    "Q1": (5, 5.4), "Q2": (1, 0.4), "Q3": (143, 28.1), "T1": (187, 37.4), "T2": (195, 48.3), "T3": (420, 84.8),
    "P1": (81, 16.3), "P2": (108, 26.0), "P3": (102, 21.9), "S1": (269, 0.0), "S2": (10, 0.0), "S3": (190, 0.0),
}
# Paper Table 19: union over attack sets (noul, choice, score, all)
PAPER_UNION = {
    "any_delivered_9": (29.9, 32.3, 21.1, 29.2), "state_or_injection_6": (28.3, 32.0, 17.4, 27.7),
    "question_or_structure_6": (5.1, 4.5, 8.7, 5.5), "question_3": (4.8, 3.6, 8.7, 5.0),
    "state_3": (6.7, 21.1, 14.9, 14.3), "injection_3": (25.2, 19.9, 8.1, 19.6),
    "structure_3": (0.3, 1.8, 3.1, 1.5), "rerun_and_structure_4": (0.3, 1.8, 3.1, 1.5),
}
# Paper Table 3: tolerant accuracy on human-reviewed labels
PAPER_HUMAN = {"clean": 87.4, "rerun": 86.0, "Q3": 81.1, "T2": 68.5, "T3": 77.6, "P1": 74.1, "P2": 72.0, "P3": 74.1}
# Headline scalars from Sections 4.2-4.4
PAPER_SCALARS = {
    "top10_share_delivered_flips": 59.2, "chars_tokens_pearson_r": 0.987, "chars_tokens_n": 5684,
    "choice_flips_on_target_pct": 88.8, "choice_flips_uniform_ref_pct": 31.2,
    "target_hit_rerun_pooled": 0.2, "target_hit_placebo_state_note": 0.4,
    "confident_clean_answers": 405, "rerun_pushed_below_gate_pct": 0.5, "clean_share_below_gate_pct": 18.7,
    "delivered_drops_below_gate": 534, "delivered_drops_decision_kept": 441,
    "gate_answers": 4482, "gate_flips": 293,
    "auroc_all_delivered_attack_conf": 0.885, "auroc_all_delivered_clean_conf": 0.808,
    "auroc_observer_opinion_attack_conf": 0.762, "auroc_observer_opinion_clean_conf": 0.751,
    "auroc_commands_attack_conf": 0.894, "auroc_commands_clean_conf": 0.781,
    "escape_all_delivered_pct": 12.6, "escape_observer_opinion_pct": 24.1,
    "noul_flips_outside_0.4_0.6_pct": 51.9, "human_reviewed_questions": 143, "slot_both_questions": 245,
}
PAPER_TARGET_HIT = {"T2": 11.4, "P2": 9.6}
PAPER_SHIFT = {"T2": (12.1, 35.6, 47.7), "Q3": (4.6, 17.4, None), "rerun": (1.0, 0.1, None)}
PAPER_GATE = {"T2": (154, 38.0, 37.5, 119), "T3": (None, None, 23.7, None), "P2": (None, None, 21.7, None),
              "Q3": (None, None, 6.7, None), "T1": (None, None, 2.2, None)}
PAPER_SLOT = {("commands", "all"): (15.3, 2.6), ("commands", "choice"): (30.7, 2.1),
              ("commands", "noul"): (11.8, 7.5), ("commands", "score"): (5.9, 2.6),
              ("unrelated_sentences", "all"): (5.0, 4.1)}


def main():
    ok, bad, ci_notes = 0, [], []

    def eq(label, got, want, tol=0.0):
        nonlocal ok
        if want is None:
            return
        if abs(float(got) - float(want)) <= tol + 1e-9:
            ok += 1
        else:
            bad.append(f"{label}: regenerated {got}, paper {want}")

    def ci(label, got, want):
        if abs(float(got) - float(want)) > 1e-9:
            ci_notes.append(f"{label}: {got} vs paper {want}")
        eq(label, got, want, CI_TOL)

    fr = table("flip_rates.csv")
    for a, (n, c, s, r, lo, hi) in PAPER_FLIPS.items():
        eq(f"flips {a} noul", fr[a]["noul_flips"], n)
        eq(f"flips {a} choice", fr[a]["choice_flips"], c)
        eq(f"flips {a} score", fr[a]["score_flips"], s)
        eq(f"rate {a}", fr[a]["all_rate"], r)
        ci(f"rate CI lo {a}", fr[a]["all_ci_lo"], lo)
        ci(f"rate CI hi {a}", fr[a]["all_ci_hi"], hi)
    ex = table("excess_tests.csv")
    for a, (e, lo, hi, n10, n01) in PAPER_EXCESS.items():
        eq(f"excess {a}", ex[a]["excess_pp"], e)
        eq(f"n10 {a}", ex[a]["n10_attack_only"], n10)
        eq(f"n01 {a}", ex[a]["n01_rerun_only"], n01)
        ci(f"excess CI lo {a}", ex[a]["ci_lo"], lo)
        ci(f"excess CI hi {a}", ex[a]["ci_hi"], hi)
    significant = {a for a, r in ex.items() if float(r["p_perm_holm"]) < 0.05}
    eq("attacks significant after Holm (perm)", len(significant), 6)
    dl = table("delivery.csv")
    for a, (ch, tk) in PAPER_DELIVERY.items():
        eq(f"chars {a}", dl[a]["median_added_chars"], ch)
        eq(f"tokens {a}", dl[a]["mean_delta_billed_tokens"], tk)
    un = table("union.csv", key="set")
    for k, vals in PAPER_UNION.items():
        for col, v in zip(("noul", "choice", "score", "all"), vals):
            eq(f"union {k} {col}", un[k][col], v)
    hu = table("human_label_accuracy.csv")
    for a, v in PAPER_HUMAN.items():
        eq(f"human acc {a}", hu[a]["accuracy_pct"], v)
    th = table("target_hit.csv")
    for a, v in PAPER_TARGET_HIT.items():
        eq(f"target hit {a}", th[a]["target_hit_pct"], v)
    sh = table("shift.csv")
    for a, vals in PAPER_SHIFT.items():
        for col, v in zip(("flip_pct", "shift_no_flip_pct", "flip_or_shift_pct"), vals):
            eq(f"shift {a} {col}", sh[a][col], v)
    cg = table("confidence_gate.csv")
    for a, vals in PAPER_GATE.items():
        for col, v in zip(("pushed_below_0.8", "pct_of_confident", "excess_over_rerun_pp", "of_which_decision_unchanged"), vals):
            eq(f"gate {a} {col}", cg[a][col], v)
    with (RESULTS / "injection_slot.csv").open(encoding="utf-8") as f:
        sl = {(r["edit"], r["type"]): r for r in csv.DictReader(f)}
    for k, (i, c) in PAPER_SLOT.items():
        eq(f"slot {k} instructions", sl[k]["instructions_flip_pct"], i)
        eq(f"slot {k} criteria", sl[k]["criteria_flip_pct"], c)
    sc = json.loads((RESULTS / "headline.json").read_text())
    for k, v in PAPER_SCALARS.items():
        eq(k, sc[k], v)
    eq("slot gap", sc["slot_within_question_gap_pp"][0], 14.3)

    report = {"checked": ok + len(bad), "matched": ok, "mismatched": bad,
              "ci_endpoints_differing_within_tolerance": ci_notes}
    (RESULTS / "paper_check.json").write_text(json.dumps(report, indent=1) + "\n")
    print(f"{ok}/{ok + len(bad)} values match the paper"
          f" ({len(ci_notes)} bootstrap CI endpoints differ by <= {CI_TOL} pp).")
    for b in bad:
        print("  MISMATCH", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
