"""Saltmoss Harbor - SFX building blocks (water, wood, metal, creatures, weather).

All synthesis: noise, oscillators, modal resonators.  Mono unless stated.
"""
from __future__ import annotations

import math

import numpy as np
import scipy.signal as sps

import dsp
from dsp import SR, TWO_PI, ns, tvec, lp, hp, bp, peak, svf, smooth_noise, colored_noise


# ----------------------------------------------------------------------------
# generic helpers
# ----------------------------------------------------------------------------

def ad(n, attack, decay60, curve=1.0):
    """attack (s, sin^2) then exponential decay with the given 60 dB time."""
    t = tvec(n)
    e = np.exp(-6.907755 * np.maximum(t - attack, 0) / max(decay60, 1e-4))
    if attack > 0:
        k = np.clip(t / attack, 0, 1)
        e = e * np.sin(0.5 * np.pi * k) ** 2
    return e ** curve


def place(buf, sig, start, gain=1.0, wrap=False):
    """Add sig (mono or stereo) into buf at sample `start`.  With wrap=True the
    signal wraps around the end (seamless loops)."""
    if sig.ndim == 1 and buf.ndim == 2:
        sig = np.stack([sig, sig])
    sig = sig * gain
    n = buf.shape[-1]
    if not wrap:
        dsp.mix_into(buf, sig, start)
        return
    m = sig.shape[-1]
    while m > n:  # fold very long events
        sig = sig[..., :n] + np.pad(sig[..., n:], [(0, 0)] * (sig.ndim - 1) + [(0, max(0, 2 * n - m))])[..., :n]
        m = sig.shape[-1]
    idx = (start + np.arange(m)) % n
    buf[..., idx] += sig


def pan_st(x, p):
    return dsp.pan(x, p)


def modal_bank(x, freqs, amps, t60s):
    """Excite a bank of two-pole resonators; an impulse of 1 gives decaying
    sines of amplitude `amps` (unit-normalised modal synthesis)."""
    out = np.zeros(x.shape, dtype=float)
    for f, a, d in zip(freqs, amps, t60s):
        if f <= 0 or f >= SR * 0.45 or a == 0:
            continue
        r = math.exp(-6.907755 / (d * SR))
        w = TWO_PI * f / SR
        out += sps.lfilter([a * math.sin(w)], [1.0, -2 * r * math.cos(w), r * r], x, axis=-1)
    return out


def impulses(n, times, amps, width=0):
    x = np.zeros(n)
    for t, a in zip(times, amps):
        i = ns(t)
        if 0 <= i < n:
            x[i] += a
    if width > 1:
        x = np.convolve(x, np.hanning(width + 2)[1:-1], mode="same")
    return x


def glide_sine(f_curve, amp_env, ph0=0.0):
    ph = dsp.phase_cycles(f_curve, len(f_curve), ph0)
    return np.sin(TWO_PI * ph) * amp_env


def exp_curve(n, f0, f1, tau=None):
    """frequency curve from f0 approaching f1 exponentially (tau s) or linear-in-log over n."""
    t = tvec(n)
    if tau is None:
        return f0 * (f1 / f0) ** (t / max(t[-1], 1e-9))
    return f1 + (f0 - f1) * np.exp(-t / tau)


def norm(x, p=1.0):
    m = np.max(np.abs(x))
    return x * (p / m) if m > 0 else x


def mono_reverb(x, rt60=1.0, wet=0.2, predelay=0.01, hf_ratio=0.4, seed=3, er=0.6):
    ir = dsp.make_ir(rt60=rt60, predelay=predelay, hf_ratio=hf_ratio, er_level=er, seed=seed)
    w = dsp.reverb(x, ir, wet=wet, hp_send=120.0)
    out = np.zeros(w.shape[1])
    out[:x.shape[-1]] += x
    out += w.mean(axis=0)
    return out


def stereo_reverb(x, rt60=1.0, wet=0.2, predelay=0.01, hf_ratio=0.4, seed=3, er=0.6, width=1.0):
    ir = dsp.make_ir(rt60=rt60, predelay=predelay, hf_ratio=hf_ratio, er_level=er, seed=seed, width=width)
    xs = dsp.to_stereo(x)
    w = dsp.reverb(xs, ir, wet=wet, hp_send=120.0)
    out = np.zeros_like(w)
    out[:, :xs.shape[1]] += xs
    return out + w


def loop_reverb(x, rt60=1.0, wet=0.2, predelay=0.01, hf_ratio=0.4, seed=3, er=0.6, width=1.0):
    """Reverb for a loop buffer (stereo): wet tail wraps to the start."""
    ir = dsp.make_ir(rt60=rt60, predelay=predelay, hf_ratio=hf_ratio, er_level=er, seed=seed, width=width)
    n = x.shape[-1]
    w = dsp.reverb(dsp.to_stereo(x), ir, wet=wet, hp_send=120.0)
    return dsp.to_stereo(x) + dsp.fold_loop(w, 0, n)


def cfilter(x, fn, pad=1.0):
    """Stateful filter applied circularly (for loops)."""
    return dsp.circular(x, fn, pad)


# ----------------------------------------------------------------------------
# water
# ----------------------------------------------------------------------------

def bubble(rng, f, dur=0.04, rise=1.6, amp=1.0, attack=0.0007):
    """Minnaert-style bubble 'bloop': damped sine with upward glide."""
    n = max(8, ns(dur))
    t = tvec(n)
    fc = f * (1 + (rise - 1) * (1 - np.exp(-t / (dur * 0.45))))
    env = (1 - np.exp(-t / attack)) * np.exp(-t / (dur * 0.3))
    return glide_sine(fc, env, rng.random()) * amp


def droplets(rng, n, count, t0, span, f_lo=700, f_hi=2600, amp=0.3, decay=True, dur=(0.012, 0.04)):
    out = np.zeros(n)
    for i in range(count):
        t = t0 + span * (rng.random() ** 1.3 if decay else rng.random())
        a = amp * rng.uniform(0.3, 1.0) * ((1 - (t - t0) / (span + 1e-9)) ** 1.2 if decay else 1.0)
        b = bubble(rng, math.exp(rng.uniform(math.log(f_lo), math.log(f_hi))),
                   rng.uniform(*dur), rng.uniform(1.2, 2.2), a)
        place(out, b, ns(t))
    return out


def noise_burst(rng, n, attack, decay60, f_lo=None, f_hi=None, cut_from=None, cut_to=None, q=0.7):
    x = rng.standard_normal(n)
    if cut_from is not None:
        c = exp_curve(n, cut_from, cut_to)
        x = svf(x, c, q, "lp")
    if f_lo:
        x = hp(x, f_lo)
    if f_hi:
        x = lp(x, f_hi)
    return x * ad(n, attack, decay60)


def splash(rng, size=1.0, dur=None, bright=1.0):
    """Object entering water: slap + plunge + plume + droplet patter."""
    dur = dur or (0.6 + 1.2 * size)
    n = ns(dur + 0.3)
    t = tvec(n)
    out = np.zeros(n)
    # slap transient
    k = ns(0.03)
    out[:k] += hp(rng.standard_normal(k), 900) * np.exp(-np.arange(k) / (0.004 * SR)) * 0.9
    # plunge: low cavity bubble
    place(out, bubble(rng, 110 + 90 / size ** 0.5, 0.12 + 0.12 * size, 1.9, 0.9 * min(size, 1.5)), 0)
    # plume: broadband noise, closing lowpass
    pl = rng.standard_normal(n)
    cut = (1200 + 6500 * bright * np.exp(-t / (0.08 + 0.12 * size)))
    pl = svf(pl, cut, 0.8, "lp")
    pl = hp(pl, 250)
    env = ad(n, 0.006, 0.25 + 0.5 * size)
    out += pl * env * 0.8
    # fizz / foam
    fz = hp(rng.standard_normal(n), 3500) * ad(n, 0.02, 0.35 + 0.6 * size) * 0.18 * bright
    out += fz
    # droplets falling back
    out += droplets(rng, n, int(14 + 26 * size), 0.12, 0.4 + 0.7 * size,
                    f_lo=700, f_hi=3000, amp=0.22)
    return out


def slosh(rng, dur=0.5, fc=650.0, amp=1.0):
    n = ns(dur + 0.1)
    t = tvec(n)
    x = rng.standard_normal(n)
    c = fc * (0.7 + 0.6 * np.sin(np.pi * np.clip(t / dur, 0, 1)))
    x = svf(x, c, 1.2, "bp")
    x = lp(x, 2600, order=4) + hp(x, 2600) * 0.08  # water, not hiss
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.6
    return x * env * amp


def clop(rng, f=None, amp=1.0):
    """Hollow water knock against a piling."""
    f = f or rng.uniform(170, 330)
    n = ns(0.18)
    out = bubble(rng, f, rng.uniform(0.05, 0.09), rng.uniform(1.15, 1.5), 1.0, attack=0.003)
    out = np.pad(out, (0, max(0, n - out.size)))[:n]
    k = ns(0.05)
    tk = np.arange(k) / SR
    nz = lp(rng.standard_normal(k), 1100) * (1 - np.exp(-tk / 0.004)) * np.exp(-tk / 0.012) * 0.6
    out[:k] += nz
    exc = np.zeros(n)
    exc[0] = 1
    out += modal_bank(exc, [f * 1.4, f * 2.9], [0.25, 0.12], [0.06, 0.04])
    return out * amp


def lap_event(rng, amp=1.0):
    """Lapping against a piling: slosh + clop + a few bubbles."""
    dur = rng.uniform(0.35, 0.8)
    n = ns(dur + 0.4)
    out = np.zeros(n)
    place(out, slosh(rng, dur, rng.uniform(450, 900), 0.8), 0)
    if rng.random() < 0.8:
        place(out, clop(rng, amp=rng.uniform(0.5, 1.0)), ns(dur * rng.uniform(0.25, 0.55)))
    for _ in range(rng.integers(1, 5)):
        place(out, bubble(rng, rng.uniform(500, 1500), rng.uniform(0.015, 0.04), 1.6, rng.uniform(0.06, 0.2),
                          attack=0.002), ns(rng.uniform(0.1, dur + 0.2)))
    return out * amp


def csvf(x, fc, q=0.7071, mode="lp", pad_s=1.0):
    """Time-varying SVF applied circularly to a loop (fc per-sample or scalar)."""
    n = x.shape[-1]
    p = min(ns(pad_s), n)
    fc = np.broadcast_to(np.asarray(fc, dtype=float), (n,))
    xe = np.concatenate([x[n - p:], x, x[:p]])
    fe = np.concatenate([fc[n - p:], fc, fc[:p]])
    return svf(xe, fe, q, mode)[p:p + n]


def water_bed(n, rng, cut=800.0, swell_rate=0.12, depth=0.6, slope=-4.0, stereo=True):
    """Periodic gentle wash bed with slow swells (loopable)."""
    sw = smooth_noise(n, swell_rate, rng, periodic=True)
    env = 0.55 + 0.45 * depth * sw
    chans = []
    for c in range(2 if stereo else 1):
        x = colored_noise(n, rng, slope)
        cc = cut * (0.55 + 0.9 * np.clip(env, 0, 1.5))
        y = csvf(x, cc, 0.6, "lp") * env
        chans.append(dsp.circular(y, lambda z: hp(z, 75), 0.5))
    return np.stack(chans) if stereo else chans[0]


def wave_crash(rng, size=1.0):
    """Big breaking wave: building swell, impact boom, roar, foam fizz."""
    pre = 0.7 * size
    dur = pre + 2.8 * size
    n = ns(dur + 0.5)
    t = tvec(n)
    out = np.zeros(n)
    x = rng.standard_normal(n)
    # build-up curl
    up = np.clip(t / pre, 0, 1) ** 2.2
    after = np.exp(-np.maximum(t - pre, 0) / (0.35 * size))
    slow = np.exp(-np.maximum(t - pre, 0) / (0.9 * size))
    env = np.where(t < pre, 0.35 * up, (0.45 + 0.55 * after) * slow)
    cut = np.where(t < pre, 400 + 2600 * up, 1200 + 5000 * np.exp(-(t - pre) / (0.35 * size)))
    roar = svf(x, cut, 0.7, "lp") * env
    # attack swell into impact
    i0 = ns(pre)
    out += roar
    boom_n = n - i0
    tb = tvec(boom_n)
    boom = np.sin(TWO_PI * dsp.phase_cycles(55 + 40 * np.exp(-tb / 0.08), boom_n)) * np.exp(-tb / 0.3) * 0.35
    boom += lp(rng.standard_normal(boom_n), 180) * np.exp(-tb / 0.45) * 0.45
    out[i0:] += boom
    fz = hp(rng.standard_normal(n), 3000) * np.where(t < pre, 0, np.exp(-(t - pre) / (1.2 * size))) * 0.25
    grains = (rng.random(n) < 0.02) * rng.standard_normal(n)
    fz += hp(grains, 2500) * np.where(t < pre, 0, np.exp(-(t - pre) / (1.5 * size))) * 0.5
    out += fz
    out += np.pad(droplets(rng, n - i0, int(30 * size), 0.4, 2.0 * size, amp=0.12), (i0, 0))[:n]
    # the wash dies away exponentially (no cliff at the end), then a short safety fade
    t_tail = dur - 1.4 * size
    out *= np.exp(-np.maximum(t - t_tail, 0) / (0.32 * size))
    return dsp.fade(out, 0.0, 0.08)


# ----------------------------------------------------------------------------
# wind & weather
# ----------------------------------------------------------------------------

def wind(n, rng, center=600.0, q=0.6, gust_rate=0.08, gust=0.6, whistle=0.0, whistle_f=900.0,
         low=0.0, stereo=True):
    """Periodic wind bed with gusts; optional whistling resonance and low roar."""
    g = smooth_noise(n, gust_rate, rng, periodic=True)
    g2 = smooth_noise(n, gust_rate * 2.7, rng, periodic=True)
    level = np.clip(0.55 + gust * 0.45 * g + 0.15 * gust * g2, 0.05, 2.0)
    chans = []
    for c in range(2 if stereo else 1):
        x = colored_noise(n, rng, -3.0)
        fc = center * (0.6 + 0.7 * level)
        y = csvf(x, fc, q, "bp") * level
        if whistle:
            wf = whistle_f * (0.8 + 0.35 * level) * (1 + 0.04 * smooth_noise(n, 0.6, rng, periodic=True))
            y += csvf(x, wf, 18.0, "bp") * whistle * level ** 2.5
        if low:
            r = colored_noise(n, rng, -6.0)
            r = dsp.circular(r, lambda z: lp(z, 160), 1.0)
            y += r * low * level
        chans.append(y)
    return np.stack(chans) if stereo else chans[0]


def rain_bed(n, rng, density=900.0, hiss=0.6, stereo=True):
    """Loopable rain: dense tiny drops + hiss."""
    chans = []
    for c in range(2 if stereo else 1):
        k = int(density * n / SR)
        x = np.zeros(n)
        idx = rng.integers(0, n, k)
        np.add.at(x, idx, rng.uniform(-1, 1, k) * rng.random(k) ** 2)
        drops = dsp.circular(x, lambda z: bp(hp(z, 1500), 5200, 0.6), 0.2)
        h = colored_noise(n, rng, -1.5)
        h = dsp.circular(h, lambda z: bp(z, 4500, 0.5), 0.3)
        chans.append(drops * 1.2 + h * hiss * 0.25)
    return np.stack(chans) if stereo else chans[0]


def thunder(rng, dur=7.0, close=1.0):
    n = ns(dur)
    t = tvec(n)
    out = np.zeros(n)
    # crackle onset (close strikes)
    if close > 0:
        k = ns(0.35)
        cr = (rng.random(k) < 0.08) * rng.standard_normal(k)
        cr = hp(cr, 1200) * np.exp(-np.arange(k) / (0.07 * SR))
        out[:k] += cr * 1.2 * close
        # tearing ripping
        k2 = ns(0.6)
        tear = hp(rng.standard_normal(k2), 600) * (rng.random(k2) < 0.25)
        tear = lp(tear, 5000) * np.exp(-np.arange(k2) / (0.15 * SR))
        out[:k2] += tear * 0.6 * close
    # rumble: a main roll then several distinct later arrivals (echoes / branches)
    rum = colored_noise(n, rng, -7.0, periodic=False)
    env = np.zeros(n)
    first = 0.02 if close else 0.4
    arrivals = [(first, 1.0, 0.015 if close else 0.35, 1.3)]
    for a in np.sort(rng.uniform(0.9, dur * 0.6, 4)):
        arrivals.append((a, rng.uniform(0.35, 0.75) * (1 - a / dur), rng.uniform(0.08, 0.3), rng.uniform(0.5, 1.2)))
    for a, amp, rise, dec in arrivals:
        e = np.where(t < a, 0.0, (1 - np.exp(-(t - a) / rise)) * np.exp(-(t - a) / dec))
        env += amp * e
    env += 0.06 * np.exp(-t / (dur * 0.4))
    cut = 140 + (450 if close else 180) * np.exp(-t / 1.0)
    r = svf(rum, cut, 0.8, "lp") * env
    r += lp(rng.standard_normal(n), 60) * env * 0.6
    out += r * 1.4
    am = 1 + 0.35 * smooth_noise(n, 6.0, rng, periodic=False)
    return dsp.fade(out * am, 0.0, 1.2)


# ----------------------------------------------------------------------------
# wood
# ----------------------------------------------------------------------------

def stick_slip(rng, dur, rate_pts, freqs, t60s, amps, jitter=0.12, roughness=0.3, env_pts=None):
    """Creak: a stick-slip pulse train (rate in Hz following rate_pts) driving
    wood resonances."""
    n = ns(dur)
    rate = dsp.env_points(rate_pts, n)
    rate *= 1 + jitter * smooth_noise(n, 25.0, rng, periodic=False)
    ph = np.cumsum(rate / SR)
    idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0] + 1
    x = np.zeros(n)
    x[idx] = rng.uniform(1 - roughness, 1.0, idx.size) * np.sign(rng.uniform(-0.3, 1, idx.size))
    # each slip is a tiny smeared impulse
    x = np.convolve(x, np.hanning(5), mode="same")
    env = dsp.env_points(env_pts or [(0, 0), (0.08 * dur, 1), (0.85 * dur, 0.8), (dur, 0)], n)
    x *= env
    y = modal_bank(x, freqs, amps, t60s)
    y += hp(x, 2000) * 0.15
    return hp(y, 75, order=4)


def creak(rng, dur=1.0, base=60.0, top=160.0, scale=1.0, pitch=1.0):
    pts = [(0, base * rng.uniform(0.8, 1.2))]
    k = rng.integers(2, 4)
    for i in range(k):
        pts.append(((i + 1) / (k + 1) * dur, rng.uniform(base, top)))
    pts.append((dur, base * rng.uniform(0.7, 1.1)))
    fr = [f * pitch * rng.uniform(0.93, 1.07) for f in (310, 640, 1050, 1580, 2300)]
    return stick_slip(rng, dur, pts, fr, [0.05, 0.04, 0.03, 0.025, 0.02],
                      [1.0, 0.7, 0.5, 0.3, 0.2]) * scale


def wood_thump(rng, freqs, t60s, amps, click=0.3, soft=0.0015, n_s=0.4):
    """Struck wooden structure.  The excitation pulse has unit area, so the
    low modes ring at roughly `amps`; `click` adds a bright contact transient."""
    n = ns(n_s)
    k = max(3, ns(soft))
    exc = np.zeros(n)
    h = np.hanning(k + 2)[1:-1]
    h /= h.sum()
    exc[:k] = h
    m = ns(0.02)
    exc[:m] += rng.standard_normal(m) * 0.12 * h.max() * np.exp(-np.arange(m) / (0.003 * SR))
    y = modal_bank(exc, freqs, amps, t60s)
    kc = ns(0.006)
    y[:kc] += hp(rng.standard_normal(kc), 1500) * np.exp(-np.arange(kc) / (0.001 * SR)) * click
    return y


# ----------------------------------------------------------------------------
# metal
# ----------------------------------------------------------------------------

def metal_hit(rng, f, n_modes=6, t60=0.3, inharm=1.0, amp=1.0, dur=None, bright=1.0):
    ratios = [1.0] + list(np.sort(rng.uniform(1.3, 5.5 * inharm, n_modes - 1)))
    fr = [f * r for r in ratios]
    am = [1.0] + [rng.uniform(0.3, 0.9) * bright ** i for i in range(1, n_modes)]
    tt = [t60 * rng.uniform(0.5, 1.0) / (1 + 0.25 * i) for i in range(n_modes)]
    n = ns(dur or (max(tt) * 1.1 + 0.01))
    exc = np.zeros(n)
    exc[0] = 1.0
    y = modal_bank(exc, fr, am, tt)
    k = ns(0.004)
    y[:k] += hp(rng.standard_normal(k), 3000) * 0.3 * np.exp(-np.arange(k) / (0.0008 * SR))
    return y * amp


def link_clink(rng, amp=1.0, f=None):
    f = f or rng.uniform(1800, 4200)
    return metal_hit(rng, f, 5, rng.uniform(0.04, 0.12), 1.4, amp)


def chain(rng, dur=1.4, rate=35.0, env_pts=None, low=0.25):
    n = ns(dur + 0.3)
    out = np.zeros(n)
    t = 0.0
    env_pts = env_pts or [(0, 1.0), (dur, 0.2)]
    while t < dur:
        e = np.interp(t, [p[0] for p in env_pts], [p[1] for p in env_pts])
        place(out, link_clink(rng, e * rng.uniform(0.3, 1.0)), ns(t))
        if rng.random() < low:
            place(out, metal_hit(rng, rng.uniform(380, 800), 5, 0.12, 1.2, 0.6 * e), ns(t))
        t += rng.exponential(1.0 / rate)
    return out


def bell_modes(rng, f_nominal, length=1.0, bright=1.0):
    """Fixed partial set for one physical bell (doublets for warble)."""
    from instruments import BELL_RATIOS, BELL_AMPS, BELL_T60
    sc = length * (880.0 / f_nominal) ** 0.35
    fr, am, tt = [], [], []
    for r, a, d in zip(BELL_RATIOS, BELL_AMPS, BELL_T60):
        ff = f_nominal * r * (1 + rng.normal(0, 0.002))
        if ff > 18000:
            continue
        a2 = a * (bright ** (math.log2(max(r, 0.25)) * 0.8))
        split = rng.uniform(0.4, 2.0) / ff
        for s in (-0.5, 0.5):
            fr.append(ff * (1 + s * split))
            am.append(a2 * 0.5 * rng.uniform(0.8, 1.2))
            tt.append(d * sc)
    for r in (3.37, 4.53, 6.11, 7.3):
        ff = f_nominal * r * rng.uniform(0.98, 1.02)
        if ff < 18000:
            fr.append(ff)
            am.append(0.12 * bright)
            tt.append(0.12)
    return fr, am, tt


def ring_bell(rng, modes, strikes, dur):
    """strikes: list of (time, amp). Same bell struck repeatedly."""
    n = ns(dur)
    exc = np.zeros(n)
    for t, a in strikes:
        i = ns(t)
        if i < n:
            exc[i] += a
    fr, am, tt = modes
    y = modal_bank(exc, fr, am, tt)
    for t, a in strikes:
        i = ns(t)
        k = ns(0.008)
        if i + k < n:
            y[i:i + k] += bp(rng.standard_normal(k), 4000, 0.8) * np.exp(-np.arange(k) / (0.0012 * SR)) * 0.2 * a
    return y


# ----------------------------------------------------------------------------
# creatures
# ----------------------------------------------------------------------------

def _harmonic_source(f0, n, nh=14, tilt=0.6, rough=0.0, rng=None):
    ph = dsp.phase_cycles(f0, n)
    out = np.zeros(n)
    for k in range(1, nh + 1):
        w = np.clip((16000 - k * f0) / 2000.0, 0, 1)
        if np.max(w) <= 0:
            break
        out += (k ** -tilt) * w * np.sin(TWO_PI * k * ph + (rng.random() * 6 if rng is not None else 0))
    if rough:
        out *= 1 + rough * np.sin(np.pi * ph + 0.7)  # period doubling -> subharmonic grit
    return out


def gull_note(rng, dur, fpts, fpeak, f1pts, f2pts, rough=0.14, amp_pts=None, breath=0.04):
    n = ns(dur)
    tt = [p[0] * dur for p in fpts]
    f0 = np.interp(tvec(n), tt, [p[1] * fpeak for p in fpts])
    f0 = sps.savgol_filter(f0, min(n - (1 - n % 2), 301), 2) if n > 400 else f0
    f0 *= 1 + 0.012 * smooth_noise(n, 35.0, rng, periodic=False)
    src = _harmonic_source(f0, n, 12, 0.55, rough, rng)
    F1 = np.interp(tvec(n), [p[0] * dur for p in f1pts], [p[1] for p in f1pts])
    F2 = np.interp(tvec(n), [p[0] * dur for p in f2pts], [p[1] for p in f2pts])
    y = svf(src, F1, 3.5, "bp") + 0.7 * svf(src, F2, 4.5, "bp") + 0.12 * src
    y += svf(rng.standard_normal(n), F2, 2.0, "bp") * breath
    y = lp(lp(y, 7000), 9000)
    amp_pts = amp_pts or [(0, 0), (0.06, 1.0), (0.75, 0.8), (1.0, 0)]
    env = np.interp(tvec(n), [p[0] * dur for p in amp_pts], [p[1] for p in amp_pts])
    y = hp(y * env, 450)
    return y


def gull_kyow(rng, scale=1.0, dur=0.55):
    fp = rng.uniform(1450, 1750) * scale
    return gull_note(rng, dur,
                     [(0, 0.62), (0.07, 0.97), (0.16, 1.0), (0.45, 0.82), (1.0, 0.56)], fp,
                     [(0, 3300), (0.2, 3000), (1.0, 2100)], [(0, 4600), (1.0, 3600)],
                     rough=0.2, amp_pts=[(0, 0), (0.05, 0.9), (0.18, 1.0), (0.7, 0.75), (1.0, 0)])


def gull_ha(rng, fpeak, dur=0.13, amp=1.0):
    return gull_note(rng, dur, [(0, 0.78), (0.3, 1.0), (1.0, 0.72)], fpeak,
                     [(0, 2600), (1.0, 2100)], [(0, 3900), (1.0, 3400)], rough=0.3,
                     amp_pts=[(0, 0), (0.12, 1.0), (0.6, 0.85), (1.0, 0)]) * amp


def seal_bark_note(rng, dur=0.22, f=260.0, amp=1.0):
    n = ns(dur)
    t = tvec(n)
    f0 = np.interp(t, [0, 0.25 * dur, dur], [f * 0.82, f, f * 0.74])
    f0 *= 1 + 0.035 * smooth_noise(n, 60.0, rng, periodic=False)  # strong jitter
    src = _harmonic_source(f0, n, 30, 0.9, 0.45, rng)
    fry = 1 + 0.5 * np.sin(TWO_PI * dsp.phase_cycles(42 + 10 * rng.random(), n))
    src *= fry
    y = (svf(src, 640, 3.0, "bp") * 1.0 + svf(src, 1150, 4.0, "bp") * 0.7
         + svf(src, 2500, 5.0, "bp") * 0.3 + 0.1 * src)
    y += svf(rng.standard_normal(n), 900, 1.5, "bp") * 0.15
    env = np.interp(t, [0, 0.03, 0.4 * dur, dur], [0, 1, 0.85, 0])
    return lp(hp(y * env, 120), 3800) * amp


# ----------------------------------------------------------------------------
# small foley
# ----------------------------------------------------------------------------

def pop(rng, f0, f1, dur=0.06, tau=None, amp=1.0):
    n = ns(dur)
    t = tvec(n)
    f = f1 + (f0 - f1) * np.exp(-t / (tau or dur * 0.3))
    env = (1 - np.exp(-t / 0.001)) * np.exp(-t / (dur * 0.28))
    return glide_sine(f, env) * amp


def squelch(rng, dur=0.12, fc=900.0, amp=1.0, wet=1.0):
    n = ns(dur)
    t = tvec(n)
    x = rng.standard_normal(n)
    am = np.clip(1 + 1.2 * smooth_noise(n, 70.0, rng, periodic=False), 0, None)
    c = fc * (1 + 0.8 * smooth_noise(n, 25.0, rng, periodic=False))
    y = svf(x * am, np.clip(c, 150, 8000), 2.5, "bp") * wet + lp(x, fc * 0.8) * 0.3
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.2
    return y * env * amp


def click(rng, f=3000.0, dur=0.008, amp=1.0, q=1.0):
    n = ns(dur)
    x = rng.standard_normal(n) * np.exp(-np.arange(n) / (dur * 0.2 * SR))
    return bp(x, f, q) * amp


def granular(rng, dur, density, f_lo, f_hi, amp_env_pts, grain=0.0003, q=1.2):
    """Dense tiny filtered clicks (sand crunch, paper crinkle, foam)."""
    n = ns(dur)
    k = int(density * dur)
    x = np.zeros(n)
    idx = rng.integers(0, n, k)
    np.add.at(x, idx, rng.uniform(-1, 1, k))
    g = max(3, ns(grain))
    x = np.convolve(x, np.hanning(g), mode="same")
    x = bp(hp(x, f_lo), math.sqrt(f_lo * f_hi), q * 0.5)
    x = lp(x, f_hi)
    env = dsp.env_points([(p[0] * dur, p[1]) for p in amp_env_pts], n)
    return x * env


def whoosh(rng, dur, f_pts, amp_pts, q=1.2):
    n = ns(dur)
    t = tvec(n)
    fc = np.interp(t, [p[0] * dur for p in f_pts], [p[1] for p in f_pts])
    env = np.interp(t, [p[0] * dur for p in amp_pts], [p[1] for p in amp_pts])
    x = colored_noise(n, rng, -1.5, periodic=False)
    return svf(x, fc, q, "bp") * env + svf(x, fc * 2.2, q, "bp") * env * 0.3


def chirp_down(rng, f_hi, f_lo, dur, tau=0.02, amp=1.0, decay=None):
    """Dispersive 'pew' (flexural waves in ice): f ~ 1/(1+t/tau)^2."""
    n = ns(dur)
    t = tvec(n)
    f = np.maximum(f_hi / (1 + t / tau) ** 2, f_lo)
    fade_lo = np.clip((f - f_lo) / (2 * f_lo), 0, 1)  # dies away as it reaches the bottom
    env = (1 - np.exp(-t / 0.0005)) * np.exp(-t / (decay or dur * 0.35)) * fade_lo
    return glide_sine(f, env) * amp
