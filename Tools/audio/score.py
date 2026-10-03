"""Saltmoss Harbor - music theory helpers, sequencing grid and mixer.

* parse_chord / voice / uke_shape / bass_pitch: harmony and voicing
* parse_line: compact melody notation  "D5:3 C#5:1 D5:2 | A5:4 F#5:2"
  (durations in grid units, usually eighth notes; flags: '~' slur into this
  note, '/' slide into this note, '>' accent, '^' cut (grace) ornament, '.' staccato)
* Grid: bar/eighth -> seconds with optional swing
* Mix / Track: humanised note placement, per-track EQ, pan, reverb sends,
  loop folding, master tape + loudness normalisation.
"""
from __future__ import annotations

import itertools
import math
import re
from functools import lru_cache

import numpy as np

import dsp
from dsp import SR, ns, n2m, midi_hz

# ----------------------------------------------------------------------------
# harmony
# ----------------------------------------------------------------------------

QUAL = {
    "": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "m7": [0, 3, 7, 10],
    "maj7": [0, 4, 7, 11], "dim": [0, 3, 6], "dim7": [0, 3, 6, 9], "aug": [0, 4, 8],
    "sus4": [0, 5, 7], "sus2": [0, 2, 7], "add9": [0, 4, 7, 14], "madd9": [0, 3, 7, 14],
    "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9], "9": [0, 4, 7, 10, 14], "m9": [0, 3, 7, 10, 14],
    "maj9": [0, 4, 7, 11, 14], "69": [0, 4, 7, 9, 14], "7sus4": [0, 5, 7, 10],
    "m7b5": [0, 3, 6, 10], "maj7#11": [0, 4, 7, 11, 18], "7b9": [0, 4, 7, 10, 13],
    "mmaj7": [0, 3, 7, 11], "5": [0, 7],
}
_CH_RE = re.compile(r"^([A-G])([#b]?)([^/]*)(?:/([A-G][#b]?))?$")
_PCN = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _pc(s):
    return (_PCN[s[0]] + (1 if "#" in s else 0) - (1 if "b" in s[1:] else 0)) % 12


@lru_cache(maxsize=None)
def parse_chord(sym):
    m = _CH_RE.match(sym)
    if not m:
        raise ValueError(sym)
    r, acc, q, bass = m.groups()
    root = _pc(r + acc)
    ivs = QUAL[q]
    bpc = _pc(bass) if bass else root
    return root, tuple(ivs), bpc


def chord_pcs(sym):
    root, ivs, _ = parse_chord(sym)
    return [(root + i) % 12 for i in ivs]


def voice(sym, lo, hi, prev=None, n=None, drop=(7,)):
    """Choose a voicing of chord `sym` between midi lo..hi.  With `prev`,
    minimise voice movement (smooth voice-leading)."""
    root, ivs, _ = parse_chord(sym)
    ivs = list(ivs)
    if n is not None:
        for d in drop:
            if len(ivs) > n and d in ivs:
                ivs.remove(d)
        ivs = ivs[:n] if len(ivs) > n else ivs
    pcs = [(root + i) % 12 for i in ivs]
    cands = [[m for m in range(lo, hi + 1) if m % 12 == pc] for pc in pcs]
    if any(len(c) == 0 for c in cands):
        raise ValueError(f"cannot voice {sym} in {lo}-{hi}")
    best, bc = None, 1e9
    mid = (lo + hi) / 2
    for combo in itertools.product(*cands):
        if len(set(combo)) < len(combo):
            continue
        s = sorted(combo)
        span = s[-1] - s[0]
        if span > 14:
            continue
        if prev is not None and len(prev) == len(s):
            cost = sum(abs(a - b) for a, b in zip(s, sorted(prev))) + 0.1 * span
        else:
            cost = abs(np.mean(s) - mid) + 0.3 * span
        # avoid muddy clusters: seconds between adjacent voices, tight low thirds
        for a, b in zip(s[:-1], s[1:]):
            d = b - a
            if d == 1:
                cost += 4.0
            elif d == 2:
                cost += 1.5 if a < 64 else 0.5
            elif d <= 4 and a < 52:
                cost += 1.5
        if cost < bc:
            bc, best = cost, s
    return best


UKE_OPEN = (67, 60, 64, 69)  # re-entrant G4 C4 E4 A4


@lru_cache(maxsize=None)
def uke_shape(sym):
    root, ivs, _ = parse_chord(sym)
    pcs = {(root + i) % 12 for i in ivs}
    need = {root % 12}
    for i in ivs:
        if i in (3, 4, 10, 11, 9, 2, 14, 5, 1, 13, 6):  # colour tones must be present
            need.add((root + i) % 12)
    if len(need) > 4:
        need = {root % 12, (root + ivs[1]) % 12}
    best, bc = None, 1e9
    for fr in itertools.product(range(0, 6), repeat=4):
        notes = [o + f for o, f in zip(UKE_OPEN, fr)]
        got = {x % 12 for x in notes}
        if not got <= pcs or not need <= got:
            continue
        frs = [f for f in fr if f > 0]
        span = (max(frs) - min(frs)) if frs else 0
        if span > 3:
            continue
        cost = max(fr) * 1.5 + span + 0.15 * sum(fr) + (0 if len(got) >= min(3, len(pcs)) else 3)
        if cost < bc:
            bc, best = cost, notes
    return tuple(best)


def bass_pitch(sym, lo=n2m("E1"), hi=n2m("D3"), center=n2m("A1") + 5, which="bass"):
    root, ivs, bpc = parse_chord(sym)
    pc = bpc if which == "bass" else (root + 7) % 12 if which == "fifth" else root
    cands = [m for m in range(lo, hi + 1) if m % 12 == pc]
    return min(cands, key=lambda m: abs(m - center))


# ----------------------------------------------------------------------------
# melody notation
# ----------------------------------------------------------------------------

def parse_line(s, start=0.0):
    """Returns list of note dicts {pos, len, m, flags} (pos/len in grid units)
    and the end position."""
    out = []
    pos = start
    for tok in s.split():
        if tok == "|":
            continue
        name, d = tok.rsplit(":", 1)
        flags = set()
        while d and d[-1] in "~/>^.":  # flags may follow the duration too
            flags.add(d[-1])
            d = d[:-1]
        d = float(d)
        while name and name[-1] in "~/>^.":
            flags.add(name[-1])
            name = name[:-1]
        if name in ("r", "-"):
            pos += d
            continue
        out.append({"pos": pos, "len": d, "m": n2m(name), "flags": flags})
        pos += d
    return out, pos


def transpose(notes, semis):
    return [dict(n, m=n["m"] + semis) for n in notes]


# ----------------------------------------------------------------------------
# timing grid
# ----------------------------------------------------------------------------

class Grid:
    """Bars of `bar` eighth-notes; `e` = seconds per eighth note.
    swing (0.5 = straight) delays the off-beat eighth of each quarter."""

    def __init__(self, e, bar=6, swing=0.5, t0=0.0):
        self.e, self.bar, self.swing, self.t0 = e, bar, swing, t0

    @classmethod
    def from_bpm(cls, bpm_quarter, bar=6, swing=0.5, t0=0.0):
        return cls(60.0 / bpm_quarter / 2.0, bar, swing, t0)

    @property
    def bar_s(self):
        return self.bar * self.e

    def t(self, bar, e=0.0):
        p = bar * self.bar + e
        if self.swing != 0.5:
            q = math.floor(p / 2.0)
            x = (p - 2 * q) / 2.0
            s = self.swing
            xs = x * (s / 0.5) if x < 0.5 else s + (x - 0.5) * ((1 - s) / 0.5)
            p = 2 * q + 2 * xs
        return self.t0 + p * self.e

    def notes(self, line, bar0=0, legato=0.95, vel=0.8, transpose=0):
        """Convert parse_line output to absolute-time note dicts."""
        notes, _ = parse_line(line) if isinstance(line, str) else (line, None)
        out = []
        for nt in notes:
            p = bar0 * self.bar + nt["pos"]
            t = self.t(0, p)
            tend = self.t(0, p + nt["len"])
            lg = 0.55 if "." in nt["flags"] else legato
            out.append({"t": t, "dur": (tend - t) * lg, "full": tend - t, "m": nt["m"] + transpose,
                        "vel": vel * (1.12 if ">" in nt["flags"] else 1.0),
                        "slur": "~" in nt["flags"], "slide": "/" in nt["flags"],
                        "cut": "^" in nt["flags"]})
        return out


# ----------------------------------------------------------------------------
# mixer
# ----------------------------------------------------------------------------

class Track:
    def __init__(self, mix, name, gain_db=0.0, pan=0.0, eq=None, rev=0.15, rev2=0.0,
                 width=1.0, human=0.008, comp=None):
        self.mix, self.name = mix, name
        self.gain_db, self.pan, self.eq = gain_db, pan, eq or []
        self.rev, self.rev2, self.width, self.human, self.comp = rev, rev2, width, human, comp
        self.buf = np.zeros((2, mix.N))

    def put(self, t, sig, gain=1.0, pan=None):
        k = min(sig.shape[-1], ns(0.004))  # safety fade so no note can end in a click
        if k > 1:
            sig = sig.copy()
            sig[..., -k:] *= np.linspace(1.0, 0.0, k)
        st = sig if sig.ndim == 2 else dsp.pan(sig, self.pan if pan is None else pan)
        dsp.mix_into(self.buf, st * gain, self.mix.pre_n + ns(t))

    def jitter(self, scale=1.0):
        r = self.mix.rng
        h = self.human * scale
        return float(np.clip(r.normal(0, h), -2 * h, 2 * h)) if h > 0 else 0.0

    def note(self, inst, t, m, dur, vel, pan=None, human=1.0, **kw):
        r = self.mix.rng
        t = t + self.jitter(human)
        v = float(np.clip(vel * (1 + r.normal(0, 0.06)), 0.05, 1.2))
        f = float(midi_hz(m)) if m < 200 else float(m)
        sig = inst(f, dur, v, r, **kw)
        self.put(t, sig, pan=pan)

    def hit(self, fn, t, vel, pan=None, human=1.0, **kw):
        r = self.mix.rng
        t = t + self.jitter(human)
        v = float(np.clip(vel * (1 + r.normal(0, 0.06)), 0.05, 1.2))
        self.put(t, fn(v, r, **kw), pan=pan)

    def line(self, fn, notes, pan=None, **kw):
        """Monophonic legato line (whistle/fiddle). Humanises note times."""
        r = self.mix.rng
        nn = []
        for nt in notes:
            j = self.jitter(1.0)
            nn.append(dict(nt, t=nt["t"] + j, vel=float(np.clip(nt["vel"] * (1 + r.normal(0, 0.05)), 0.1, 1.2))))
        # keep order / no overlaps
        for i in range(1, len(nn)):
            if nn[i]["t"] <= nn[i - 1]["t"] + 0.02:
                nn[i]["t"] = nn[i - 1]["t"] + 0.02
            maxd = nn[i]["t"] - nn[i - 1]["t"]
            nn[i - 1]["dur"] = min(nn[i - 1]["dur"], maxd)
        nn = add_cuts(nn)
        t0, sig = fn(nn, r, **kw)
        self.put(t0, sig, pan=pan)


def add_cuts(notes, cut_len=0.032):
    """Insert Irish-style 'cut' grace notes (a step or two above) before notes
    flagged with '^'."""
    out = []
    for nt in notes:
        if nt.get("cut") and nt["dur"] > 0.15:
            g = dict(nt, t=nt["t"], dur=cut_len, m=nt["m"] + 2, slur=False)
            main = dict(nt, t=nt["t"] + cut_len, dur=nt["dur"] - cut_len, slur=True)
            out += [g, main]
        else:
            out.append(nt)
    return out


class Mix:
    def __init__(self, name, length, loop=True, pre=1.0, tail=9.0, seed=None,
                 ir=None, ir2=None):
        self.name, self.length, self.loop = name, length, loop
        self.pre_n = ns(pre)
        self.L = ns(length)
        self.N = self.pre_n + self.L + ns(tail)
        self.rng = dsp.rng_for("mix", seed or name)
        self.tracks: list[Track] = []
        self.ir = ir or dict(rt60=2.0, predelay=0.022, hf_ratio=0.35, er_level=0.6)
        self.ir2 = ir2 or dict(rt60=0.7, predelay=0.008, hf_ratio=0.5, er_level=0.9, seed=11)

    def track(self, name, **kw):
        tr = Track(self, name, **kw)
        self.tracks.append(tr)
        return tr

    def render(self, target_lufs=-16.0, ceiling_db=-1.5, master_eq=None, drive=1.5,
               report=True, fade_out=None):
        ir = dsp.make_ir(**self.ir)
        ir2 = dsp.make_ir(**self.ir2)
        M = self.N + ir.shape[1]
        dry = np.zeros((2, M))
        send = np.zeros((2, self.N))
        send2 = np.zeros((2, self.N))
        stems = {}
        for tr in self.tracks:
            x = tr.buf
            if not np.any(x):
                continue
            if tr.eq:
                x = dsp.eq(x, tr.eq)
            if tr.comp:
                x = dsp.compressor(x, **tr.comp)
            if tr.width != 1.0:
                x = dsp.width(x, tr.width)
            x = x * dsp.undb(tr.gain_db)
            dry[:, :self.N] += x
            send += x * tr.rev
            send2 += x * tr.rev2
            stems[tr.name] = x
        if np.any(send):
            w = dsp.reverb(send, ir, wet=1.0, hp_send=200.0)
            dry[:, :w.shape[1]] += w[:, :M]
        if np.any(send2):
            w2 = dsp.reverb(send2, ir2, wet=1.0, hp_send=150.0)
            dry[:, :min(M, w2.shape[1])] += w2[:, :M]
        if self.loop:
            out = dsp.fold_loop(dry, self.pre_n, self.L)
            proc = lambda z: dsp.eq(z, master_eq) if master_eq else z
            out = dsp.circular(out, proc, 1.0)
        else:
            out = dry[:, self.pre_n:self.pre_n + self.L]
            if master_eq:
                out = dsp.eq(out, master_eq)
        # consistent drive: bring the mix to -18 LUFS, then gentle tape saturation
        L0 = dsp.lufs_loop(out) if self.loop else dsp.lufs(out)
        pre_peak = dsp.peak_db(out)
        out = out * dsp.undb(-18.0 - L0)
        sat_in = np.max(np.abs(out))
        out = dsp.tape(out * 0.7, drive=drive) / 0.7
        sat_db = dsp.db(np.max(np.abs(out))) - dsp.db(sat_in)
        if self.loop:
            out = dsp.circular(out, dsp.dc_block, 2.0)
        else:
            out = dsp.dc_block(out)
            if fade_out:
                out = dsp.fade(out, 0.0, fade_out)
        before = out
        out = dsp.normalize_lufs(out, target_lufs, ceiling_db, loop=self.loop)
        # limiter activity: gain change relative to a pure static gain
        k = dsp.undb(target_lufs - (dsp.lufs_loop(before) if self.loop else dsp.lufs(before)))
        lin = np.max(np.abs(before * k), axis=0)
        act = np.max(np.abs(out), axis=0)
        sel = lin > 1e-3
        gr = dsp.db(act[sel] / lin[sel]) if np.any(sel) else np.zeros(1)
        self.stats = {"raw_mix_peak_db": round(pre_peak, 1), "tape_peak_change_db": round(float(sat_db), 2),
                      "limiter_max_gr_db": round(float(-np.min(gr)), 2),
                      "limiter_pct_over_1db": round(float(np.mean(gr < -1.0) * 100), 3)}
        if report:
            tot = dsp.lufs(out)
            msg = [f"[{self.name}] {out.shape[1] / SR:.2f}s LUFS {tot:.1f} peak {dsp.peak_db(out):.1f} {self.stats}"]
            ref = None
            for k, v in stems.items():
                seg = v[:, self.pre_n:self.pre_n + self.L]
                L = dsp.lufs(seg)
                msg.append(f"   {k:12s} {L:6.1f}")
            print("\n".join(msg))
        return out
