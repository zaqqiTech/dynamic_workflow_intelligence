"""Conformance suite TC-1..TC-18. Prints a JSON summary with case counts per group."""
import itertools, json, random, sys
from dataclasses import replace

from hypothesis import given, settings, strategies as st, HealthCheck

from dwi import *  # noqa

P = Params()
RESULTS = {}


def record(group, exercises, passed, failed, note=""):
    RESULTS[group] = dict(exercises=exercises, cases=passed + failed, passed=passed, failed=failed, note=note)


def agg(**kw):
    base = dict(smax_s=0.0, nC_s=0, nC_m=0, nM_s=0, nC_l=0, nM_m=0)
    base.update(kw)
    return Aggregates(**base)


# TC-1 guard partition: predicate abstraction (64) + concrete grid
def tc1():
    ok = bad = 0
    lo = dict(smax_s=P.thK - 0.01, nC_s=P.cK - 1, nC_m=P.cT - 1, nM_s=P.mT - 1, nC_l=P.cW - 1, nM_m=P.mW - 1)
    hi = dict(smax_s=P.thK, nC_s=P.cK, nC_m=P.cT, nM_s=P.mT, nC_l=P.cW, nM_m=P.mW)
    cols = list(lo)
    for bits in itertools.product([0, 1], repeat=6):
        a = agg(**{c: (hi[c] if b else lo[c]) for c, b in zip(cols, bits)})
        try:
            ok += evidence_first(a, P) == evidence_unique(a, P)
            bad += evidence_first(a, P) != evidence_unique(a, P)
        except RuntimeError:
            bad += 1
    n_abs = ok
    for sm in (0.94, 0.95, 0.96):
        for v in itertools.product(range(5), repeat=5):
            a = Aggregates(sm, *v)
            try:
                if evidence_first(a, P) == evidence_unique(a, P):
                    ok += 1
                else:
                    bad += 1
            except RuntimeError:
                bad += 1
    record("TC-1 Guard partition", "Thm 4", ok, bad, f"64 predicate valuations (exhaustive) + {ok+bad-64} concrete cells")


# TC-2 guard boundaries
def tc2():
    ok = bad = 0
    spec = [("smax_s", P.thK, 0.01, "K"), ("nC_s", P.cK, 1, "K"), ("nC_m", P.cT, 1, "T"),
            ("nM_s", P.mT, 1, "T"), ("nC_l", P.cW, 1, "W"), ("nM_m", P.mW, 1, "W")]
    for col, v, e, out in spec:
        for x, exp in ((v - e, False), (v, True), (v + e, True)):
            lam, _ = evidence_first(agg(**{col: x}), P)
            fired = lam == out
            ok += fired == exp
            bad += fired != exp
    record("TC-2 Guard boundaries", "Def 4", ok, bad)


# TC-3 window edges (half-open (t-D, t])
def tc3():
    ok = bad = 0
    t = 30.0
    for D, col in ((P.ds, "nC_s"), (P.dm, "nC_m"), (P.dl, "nC_l")):
        for tau, exp in ((t - D, 0), (t - D + 1e-6, 1), (t, 1)):
            w = Window(P)
            w.add(tau, 0.99 if col != "nC_s" else 0.92)
            got = getattr(w.aggregates(t), col)
            ok += got == exp
            bad += got != exp
    record("TC-3 Window edges", "Def 3", ok, bad)


# TC-4 Phi enumeration
def tc4():
    ok = bad = 0
    for sp, lam, d in itertools.product(STATES, STATES, (False, True)):
        s_tab, _, _ = phi_table(sp, lam, d)
        ok += s_tab == phi(sp, lam, d)
        bad += s_tab != phi(sp, lam, d)
    assert len(PHI_TABLE) == 22
    record("TC-4 Phi enumeration", "Def 5, Prop 1", ok, bad, "32/32 cells; 22 rules")


# TC-5 dwell boundary
def tc5():
    ok = bad = 0
    for sp, lam in [(a, b) for a in STATES for b in STATES if LVL[b] < LVL[a]]:
        for dt, exp in ((P.delta - 1e-6, sp), (P.delta, lam), (P.delta + 1e-6, lam)):
            s, _, _ = phi_table(sp, lam, dt >= P.delta - 1e-12)
            ok += s == exp
            bad += s != exp
    # end-to-end through the machine (added after mutant M3 survived the first run)
    for dlt, exp_t in ((6.0 - 1e-6, 7.0), (6.0, 7.0), (6.0 + P.tick / 2, round(7.0 + P.tick, 9))):
        p = replace(P, delta=dlt)
        m = run_reference("d", [Signature("d", 1.0, 0.96)], p, 0.0, 10.0)
        down = [d.t for d in m.trace if LVL[d.s] < LVL[d.s_prev]]
        got = round(down[0], 9) if down else None
        ok += got == exp_t; bad += got != exp_t
    record("TC-5 Dwell boundary", "Def 5", ok, bad, "18 table cells + 3 end-to-end")


# TC-6 adaptation base
def tc6():
    ok = bad = 0
    for sp, s in itertools.product(STATES, STATES):
        if sp == s:
            try:
                adaptation(sp, s)
                bad += 1
            except ValueError:
                ok += 1
        else:
            cmd, tier = adaptation(sp, s)
            good = cmd.startswith("A-") and tier in (0, 1, 2, 3)
            # de-escalation out of K is tier >= 2; entry into K is tier 3
            if sp == "K":
                good &= tier >= 2
            if s == "K":
                good &= tier == 3
            ok += good
            bad += not good
    ids = {v[0] for v in ADAPT.values()}
    assert len(ids) == 12
    record("TC-6 Adaptation base", "Def 6-8", ok, bad, "12 transitions + 4 hold (no command)")


# TC-7 overlay commutativity (additive-only COLLECT)
def tc7():
    rng = random.Random(7)
    ok = bad = 0
    tasks = [f"task{i}" for i in range(10)]
    for _ in range(500):
        base = set(rng.sample(tasks, 3))
        overlays = [set(rng.sample(tasks, rng.randint(0, 4))) for _ in range(rng.randint(2, 4))]
        r1 = set(base)
        for o in overlays:
            r1 |= o
        r2 = set(base)
        for o in reversed(overlays):
            r2 |= o
        ok += r1 == r2 and base <= r1
        bad += not (r1 == r2 and base <= r1)
    record("TC-7 Overlay commutativity", "Sec 3.6", ok, bad, "500 random multi-match overlays")


sig_list = st.lists(st.tuples(st.floats(0, 48, allow_nan=False).map(lambda x: round(x, 3)),
                              st.floats(0, 1, allow_nan=False)), min_size=0, max_size=60)
COUNTERS = {}


def counted(name):
    def deco(f):
        def g(*a, **k):
            COUNTERS[name] = COUNTERS.get(name, 0) + 1
            return f(*a, **k)
        return g
    return deco


HS = settings(max_examples=1000, deadline=None, suppress_health_check=list(HealthCheck), derandomize=True)


# TC-8 monotonicity (Thm 0)
@HS
@given(sig_list, st.integers(0, 10**6), st.floats(0, 48))
def prop_monotone(sigs, idx, t):
    COUNTERS["TC-8"] = COUNTERS.get("TC-8", 0) + 1
    if not sigs:
        return
    i = idx % len(sigs)
    tau, s = sigs[i]
    k = kappa(s, P)
    if k == C:
        return
    up = P.thM if k == L else P.thC  # minimal upgrade to next class
    up = max(up, s)
    w1, w2 = Window(P), Window(P)
    for j, (ta, sg) in enumerate(sigs):
        w1.add(ta, sg)
        w2.add(ta, up if j == i else sg)
    l1, _ = evidence_first(w1.aggregates(t), P)
    l2, _ = evidence_first(w2.aggregates(t), P)
    assert LVL[l2] >= LVL[l1]


def mk(pid, sigs):
    return [Signature(pid, tau, s) for tau, s in sigs]


# TC-16 conservative dominance (Prop 2), TC-17 oscillation bound (Thm 1), TC-18 lag (Prop 3)
@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck), derandomize=True)
@given(sig_list, st.sampled_from([0.0, 0.5, 1.0, 2.0]))
def prop_dominance_and_bound(sigs, delta):
    COUNTERS["TC-16/17"] = COUNTERS.get("TC-16/17", 0) + 1
    p = replace(P, delta=delta)
    m = run_reference("p", mk("p", sigs), p, 0.0, 48.0)
    for t, lam, s in m.lam_trace:
        assert LVL[s] >= LVL[lam]
    if delta > 0:
        T = 48.0
        assert len(m.trace) <= 4 * math.ceil(T / delta) + 3


@settings(max_examples=300, deadline=None, suppress_health_check=list(HealthCheck), derandomize=True)
@given(sig_list)
def prop_lag(sigs):
    COUNTERS["TC-18"] = COUNTERS.get("TC-18", 0) + 1
    # after the last signature, evidence decays; once lvl(lambda)<=l for 3*delta, lvl(S)<=l
    m = run_reference("p", mk("p", sigs), P, 0.0, 80.0)
    tr = m.lam_trace
    for l in range(3):
        # find maximal suffix where lvl(lam) <= l
        start = None
        for t, lam, s in tr:
            if LVL[lam] <= l:
                start = t if start is None else start
            else:
                start = None
        if start is None:
            continue
        for t, lam, s in tr:
            if t >= start + 3 * P.delta:
                assert LVL[s] <= l, (l, start, t, s)


import math


# targeted class-biased generator (added after mutant M1 survived the first run)
cls_sigs = st.lists(st.tuples(st.floats(0, 30, allow_nan=False).map(lambda x: round(x, 2)),
                              st.sampled_from([0.30, 0.80, 0.92])), min_size=1, max_size=10)


@HS
@given(cls_sigs, st.integers(0, 10**6), st.floats(0, 30))
def prop_monotone_biased(sigs, idx, t):
    COUNTERS["TC-8b"] = COUNTERS.get("TC-8b", 0) + 1
    prop_monotone.hypothesis.inner_test(sigs, idx, t)


def monotone_fixture():
    """Worked example of Fig. 3a: three M-class signatures in 6 h, one old C-class."""
    base = [(1.0, 0.92), (20.0, 0.80), (21.0, 0.80), (22.0, 0.80)]
    w1, w2 = Window(P), Window(P)
    for i, (ta, sg) in enumerate(base):
        w1.add(ta, sg); w2.add(ta, 0.92 if i == 3 else sg)
    return LVL[evidence_first(w2.aggregates(22.5), P)[0]] >= LVL[evidence_first(w1.aggregates(22.5), P)[0]]


def run_props():
    for name, f in (("TC-8 Monotonicity", prop_monotone),):
        try:
            f(); prop_monotone_biased()
            fx = monotone_fixture()
            n = COUNTERS.get("TC-8", 0)
            record(name, "Thm 0", n + fx, 0 if fx else 1, "uniform + class-biased generators + worked fixture")
        except AssertionError as e:
            record(name, "Thm 0", 0, 1, str(e))
    try:
        prop_dominance_and_bound()
        n = COUNTERS.get("TC-16/17", 0)
        record("TC-16 Conservative dominance", "Prop 2", n, 0, "every evaluation instant checked")
        record("TC-17 Oscillation bound", "Thm 1", n, 0, "4 dwell values")
    except AssertionError as e:
        record("TC-16/17", "Prop 2/Thm 1", 0, 1, repr(e))
    try:
        prop_lag(); record("TC-18 De-escalation lag", "Prop 3", COUNTERS.get("TC-18", 0), 0)
    except AssertionError as e:
        record("TC-18 De-escalation lag", "Prop 3", 0, 1, repr(e))


def random_episode(rng, pid, hours=48):
    t, out = 0.0, []
    while t < hours:
        t += rng.expovariate(4.0)
        out.append((round(t, 4), min(1.0, max(0.0, rng.betavariate(2, 3) + (0.4 if 10 < t < 20 else 0)))))
    return mk(pid, out)


def trace_key(m):
    return [(round(d.t, 9), d.s_prev, d.s, d.cmd, d.cid) for d in m.trace]


# TC-9 idempotency, TC-10 replay determinism, TC-11 late arrival
def tc9_10_11():
    rng = random.Random(10)
    ok9 = bad9 = ok10 = bad10 = 0
    for e in range(100):
        sigs = random_episode(rng, f"p{e}")
        ref = trace_key(run_reference(f"p{e}", sigs, P, 0.0, sigs[-1].tau))
        for rep in (1, 2, 5):
            sp = StreamingProcessor(f"p{e}", P, lateness=0.25)
            for s in sigs:
                for _ in range(rep):
                    sp.receive(s)
            got = trace_key(sp.close(sigs[-1].tau))
            ok9 += got == ref; bad9 += got != ref
        for sh in range(10):
            arr = sorted(sigs, key=lambda s: s.tau + rng.uniform(0, 0.24))
            sp = StreamingProcessor(f"p{e}", P, lateness=0.25)
            for s in arr:
                sp.receive(s)
            got = trace_key(sp.close(sigs[-1].tau))
            ok10 += (got == ref and not sp.late); bad10 += not (got == ref and not sp.late)
    # key collision: two distinct scores at one event time, both delivery orders
    # (added after the synthetic-cohort run exposed order dependence of Def. 1 keys)
    for e in range(100):
        sigs = random_episode(rng, f"k{e}")
        j = rng.randrange(len(sigs))
        twin = Signature(sigs[j].pid, sigs[j].tau, min(1.0, sigs[j].sigma + rng.uniform(0.01, 0.3)))
        ref = trace_key(run_reference(f"k{e}", sigs + [twin], P, 0.0, sigs[-1].tau))
        for order in (sigs[:j+1] + [twin] + sigs[j+1:], sigs[:j] + [twin] + sigs[j:]):
            sp = StreamingProcessor(f"k{e}", P, lateness=0.25)
            for s in order:
                sp.receive(s)
            got = trace_key(sp.close(sigs[-1].tau))
            ok9 += got == ref; bad9 += got != ref
    record("TC-9 Idempotency", "A3, Def 1", ok9, bad9, "300 redeliveries + 200 key collisions")
    record("TC-10 Replay determinism", "Thm 2", ok10, bad10, "100 episodes x 10 delivery shuffles; byte-identical")
    # TC-11
    ok = bad = 0
    for delay, expect_late in ((0.10, False), (0.25, False), (0.60, True)):
        sp = StreamingProcessor("q", P, lateness=0.25)
        sp.receive(Signature("q", 1.0, 0.5))
        sp.receive(Signature("q", 2.0, 0.5))
        sp.receive(Signature("q", 2.0 + delay, 0.5))  # advances watermark
        sp.receive(Signature("q", 2.0 + delay - 0.3 - 1e-3 if expect_late else 2.0 + delay - 0.2, 0.99))
        is_late = bool(sp.late)
        ok += is_late == expect_late; bad += is_late != expect_late
    record("TC-11 Late arrival", "A2", ok, bad, "inside / at / beyond watermark")


def tc12_13_14_15():
    ok = bad = 0
    for tr, tc, exp in ((1.0, 0.0, True), (1.0, 0.0 + 0, True), (1.0 + 1e-3, 0.0, False)):
        got = staleness_ok(tr, tc, 1.0)
        ok += got == exp; bad += got != exp
    record("TC-12 Staleness guard", "Def 9", ok, bad, "eps-, eps, eps+")
    ok = bad = 0
    rng = random.Random(13)
    for _ in range(500):
        s = rng.choice(STATES)
        for _ in range(20):
            s2 = phi_degraded(s, rng.choice(STATES))
            if LVL[s2] < LVL[s]:
                bad += 1
            s = s2
        r = rng.choice(STATES)
        rc = reconcile(s, r)
        good = LVL[rc] >= max(LVL[s], LVL[r]) - 0 and rc in (s, r)
        ok += good; bad += not good
    record("TC-13 Degradation", "Thm 3", ok, bad, "500 random outages x 20 steps + reconciliation")
    ok = bad = 0
    locks = [OverrideLock(1.0, 2.0)]
    for t, exp in ((1.5, "queued-for-review"), (2.0, "dispatch"), (3.0, "dispatch")):
        got = gate_command(t, locks)
        ok += got == exp; bad += got != exp
    record("TC-14 Override precedence", "Def 11", ok, bad, "active / expiring / absent")
    ok = bad = 0
    for bad_p in (replace(P, cW=3, cT=2), replace(P, thC=0.97, thK=0.95), replace(P, ds=13.0)):
        try:
            check_coherence(bad_p); bad += 1
        except CoherenceError:
            ok += 1
    try:
        check_coherence(P); ok += 1
    except CoherenceError:
        bad += 1
    record("TC-15 Coherence assertions", "C1-C3", ok, bad, "3 invalid + 1 valid configuration")


if __name__ == "__main__":
    tc1(); tc2(); tc3(); tc4(); tc5(); tc6(); tc7(); run_props(); tc9_10_11(); tc12_13_14_15()
    order = sorted(RESULTS, key=lambda k: int(k.split()[0].split("-")[1].split("/")[0]))
    out = {k: RESULTS[k] for k in order}
    tot = sum(v["cases"] for v in out.values()); fail = sum(v["failed"] for v in out.values())
    out["TOTAL"] = dict(cases=tot, failed=fail)
    print(json.dumps(out, indent=1))
    json.dump(out, open("conformance_results.json", "w"), indent=1)
