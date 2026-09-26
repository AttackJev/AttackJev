"""Flip rates, excess over the identical re-run, tests and unions (paper Tables 2, 17-19)."""
from common import *


def flip_vec(qs, a):
    if a == "rerun":
        return [(q["scenario"], int(flipped(q["clean"], q["rerun"]))) for q in qs]
    return [(q["scenario"], int(flipped(q["clean"], q["attacks"][a]["ans"]))) for q in qs]


def main():
    Q = load()
    qs = list(Q.values())
    subsets = {"all": qs, **{t: [q for q in qs if q["type"] == t] for t in TYPES}}

    rows, excess, stats = [], [], {}
    p_perm, p_mcn = {k: {} for k in subsets}, {k: {} for k in subsets}
    for a in ["rerun"] + ATTACKS:
        row = [a, "re-run" if a == "rerun" else NAMES[a], "Noise" if a == "rerun" else FAMILY[a]]
        for t in TYPES + ["all"]:
            g = by_scenario(flip_vec(subsets[t], a))
            k = sum(sum(v) for v in g.values())
            lo, hi = bootstrap_ci(g)
            row += [k, len(subsets[t]), fmt(rate(g)), fmt(lo), fmt(hi)]
            stats[(a, t)] = rate(g)
            if a != "rerun":
                att = flip_vec(subsets[t], a)
                rer = flip_vec(subsets[t], "rerun")
                diff = by_scenario((s, x - y) for (s, x), (_, y) in zip(att, rer))
                n10 = sum(x and not y for (_, x), (_, y) in zip(att, rer))
                n01 = sum(y and not x for (_, x), (_, y) in zip(att, rer))
                p_perm[t][a] = sign_flip_p(diff)
                p_mcn[t][a] = mcnemar_p(n10, n01)
                if t == "all":
                    elo, ehi = bootstrap_ci(diff, stat=rate)
                    excess.append([a, NAMES[a], fmt(rate(diff)), fmt(elo), fmt(ehi), n10, n01])
        rows.append(row)

    hdr = ["id", "attack", "family"]
    for t in TYPES + ["all"]:
        hdr += [f"{t}_flips", f"{t}_n", f"{t}_rate", f"{t}_ci_lo", f"{t}_ci_hi"]
    write_csv("flip_rates.csv", hdr, rows)

    adj_perm = {t: holm(p_perm[t]) for t in subsets}
    adj_mcn = {t: holm(p_mcn[t]) for t in subsets}
    out = []
    for e in excess:
        a = e[0]
        out.append(e + [f"{adj_perm['all'][a]:.4f}", f"{adj_mcn['all'][a]:.4f}"]
                   + [f"{adj_perm[t][a]:.4f}/{adj_mcn[t][a]:.4f}" for t in TYPES])
    write_csv("excess_tests.csv",
              ["id", "attack", "excess_pp", "ci_lo", "ci_hi", "n10_attack_only", "n01_rerun_only",
               "p_perm_holm", "p_mcnemar_holm", "noul_perm/mcn", "choice_perm/mcn", "score_perm/mcn"], out)

    # union of flipped questions over attack sets (Table 19)
    sets = {
        "any_delivered_9": DELIVERED, "any_of_12": ATTACKS,
        "state_or_injection_6": ["T1", "T2", "T3", "P1", "P2", "P3"],
        "question_or_structure_6": ["Q1", "Q2", "Q3", "S1", "S2", "S3"],
        "question_3": ["Q1", "Q2", "Q3"], "state_3": ["T1", "T2", "T3"],
        "injection_3": ["P1", "P2", "P3"], "structure_3": STRUCTURE,
        "rerun_and_structure_4": ["rerun"] + STRUCTURE,
    }
    urows = []
    for name, members in sets.items():
        row = [name, len(members)]
        for t in TYPES + ["all"]:
            vec = [(q["scenario"], int(any(flipped(q["clean"], q["rerun"] if a == "rerun" else q["attacks"][a]["ans"])
                                           for a in members))) for q in subsets[t]]
            g = by_scenario(vec)
            row.append(fmt(rate(g)))
            if t == "all":
                lo, hi = bootstrap_ci(g)
                row += [fmt(lo), fmt(hi)]
        p0 = stats[("rerun", "all")] / 100
        row.append(fmt(100 * (1 - (1 - p0) ** len(members))))
        urows.append(row)
    write_csv("union.csv", ["set", "size", "noul", "choice", "score", "all", "ci_lo", "ci_hi", "indep_ref"], urows)

    # concentration: share of delivered flips carried by the top 10% of questions
    counts = sorted((sum(flipped(q["clean"], q["attacks"][a]["ans"]) for a in DELIVERED) for q in qs), reverse=True)
    top = sum(counts[: round(0.1 * len(counts))]) / sum(counts)
    return {"top10_share_delivered_flips": round(100 * top, 1)}


if __name__ == "__main__":
    print(main())
