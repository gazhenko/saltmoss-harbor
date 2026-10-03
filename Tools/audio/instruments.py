"""Saltmoss Harbor - synthesized instrument voices.

Every voice returns a MONO numpy array starting at the note onset (unless the
docstring says stereo).  `vel` is 0..1.  Frequencies are in Hz.
"""
from __future__ import annotations

import math

import numpy as np

from dsp import (SR, TWO_PI, ns, tvec, karplus, modal, modal_tv, saw, pulse, sine,
                 additive, lp, hp, bp, peak, eq, hshelf, lshelf, svf, onepole_lp,
                 dc_block, gate_release, env_perc, smooth_noise, phase_cycles,
                 midi_hz, fade, pan, resonate)


def amp_of(vel):
    return float(np.clip(vel, 0.0, 1.2)) ** 1.5


# ============================================================================
# plucked strings (Karplus-Strong)
# ============================================================================

def uke_note(f, dur, vel, rng, ring=1.0):
    """Ukulele: nylon string on a small, bright, boxy body."""
    t60 = 1.25 * ring * (392.0 / f) ** 0.35
    total = min(dur + 0.12, t60 * 1.1)
    x = karplus(f, total, rng, t60=t60, damp=0.42 - 0.12 * vel,
                pluck_pos=0.13 + 0.08 * rng.random(), soft=0.62 - 0.3 * vel)
    x = gate_release(x, dur, 0.07)
    # finger noise
    k = ns(0.012)
    nz = hp(rng.standard_normal(k), 1800) * np.exp(-np.arange(k) / (0.002 * SR)) * 0.08 * vel
    x[:k] += nz
    return dc_block(x) * amp_of(vel)


UKE_BODY = [("hp", 150, 0.7, 0), ("peak", 430, 2.0, 5.0), ("peak", 1150, 1.6, 2.5),
            ("peak", 2600, 2.0, 2.0), ("lp", 9500, 0.7, 0)]


def nylon_note(f, dur, vel, rng, ring=1.0):
    """Classical/nylon guitar."""
    t60 = 2.6 * ring * (196.0 / f) ** 0.45
    total = min(dur + 0.2, t60 * 1.05)
    x = karplus(f, total, rng, t60=t60, damp=0.45 - 0.15 * vel,
                pluck_pos=0.11 + 0.06 * rng.random(), soft=0.55 - 0.25 * vel)
    x = gate_release(x, dur, 0.12)
    return dc_block(x) * amp_of(vel)


NYLON_BODY = [("hp", 75, 0.7, 0), ("peak", 105, 1.4, 3.0), ("peak", 215, 2.0, 2.5),
              ("peak", 480, 1.5, 1.0), ("peak", 900, 1.0, -1.5), ("lp", 6000, 0.7, 0)]


def harp_note(f, dur, vel, rng, ring=1.0):
    """Concert/folk harp: long-ringing, rounder pluck."""
    t60 = 4.2 * ring * (262.0 / f) ** 0.55
    total = min(max(dur, t60) + 0.1, 7.0)
    x = karplus(f, total, rng, t60=t60, damp=0.22 - 0.08 * vel,
                pluck_pos=0.5 + 0.04 * rng.random(), soft=0.45 - 0.2 * vel)
    return dc_block(x) * amp_of(vel)


HARP_BODY = [("hp", 60, 0.7, 0), ("peak", 240, 1.2, 2.0), ("peak", 1200, 1.0, 1.0),
             ("hs", 6000, 0.7, -3.0)]


def bass_pizz(f, dur, vel, rng):
    """Upright bass pizzicato (additive string with stiffness, pitch-glide and
    finger thump)."""
    T1 = 1.5 * (55.0 / f) ** 0.15
    total = min(dur + 0.15, T1 * 1.2)
    n = ns(total)
    t = tvec(n)
    B = 0.00012
    bright = 0.55 - 0.3 * vel
    freqs, amps, t60s = [], [], []
    for k in range(1, 16):
        fk = k * f * math.sqrt(1 + B * k * k)
        if fk > 6000:
            break
        a = (1.0 / k ** 1.05) * abs(math.sin(math.pi * k * 0.23)) * math.exp(-(k - 1) * bright)
        freqs.append(fk)
        amps.append(a)
        t60s.append(T1 / (1 + 0.55 * (k - 1)))
    fmul = 1.0 + 0.009 * vel * np.exp(-t / 0.045)
    x = modal_tv(freqs, amps, t60s, n, fmul, attack=0.0025,
                 phases=rng.uniform(0, 0.3, len(freqs)))
    thump = lp(rng.standard_normal(n), 160) * np.exp(-t / 0.018) * 0.25
    x = x + thump
    x = gate_release(x, dur, 0.09)
    return dc_block(x, 20) * amp_of(vel)


BASS_BODY = [("hp", 38, 0.7, 0), ("peak", 95, 1.0, 2.0), ("peak", 260, 1.0, -1.0),
             ("peak", 700, 1.5, 1.5), ("lp", 3800, 0.7, 0)]


# ============================================================================
# mallets & bells (modal)
# ============================================================================

def _clip_modes(f, ratios, amps, t60s):
    fr, am, tt = [], [], []
    for r, a, d in zip(ratios, amps, t60s):
        if f * r < 19000:
            fr.append(f * r)
            am.append(a)
            tt.append(d)
    return fr, am, tt


def glock(f, dur, vel, rng):
    """Glockenspiel (steel bars, hard mallet)."""
    base = 3.2 * (1046.0 / f) ** 0.4
    v = vel
    fr, am, tt = _clip_modes(f, [1, 2.756, 5.404, 8.933],
                             [1.0, 0.30 * v ** 1.2, 0.10 * v ** 1.5, 0.04 * v ** 2],
                             [base, base * 0.35, base * 0.14, base * 0.07])
    n = ns(min(base * 1.05, 4.5))
    x = modal(fr, am, tt, n, attack=0.0004, phases=rng.uniform(0, 0.2, len(fr)))
    k = ns(0.006)
    click = hp(rng.standard_normal(k), 4500) * np.exp(-np.arange(k) / (0.0012 * SR)) * 0.12 * v
    x[:k] += click
    return x * amp_of(vel) * 0.8


def celesta(f, dur, vel, rng):
    """Celesta: felt hammer on steel plate over a wooden resonator."""
    base = 2.4 * (523.0 / f) ** 0.5
    fr, am, tt = _clip_modes(f, [1, 2.0, 3.0, 4.16, 6.1],
                             [1.0, 0.16 * vel, 0.05, 0.04 * vel, 0.015],
                             [base, base * 0.4, base * 0.25, base * 0.15, base * 0.08])
    n = ns(min(base * 1.1, 4.0))
    x = modal(fr, am, tt, n, attack=0.0018, phases=rng.uniform(0, 0.3, len(fr)))
    k = ns(0.02)
    thunk = lp(rng.standard_normal(k), 400) * np.exp(-np.arange(k) / (0.004 * SR)) * 0.05
    x[:k] += thunk
    return x * amp_of(vel)


def music_box(f, dur, vel, rng):
    """Music-box comb tine (cantilever modes) with pin pluck and slight
    double-tine shimmer."""
    base = 2.8 * (1046.0 / f) ** 0.45
    det = 2 ** (rng.normal(0, 3.5) / 1200)
    f = f * det
    fr, am, tt = _clip_modes(f, [1, 2.0, 6.27, 17.55],
                             [1.0, 0.05, 0.32 * vel, 0.06 * vel],
                             [base, base * 0.5, base * 0.16, base * 0.05])
    n = ns(min(base * 1.05, 4.0))
    x = modal(fr, am, tt, n, attack=0.0003, phases=rng.uniform(0, 1, len(fr)))
    if rng.random() < 0.6:  # neighbouring tine a hair off-pitch
        f2 = f * 2 ** (rng.uniform(2, 5) / 1200)
        x += 0.35 * modal([f2], [1.0], [base * 0.8], n, attack=0.0003)
    k = ns(0.004)
    click = hp(rng.standard_normal(k), 3000) * np.exp(-np.arange(k) / (0.0008 * SR)) * 0.10
    x[:k] += click
    return x * amp_of(vel) * 0.7


def marimba(f, dur, vel, rng):
    """Marimba: rosewood bar tuned to 1:4:10, tube resonator, yarn mallet."""
    T = 1.7 * (220.0 / f) ** 0.65
    v = vel
    fr, am, tt = _clip_modes(f, [1, 3.93, 9.24],
                             [1.0, 0.26 * v ** 1.3, 0.06 * v ** 1.8],
                             [T, T * 0.28, T * 0.12])
    n = ns(min(T * 1.1, 3.5))
    x = modal(fr, am[:1] + [0] * (len(am) - 1), tt, n, attack=0.0035)  # resonator bloom
    x += modal(fr[1:], am[1:], tt[1:], n, attack=0.0006) if len(fr) > 1 else 0
    k = ns(0.015)
    knock = lp(rng.standard_normal(k), 1500) * np.exp(-np.arange(k) / (0.0025 * SR)) * 0.12 * v
    x[:k] += knock
    if dur < T * 0.6:  # player damping for short notes
        x = gate_release(x, max(dur, 0.12), 0.25)
    return x * amp_of(vel)


def vibes(f, dur, vel, rng):
    T = 3.0 * (440.0 / f) ** 0.4
    fr, am, tt = _clip_modes(f, [1, 4.0, 10.0], [1.0, 0.12 * vel, 0.02], [T, T * 0.3, T * 0.1])
    n = ns(min(T, 4.0))
    x = modal(fr, am, tt, n, attack=0.0015)
    trem = 1 - 0.18 * (0.5 + 0.5 * np.sin(TWO_PI * 5.2 * tvec(n)))
    return x * trem * amp_of(vel)


BELL_RATIOS = [0.25, 0.5, 0.6, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 2.66, 3.0, 4.1, 5.3]
BELL_AMPS = [0.30, 0.45, 0.55, 0.22, 1.0, 0.25, 0.40, 0.28, 0.12, 0.10, 0.08, 0.05, 0.03]
BELL_T60 = [9.0, 7.0, 6.0, 4.5, 4.5, 3.0, 2.6, 1.8, 1.2, 1.0, 0.8, 0.5, 0.3]


def bell(f_nominal, vel, rng, length=1.0, bright=1.0, dur=None):
    """Cast brass bell (ship's bell / buoy bell).  f_nominal is the strike-note.
    `length` scales decay times.  Partials are split into beating doublets."""
    sc = length * (880.0 / f_nominal) ** 0.35
    total = min(max(BELL_T60) * sc * 0.75, 12.0) if dur is None else dur
    n = ns(total)
    freqs, amps, t60s, phs = [], [], [], []
    for r, a, d in zip(BELL_RATIOS, BELL_AMPS, BELL_T60):
        ff = f_nominal * r * (1 + rng.normal(0, 0.002))
        if ff > 18000:
            continue
        a2 = a * (bright ** (math.log2(max(r, 0.25)) * 0.8))
        split = rng.uniform(0.4, 2.2) / ff  # relative split -> 0.4..2.2 Hz beats
        for s in (-0.5, 0.5):
            freqs.append(ff * (1 + s * split))
            amps.append(a2 * 0.5 * rng.uniform(0.8, 1.2))
            t60s.append(d * sc)
            phs.append(rng.uniform(0, TWO_PI))
    # clang: short inharmonic strike partials
    for r in (3.37, 4.53, 6.11, 7.3):
        ff = f_nominal * r * rng.uniform(0.98, 1.02)
        if ff < 18000:
            freqs.append(ff)
            amps.append(0.12 * vel * bright)
            t60s.append(0.12)
            phs.append(0.0)
    x = modal(freqs, amps, t60s, n, attack=0.0005, phases=phs)
    k = ns(0.01)
    clk = bp(rng.standard_normal(k), 3500, 0.8) * np.exp(-np.arange(k) / (0.0015 * SR)) * 0.25 * vel
    x[:k] += clk
    return x * amp_of(vel) * 0.5


# ============================================================================
# reeds & winds
# ============================================================================

def accordion_note(f, dur, vel, rng, reeds=((0.0, 1.0), (6.5, 0.7)), attack=0.045,
                   release=0.07, bright=1.0, swell=0.0, shake=0.0):
    """Free-reed accordion voice.  reeds: (cents, amp) per reed rank.
    swell > 0 adds a bellows crescendo over the note; shake adds bellows shake."""
    n = ns(dur + release + 0.01)
    t = tvec(n)
    g = ns(dur)
    a = attack * (1.25 - 0.45 * vel)
    env = np.ones(n)
    ka = t < a
    env[ka] = np.sin(0.5 * np.pi * t[ka] / a) ** 2
    if swell:
        env *= 1.0 + swell * np.clip(t / max(dur, 1e-3), 0, 1) - swell * 0.5
    if shake:
        env *= 1.0 + shake * np.sin(TWO_PI * 7.0 * t) ** 2 - shake * 0.5
    drift = 1.0 + 0.03 * smooth_noise(n, 2.5, rng, periodic=False)
    env *= drift
    if g < n:
        env[g:] *= np.exp(-6.9 * (t[g:] - t[g]) / release)  # -60 dB at the end
    wander = 1.0 + 0.0006 * smooth_noise(n, 1.5, rng, periodic=False)
    sig = np.zeros(n)
    for cents, amp in reeds:
        ff = f * 2 ** ((cents + rng.normal(0, 0.7)) / 1200.0)
        fr = ff * wander
        ph0 = rng.random()
        sig += amp * (0.6 * saw(fr, n, ph0) + 0.4 * pulse(fr, n, 0.29, ph0))
    # pressure-dependent brightness (reeds get brighter when pushed)
    cut = (1800 + 3800 * vel) * bright
    sig = lp(sig, min(cut, 9000), 0.6)
    # onset buzz
    kb = ns(0.03)
    sig[:kb] += bp(rng.standard_normal(kb), 2200, 1.0) * np.exp(-np.arange(kb) / (0.008 * SR)) * 0.15
    return sig * env * amp_of(vel) * 0.5


ACC_BODY = [("hp", 95, 0.7, 0), ("peak", 1250, 1.1, 1.5), ("peak", 2900, 2.0, 2.0),
            ("hs", 7000, 0.7, -2.5)]


def _pitch_curve(notes, n, t0, glide, scoop=0.0, slide_glide=None):
    """Per-sample midi pitch for a monophonic line.
    notes: list of dicts with t, dur, m, (slide)."""
    pitch = np.full(n, float(notes[0]["m"]))
    for i, nt in enumerate(notes):
        s = ns(nt["t"] - t0)
        e = ns(notes[i + 1]["t"] - t0) if i + 1 < len(notes) else n
        pitch[max(s, 0):e] = nt["m"]
    for i, nt in enumerate(notes):
        s = ns(nt["t"] - t0)
        if i == 0:
            prevm, gap = None, 1.0
        else:
            prev = notes[i - 1]
            prevm = prev["m"]
            gap = nt["t"] - (prev["t"] + prev["dur"])
        if prevm is not None and gap < 0.06 and prevm != nt["m"]:
            gl = (slide_glide if nt.get("slide") and slide_glide else glide)
            k = max(2, ns(gl))
            seg = prevm + (nt["m"] - prevm) * (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, k)))
            a = max(0, s - k // 3)
            b = min(n, a + k)
            pitch[a:b] = seg[:b - a]
        elif scoop and (prevm is None or gap >= 0.06):
            k = ns(0.05)
            b = min(n, s + k)
            if b > s:
                pitch[s:b] += -scoop * (1 - np.linspace(0, 1, b - s)) ** 2
    return pitch


def _gate_curve(notes, n, t0, att, rel, dip_depth, dip_len, legato_overlap=0.0):
    gate = np.zeros(n)
    level = np.zeros(n)
    for i, nt in enumerate(notes):
        s = max(0, ns(nt["t"] - t0))
        e = min(n, ns(nt["t"] + nt["dur"] + legato_overlap - t0))
        gate[s:e] = 1.0
        level[s:e] = nt.get("vel", 0.8)
    # asymmetric smoothing
    ca = math.exp(-1.0 / (att * SR))
    cr = math.exp(-1.0 / (rel * SR))
    env = _asym(gate * np.maximum(level, 1e-3), ca, cr)
    # tongue / bow-change dips on re-articulated notes
    for i, nt in enumerate(notes[1:], start=1):
        prev = notes[i - 1]
        gap = nt["t"] - (prev["t"] + prev["dur"])
        if gap < 0.06 and not nt.get("slur"):
            s = ns(nt["t"] - t0)
            k = ns(dip_len)
            a = max(0, s - k // 2)
            b = min(n, a + k)
            w = 1 - dip_depth * np.sin(np.linspace(0, np.pi, b - a)) ** 2
            env[a:b] *= w
    return env


def _asym(x, ca, cr):
    from dsp import _smooth_gr
    return _smooth_gr(x, ca, cr)


def whistle_line(notes, rng, vib_depth=0.13, vib_rate=5.6, breath=1.0):
    """Tin whistle phrase. notes: list of dicts {t, dur, m, vel, slur?, slide?}.
    Returns (t_start, mono)."""
    t0 = notes[0]["t"] - 0.08
    t_end = notes[-1]["t"] + notes[-1]["dur"] + 0.35
    n = ns(t_end - t0)
    t = tvec(n)
    pitch = _pitch_curve(notes, n, t0, glide=0.014, scoop=0.25, slide_glide=0.09)
    # vibrato on long notes, delayed onset
    depth = np.zeros(n)
    for nt in notes:
        if nt["dur"] > 0.32:
            s = ns(nt["t"] - t0 + 0.2)
            e = ns(nt["t"] + nt["dur"] - t0)
            if e > s:
                ramp = np.clip(np.arange(e - s) / (0.3 * SR), 0, 1)
                depth[s:e] = np.maximum(depth[s:e], ramp * vib_depth)
    rate = vib_rate * (1 + 0.06 * smooth_noise(n, 0.7, rng, periodic=False))
    vib = np.sin(TWO_PI * phase_cycles(rate, n))
    jitter = 0.012 * smooth_noise(n, 9.0, rng, periodic=False)
    m = pitch + depth * vib + jitter
    f0 = midi_hz(m)
    env = _gate_curve(notes, n, t0, att=0.018, rel=0.05, dip_depth=0.75, dip_len=0.035)
    ph = phase_cycles(f0, n)
    tone = (np.sin(TWO_PI * ph) + 0.10 * np.sin(2 * TWO_PI * ph + 0.3)
            + 0.035 * np.sin(3 * TWO_PI * ph + 1.1) + 0.012 * np.sin(4 * TWO_PI * ph))
    # breath: hiss + noise focused around the tone
    wn = rng.standard_normal(n)
    hiss = svf(wn, 3800.0, 0.7, "bp") * 0.05 * breath
    airy = svf(wn, f0 * 1.0, 6.0, "bp") * 0.22 * breath
    sig = (tone + hiss + airy) * env
    # chiff on tongued onsets
    for i, nt in enumerate(notes):
        if i == 0 or not nt.get("slur"):
            s = ns(nt["t"] - t0)
            k = ns(0.025)
            if s + k < n:
                ch = bp(rng.standard_normal(k), 2.5 * midi_hz(nt["m"]), 1.2)
                sig[s:s + k] += ch * np.exp(-np.arange(k) / (0.006 * SR)) * 0.25 * nt.get("vel", 0.8)
    return t0, sig * 0.5


def fiddle_line(notes, rng, vib_depth=0.22, vib_rate=5.9, bright=1.0):
    """Bowed fiddle phrase (band-limited saw at 2x oversampling, bow noise,
    dynamic brightness).  Body formants are applied by FIDDLE_BODY at track
    level.  Returns (t_start, mono)."""
    t0 = notes[0]["t"] - 0.1
    t_end = notes[-1]["t"] + notes[-1]["dur"] + 0.85
    n = ns(t_end - t0)
    pitch = _pitch_curve(notes, n, t0, glide=0.04, scoop=0.12, slide_glide=0.16)
    depth = np.zeros(n)
    for nt in notes:
        if nt["dur"] > 0.28:
            s = ns(nt["t"] - t0 + 0.16)
            e = ns(nt["t"] + nt["dur"] - t0)
            if e > s:
                ramp = np.clip(np.arange(e - s) / (0.35 * SR), 0, 1)
                depth[s:e] = np.maximum(depth[s:e], ramp * vib_depth)
    rate = vib_rate * (1 + 0.07 * smooth_noise(n, 0.6, rng, periodic=False))
    vib = np.sin(TWO_PI * phase_cycles(rate, n))
    jitter = 0.02 * smooth_noise(n, 14.0, rng, periodic=False)
    m = pitch + depth * vib + jitter
    env = _gate_curve(notes, n, t0, att=0.055, rel=0.12, dip_depth=0.45, dip_len=0.05,
                      legato_overlap=0.0)
    # bow pressure swell on long notes
    swell = np.ones(n)
    for nt in notes:
        if nt["dur"] > 0.5:
            s = ns(nt["t"] - t0)
            e = min(n, ns(nt["t"] + nt["dur"] - t0))
            k = e - s
            if k > 0:
                swell[s:e] *= 0.9 + 0.2 * np.sin(np.linspace(0, np.pi, k)) ** 1.5
    env = env * swell * (1 + 0.025 * smooth_noise(n, 25.0, rng, periodic=False))
    # oscillator at 2x
    from scipy.signal import resample_poly
    f2 = np.repeat(midi_hz(m), 2) * 0.5  # per-sample at 2x rate -> halve increment
    # saw() assumes SR; at 2x rate the per-sample increment halves -> pass f/2
    osc2 = 0.75 * saw(f2, 2 * n, rng.random()) + 0.25 * pulse(f2, 2 * n, 0.18, rng.random())
    osc = resample_poly(osc2, 1, 2)[:n]
    cut = (1600 + 6200 * env / (np.max(env) + 1e-9)) * bright
    sig = svf(osc, cut, 0.6, "lp") * env
    wn = rng.standard_normal(n)
    bow = svf(wn, 2600.0, 0.6, "bp") * env * 0.06
    sig = sig + bow
    for i, nt in enumerate(notes):
        if i == 0 or not nt.get("slur"):
            s = ns(nt["t"] - t0)
            k = ns(0.04)
            if s + k < n:
                sc = bp(rng.standard_normal(k), 3200, 0.8) * np.sin(np.linspace(0, np.pi, k)) * 0.05
                sig[s:s + k] += sc * nt.get("vel", 0.8)
    return t0, sig * 0.45


FIDDLE_BODY = [("hp", 185, 0.7, 0), ("peak", 280, 3.0, 4.0), ("peak", 465, 3.0, 3.0),
               ("peak", 560, 3.0, 2.0), ("peak", 1500, 1.4, -3.0), ("peak", 2550, 1.3, 5.0),
               ("peak", 3500, 2.0, 2.0), ("lp", 7500, 0.7, 0), ("lp", 9000, 0.7, 0)]


# ============================================================================
# bowed ensemble
# ============================================================================

def strings_note(f, dur, vel, rng, voices=4, attack=0.25, release=0.35, vib=0.12,
                 detune=7.0, bright=1.0, spread=0.7, trem=0.0):
    """Section strings (cello/bass/violas).  Returns STEREO (2, n)."""
    n = ns(dur + release + 0.01)
    t = tvec(n)
    g = ns(dur)
    env = np.ones(n)
    a = max(attack, 0.005)
    ka = t < a
    env[ka] = np.sin(0.5 * np.pi * t[ka] / a) ** 2
    if g < n:
        env[g:] *= np.exp(-6.9 * (t[g:] - t[g]) / release)  # -60 dB at the end
    if trem:
        env *= 1 - trem * (0.5 + 0.5 * np.sin(TWO_PI * 11.0 * t + rng.random() * 6))
    out = np.zeros((2, n))
    for v in range(voices):
        cents = (v - (voices - 1) / 2) / max(1, (voices - 1) / 2) * detune + rng.normal(0, 1.5)
        rate = rng.uniform(4.6, 6.0)
        dep = vib * rng.uniform(0.7, 1.2)
        onset = np.clip((t - 0.15) / 0.4, 0, 1)
        m = 12 * math.log2(f / 440.0) + 69 + cents / 100.0
        mm = m + dep * onset * np.sin(TWO_PI * rate * t + rng.random() * 6) \
            + 0.015 * smooth_noise(n, 10.0, rng, periodic=False)
        fv = midi_hz(mm)
        osc = saw(fv, n, rng.random())
        p = spread * ((v / max(1, voices - 1)) * 2 - 1) if voices > 1 else 0.0
        out += pan(osc, p)
    cut = (900 + 2600 * vel) * bright
    out = lp(out, min(cut, 8000), 0.6)
    out = lp(out, min(cut * 1.6, 12000), 0.7)
    out *= env * amp_of(vel) * (0.5 / math.sqrt(voices))
    wn = rng.standard_normal(n)
    bow = bp(wn, 2000, 0.7) * env * 0.03 * amp_of(vel)
    out += np.stack([bow, bow])
    return out


CELLO_BODY = [("hp", 45, 0.7, 0), ("peak", 210, 1.5, 2.5), ("peak", 420, 1.0, -2.0),
              ("peak", 620, 2.0, 2.0), ("peak", 1250, 1.5, -2.0), ("peak", 2400, 1.5, 2.0)]


# ============================================================================
# percussion
# ============================================================================

def timpani(f, vel, rng, length=1.0):
    p = f
    ratios = [1.0, 1.504, 1.742, 2.0, 2.245, 2.494, 2.8, 2.98]
    amps = [1.0, 0.55, 0.25, 0.32, 0.18, 0.12, 0.08, 0.05]
    t60s = [3.2, 2.0, 1.5, 1.3, 1.0, 0.8, 0.6, 0.5]
    b = 0.35 + 0.65 * vel
    amps = [a * (b ** i) for i, a in enumerate(amps)]
    n = ns(3.5 * length)
    t = tvec(n)
    fmul = 1.0 + 0.025 * vel * np.exp(-t / 0.07)
    x = modal_tv([p * r for r in ratios], amps, [d * length for d in t60s], n, fmul,
                 attack=0.0015, phases=rng.uniform(0, 1, len(ratios)))
    thud = modal_tv([p * 0.62], [1.1], [0.3], n, fmul, attack=0.002)
    mallet = lp(rng.standard_normal(n), 700 + 900 * vel) * np.exp(-t / 0.012) * 0.6
    x = x + thud + mallet
    return x * amp_of(vel) * 0.33


def gran_cassa(vel, rng, f=48.0):
    n = ns(2.5)
    t = tvec(n)
    fmul = 1.0 + 0.35 * np.exp(-t / 0.04)
    x = modal_tv([f, f * 1.58, f * 2.13, f * 2.66], [1.0, 0.5, 0.3, 0.15], [1.6, 0.8, 0.5, 0.3],
                 n, fmul, attack=0.003, phases=rng.uniform(0, 1, 4))
    beat = lp(rng.standard_normal(n), 500) * np.exp(-t / 0.02) * 0.5
    return (x + beat) * amp_of(vel) * 0.65


def bodhran(vel, rng, f=82.0, tone=0.0):
    """Frame drum.  tone 0 = open bass, 1 = top-end (higher, drier)."""
    n = ns(0.9)
    t = tvec(n)
    ff = f * (1 + 0.6 * tone) * rng.uniform(0.985, 1.015)
    fmul = 1.0 + 0.07 * vel * np.exp(-t / 0.03)
    dec = 1.0 - 0.6 * tone
    x = modal_tv([ff, ff * 1.59, ff * 2.14, ff * 2.65, ff * 3.16],
                 [1.0, 0.55, 0.35, 0.22, 0.12],
                 [0.5 * dec, 0.25 * dec, 0.17 * dec, 0.12 * dec, 0.09 * dec], n, fmul,
                 attack=0.0012, phases=rng.uniform(0, 1, 5))
    k = ns(0.012)
    stick = bp(rng.standard_normal(k), 2200, 0.9) * np.exp(-np.arange(k) / (0.0018 * SR)) * 0.45
    x[:k] += stick
    return x * amp_of(vel) * 0.5


def brush_tap(vel, rng):
    n = ns(0.35)
    t = tvec(n)
    nz = rng.standard_normal(n)
    wires = bp(hp(nz, 1800), 4500, 0.6) * np.exp(-t / 0.07)
    head = sine(195.0 * (1 + 0.05 * np.exp(-t / 0.01)), n) * np.exp(-t / 0.04) * 0.35
    att = np.clip(t / 0.002, 0, 1)
    return (wires + head) * att * amp_of(vel) * 0.55


def brush_sweep(dur, vel, rng):
    n = ns(dur)
    t = tvec(n)
    nz = rng.standard_normal(n)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    bristle = 1 + 0.5 * smooth_noise(n, 40.0, rng, periodic=False)
    x = bp(hp(nz, 1500), 3800, 0.5) * env * bristle
    return x * amp_of(vel) * 0.35


def shaker(vel, rng, length=0.11):
    n = ns(length + 0.06)
    t = tvec(n)
    env = np.clip(t / 0.012, 0, 1) ** 2 * np.exp(-np.maximum(t - 0.012, 0) / (length * 0.45))
    grains = (rng.random(n) < 0.25) * rng.standard_normal(n)
    x = bp(hp(grains + 0.4 * rng.standard_normal(n), 4000), 7500, 0.8) * env
    return x * amp_of(vel) * 0.8


def woodblock(vel, rng, f=950.0):
    n = ns(0.25)
    x = modal([f, f * 2.57, f * 4.1], [1.0, 0.35, 0.12], [0.09, 0.05, 0.03], n,
              attack=0.0004, phases=rng.uniform(0, 1, 3))
    k = ns(0.004)
    x[:k] += hp(rng.standard_normal(k), 3000) * 0.2
    return x * amp_of(vel) * 0.6


def triangle(vel, rng, f=1250.0, length=1.6):
    n = ns(length)
    rs = [1, 2.71, 4.4, 5.8, 7.6, 9.9]
    x = modal([f * r for r in rs], [0.6, 0.8, 0.6, 0.45, 0.3, 0.2],
              [length, length * 0.9, length * 0.8, length * 0.6, length * 0.5, length * 0.4],
              n, attack=0.0002, phases=rng.uniform(0, 6, len(rs)))
    return x * amp_of(vel) * 0.5


# ============================================================================
# textures
# ============================================================================

def sea_wash(dur, rng, swells=(0.0,), swell_len=5.0, level=1.0):
    """Gentle surf/wash for musical intros: shaped noise swells."""
    n = ns(dur)
    t = tvec(n)
    env = np.zeros(n)
    for s in swells:
        x = (t - s) / swell_len
        m = (x > 0) & (x < 1)
        env[m] += np.sin(np.pi * x[m]) ** 2 * (1 - 0.4 * x[m])
    nz = rng.standard_normal(n)
    cut = 500 + 2500 * env
    body = svf(nz, cut, 0.6, "lp")
    fizz = hp(rng.standard_normal(n), 3000) * env ** 2 * 0.25
    return (body * (0.15 + env) + fizz) * level * 0.3


def shimmer(f, dur, vel, rng, notes=6, spread=0.06):
    """Fairy-dust shimmer: rapid celesta/glock grace cluster upwards from f."""
    out = np.zeros(ns(dur + 3.0))
    steps = [0, 4, 7, 12, 16, 19, 24, 28]
    for i in range(notes):
        ff = f * 2 ** (steps[i % len(steps)] / 12.0)
        x = glock(ff, 0.3, vel * (0.6 + 0.4 * rng.random()), rng) if i % 2 else \
            celesta(ff, 0.3, vel * 0.8, rng)
        s = ns(i * spread + rng.uniform(0, 0.01))
        e = min(out.size, s + x.size)
        out[s:e] += x[:e - s]
    return out
