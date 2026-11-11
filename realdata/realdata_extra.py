"""Additional real-data analyses (hospital B, PhysioNet/CinC 2019):
1) reachability of the earlier fixed theta_K = 0.95;
2) the earlier default thresholds (P70/P90 with theta_K = 0.95) on real data;
3) selection of a worked trace (septic, evaluable, detected, with a damped de-escalation if available).
"""
import json, sys
from dataclasses import replace
from multiprocessing import Pool
import numpy as np, pandas as pd
import importlib.util
spec = importlib.util.spec_from_file_location("rd", "scripts/realdata_eval.py")
rd = importlib.util.module_from_spec(spec); spec.loader.exec_module(rd)
from dwi import run_reference, Signature, LVL, check_coherence, CoherenceError  # noqa: E402

out = {}
sc = pd.read_pickle("scores.pkl")
pa = np.array(sorted(sc.loc[sc.hospital == "A", "patient"].unique()), dtype=object)
r = np.random.default_rng(2026); r.shuffle(pa)
cal = set(pa[int(0.7 * len(pa)):])
va = sc.loc[sc.patient.isin(cal), "sigma"].values
vb = sc.loc[sc.hospital == "B", "sigma"].values
out["max_sigma"] = {"A_calibration": float(va.max()), "B": float(vb.max())}
out["hours_ge_0.95"] = {"A_calibration": int((va >= 0.95).sum()), "B": int((vb >= 0.95).sum()), "B_total_hours": int(len(vb))}

# earlier default thresholds: P70 / P90 of hospital A calibration scores, fixed theta_K = 0.95
q = np.quantile(va, [0.70, 0.90])
P_old = replace(rd.P, thM=round(float(q[0]), 4), thC=round(float(q[1]), 4), thK=0.95)
out["earlier_default_params"] = dict(thM=P_old.thM, thC=P_old.thC, thK=P_old.thK)
try:
    check_coherence(P_old); out["earlier_default_coherence"] = "pass"
except CoherenceError as e:
    out["earlier_default_coherence"] = f"refused ({e})"
rd.P = P_old
if True:
    out["earlier_default"] = {}
    for st in ("level-triggered", "DWI"):
        rows = [rd.run_patient((pid, t, s_, o, e, st, 2.0)) for pid, t, s_, o, e in rd.PATIENTS]
        out["earlier_default"][st] = rd.summarize(rows)
        print("old", st, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out["earlier_default"][st].items()}, flush=True)

# worked trace: primary parameters
P0 = rd.P = json.load(open("realdata_results.json"))["params"]
P = replace(rd.Params(), thM=P0["thM"], thC=P0["thC"], thK=P0["thK"], tick=1.0, delta=2.0)
cands = []
for pid, taus, sig, onset, ev in rd.PATIENTS:
    if onset is None or not ev or len(taus) > 72 or len(taus) < 24:
        continue
    m = run_reference(pid, [Signature(pid, float(t), float(s)) for t, s in zip(taus, sig)], P, 0.0, float(taus[-1]))
    damped = sum(1 for t, lam, s in m.lam_trace if LVL[s] > LVL[lam])
    det = any(LVL[s] >= 2 and onset - 12 <= t <= onset + 3 for t, _, s in m.lam_trace)
    if det and 3 <= len(m.trace) <= 8 and onset - taus[0] >= 10:
        cands.append((damped > 0, len(m.trace), pid))
cands.sort(reverse=True)
out["trace_candidates"] = cands[:10]
out["trace_patient"] = cands[0][2] if cands else None
print("trace candidates", cands[:10])
json.dump(out, open("realdata_extra.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "trace_candidates"}, indent=1, default=str))
