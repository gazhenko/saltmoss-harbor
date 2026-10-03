"""Saltmoss Harbor - shared synthesis / DSP library.

Everything here is original synthesis: oscillators, filters, physical models,
reverb, dynamics, IO and measurement. No samples are used anywhere.

Conventions
-----------
* Sample rate SR = 44100.
* Mono signals are 1-D float64 arrays; stereo signals are shape (2, n).
* Times are seconds unless a name says otherwise.
"""
from __future__ import annotations

import json
import math
import os
import re
from functools import lru_cache

import numpy as np
import scipy.signal as sps
import scipy.ndimage as ndi
from numba import njit

SR = 44100
TWO_PI = 2.0 * np.pi


# ----------------------------------------------------------------------------
# basic helpers
# ----------------------------------------------------------------------------

def ns(t: float) -> int:
    """seconds -> samples"""
    return int(round(t * SR))


def db(x):
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-12))


def undb(d):
    return 10.0 ** (np.asarray(d) / 20.0)


def midi_hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]*)(-?\d+)$")
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def n2m(name: str) -> int:
    """'C4' -> 60, 'F#5' -> 78, 'Bb3' -> 58"""
    m = _NOTE_RE.match(name.strip())
    if not m:
        raise ValueError(f"bad note {name!r}")
    letter, acc, octv = m.groups()
    pc = _PC[letter.upper()] + acc.count("#") - acc.count("b")
    return 12 * (int(octv) + 1) + pc


def rng_for(*keys) -> np.random.Generator:
    """Deterministic RNG from any hashable keys (stable across runs)."""
    s = "|".join(str(k) for k in keys)
    h = 2166136261
    for ch in s.encode():
        h = ((h ^ ch) * 16777619) & 0xFFFFFFFF
    return np.random.default_rng(h)


def pad_to(x, n):
    if x.shape[-1] >= n:
        return x[..., :n]
    pad = [(0, 0)] * (x.ndim - 1) + [(0, n - x.shape[-1])]
    return np.pad(x, pad)


def mix_into(buf, sig, start):
    """Add sig into buf at sample index start (handles clipping at both ends)."""
    n = buf.shape[-1]
    m = sig.shape[-1]
    s0 = max(0, start)
    s1 = min(n, start + m)
    if s1 <= s0:
        return
    buf[..., s0:s1] += sig[..., s0 - start:s1 - start]


def fade(x, fin=0.0, fout=0.0):
    x = np.array(x, dtype=float, copy=True)
    n = x.shape[-1]
    a = min(ns(fin), n)
    b = min(ns(fout), n)
    if a > 0:
        x[..., :a] *= np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    if b > 0:
        x[..., n - b:] *= np.cos(np.linspace(0, np.pi / 2, b)) ** 2
    return x


def tvec(n):
    return np.arange(n) / SR


# ----------------------------------------------------------------------------
# envelopes
# ----------------------------------------------------------------------------

def env_points(points, n):
    """Piecewise linear envelope through (time, value) points, n samples long."""
    ts = np.array([p[0] for p in points], dtype=float) * SR
    vs = np.array([p[1] for p in points], dtype=float)
    return np.interp(np.arange(n), ts, vs)


def env_adsr(n, a, d, s, r, gate):
    """ADSR with exponential-ish decay/release. gate in seconds."""
    t = tvec(n)
    env = np.zeros(n)
    a = max(a, 1e-4)
    g = max(gate, a)
    att = t < a
    env[att] = (t[att] / a)
    dec = (t >= a) & (t < g)
    env[dec] = s + (1 - s) * np.exp(-(t[dec] - a) / max(d, 1e-4))
    # level at gate
    lg = 1.0 if g <= a else s + (1 - s) * math.exp(-(g - a) / max(d, 1e-4))
    rel = t >= g
    env[rel] = lg * np.exp(-(t[rel] - g) / max(r, 1e-4) * 3.0)
    return env


def env_perc(n, attack, t60, curve_attack=True):
    t = tvec(n)
    e = np.exp(-6.907755 * t / max(t60, 1e-4))
    if attack > 0:
        k = np.clip(t / attack, 0, 1)
        e *= (np.sin(k * np.pi / 2) ** 2) if curve_attack else k
    return e


def gate_release(sig, gate_s, rel_s):
    """Damp a decaying sound after gate_s with a release of rel_s (60 dB)."""
    n = sig.shape[-1]
    g = ns(gate_s)
    if g >= n:
        return sig
    e = np.ones(n)
    t = np.arange(n - g) / SR
    e[g:] = np.exp(-6.907755 * t / max(rel_s, 1e-3))
    out = sig * e
    end = min(n, g + ns(rel_s) + 1)
    return out[..., :end]


# ----------------------------------------------------------------------------
# noise & random curves
# ----------------------------------------------------------------------------

def white(n, rng):
    return rng.standard_normal(n)


def colored_noise(n, rng, slope_db_oct=-3.0, fmin=20.0, fmax=None, periodic=True):
    """Gaussian noise with a spectral slope (dB/octave); generated in the
    frequency domain so it is exactly periodic over n samples (seamless loops)."""
    spec = rng.standard_normal(n // 2 + 1) + 1j * rng.standard_normal(n // 2 + 1)
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = 1.0
    mag = (np.maximum(f, fmin) / 1000.0) ** (slope_db_oct / 6.0206)
    mag[0] = 0
    if fmax:
        mag *= 1.0 / np.sqrt(1 + (f / fmax) ** 8)
    x = np.fft.irfft(spec * mag, n)
    return x / (np.std(x) + 1e-12)


def shaped_noise(n, rng, freqs, gains_db):
    """Periodic noise with an arbitrary magnitude curve (interpolated in log-f)."""
    spec = rng.standard_normal(n // 2 + 1) + 1j * rng.standard_normal(n // 2 + 1)
    f = np.fft.rfftfreq(n, 1 / SR)
    lf = np.log10(np.maximum(f, 10.0))
    g = np.interp(lf, np.log10(freqs), gains_db)
    mag = undb(g)
    mag[0] = 0
    x = np.fft.irfft(spec * mag, n)
    return x / (np.std(x) + 1e-12)


def smooth_noise(n, rate_hz, rng, periodic=True):
    """Slow random curve, roughly in [-1, 1], with energy below rate_hz.
    Periodic over n samples when periodic=True."""
    if periodic:
        spec = rng.standard_normal(n // 2 + 1) + 1j * rng.standard_normal(n // 2 + 1)
        f = np.fft.rfftfreq(n, 1 / SR)
        spec *= np.exp(-(f / max(rate_hz, 1e-3)) ** 2)
        spec[0] = 0
        x = np.fft.irfft(spec, n)
    else:
        k = max(4, int(n * rate_hz / SR) + 3)
        pts = rng.standard_normal(k)
        from scipy.interpolate import CubicSpline
        cs = CubicSpline(np.linspace(0, n, k), pts)
        x = cs(np.arange(n))
    x = x - np.mean(x)
    return x / (np.max(np.abs(x)) + 1e-12)


# ----------------------------------------------------------------------------
# oscillators (band-limited)
# ----------------------------------------------------------------------------

def phase_cycles(freq, n, ph0=0.0):
    """Running phase in cycles (not wrapped) for scalar or per-sample frequency."""
    if np.isscalar(freq):
        return ph0 + np.arange(n) * (freq / SR)
    f = np.asarray(freq, dtype=float)[:n]
    ph = np.empty(n)
    ph[0] = ph0
    np.cumsum(f[:-1] / SR, out=ph[1:])
    ph[1:] += ph0
    return ph


def _polyblep(p, dt):
    out = np.zeros_like(p)
    m = p < dt
    t = p[m] / dt[m]
    out[m] = t + t - t * t - 1.0
    m2 = p > 1.0 - dt
    t2 = (p[m2] - 1.0) / dt[m2]
    out[m2] = t2 * t2 + t2 + t2 + 1.0
    return out


def saw(freq, n, ph0=0.0):
    """PolyBLEP sawtooth, range ~[-1, 1]."""
    ph = phase_cycles(freq, n, ph0)
    p = ph - np.floor(ph)
    if np.isscalar(freq):
        dt = np.full(n, float(freq) / SR)
    else:
        dt = np.asarray(freq, dtype=float)[:n] / SR
    return 2.0 * p - 1.0 - _polyblep(p, dt)


def pulse(freq, n, width=0.5, ph0=0.0):
    """PolyBLEP pulse (difference of two saws), zero-mean."""
    a = saw(freq, n, ph0)
    b = saw(freq, n, ph0 + width)
    return 0.5 * (a - b)  # levels -width / 1-width: already zero-mean


def sine(freq, n, ph0=0.0):
    return np.sin(TWO_PI * phase_cycles(freq, n, ph0))


def additive(freq, n, amps, ph0=None, fmax=18000.0, rng=None):
    """Sum of harmonics k*freq with amplitudes amps[k-1]; harmonics fade out
    smoothly as they approach fmax (alias-free)."""
    ph = phase_cycles(freq, n, 0.0)
    f = np.asarray(freq, dtype=float)
    out = np.zeros(n)
    for k, a in enumerate(amps, start=1):
        if a == 0:
            continue
        fk = f * k
        if np.isscalar(freq) or f.ndim == 0:
            if fk >= fmax:
                break
            w = 1.0
        else:
            if np.min(fk) >= fmax:
                break
            w = np.clip((fmax - fk) / (0.1 * fmax), 0, 1)
        p0 = 0.0 if ph0 is None else ph0[k - 1]
        out += a * w * np.sin(TWO_PI * (k * ph + p0))
    return out


# ----------------------------------------------------------------------------
# filters
# ----------------------------------------------------------------------------

def _rbj(kind, f0, q=0.7071, gain_db=0.0):
    f0 = float(np.clip(f0, 5.0, SR * 0.49))
    A = 10 ** (gain_db / 40.0)
    w0 = TWO_PI * f0 / SR
    cw, sw = math.cos(w0), math.sin(w0)
    alpha = sw / (2 * q)
    if kind == "lp":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "hp":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "bp":  # constant 0 dB peak gain
        b = [alpha, 0, -alpha]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "notch":
        b = [1, -2 * cw, 1]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "ap":
        b = [1 - alpha, -2 * cw, 1 + alpha]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "peak":
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]
        a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind in ("ls", "hs"):
        sq = 2 * math.sqrt(A) * alpha
        if kind == "ls":
            b = [A * ((A + 1) - (A - 1) * cw + sq), 2 * A * ((A - 1) - (A + 1) * cw),
                 A * ((A + 1) - (A - 1) * cw - sq)]
            a = [(A + 1) + (A - 1) * cw + sq, -2 * ((A - 1) + (A + 1) * cw),
                 (A + 1) + (A - 1) * cw - sq]
        else:
            b = [A * ((A + 1) + (A - 1) * cw + sq), -2 * A * ((A - 1) + (A + 1) * cw),
                 A * ((A + 1) + (A - 1) * cw - sq)]
            a = [(A + 1) - (A - 1) * cw + sq, 2 * ((A - 1) - (A + 1) * cw),
                 (A + 1) - (A - 1) * cw - sq]
    else:
        raise ValueError(kind)
    b = np.array(b) / a[0]
    a = np.array(a) / a[0]
    return np.concatenate([b, a])[None, :]


def sos_chain(specs):
    """specs: list of (kind, f0, q, gain_db) -> sos array."""
    return np.concatenate([_rbj(*s) for s in specs], axis=0)


def sosf(x, sos):
    return sps.sosfilt(sos, x, axis=-1)


def lp(x, f, q=0.7071, order=2):
    sos = np.concatenate([_rbj("lp", f, q)] * (order // 2), axis=0)
    return sps.sosfilt(sos, x, axis=-1)


def hp(x, f, q=0.7071, order=2):
    sos = np.concatenate([_rbj("hp", f, q)] * (order // 2), axis=0)
    return sps.sosfilt(sos, x, axis=-1)


def bp(x, f, q=1.0):
    return sps.sosfilt(_rbj("bp", f, q), x, axis=-1)


def peak(x, f, gain_db, q=1.0):
    return sps.sosfilt(_rbj("peak", f, q, gain_db), x, axis=-1)


def lshelf(x, f, gain_db, q=0.7071):
    return sps.sosfilt(_rbj("ls", f, q, gain_db), x, axis=-1)


def hshelf(x, f, gain_db, q=0.7071):
    return sps.sosfilt(_rbj("hs", f, q, gain_db), x, axis=-1)


def eq(x, specs):
    """Apply a list of (kind, f0, q, gain_db) biquads."""
    if not specs:
        return x
    return sps.sosfilt(sos_chain(specs), x, axis=-1)


def onepole_lp(x, f):
    a = math.exp(-TWO_PI * f / SR)
    return sps.lfilter([1 - a], [1, -a], x, axis=-1)


def onepole_hp(x, f):
    a = math.exp(-TWO_PI * f / SR)
    return sps.lfilter([(1 + a) / 2, -(1 + a) / 2], [1, -a], x, axis=-1)


def dc_block(x, f=8.0):
    return onepole_hp(x, f)


@njit(cache=True)
def _svf_tv(x, fc, q, mode):
    n = x.shape[0]
    y = np.empty(n)
    ic1 = 0.0
    ic2 = 0.0
    k = 1.0 / q
    for i in range(n):
        f = fc[i]
        if f < 10.0:
            f = 10.0
        if f > 20000.0:
            f = 20000.0
        g = math.tan(math.pi * f / 44100.0)
        a1 = 1.0 / (1.0 + g * (g + k))
        a2 = g * a1
        a3 = g * a2
        v3 = x[i] - ic2
        v1 = a1 * ic1 + a2 * v3
        v2 = ic2 + a2 * ic1 + a3 * v3
        ic1 = 2.0 * v1 - ic1
        ic2 = 2.0 * v2 - ic2
        if mode == 0:
            y[i] = v2
        elif mode == 1:
            y[i] = v1 * k  # unity-peak bandpass
        else:
            y[i] = x[i] - k * v1 - v2
    return y


def svf(x, fc, q=0.7071, mode="lp"):
    """Time-varying state-variable filter (TPT). fc may be scalar or per-sample."""
    x = np.ascontiguousarray(x, dtype=float)
    fc = np.broadcast_to(np.asarray(fc, dtype=float), x.shape).copy()
    m = {"lp": 0, "bp": 1, "hp": 2}[mode]
    return _svf_tv(x, fc, float(q), m)


# ----------------------------------------------------------------------------
# physical / modal models
# ----------------------------------------------------------------------------

def modal(freqs, amps, t60s, n, rng=None, attack=0.0, phases=None):
    """Bank of exponentially-decaying sinusoids (struck objects)."""
    t = tvec(n)
    out = np.zeros(n)
    for i, (f, a, d) in enumerate(zip(freqs, amps, t60s)):
        if f <= 0 or f >= SR * 0.45 or a == 0:
            continue
        ph = 0.0 if phases is None else phases[i]
        out += a * np.exp(-6.907755 * t / d) * np.sin(TWO_PI * f * t + ph)
    if attack > 0:
        k = np.clip(t / attack, 0, 1)
        out *= np.sin(k * np.pi / 2) ** 2
    return out


def modal_tv(freqs, amps, t60s, n, fmul, attack=0.0, phases=None):
    """Modal bank where all frequencies follow a per-sample multiplier fmul."""
    t = tvec(n)
    out = np.zeros(n)
    base = phase_cycles(fmul, n)  # integral of fmul (cycles at 1 Hz)
    for i, (f, a, d) in enumerate(zip(freqs, amps, t60s)):
        if f <= 0 or f >= SR * 0.45 or a == 0:
            continue
        ph = 0.0 if phases is None else phases[i]
        out += a * np.exp(-6.907755 * t / d) * np.sin(TWO_PI * f * base + ph)
    if attack > 0:
        k = np.clip(t / attack, 0, 1)
        out *= np.sin(k * np.pi / 2) ** 2
    return out


def resonate(x, freqs, t60s, gains):
    """Run an excitation through a bank of two-pole resonators (sum)."""
    out = np.zeros_like(x, dtype=float)
    for f, d, g in zip(freqs, t60s, gains):
        if f >= SR * 0.45:
            continue
        r = math.exp(-6.907755 / (d * SR))
        w = TWO_PI * f / SR
        a = [1.0, -2 * r * math.cos(w), r * r]
        b = [(1 - r * r) * 0.5, 0, -(1 - r * r) * 0.5]
        out += g * sps.lfilter(b, a, x, axis=-1)
    return out


@njit(cache=True)
def _ks(n, excite, N, apc, lpa, g):
    """Karplus-Strong string: integer delay N, first-order allpass fine tuning
    coefficient apc, one-pole loop lowpass coefficient lpa, loop gain g."""
    size = N + 4
    buf = np.zeros(size)
    out = np.zeros(n)
    w = 0
    ap_x1 = 0.0
    ap_y1 = 0.0
    lp_y = 0.0
    m = excite.shape[0]
    for i in range(n):
        r = w - N
        if r < 0:
            r += size
        d = buf[r]
        # loop lowpass
        lp_y = (1.0 - lpa) * d + lpa * lp_y
        # fractional allpass
        ap = apc * lp_y + ap_x1 - apc * ap_y1
        ap_x1 = lp_y
        ap_y1 = ap
        v = g * ap
        if i < m:
            v += excite[i]
        buf[w] = v
        out[i] = v
        w += 1
        if w >= size:
            w = 0
    return out


def karplus(freq, dur, rng, t60=1.5, damp=0.4, pluck_pos=0.2, soft=0.5, excite_len=None):
    """Plucked string (Karplus-Strong with tuned allpass and loop lowpass).

    damp: loop one-pole coefficient (0 bright .. 0.8 dull)
    soft: excitation lowpass amount (0 sharp pick .. 0.9 soft finger)
    """
    n = ns(dur)
    w0 = TWO_PI * freq / SR
    # phase delay of one-pole lowpass at w0
    a = damp
    lp_pd = math.atan2(a * math.sin(w0), 1 - a * math.cos(w0)) / w0
    lp_mag = (1 - a) / math.sqrt(1 - 2 * a * math.cos(w0) + a * a)
    total = SR / freq - lp_pd
    N = int(math.floor(total - 0.15))
    frac = total - N  # in [0.15, 1.15)
    apc = math.sin((1 - frac) * w0 / 2) / math.sin((1 + frac) * w0 / 2)
    g = 10 ** (-3.0 / (t60 * freq)) / lp_mag
    g = min(g, 0.99995)
    L = excite_len or max(N, 2)
    ex = rng.uniform(-1, 1, L)
    if soft > 0:
        ex = sps.lfilter([1 - soft], [1, -soft], ex)
        ex = sps.lfilter([1 - soft], [1, -soft], ex)
    ex -= ex.mean()
    # pluck position comb
    k = max(1, int(round(pluck_pos * N)))
    ex2 = ex.copy()
    ex2[k:] -= ex[:-k]
    ex2 -= ex2.mean()
    ex2 /= np.max(np.abs(ex2)) + 1e-9
    return _ks(n, ex2, N, apc, a, g)


# ----------------------------------------------------------------------------
# reverb (convolution with synthetic, frequency-dependent decaying noise IR)
# ----------------------------------------------------------------------------

@lru_cache(maxsize=16)
def make_ir(rt60=2.0, predelay=0.02, hf_ratio=0.35, lf_ratio=1.15, er_level=0.6,
            er_span=0.07, diffusion=0.025, width=1.0, seed=7, bright=1.0):
    """Synthesise a stereo room impulse response.

    The late tail is Gaussian noise split into log-spaced bands (perfect-
    reconstruction cosine masks); each band decays with its own RT60
    (longer lows, shorter highs).  Early reflections are sparse taps.
    """
    rng = np.random.default_rng(seed)
    n_tail = ns(rt60 * 1.25)
    t = np.arange(n_tail) / SR
    centers = np.geomspace(63, 16000, 9)
    rts = np.interp(np.log10(centers), np.log10([125, 1000, 8000]),
                    [rt60 * lf_ratio, rt60, rt60 * hf_ratio])
    chans = []
    for c in range(2):
        noise = rng.standard_normal(n_tail)
        spec = np.fft.rfft(noise)
        f = np.fft.rfftfreq(n_tail, 1 / SR)
        lf = np.log2(np.maximum(f, 1.0))
        lc = np.log2(centers)
        tail = np.zeros(n_tail)
        K = len(centers)
        for i in range(K):
            # cosine crossover masks in log-frequency that sum to exactly one
            m = np.zeros_like(lf)
            if i == 0:
                m[lf <= lc[0]] = 1.0
            else:
                lo, hi = lc[i - 1], lc[i]
                sel = (lf > lo) & (lf <= hi)
                m[sel] = np.sin(0.5 * np.pi * (lf[sel] - lo) / (hi - lo)) ** 2
            if i == K - 1:
                m[lf > lc[-1]] = 1.0
            else:
                lo, hi = lc[i], lc[i + 1]
                sel = (lf > lo) & (lf <= hi)
                m[sel] = np.cos(0.5 * np.pi * (lf[sel] - lo) / (hi - lo)) ** 2
            band = np.fft.irfft(spec * m, n_tail)
            tail += band * np.exp(-6.907755 * t / rts[i])
        # diffusion build-up
        tail *= 1.0 - np.exp(-t / max(diffusion, 1e-3))
        chans.append(tail)
    tail = np.stack(chans)
    # stereo width: blend towards mono
    mid = tail.mean(axis=0)
    tail = mid + width * (tail - mid)
    if bright != 1.0:
        tail = hshelf(tail, 4000, 6 * math.log2(bright))
    tail /= np.sqrt(np.mean(np.sum(tail ** 2, axis=1)))
    pre = ns(predelay)
    ir = np.zeros((2, pre + n_tail + ns(er_span)))
    ir[:, pre:pre + n_tail] += tail
    # early reflections
    k = 14
    times = np.sort(rng.uniform(0.004, er_span, k))
    for i, tt in enumerate(times):
        amp = er_level * 0.35 * (1 - tt / (er_span * 1.6)) * rng.uniform(0.5, 1.0)
        side = rng.uniform(-1, 1)
        idx = ns(predelay * 0.35 + tt)
        ir[0, idx] += amp * math.sqrt(0.5 * (1 - side))
        ir[1, idx] += amp * math.sqrt(0.5 * (1 + side))
    ir = lp(ir, 9000 * bright)
    return ir


def reverb(x, ir, wet=0.25, hp_send=180.0, lp_return=None):
    """Convolve stereo (or mono) x with a stereo IR. Returns the WET signal only,
    length n + len(ir) - 1."""
    if x.ndim == 1:
        x = np.stack([x, x])
    s = hp(x, hp_send) if hp_send else x
    out = np.stack([sps.oaconvolve(s[c], ir[c]) for c in range(2)])
    if lp_return:
        out = lp(out, lp_return)
    return out * wet


# ----------------------------------------------------------------------------
# stereo helpers
# ----------------------------------------------------------------------------

def pan(mono, p=0.0):
    """Constant-power pan; p in [-1 (left), 1 (right)]."""
    th = (p + 1) * np.pi / 4
    return np.stack([mono * math.cos(th), mono * math.sin(th)])


def width(st, w):
    mid = 0.5 * (st[0] + st[1])
    side = 0.5 * (st[0] - st[1])
    return np.stack([mid + w * side, mid - w * side])


def to_stereo(x):
    return x if x.ndim == 2 else np.stack([x, x])


# ----------------------------------------------------------------------------
# dynamics & colour
# ----------------------------------------------------------------------------

def tape(x, drive=1.6, bias=0.06):
    """Gentle tape-ish saturation (memoryless, unity small-signal gain) with a
    touch of asymmetry for warm even harmonics."""
    tb = math.tanh(drive * bias)
    g0 = drive * (1 - tb * tb)
    return (np.tanh(drive * (x + bias)) - tb) / g0


def limiter(x, ceiling_db=-1.0, lookahead_ms=2.0, release_ms=120.0):
    """Look-ahead peak limiter. Guarantees |y| <= ceiling (before inter-sample
    peaks). Works on mono or stereo (linked)."""
    c = undb(ceiling_db)
    peakv = np.max(np.abs(x), axis=0) if x.ndim == 2 else np.abs(x)
    need = np.minimum(1.0, c / np.maximum(peakv, 1e-12))
    W = max(1, int(lookahead_ms * 1e-3 * SR))
    m = ndi.minimum_filter1d(need, 2 * W + 1, mode="nearest")
    s = ndi.uniform_filter1d(m, 2 * W + 1, mode="nearest")
    g = _release(s, math.exp(-1.0 / (release_ms * 1e-3 * SR)))
    g = np.minimum(g, need)  # safety
    return x * g, g


@njit(cache=True)
def _release(target, rc):
    n = target.shape[0]
    y = np.empty(n)
    v = 1.0
    for i in range(n):
        t = target[i]
        v = 1.0 - (1.0 - v) * rc  # recover towards 1
        if t < v:
            v = t
        y[i] = v
    return y


def compressor(x, thresh_db=-18, ratio=2.0, attack_ms=10, release_ms=150, knee_db=6):
    """Simple feed-forward RMS-ish compressor (linked stereo). Returns y."""
    sig = np.max(np.abs(x), axis=0) if x.ndim == 2 else np.abs(x)
    lvl = db(sig)
    over = lvl - thresh_db
    gr = np.where(over <= -knee_db / 2, 0.0,
                  np.where(over >= knee_db / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee_db / 2) ** 2 / (2 * knee_db)))
    gr = _smooth_gr(gr, math.exp(-1 / (attack_ms * 1e-3 * SR)), math.exp(-1 / (release_ms * 1e-3 * SR)))
    return x * undb(-gr)


@njit(cache=True)
def _smooth_gr(gr, ac, rc):
    n = gr.shape[0]
    y = np.empty(n)
    v = 0.0
    for i in range(n):
        t = gr[i]
        if t > v:
            v = t + (v - t) * ac
        else:
            v = t + (v - t) * rc
        y[i] = v
    return y


def circular(x, fn, pad_s=2.0):
    """Apply a stateful process to a loop so its state wraps seamlessly:
    process [tail, x, head] and keep the middle."""
    n = x.shape[-1]
    p = min(ns(pad_s), n)
    ext = np.concatenate([x[..., n - p:], x, x[..., :p]], axis=-1)
    y = fn(ext)
    return y[..., p:p + n]


def fold_loop(buf, pre_n, loop_n):
    """buf covers time [-pre, loop+tail). Fold pre-roll onto the loop end and
    the tail onto the loop start -> seamless loop of loop_n samples."""
    out = buf[..., pre_n:pre_n + loop_n].copy()
    tail = buf[..., pre_n + loop_n:]
    k = 0
    while tail.shape[-1] > 0:
        m = min(loop_n, tail.shape[-1])
        out[..., :m] += tail[..., :m]
        tail = tail[..., m:]
        k += 1
    pre = buf[..., :pre_n]
    if pre_n > 0:
        out[..., loop_n - pre_n:] += pre
    return out


# ----------------------------------------------------------------------------
# measurement
# ----------------------------------------------------------------------------

def lufs(x):
    import pyloudnorm as pyln
    meter = pyln.Meter(SR)
    data = x.T if x.ndim == 2 else x
    if data.shape[0] < ns(0.45):
        reps = int(math.ceil(ns(0.45) / max(1, data.shape[0])))
        data = np.concatenate([data] + [np.zeros_like(data)] * reps, axis=0)
    with np.errstate(divide="ignore"):
        v = meter.integrated_loudness(data)
    return float(v)


def lufs_loop(x):
    """Integrated loudness of a loop measured as it plays (two passes)."""
    return lufs(np.concatenate([x, x], axis=-1))


def peak_db(x):
    return float(db(np.max(np.abs(x))))


def true_peak_db(x):
    up = sps.resample_poly(x, 4, 1, axis=-1)
    return float(db(np.max(np.abs(up))))


def rms_db(x):
    return float(db(np.sqrt(np.mean(np.square(x)))))


def seam_report(x, win_s=0.05):
    """Loop seam metrics: RMS of first/last 50 ms, and the size of the
    wrap-around sample step relative to the signal's typical steps."""
    w = ns(win_s)
    first = x[..., :w]
    last = x[..., -w:]
    r1, r2 = rms_db(first), rms_db(last)
    d = np.abs(np.diff(x, axis=-1))
    jump = np.max(np.abs(x[..., 0] - x[..., -1]))
    p99 = float(np.percentile(d, 99.0))
    # local steps around the seam
    loc = np.max(np.abs(np.diff(np.concatenate([x[..., -w:], x[..., :w]], axis=-1), axis=-1)))
    return {"rms_first_db": round(r1, 2), "rms_last_db": round(r2, 2),
            "rms_diff_db": round(abs(r1 - r2), 2),
            "seam_step": float(jump), "p99_step": p99,
            "seam_ratio": float(jump / (p99 + 1e-12)),
            "local_max_step": float(loc)}


def sanity(x):
    return {"nan": bool(np.isnan(x).any() or np.isinf(x).any()),
            "dc": float(np.max(np.abs(np.mean(x, axis=-1)))),
            "clip": bool(np.max(np.abs(x)) >= 0.999)}


# ----------------------------------------------------------------------------
# finishing & IO
# ----------------------------------------------------------------------------

def normalize_peak(x, peak_target_db=-3.0):
    p = np.max(np.abs(x))
    if p <= 0:
        return x
    return x * undb(peak_target_db) / p


def normalize_lufs(x, target=-16.0, ceiling_db=-1.5, loop=False, max_iter=4):
    """Gain to target integrated loudness, then look-ahead limit to ceiling.
    For loops the limiter runs circularly so the seam stays clean."""
    y = x
    for _ in range(max_iter):
        L = lufs_loop(y) if loop else lufs(y)
        if not np.isfinite(L):
            return y
        y = y * undb(target - L)
        if loop:
            y = circular(y, lambda z: limiter(z, ceiling_db)[0], 0.5)
        else:
            y = limiter(y, ceiling_db)[0]
        L2 = lufs_loop(y) if loop else lufs(y)
        if abs(L2 - target) < 0.15:
            break
    return y


def trim_silence(x, thresh_db=-60.0, pad_start_s=0.0, pad_end_s=0.01, fade_end_s=0.005):
    a = np.max(np.abs(x), axis=0) if x.ndim == 2 else np.abs(x)
    thr = undb(thresh_db) * np.max(a)
    idx = np.where(a > thr)[0]
    if idx.size == 0:
        return x
    s = max(0, idx[0] - ns(pad_start_s))
    e = min(a.size, idx[-1] + ns(pad_end_s))
    y = x[..., s:e]
    return fade(y, 0.0, fade_end_s)


def tpdf_dither(x, bits=16, rng=None):
    rng = rng or np.random.default_rng(1234)
    q = 1.0 / (2 ** (bits - 1))
    return x + (rng.uniform(-0.5, 0.5, x.shape) + rng.uniform(-0.5, 0.5, x.shape)) * q


def write_wav(path, x, bits=16):
    import soundfile as sf
    os.makedirs(os.path.dirname(path), exist_ok=True)
    y = tpdf_dither(x, bits) if bits == 16 else x
    y = np.clip(y, -1.0, 32767 / 32768)
    data = y.T if y.ndim == 2 else y
    sf.write(path, data.astype(np.float32), SR, subtype="PCM_16" if bits == 16 else "FLOAT")


def write_ogg(path, x, quality=0.6):
    """OGG Vorbis via libsndfile; quality 0.6 == oggenc -q 6."""
    import soundfile as sf
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = np.ascontiguousarray((x.T if x.ndim == 2 else x).astype(np.float32))
    ch = 1 if data.ndim == 1 else data.shape[1]
    # libsndfile's Vorbis encoder crashes on very large single writes -> blocks
    with sf.SoundFile(path, "w", SR, ch, format="OGG", subtype="VORBIS",
                      compression_level=1.0 - quality) as f:
        for i in range(0, data.shape[0], 8192):
            f.write(data[i:i + 8192])


def read_audio(path):
    import soundfile as sf
    d, sr = sf.read(path, always_2d=True)
    assert sr == SR
    return d.T


def spectrogram_png(x, path, title=""):
    """Log-frequency spectrogram (+ RMS strip) for eyeballing arrangement
    density and balance."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    mono = x.mean(axis=0) if x.ndim == 2 else x
    nper = 4096 if mono.size > SR * 4 else 1024
    hop = max(nper // 4, int(mono.size / 2400))
    f, t, S = sps.spectrogram(mono, SR, nperseg=nper, noverlap=max(0, nper - hop), mode="magnitude")
    logf = np.geomspace(30, 18000, 360)
    Sl = np.empty((logf.size, S.shape[1]))
    for j in range(S.shape[1]):
        Sl[:, j] = np.interp(logf, f, S[:, j])
    Sdb = 20 * np.log10(Sl + 1e-9)
    Sdb -= Sdb.max()
    dur = mono.size / SR
    fig, axes = plt.subplots(2, 1, figsize=(16, 7), gridspec_kw={"height_ratios": [4, 1]})
    ax = axes[0]
    ax.imshow(Sdb, origin="lower", aspect="auto", vmin=-90, vmax=0, cmap="magma",
              extent=[0, dur, 0, logf.size])
    ticks = [50, 100, 200, 500, 1000, 2000, 5000, 10000]
    ax.set_yticks([np.argmin(np.abs(logf - v)) for v in ticks])
    ax.set_yticklabels([str(v) for v in ticks])
    ax.set_ylabel("Hz")
    ax.set_title(title)
    hop2 = max(1, ns(0.05))
    k = mono.size // hop2
    rms = np.sqrt(np.mean(mono[:k * hop2].reshape(k, hop2) ** 2, axis=1))
    axes[1].plot(np.arange(k) * hop2 / SR, 20 * np.log10(rms + 1e-9), lw=0.8)
    axes[1].set_ylim(-60, 0)
    axes[1].set_xlim(0, dur)
    axes[1].set_ylabel("RMS dB")
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=70)
    plt.close(fig)


def describe(path, x, kind, loop):
    """Manifest entry + diagnostics for a finished file (x = what was written)."""
    entry = {
        "file": os.path.basename(path),
        "kind": kind,
        "seconds": round(x.shape[-1] / SR, 3),
        "loop": bool(loop),
        "lufs": round(lufs_loop(x) if loop else lufs(x), 2),
        "peak_db": round(peak_db(x), 2),
    }
    diag = {"true_peak_db": round(true_peak_db(x), 2), **sanity(x)}
    if loop:
        diag.update(seam_report(x))
    return entry, diag


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def octave_bands(x):
    """Long-term average spectrum in octave bands (dB, relative to the 1 kHz band)."""
    mono = x.mean(axis=0) if x.ndim == 2 else x
    f, P = sps.welch(mono, SR, nperseg=8192)
    out = {}
    for c in (63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000):
        sel = (f >= c / math.sqrt(2)) & (f < c * math.sqrt(2))
        out[c] = 10 * math.log10(np.sum(P[sel]) + 1e-20)
    ref = out[1000]
    return {k: round(v - ref, 1) for k, v in out.items()}
