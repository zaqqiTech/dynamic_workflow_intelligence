"""Figures 3 and 4 from the real hospital B data (PhysioNet/CinC 2019)."""
import json, sys
from dataclasses import replace
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, "/home/claude/dwi")
from dwi import Params, Signature, run_reference, LVL, STATES  # noqa: E402

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#52514e", "axes.labelcolor": "#0b0b0b",
                     "xtick.color": "#52514e", "ytick.color": "#52514e", "axes.titlesize": 8.5,
                     "axes.titleweight": "bold", "savefig.dpi": 300})
BLUE, ORANGE, AQUA, YELLOW, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#0b0b0b", "#52514e", "#e4e3df"

R = json.load(open("realdata_results.json")); X = json.load(open("realdata_extra.json"))
pp = R["params"]
P = replace(Params(), thM=pp["thM"], thC=pp["thC"], thK=pp["thK"], tick=1.0, delta=2.0)


def fig3(pid):
    sc = pd.read_pickle("scores.pkl")
    d = sc[sc.patient == pid].sort_values("ICULOS")
    taus = d.ICULOS.values.astype(float); sig = d.sigma.values; lab = d.SepsisLabel.values
    onset = float(taus[np.where(lab == 1)[0][0]] + 6.0)
    m = run_reference(pid, [Signature(pid, float(t), float(s)) for t, s in zip(taus, sig)], P, 0.0, float(taus[-1]))
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.6, 2.9), sharex=True, gridspec_kw=dict(height_ratios=[1.15, 1]))
    lo, hi = taus[0] - 0.5, taus[-1] + 0.5
    for a in (a1, a2):
        a.axvspan(onset - 12, min(onset + 3, hi), color="#f0efec", lw=0)
        a.axvline(onset, color=MUTED, lw=0.8, ls=(0, (2, 2)))
        a.grid(axis="y", color=GRID, lw=0.5)
    cls = np.where(sig >= P.thC, ORANGE, np.where(sig >= P.thM, YELLOW, "#b9b8b2"))
    a1.plot(taus, sig, color="#cfcec9", lw=0.6, zorder=2)
    a1.scatter(taus, sig, s=9, c=cls, lw=0, zorder=3)
    for th, name in ((P.thM, r"$\theta_M$"), (P.thC, r"$\theta_C$"), (P.thK, r"$\theta_K$")):
        a1.axhline(th, color=MUTED, lw=0.6, ls=(0, (3, 2)))
        a1.text(hi + 0.4, th, name, va="center", fontsize=6.5, color=MUTED)
    a1.set_ylabel(r"anomaly score $\sigma$"); a1.set_ylim(0, max(0.75, sig.max() * 1.1))
    a1.text(onset + 0.3, a1.get_ylim()[1] * 0.70, "sepsis onset", fontsize=6.5, color=MUTED)
    a1.text(onset - 11.7, a1.get_ylim()[1] * 0.92, "detection window", fontsize=6.5, color=MUTED)
    tt = np.array([t for t, _, _ in m.lam_trace]); lam = np.array([LVL[l] for _, l, _ in m.lam_trace])
    S = np.array([LVL[s] for _, _, s in m.lam_trace])
    a2.step(tt, lam, where="post", color=ORANGE, lw=1.0, label=r"evidence $\lambda(t)$")
    a2.step(tt, S, where="post", color=BLUE, lw=1.8, alpha=0.9, label=r"committed $S(t)$")
    for d_ in m.trace:
        a2.annotate(d_.cmd, (d_.t, LVL[d_.s]), xytext=(0, 5 if LVL[d_.s] > LVL[d_.s_prev] else -9),
                    textcoords="offset points", ha="center", fontsize=5.8, color=INK)
    a2.set_yticks(range(4)); a2.set_yticklabels(STATES); a2.set_ylim(-0.6, 3.7)
    a2.set_xlabel("ICU length of stay (h)"); a2.set_ylabel("state")
    a2.legend(loc="upper left", frameon=False, fontsize=6.5, ncol=2)
    a2.set_xlim(lo, hi + 2)
    fig.align_ylabels(); fig.tight_layout(h_pad=0.4)
    fig.savefig("fig3_trace_real.png", bbox_inches="tight", pad_inches=0.03)
    damped = [(t, lam_, s) for t, lam_, s in m.lam_trace if LVL[s] > LVL[lam_]]
    return dict(pid=pid, hours=len(taus), onset=onset, label_first=float(onset - 6),
                transitions=[(d_.t, d_.s_prev, d_.s, d_.cmd) for d_ in m.trace],
                damped_hours=[(t, l, s) for t, l, s in damped])


def fig4():
    S = R["strategies"]; O = R["ordering"]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(6.8, 2.2), gridspec_kw=dict(width_ratios=[1.15, 1.2, 1]))
    names = ["threshold-alert", "level-triggered", "edge-no-hysteresis", "DWI"]
    cols = [YELLOW, ORANGE, AQUA, BLUE]
    v = [S[n]["commands_per_pd"] for n in names]
    ci = [S[n]["commands_per_pd_ci95"] for n in names]
    err = np.array([[vi - c_[0] for vi, c_ in zip(v, ci)], [c_[1] - vi for vi, c_ in zip(v, ci)]])
    a.bar(range(4), v, color=cols, width=0.62, yerr=err, error_kw=dict(lw=0.6, capsize=2, ecolor=MUTED))
    a.set_yscale("log"); a.set_xticks(range(4)); a.set_xticklabels(["B1", "B2", "B3", "DWI"], fontsize=7)
    for i, x in enumerate(v):
        a.text(i, x * 1.35, f"{x:.2f}", ha="center", fontsize=6.5, color=INK)
    a.set_ylabel("commands per patient-day (log)"); a.set_title("(a) Automated workload", loc="left")
    a.set_ylim(0.05, 5); a.grid(axis="y", color=GRID, lw=0.5)
    ds = sorted(R["sweep"], key=float); x = [float(k) for k in ds]
    rv = [1000 * R["sweep"][k]["reversals_per_pd"] for k in ds]
    b.plot(x, rv, color=BLUE, lw=1.6, marker="o", ms=3.5)
    b.set_xlabel(r"dwell $\delta_{\mathrm{down}}$ (h)"); b.set_ylabel("reversals per 1,000 patient-days")
    b.set_title("(b) Dwell trade-off", loc="left"); b.grid(axis="y", color=GRID, lw=0.5); b.set_ylim(0, max(rv) * 1.3)
    labels = ["A1 enforced\n(reorder buffer)", "No buffer,\nlate folded in", "No buffer,\nlate dropped"]
    vals = [100 * O["identical"][k] / O["replays"] for k in ("A1", "fold", "drop")]
    c.barh(range(3)[::-1], vals, color=[BLUE, "#b9b8b2", "#b9b8b2"], height=0.55)
    c.set_yticks(range(3)[::-1]); c.set_yticklabels(labels, fontsize=6.2)
    for i, xv in zip(range(3)[::-1], vals):
        c.text(xv + 2, i, f"{xv:.1f}%", va="center", fontsize=6.5)
    c.set_xlim(0, 125); c.set_xlabel("replays identical to oracle (%)"); c.set_title("(c) Replay determinism", loc="left")
    fig.tight_layout(w_pad=1.6)
    fig.savefig("fig4_results_real.png", bbox_inches="tight", pad_inches=0.03)


if __name__ == "__main__":
    info = fig3(X["trace_patient"]); fig4()
    json.dump(info, open("fig3_trace_info.json", "w"), indent=1, default=float)
    print(json.dumps(info, indent=1, default=float))
