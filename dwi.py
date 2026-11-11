"""Dynamic Workflow Intelligence (DWI) -- pure-function reference implementation.

Everything is stated over event time (hours, float). One state machine per patient.
The module is intentionally dependency-free so that it can serve as the conformance
oracle for any other realization.
"""
from __future__ import annotations

import hashlib
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

STATES = ("R", "W", "T", "K")
LVL = {s: i for i, s in enumerate(STATES)}
L, M, C = "L", "M", "C"


# --------------------------------------------------------------------------- params
@dataclass(frozen=True)
class Params:
    ds: float = 6.0     # short window (h)
    dm: float = 12.0    # mid window (h)
    dl: float = 24.0    # long window (h)
    cW: int = 1
    cT: int = 2
    cK: int = 3
    mW: int = 2
    mT: int = 3
    thM: float = 0.70
    thC: float = 0.90
    thK: float = 0.95
    delta: float = 2.0  # dwell before de-escalation (h)
    tick: float = 5 / 60  # evaluation clock (h), event-time
    version: str = "p-1.0"


class CoherenceError(ValueError):
    pass


def check_coherence(p: Params) -> None:
    """C1-C3, asserted at start-up; deployment fails on violation."""
    if not (p.cW <= p.cT <= p.cK and p.mW <= p.mT):
        raise CoherenceError("C1")
    if not (0 < p.thM < p.thC <= p.thK < 1 or (0 < p.thM < p.thC <= p.thK <= 1)):
        raise CoherenceError("C2")
    if not (0 < p.ds <= p.dm <= p.dl):
        raise CoherenceError("C3")
    if p.delta < 0 or p.tick <= 0:
        raise CoherenceError("C4")


# --------------------------------------------------------------------------- Def. 1-2
@dataclass(frozen=True)
class Signature:
    pid: str
    tau: float
    sigma: float
    model: str = "m-1"

    @property
    def sid(self) -> str:
        return hashlib.sha256(f"{self.pid}|{self.tau!r}|{self.model}".encode()).hexdigest()[:16]


def kappa(sigma: float, p: Params) -> str:
    if sigma < p.thM:
        return L
    if sigma < p.thC:
        return M
    return C


# --------------------------------------------------------------------------- Def. 3
@dataclass(frozen=True)
class Aggregates:
    smax_s: float
    nC_s: int
    nC_m: int
    nM_s: int  # n_{>=M} short
    nC_l: int
    nM_m: int  # n_{>=M} mid


class Window:
    """Per-patient sorted signature store supporting half-open (t-D, t] queries."""

    def __init__(self, p: Params):
        self.p = p
        self.taus: List[float] = []
        self.sig: List[float] = []

    def add(self, tau: float, sigma: float) -> None:
        i = bisect_right(self.taus, tau)
        self.taus.insert(i, tau)
        self.sig.insert(i, sigma)

    def _slice(self, t: float, D: float):
        lo = bisect_right(self.taus, t - D)
        hi = bisect_right(self.taus, t)
        return self.sig[lo:hi]

    def aggregates(self, t: float) -> Aggregates:
        p = self.p
        s = self._slice(t, p.ds)
        m = self._slice(t, p.dm)
        l_ = self._slice(t, p.dl)
        return Aggregates(
            smax_s=max(s) if s else 0.0,
            nC_s=sum(1 for x in s if x >= p.thC),
            nC_m=sum(1 for x in m if x >= p.thC),
            nM_s=sum(1 for x in s if x >= p.thM),
            nC_l=sum(1 for x in l_ if x >= p.thC),
            nM_m=sum(1 for x in m if x >= p.thM),
        )


# --------------------------------------------------------------------------- Def. 4 / Table 3 (compact, FIRST)
def evidence_first(a: Aggregates, p: Params) -> Tuple[str, str]:
    if a.smax_s >= p.thK:
        return "K", "G1"
    if a.nC_s >= p.cK:
        return "K", "G2"
    if a.nC_m >= p.cT:
        return "T", "G3"
    if a.nM_s >= p.mT:
        return "T", "G4"
    if a.nC_l >= p.cW:
        return "W", "G5"
    if a.nM_m >= p.mW:
        return "W", "G6"
    return "R", "G7"


# --------------------------------------------------------------------------- Table S1 (expanded, UNIQUE)
def expanded_rules(p: Params):
    """Each rule is a list of (column, op, value). Staircase form."""
    c1 = ("smax_s", ">=", p.thK)
    c2 = ("nC_s", ">=", p.cK)
    c3 = ("nC_m", ">=", p.cT)
    c4 = ("nM_s", ">=", p.mT)
    c5 = ("nC_l", ">=", p.cW)
    c6 = ("nM_m", ">=", p.mW)
    conds = [c1, c2, c3, c4, c5, c6]
    out = ["K", "K", "T", "T", "W", "W", "R"]
    rules = []
    for i in range(7):
        body = [(c, "<", v) for (c, _, v) in conds[:i]]
        if i < 6:
            body.append(conds[i])
        rules.append((f"G{i+1}", body, out[i]))
    return rules


def _holds(a: Aggregates, cond) -> bool:
    col, op, v = cond
    x = getattr(a, col)
    return x >= v if op == ">=" else x < v


def evidence_unique(a: Aggregates, p: Params) -> Tuple[str, str]:
    hits = [(rid, o) for rid, body, o in expanded_rules(p) if all(_holds(a, c) for c in body)]
    if len(hits) != 1:
        raise RuntimeError(f"UNIQUE hit policy violated: {hits}")
    return hits[0][1], hits[0][0]


# --------------------------------------------------------------------------- Def. 5 / Table S2
def _build_phi_table():
    rows = []
    k = 0
    for sp in STATES:
        for lam in STATES:
            if LVL[lam] > LVL[sp]:
                rows.append((sp, lam, None, lam, "escalate"))
            elif LVL[lam] == LVL[sp]:
                rows.append((sp, lam, None, sp, "hold"))
            else:
                rows.append((sp, lam, False, sp, "damped"))
                rows.append((sp, lam, True, lam, "de-escalate"))
    return [(f"T{i+1:02d}",) + r for i, r in enumerate(rows)]


PHI_TABLE = _build_phi_table()  # 22 rules


def phi_table(sp: str, lam: str, dwell_ok: bool) -> Tuple[str, str, str]:
    hits = [r for r in PHI_TABLE if r[1] == sp and r[2] == lam and (r[3] is None or r[3] == dwell_ok)]
    if len(hits) != 1:
        raise RuntimeError("Phi table not UNIQUE")
    rid, _, _, _, s, cls = hits[0]
    return s, rid, cls


def phi(sp: str, lam: str, dwell_ok: bool) -> str:
    if LVL[lam] > LVL[sp]:
        return lam
    if LVL[lam] < LVL[sp] and dwell_ok:
        return lam
    return sp


# --------------------------------------------------------------------------- Table S3 (adaptation)
ADAPT = {
    ("R", "W"): ("A-01", 0), ("R", "T"): ("A-02", 2), ("R", "K"): ("A-03", 3),
    ("W", "T"): ("A-04", 2), ("W", "K"): ("A-05", 3), ("T", "K"): ("A-06", 3),
    ("K", "T"): ("A-07", 2), ("K", "W"): ("A-08", 2), ("K", "R"): ("A-09", 2),
    ("T", "W"): ("A-10", 1), ("T", "R"): ("A-11", 2), ("W", "R"): ("A-12", 1),
}
MONITOR_INTERVAL_H = {"R": 4.0, "W": 2.0, "T": 1.0, "K": 0.0}


def adaptation(sp: str, s: str) -> Tuple[str, int]:
    if sp == s:
        raise ValueError("edge-triggered: no command on hold")
    return ADAPT[(sp, s)]


# --------------------------------------------------------------------------- state machine
@dataclass
class Decision:
    t: float
    s_prev: str
    s: str
    lam: str
    guard: str
    rule: str
    cmd: str
    tier: int
    cid: str


@dataclass
class Machine:
    pid: str
    p: Params
    s: str = "R"
    tau_last: float = 0.0
    k: int = 0
    win: Window = None
    trace: List[Decision] = field(default_factory=list)
    lam_trace: List[Tuple[float, str, str]] = field(default_factory=list)

    def __post_init__(self):
        check_coherence(self.p)
        if self.win is None:
            self.win = Window(self.p)

    def evaluate(self, t: float) -> None:
        a = self.win.aggregates(t)
        lam, g = evidence_first(a, self.p)
        self.lam_trace.append((t, lam, self.s))
        dwell_ok = (t - self.tau_last) >= self.p.delta - 1e-12
        s_new, rid, _ = phi_table(self.s, lam, dwell_ok)
        if s_new != self.s:
            self.k += 1
            cmd, tier = adaptation(self.s, s_new)
            cid = hashlib.sha256(f"{self.pid}|{self.k}".encode()).hexdigest()[:16]
            self.trace.append(Decision(t, self.s, s_new, lam, g, rid, cmd, tier, cid))
            self.s = s_new
            self.tau_last = t
        # post-state recorded for dominance checks
        self.lam_trace[-1] = (t, lam, self.s)


def evaluation_instants(taus: Sequence[float], t0: float, t1: float, tick: float) -> List[float]:
    """Signature times union event-time clock grid, sorted, de-duplicated."""
    n = int((t1 - t0) / tick + 1e-9)
    grid = [round(t0 + i * tick, 9) for i in range(n + 1)]
    return sorted(set(grid) | set(round(x, 9) for x in taus))


def run_reference(pid: str, sigs: Iterable[Signature], p: Params, t0: float = 0.0,
                  t1: Optional[float] = None) -> Machine:
    """Batch oracle: de-duplicate by content key, order by event time, evaluate."""
    uniq = {}
    for s in sigs:
        # key collision with differing content: retain the larger score (order-independent,
        # conservative); an identical redelivery is absorbed idempotently
        if s.sid not in uniq or s.sigma > uniq[s.sid].sigma:
            uniq[s.sid] = s
    ordered = sorted(uniq.values(), key=lambda s: s.tau)
    if t1 is None:
        t1 = ordered[-1].tau if ordered else t0
    m = Machine(pid, p)
    inst = evaluation_instants([s.tau for s in ordered], t0, t1, p.tick)
    j = 0
    for t in inst:
        while j < len(ordered) and round(ordered[j].tau, 9) <= t:
            m.win.add(ordered[j].tau, ordered[j].sigma)
            j += 1
        m.evaluate(t)
    return m


# --------------------------------------------------------------------------- streaming realization
class StreamingProcessor:
    """Per-patient streaming processor with content-key de-duplication (A3) and a
    watermark-driven reorder buffer (A1/A2). Signatures later than the watermark are
    logged and excluded (never silently folded in)."""

    def __init__(self, pid: str, p: Params, lateness: float, t0: float = 0.0,
                 dedup: bool = True, reorder: bool = True, late_policy: str = "exclude"):
        self.m = Machine(pid, p)
        self.p = p
        self.lateness = lateness
        self.seen = {}
        self.conflicts = 0
        self.buf: List[Signature] = []
        self.max_tau = t0
        self.t0 = t0
        self.tick_i = 0
        self.last_eval = t0 - 1e-9
        self.late: List[Signature] = []
        self.dedup = dedup
        self.reorder = reorder
        self.late_policy = late_policy
        self.folded = 0

    def _flush(self, upto: float):
        self.buf.sort(key=lambda s: s.tau)
        while True:
            nxt_sig = self.buf[0].tau if self.buf else float("inf")
            nt = round(self.t0 + self.tick_i * self.p.tick, 9)
            t = min(round(nxt_sig, 9), nt)
            if t > upto + 1e-12:
                break
            while self.buf and round(self.buf[0].tau, 9) <= t:
                s = self.buf.pop(0)
                self.m.win.add(s.tau, s.sigma)
            if t > self.last_eval:
                self.m.evaluate(t)
                self.last_eval = t
            if nt <= t:
                self.tick_i += 1

    def receive(self, s: Signature):
        if self.dedup:
            if s.sid in self.seen:
                old = self.seen[s.sid]
                if s.sigma == old.sigma:
                    return  # redelivery
                self.conflicts += 1
                if s.sigma < old.sigma:
                    return
                if s.tau <= self.last_eval:  # already evaluated: handle as late
                    self.late.append(s)
                    return
                self.buf = [b for b in self.buf if b.sid != s.sid]
            self.seen[s.sid] = s
        if not self.reorder:
            # naive: evaluate immediately at the signature's own event time
            self.m.win.add(s.tau, s.sigma)
            self.m.evaluate(s.tau)
            return
        if s.tau <= self.last_eval:
            if self.late_policy == "fold":  # silently folded in (anti-pattern)
                self.m.win.add(s.tau, s.sigma)
                self.folded += 1
            else:
                self.late.append(s)
            return
        self.buf.append(s)
        self.max_tau = max(self.max_tau, s.tau)
        self._flush(self.max_tau - self.lateness)

    def close(self, t1: float):
        if self.reorder:
            self._flush(t1)
        return self.m


# --------------------------------------------------------------------------- Def. 9-11, Thm. 3 helpers
def staleness_ok(t_read: float, t_commit: float, eps: float) -> bool:
    return (t_read - t_commit) <= eps


def phi_degraded(sp: str, static_level: str) -> str:
    """Degraded mode: escalation on static thresholds only; no de-escalation."""
    return static_level if LVL[static_level] > LVL[sp] else sp


def reconcile(s_degraded: str, s_replay: str) -> str:
    """On recovery the committed state is the more conservative of the degraded state and
    the replayed state; any de-escalation thereafter passes through the dwell gate."""
    return s_degraded if LVL[s_degraded] >= LVL[s_replay] else s_replay


@dataclass
class OverrideLock:
    start: float
    end: float

    def active(self, t: float) -> bool:
        return self.start <= t < self.end


def gate_command(t: float, locks: Sequence[OverrideLock]) -> str:
    return "queued-for-review" if any(l.active(t) for l in locks) else "dispatch"
