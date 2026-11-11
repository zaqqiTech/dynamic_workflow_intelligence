"""Fault-injection (mutation) analysis of the conformance suite: each mutant plants one
plausible specification defect; a mutant is 'killed' if at least one TC group fails."""
import importlib, json, hashlib
from bisect import bisect_left, bisect_right

import dwi
import conformance as cf


def reload():
    importlib.reload(dwi)
    importlib.reload(cf)


def run_suite():
    cf.RESULTS.clear(); cf.COUNTERS.clear()
    failed = []
    for f in (cf.tc1, cf.tc2, cf.tc3, cf.tc4, cf.tc5, cf.tc6, cf.tc7, cf.run_props, cf.tc9_10_11, cf.tc12_13_14_15):
        try:
            f()
        except Exception as e:  # crash counts as detection
            failed.append(f"{f.__name__}:crash")
    failed += [k for k, v in cf.RESULTS.items() if v["failed"]]
    return failed


def patch(name, obj):
    setattr(dwi, name, obj)
    setattr(cf, name, obj)


# ---------------------------------------------------------------- mutants
def m_class_exact():
    orig = dwi.Window.aggregates
    def aggregates(self, t):
        a = orig(self, t)
        p = self.p
        s = self._slice(t, p.ds); m = self._slice(t, p.dm)
        return dwi.Aggregates(a.smax_s, a.nC_s, a.nC_m, sum(1 for x in s if p.thM <= x < p.thC), a.nC_l,
                              sum(1 for x in m if p.thM <= x < p.thC))
    dwi.Window.aggregates = aggregates


def m_closed_window():
    def _slice(self, t, D):
        return self.sig[bisect_left(self.taus, t - D):bisect_right(self.taus, t)]
    dwi.Window._slice = _slice


def _eval_factory(dwell_fn=None, phi_fn=None, level_trigger=False):
    def evaluate(self, t):
        a = self.win.aggregates(t)
        lam, g = dwi.evidence_first(a, self.p)
        self.lam_trace.append((t, lam, self.s))
        dwell_ok = dwell_fn(self, t) if dwell_fn else (t - self.tau_last) >= self.p.delta - 1e-12
        if phi_fn:
            s_new, rid = phi_fn(self.s, lam, dwell_ok), "X"
        else:
            s_new, rid, _ = dwi.phi_table(self.s, lam, dwell_ok)
        if s_new != self.s or (level_trigger and self.s != "R"):
            self.k += 1
            cmd, tier = (dwi.adaptation(self.s, s_new) if s_new != self.s else ("A-hold", 0))
            cid = hashlib.sha256(f"{self.pid}|{self.k}".encode()).hexdigest()[:16]
            self.trace.append(dwi.Decision(t, self.s, s_new, lam, g, rid, cmd, tier, cid))
            if s_new != self.s:
                self.tau_last = t
            self.s = s_new
        self.lam_trace[-1] = (t, lam, self.s)
    return evaluate


def m_dwell_strict():
    dwi.Machine.evaluate = _eval_factory(dwell_fn=lambda self, t: (t - self.tau_last) > self.p.delta + 1e-12)


def m_symmetric_dwell():
    def phi_sym(sp, lam, d):
        return lam if (lam != sp and d) else sp
    def phi_table(sp, lam, d):
        return phi_sym(sp, lam, d), "X", "x"
    patch("phi_table", phi_table)


def m_level_trigger():
    dwi.Machine.evaluate = _eval_factory(level_trigger=True)


def m_no_terminal():
    orig = dwi.evidence_first
    def ev(a, p):
        lam, g = orig(a, p)
        if g == "G7":
            raise RuntimeError("no rule matched")
        return lam, g
    patch("evidence_first", ev)


def m_missing_negation():
    orig = dwi.expanded_rules
    def rules(p):
        r = orig(p)
        rid, body, o = r[2]
        return r[:2] + [(rid, body[1:], o)] + r[3:]
    patch("expanded_rules", rules)


def m_no_dedup():
    orig = dwi.StreamingProcessor.__init__
    def init(self, *a, **k):
        k["dedup"] = False
        orig(self, *a, **k)
    dwi.StreamingProcessor.__init__ = init


def m_no_reorder():
    orig = dwi.StreamingProcessor.__init__
    def init(self, *a, **k):
        k["reorder"] = False
        orig(self, *a, **k)
    dwi.StreamingProcessor.__init__ = init


def m_float_clock():
    """Event-time clock advanced by floating accumulation instead of integer index."""
    def _flush(self, upto):
        if not hasattr(self, "nt"):
            self.nt = self.t0
        self.buf.sort(key=lambda s: s.tau)
        while True:
            nxt = self.buf[0].tau if self.buf else float("inf")
            t = min(round(nxt, 9), self.nt)
            if t > upto + 1e-12:
                break
            while self.buf and round(self.buf[0].tau, 9) <= t:
                s = self.buf.pop(0); self.m.win.add(s.tau, s.sigma)
            if t > self.last_eval:
                self.m.evaluate(t); self.last_eval = t
            if self.nt <= t:
                self.nt = self.nt + self.p.tick
    dwi.StreamingProcessor._flush = _flush


def m_degraded_deescalate():
    patch("phi_degraded", lambda sp, st: st)


def m_tier_K_exit():
    d = dict(dwi.ADAPT); d[("K", "R")] = ("A-09", 1)
    patch("ADAPT", d)


def m_no_C2():
    orig = dwi.check_coherence
    def cc(p):
        if not (p.cW <= p.cT <= p.cK and p.mW <= p.mT):
            raise dwi.CoherenceError("C1")
        if not (0 < p.ds <= p.dm <= p.dl):
            raise dwi.CoherenceError("C3")
    patch("check_coherence", cc)


def m_override_ignored():
    patch("gate_command", lambda t, locks: "dispatch")


def m_reconcile_replay_only():
    patch("reconcile", lambda sdeg, srep: srep)


def m_first_arrival_wins():
    orig = dwi.StreamingProcessor.receive
    def receive(self, s):
        if self.dedup and s.sid in self.seen:
            return
        orig(self, s)
    dwi.StreamingProcessor.receive = receive


MUTANTS = [
    ("M1", "Class-exact instead of cumulative counting", m_class_exact),
    ("M2", "Closed window [t-D, t] instead of (t-D, t]", m_closed_window),
    ("M3", "Dwell gate > instead of >=", m_dwell_strict),
    ("M4", "Symmetric hysteresis (escalation also gated)", m_symmetric_dwell),
    ("M5", "Level-triggered command emission", m_level_trigger),
    ("M6", "Terminal rule G7 omitted", m_no_terminal),
    ("M7", "Staircase negation dropped in rule G3", m_missing_negation),
    ("M8", "Content-key de-duplication disabled", m_no_dedup),
    ("M9", "Per-patient reorder buffer disabled", m_no_reorder),
    ("M10", "Event-time clock by float accumulation", m_float_clock),
    ("M11", "Degraded mode admits de-escalation", m_degraded_deescalate),
    ("M12", "Exit from K made autonomous (Tier 1)", m_tier_K_exit),
    ("M13", "Coherence condition C2 not asserted", m_no_C2),
    ("M14", "Override lock ignored", m_override_ignored),
    ("M15", "Recovery adopts replay state only", m_reconcile_replay_only),
    ("M16", "Key collision resolved by arrival order (original Def. 1)", m_first_arrival_wins),
]

if __name__ == "__main__":
    out = []
    for mid, desc, f in MUTANTS:
        reload()
        f()
        failed = run_suite()
        out.append(dict(id=mid, mutant=desc, killed=bool(failed), detected_by=sorted(set(failed))))
        print(mid, desc, "KILLED" if failed else "SURVIVED", failed)
    reload()
    json.dump(out, open("mutation_results.json", "w"), indent=1)
