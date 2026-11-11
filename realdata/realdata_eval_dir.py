"""Real-data validation of the DWI state layer on hospital B of the PhysioNet/CinC 2019 database.

Every coupling consumes the same hourly anomaly scores from the same detector (trained on hospital A).
Sepsis onset (Sepsis-3, as labelled by the challenge) is recovered as the first positive SepsisLabel hour + 6 h,
undoing the challenge's 6-h label shift.
"""
import json, math, random, sys
from dataclasses import replace
from multiprocessing import Pool
import numpy as np, pandas as pd

sys.path.insert(0, "/home/claude/dwi")
from dwi import Params, Signature, run_reference, StreamingProcessor, LVL  # noqa: E402

det = json.load(open("detector_results.json"))
TH = det["thresholds"]
P = Params(thM=round(TH["thM_P93"], 4), thC=round(TH["thC_P98"], 4), thK=round(TH["thK_P99_9"], 4), tick=1.0, delta=2.0)
WIN_BEFORE, WIN_AFTER = 12.0, 3.0

scores = pd.read_pickle("scores.pkl")
TEST = det["test_hospital"]; TRAIN = det["train_hospital"]
B = scores[scores.hospital == TEST].sort_values(["patient", "ICULOS"])
PATIENTS = []
for pid, d in B.groupby("patient", sort=True):
    taus = d.ICULOS.values.astype(float); sig = d.sigma.values; lab = d.SepsisLabel.values
    pos = np.where(lab == 1)[0]
    onset = None; evaluable = False
    if len(pos):
        onset = float(taus[pos[0]] + 6.0)
        evaluable = pos[0] > 0            # at least one pre-label hour observed
    PATIENTS.append((pid, taus, sig, onset, evaluable))


def run_patient(args):
    pid, taus, sig, onset, evaluable, strategy, delta = args
    sigs = [Signature(pid, float(t), float(s)) for t, s in zip(taus, sig)]
    t1 = float(taus[-1]); los_h = t1 - float(taus[0]) + 1.0
    out = dict(pid=pid, los_h=los_h, septic=onset is not None, evaluable=evaluable)
    if strategy == "threshold-alert":
        al = [t for t, s in zip(taus, sig) if s >= P.thC]
        out["commands"] = len(al)
        if onset is not None and evaluable:
            hit = [t for t in al if onset - WIN_BEFORE <= t <= onset + WIN_AFTER]
            out["detected"] = bool(hit); out["lead"] = (onset - hit[0]) if hit else None
        return out
    q = replace(P, delta=0.0 if strategy in ("edge-no-hysteresis", "level-triggered") else delta)
    m = run_reference(pid, sigs, q, 0.0, t1)
    elev = [(t, LVL[s] >= 2) for t, _, s in m.lam_trace]
    if strategy == "level-triggered":
        st = set(float(t) for t in taus)
        out["commands"] = sum(1 for t, _, s in m.lam_trace if t in st and s != "R")
    else:
        out["commands"] = len(m.trace)
    out["transitions"] = len(m.trace)
    out["reversals"] = sum(1 for a, b in zip(m.trace, m.trace[1:])
                           if (LVL[a.s] - LVL[a.s_prev]) * (LVL[b.s] - LVL[b.s_prev]) < 0 and b.t - a.t <= 1.0)
    out["elev_hours"] = sum(1.0 for t, e in elev if e and t >= taus[0])     # hourly clock
    out["ever_elevated"] = any(e for _, e in elev)
    out["ever_K"] = any(s == "K" for _, _, s in m.lam_trace)
    out["bound"] = 4 * math.ceil(los_h / q.delta) + 3 if q.delta > 0 else None
    if onset is not None and evaluable:
        hit = [t for t, e in elev if e and onset - WIN_BEFORE <= t <= onset + WIN_AFTER]
        out["detected"] = bool(hit); out["lead"] = (onset - hit[0]) if hit else None
    return out


def run_patient_rm(args):
    global P
    *a, thM, thC, thK = args
    P = replace(P, thM=thM, thC=thC, thK=thK)
    return run_patient(tuple(a))


def summarize(rows, rng=None, nboot=1000):
    days = sum(r["los_h"] for r in rows) / 24.0
    non = [r for r in rows if not r["septic"]]
    ev = [r for r in rows if r["septic"] and r["evaluable"]]
    s = dict(patients=len(rows), patient_days=days, commands_per_pd=sum(r["commands"] for r in rows) / days,
             evaluable_septic=len(ev), detected=sum(1 for r in ev if r["detected"]))
    s["sensitivity"] = s["detected"] / len(ev)
    s["detected_pre_onset"] = sum(1 for r in ev if r.get("lead") is not None and r["lead"] > 0)
    s["detected_ge6h"] = sum(1 for r in ev if r.get("lead") is not None and r["lead"] >= 6)
    flag = [r for r in rows if (r.get("ever_elevated") if "ever_elevated" in r else r["commands"] > 0)]
    s["patients_flagged"] = len(flag)
    s["ppv_patient"] = sum(1 for r in flag if r["septic"]) / len(flag) if flag else None
    leads = [r["lead"] for r in ev if r.get("lead") is not None]
    s["lead_median_iqr"] = [float(np.median(leads)), float(np.percentile(leads, 25)), float(np.percentile(leads, 75))]
    nondays = sum(r["los_h"] for r in non) / 24.0
    s["nonseptic_commands_per_pd"] = sum(r["commands"] for r in non) / nondays
    if "reversals" in rows[0]:
        s["reversals_per_pd"] = sum(r["reversals"] for r in rows) / days
        s["nonseptic_elev_h_per_pd"] = sum(r["elev_hours"] for r in non) / nondays
        s["nonseptic_ever_elevated"] = sum(1 for r in non if r["ever_elevated"]) / len(non)
        s["ever_K_frac"] = sum(1 for r in rows if r["ever_K"]) / len(rows)
        if rows[0]["bound"] is not None:
            s["max_transitions_over_bound"] = max(r["transitions"] / r["bound"] for r in rows)
            s["max_transitions"] = max(r["transitions"] for r in rows)
            s["bound_violations"] = sum(1 for r in rows if r["transitions"] > r["bound"])
    if rng is not None:   # patient-level bootstrap for commands/pd and sensitivity
        idx = np.arange(len(rows)); cmd = np.array([r["commands"] for r in rows]); los = np.array([r["los_h"] for r in rows])
        evm = np.array([r["septic"] and r["evaluable"] for r in rows]); det_ = np.array([bool(r.get("detected")) for r in rows])
        bc, bs = [], []
        for _ in range(nboot):
            b = rng.choice(idx, len(idx), replace=True)
            bc.append(cmd[b].sum() / (los[b].sum() / 24)); bs.append(det_[b][evm[b]].mean())
        s["commands_per_pd_ci95"] = [float(np.percentile(bc, 2.5)), float(np.percentile(bc, 97.5))]
        s["sensitivity_ci95"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    return s


def run_all(strategy, delta=2.0, pool=None):
    args = [(pid, t, s, o, e, strategy, delta) for pid, t, s, o, e in PATIENTS]
    return pool.map(run_patient, args, chunksize=200)


def ordering(n=500, K=10, seed=7):
    rng = random.Random(seed)
    pick = rng.sample(PATIENTS, n)
    same = {"A1": 0, "fold": 0, "drop": 0}; div = {"fold": 0, "drop": 0}; total = 0
    key = lambda m: [(round(d.t, 9), d.s_prev, d.s, d.cmd, d.cid) for d in m.trace]
    for pid, taus, sig, _, _ in pick:
        sigs = [Signature(pid, float(t), float(s)) for t, s in zip(taus, sig)]
        ref = key(run_reference(pid, sigs, P, 0.0, float(taus[-1])))
        dv = {"fold": False, "drop": False}
        for _ in range(K):
            arr = sorted(sigs, key=lambda s: s.tau + (rng.uniform(0, 2.5) if rng.random() < 0.3 else 0))
            a = StreamingProcessor(pid, P, lateness=3.0)
            b = StreamingProcessor(pid, P, lateness=0.0, late_policy="fold")
            c = StreamingProcessor(pid, P, lateness=0.0, late_policy="exclude")
            for s in arr:
                a.receive(s); b.receive(s); c.receive(s)
            ra, rb, rc = key(a.close(float(taus[-1]))), key(b.close(float(taus[-1]))), key(c.close(float(taus[-1])))
            same["A1"] += ra == ref; same["fold"] += rb == ref; same["drop"] += rc == ref; total += 1
            dv["fold"] |= rb != ref; dv["drop"] |= rc != ref
        div["fold"] += dv["fold"]; div["drop"] += dv["drop"]
    return dict(patients=n, replays=total, identical=same, patients_diverged=div)


def rate_matched_params():
    """Tail probabilities x4 so that expected class counts per window match the 4/h design (A only)."""
    sc = pd.read_pickle("scores.pkl")
    import json as _j
    # calibration split of hospital A is reproduced from detector.py's seeded split
    pa = np.array(sorted(sc.loc[sc.hospital == TRAIN, "patient"].unique()), dtype=object)
    r = np.random.default_rng(2026); r.shuffle(pa)
    cal = set(pa[int(0.7 * len(pa)):])
    v = sc.loc[sc.patient.isin(cal), "sigma"].values
    q = np.quantile(v, [0.72, 0.92, 0.996])
    return replace(P, thM=round(float(q[0]), 4), thC=round(float(q[1]), 4), thK=round(float(q[2]), 4))


if __name__ == "__main__":
    res = {"params": dict(thM=P.thM, thC=P.thC, thK=P.thK, tick_h=P.tick, delta_h=P.delta,
                          window_before_h=WIN_BEFORE, window_after_h=WIN_AFTER), "detector": det}
    rng = np.random.default_rng(2026)
    with Pool(2) as pool:
        res["strategies"] = {}
        for st in ("threshold-alert", "level-triggered", "edge-no-hysteresis", "DWI"):
            rows = run_all(st, 2.0, pool)
            res["strategies"][st] = summarize(rows, rng)
            print(st, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in res["strategies"][st].items()}), flush=True)
        res["sweep"] = {}
        for d in (0.0, 1.0, 2.0, 4.0, 6.0):
            rows = run_all("DWI", d, pool)
            sm = summarize(rows)
            res["sweep"][str(d)] = sm
            print("delta", d, round(sm["commands_per_pd"], 3), round(sm["reversals_per_pd"], 4),
                  round(sm["nonseptic_elev_h_per_pd"], 3), round(sm["sensitivity"], 4), sm["lead_median_iqr"], flush=True)
        P0 = P
        P = rate_matched_params()
        res["rate_matched_params"] = dict(thM=P.thM, thC=P.thC, thK=P.thK)
        res["rate_matched"] = {}
        for st in ("threshold-alert", "level-triggered", "edge-no-hysteresis", "DWI"):
            rows = pool.map(run_patient_rm, [(pid, t, s, o, e, st, 2.0, P.thM, P.thC, P.thK) for pid, t, s, o, e in PATIENTS], chunksize=200)
            res["rate_matched"][st] = summarize(rows)
            print("RM", st, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in res["rate_matched"][st].items()}), flush=True)
        P = P0
    res["ordering"] = ordering()
    print("ordering", res["ordering"])
    json.dump(res, open("realdata_results.json", "w"), indent=1)
