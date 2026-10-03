"""Saltmoss Harbor - all sound effects and ambience loops (pure synthesis).

    Tools/.venv/bin/python Tools/audio/sfx.py              # build every SFX
    Tools/.venv/bin/python Tools/audio/sfx.py gull_1 amb_harbor_day   # selected
    Tools/.venv/bin/python Tools/audio/sfx.py --png ...    # also write spectrograms

Writes 16-bit / 44.1 kHz WAVs to Game/Assets/Saltmoss/Audio/Sfx/.
One-shots: trimmed and balanced by PERCEIVED loudness (LOUDNESS_TARGETS below)
so the game can play every one-shot at volume 1.0 without per-sound trims.
Loudness rule: BS.1770 integrated LUFS for sounds >= 1 s; for shorter sounds
the loudest 400 ms K-weighted window (momentary max, zero-padded to 400 ms).
True peak is held <= -1 dBTP: a look-ahead limiter takes at most
LIMIT_MAX_GR_DB off transients; very peaky sounds additionally get 4:1
look-ahead compression (see match_loudness).
SFX loops: seamless, peak -3 dBFS.  Ambiences: stereo seamless loops at -24 LUFS.
"""
from __future__ import annotations

import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import dsp  # noqa: E402
import instruments as I  # noqa: E402
from dsp import SR, ns, tvec, lp, hp, bp, peak, svf, smooth_noise, colored_noise  # noqa: E402
from sfx_lib import *  # noqa: E402,F401,F403
import sfx_lib as L  # noqa: E402

ASSETS: dict[str, tuple] = {}


def asset(name, kind="sfx", loop=False, seconds=None):
    def deco(fn):
        ASSETS[name] = (fn, kind, loop, seconds)
        return fn
    return deco


def variants(base, count, kind="sfx", loop=False):
    def deco(fn):
        for i in range(1, count + 1):
            ASSETS[f"{base}_{i}"] = ((lambda rng, i=i: fn(rng, i)), kind, loop, None)
        return fn
    return deco


# ============================================================================
# BOAT
# ============================================================================

def _engine(rng, rate_target, loop_s, hard):
    n = ns(loop_s)
    count = int(round(rate_target * loop_s))
    period = n / count
    t_fire = []
    amps = []
    for i in range(count):
        t_fire.append(i * period + rng.normal(0, 0.018 * period))
        a = 1.0 + rng.normal(0, 0.07)
        if rng.random() < 0.07:
            a *= 0.6  # lazy firing
        amps.append(a)
    press = np.zeros(n)
    puff = np.zeros(n)
    clat = np.zeros(n)
    k = ns(0.06)
    tk = tvec(k)
    shape = (1 - np.exp(-tk / 0.0007)) * np.exp(-tk / (0.0065 if hard else 0.009))
    shape -= 0.35 * (1 - np.exp(-tk / 0.004)) * np.exp(-tk / 0.02)  # rebound
    for ti, a in zip(t_fire, amps):
        i0 = int(round(ti)) % n
        L.place(press, shape * a, i0, wrap=True)
        m = ns(0.05)
        pz = L.noise_burst(rng, m, 0.001, 0.035 if hard else 0.05, f_lo=250, f_hi=1800 if hard else 1100)
        L.place(puff, pz * a, i0, wrap=True)
        # injector knock and valve tick
        L.place(clat, L.click(rng, rng.uniform(2000, 2600), 0.01, 0.6 * a, 2.0), i0 + ns(0.002), wrap=True)
        L.place(clat, L.metal_hit(rng, rng.uniform(2900, 3400), 4, 0.03, 1.2, 0.3), i0 + int(period * 0.46), wrap=True)
    pipe_f = 92.0 if not hard else 104.0
    exhaust = L.cfilter(press, lambda z: L.modal_bank(
        z, [pipe_f * h for h in (1, 2, 3, 4, 6, 8)], [1.0, 0.75, 0.5, 0.3, 0.18, 0.08],
        [0.09, 0.07, 0.06, 0.05, 0.04, 0.03]), 1.0)
    block = L.cfilter(press, lambda z: lp(z, 140), 1.0)
    hull = L.cfilter(press, lambda z: L.modal_bank(z, [43.0, 61.0], [0.6, 0.4], [0.25, 0.2]), 1.0)
    x = exhaust * 0.9 + block * 2.5 + hull * 0.8 + puff * (0.5 if hard else 0.35) + clat * (0.22 if hard else 0.15)
    if hard:
        roar = colored_noise(n, rng, -4.0)
        roar_env = L.cfilter(np.abs(press), lambda z: lp(z, 30), 0.5)
        roar = L.cfilter(roar, lambda z: bp(z, 450, 0.6), 0.5) * (0.4 + 3 * roar_env / (np.max(roar_env) + 1e-9))
        x += roar * 0.12
        shaft = np.sin(2 * np.pi * np.arange(n) * (round(rate_target * 4 * loop_s) / n)) * 0.03
        x += shaft
    else:
        # wet exhaust gurgle: bubbles riding the firings
        gur = np.zeros(n)
        for ti in t_fire:
            if rng.random() < 0.7:
                L.place(gur, L.bubble(rng, rng.uniform(180, 420), rng.uniform(0.03, 0.07), 1.4, rng.uniform(0.2, 0.6)),
                        int(ti + rng.uniform(0.01, 0.06) * SR) % n, wrap=True)
        x += gur * 0.35
    x = L.cfilter(x, lambda z: lp(hp(z, 30), 5200 if hard else 3800), 1.0)
    return x


@asset("engine_idle", loop=True)
def engine_idle(rng):
    x = _engine(rng, 6.25, 4.0, hard=False)
    # tame the sub-100 Hz boom for small speakers: HP ~45 Hz + gentle low shelf (circular: loop-safe)
    return dsp.circular(x, lambda z: dsp.eq(z, [("hp", 45, 0.7, 0), ("hp", 45, 0.7, 0),
                                                 ("ls", 110, 0.7, -4.5)]), 1.0)


@asset("engine_run", loop=True)
def engine_run(rng):
    return _engine(rng, 12.75, 4.0, hard=True)


@asset("boat_horn")
def boat_horn(rng):
    dur = 1.9
    n = ns(dur + 0.3)
    t = tvec(n)
    out = np.zeros(n)
    for f, a in ((174.6, 1.0), (220.0, 0.8)):
        fc = f * (1 - 0.025 * np.exp(-t / 0.06)) * (1 + 0.002 * smooth_noise(n, 5.0, rng, periodic=False))
        src = 0.55 * dsp.pulse(fc, n, 0.33, rng.random()) + 0.45 * dsp.saw(fc, n, rng.random())
        out += a * src
    env = dsp.env_points([(0, 0), (0.07, 1.0), (0.12, 0.92), (dur, 0.85), (dur + 0.2, 0)], n)
    out *= env
    out = dsp.eq(out, [("hp", 120, 0.7, 0), ("peak", 620, 1.4, 8), ("peak", 1450, 2.0, 5),
                       ("lp", 3800, 0.7, 0), ("lp", 5000, 0.7, 0)])
    out = L.mono_reverb(out, rt60=1.6, wet=0.3, predelay=0.02, hf_ratio=0.35)
    echo = np.zeros(out.size + ns(0.25))
    echo[:out.size] += out
    echo[ns(0.21):ns(0.21) + out.size] += lp(out, 2000) * 0.22
    return echo


def _wave_slap(rng, size=1.0, hull_f=80.0):
    n = ns(1.4 * size + 0.4)
    out = np.zeros(n)
    pre = ns(0.12)
    # approaching water swish
    sw = L.slosh(rng, 0.18, 900, 0.25)
    L.place(out, sw, 0)
    i0 = pre
    th = L.wood_thump(rng, [hull_f, hull_f * 1.52, hull_f * 2.4, hull_f * 3.3, hull_f * 5.1],
                      [0.35, 0.25, 0.16, 0.1, 0.06], [1.0, 0.6, 0.4, 0.22, 0.12], click=0.05,
                      soft=0.006, n_s=0.6)
    L.place(out, th * 1.1 * size, i0)
    m = ns(0.9 * size)
    sl = L.noise_burst(rng, m, 0.003, 0.32 * size, f_lo=300, cut_from=7000, cut_to=1100, q=0.8)
    L.place(out, sl * 0.9, i0)
    sp = L.noise_burst(rng, ns(1.0 * size), 0.03, 0.7 * size, f_lo=2500)
    L.place(out, sp * 0.22, i0 + ns(0.02))
    L.place(out, L.droplets(rng, ns(1.0 * size), int(16 * size), 0.08, 0.7 * size, amp=0.18), i0)
    return out


@asset("wave_slap_1")
def wave_slap_1(rng):
    return _wave_slap(rng, 1.0, 78)


@asset("wave_slap_2")
def wave_slap_2(rng):
    return _wave_slap(rng, 0.8, 95)


@asset("wave_slap_3")
def wave_slap_3(rng):
    a = _wave_slap(rng, 1.15, 70)
    b = _wave_slap(rng, 0.6, 88)
    out = np.zeros(a.size + ns(0.35))
    L.place(out, a, 0)
    L.place(out, b * 0.55, ns(0.33))
    return out


@asset("wave_crash_big")
def wave_crash_big(rng):
    x = L.wave_crash(rng, 1.25)
    th = L.wood_thump(rng, [62, 95, 150, 230], [0.5, 0.35, 0.2, 0.12], [1, 0.6, 0.35, 0.2],
                      click=0.02, soft=0.01, n_s=0.9)
    L.place(x, th * 0.6, ns(0.86))
    return L.mono_reverb(x, rt60=1.4, wet=0.18, hf_ratio=0.4)


@variants("hull_creak", 3)
def hull_creak(rng, i):
    dur = [1.1, 0.8, 1.5][i - 1]
    base = [38, 55, 30][i - 1]
    top = [110, 150, 85][i - 1]
    x = L.creak(rng, dur, base, top, 1.0, pitch=[0.62, 0.75, 0.55][i - 1])
    # body groan of the hull planking
    x = x + L.modal_bank(x, [140, 230], [0.08, 0.05], [0.12, 0.08])
    if i == 3:
        y = L.creak(rng, 0.5, 70, 130, 0.5, pitch=0.7)
        L.place(x, y, ns(1.0))
    return L.mono_reverb(x, rt60=0.5, wet=0.12)


@asset("ice_crack")
def ice_crack(rng):
    n = ns(1.2)
    out = np.zeros(n)
    k = ns(0.01)
    out[:k] += hp(rng.standard_normal(k), 1500) * np.exp(-np.arange(k) / (0.0015 * SR)) * 1.2
    L.place(out, L.chirp_down(rng, 7000, 180, 0.45, tau=0.03, amp=0.8, decay=0.12), ns(0.002))
    L.place(out, L.chirp_down(rng, 5500, 160, 0.35, tau=0.035, amp=0.45, decay=0.1), ns(0.065))
    L.place(out, L.chirp_down(rng, 6500, 200, 0.3, tau=0.025, amp=0.3, decay=0.08), ns(0.17))
    cr = L.granular(rng, 0.35, 2500, 900, 8000, [(0, 1), (0.3, 0.6), (1, 0)], grain=0.0002)
    L.place(out, cr * 1.6, 0)
    thoom = L.pop(rng, 95, 60, 0.4, amp=0.5)
    L.place(out, thoom, 0)
    return L.mono_reverb(out, rt60=0.8, wet=0.15, hf_ratio=0.6)


def _ice_hammer(rng, heavy):
    n = ns(1.2)
    out = np.zeros(n)
    th = L.wood_thump(rng, [175, 320, 590, 900], [0.12, 0.08, 0.05, 0.03], [1, 0.7, 0.4, 0.2],
                      click=0.4, soft=0.0012, n_s=0.4)
    L.place(out, th * (2.0 if heavy else 1.6), 0)
    cr = L.granular(rng, 0.25, 7000, 700, 9000, [(0, 1), (0.25, 0.7), (1, 0)], grain=0.0002)
    L.place(out, cr * (2.2 if heavy else 1.6), ns(0.003))
    for _ in range(3 if heavy else 2):
        L.place(out, L.click(rng, rng.uniform(2500, 6000), 0.006, 0.8, 0.8), ns(rng.uniform(0.0, 0.03)))
    # ice chips scattering
    for _ in range(rng.integers(6, 11)):
        t = rng.uniform(0.05, 0.6)
        f = rng.uniform(2300, 6200)
        chip = L.metal_hit(rng, f, 3, rng.uniform(0.02, 0.06), 1.6, rng.uniform(0.1, 0.35))
        L.place(out, chip, ns(t))
        if rng.random() < 0.5:
            L.place(out, chip * 0.4, ns(t + rng.uniform(0.04, 0.09)))
    deck = L.wood_thump(rng, [110, 190], [0.15, 0.1], [1, 0.5], click=0.0, soft=0.004, n_s=0.3)
    L.place(out, deck * 0.9, ns(0.005))
    if heavy:
        L.place(out, L.chirp_down(rng, 5000, 400, 0.25, tau=0.01, amp=0.25), ns(0.01))
    return out


@asset("ice_hammer_1")
def ice_hammer_1(rng):
    return _ice_hammer(rng, False)


@asset("ice_hammer_2")
def ice_hammer_2(rng):
    return _ice_hammer(rng, True)


@asset("splash_big")
def splash_big(rng):
    x = L.splash(rng, 1.7)
    return L.mono_reverb(x, rt60=0.9, wet=0.12)


# ============================================================================
# POTS
# ============================================================================

def _rope_run(rng, dur, r0=30.0, r1=10.0):
    n = ns(dur)
    t = tvec(n)
    rate = r0 + (r1 - r0) * (t / dur) ** 0.7
    ph = np.cumsum(rate / SR)
    am = 0.55 + 0.45 * np.sin(2 * np.pi * ph) ** 2
    x = rng.standard_normal(n)
    y = lp(bp(x, 1200, 0.9) * am + bp(x, 380, 1.0) * am * 0.6, 3500, order=4)
    env = dsp.env_points([(0, 0), (0.05, 1), (dur * 0.7, 0.7), (dur, 0)], n)
    # coil slaps
    out = y * env
    for p in np.nonzero(np.diff(np.floor(ph)) > 0)[0][::2]:
        L.place(out, L.click(rng, rng.uniform(500, 900), 0.02, 0.3 * env[p], 1.5), int(p))
    return out


@asset("pot_drop")
def pot_drop(rng):
    n = ns(2.6)
    out = np.zeros(n)
    sp = L.splash(rng, 1.1)
    L.place(out, sp, 0)
    for _ in range(4):
        L.place(out, L.metal_hit(rng, rng.uniform(600, 1400), 5, 0.12, 1.3, 0.25), ns(rng.uniform(0, 0.05)))
    L.place(out, _rope_run(rng, 1.8) * 0.5, ns(0.18))
    for k in range(6):
        L.place(out, L.bubble(rng, rng.uniform(140, 300), rng.uniform(0.06, 0.12), 1.5, 0.35 * (1 - k / 7)),
                ns(0.35 + 0.15 * k + rng.uniform(0, 0.05)))
    return L.mono_reverb(out, rt60=0.8, wet=0.1)


@asset("winch_loop", loop=True)
def winch_loop(rng):
    loop_s = 4.0
    n = ns(loop_s)
    t = tvec(n)
    f_h = 112.5  # 450 cycles per loop
    wob = 1 + 0.12 * np.sin(2 * np.pi * 1.5 * t)  # 6 cycles per loop
    hum = sum((k ** -1.2) * np.sin(2 * np.pi * f_h * k * t + k) for k in range(1, 14))
    mesh = np.sin(2 * np.pi * 675.0 * t) + 0.4 * np.sin(2 * np.pi * 1350.0 * t + 1.0)
    whine = (hum * 0.5 + mesh * 0.18) * wob
    whine = L.cfilter(whine, lambda z: lp(z, 3500), 0.5)
    out = whine * 0.35
    # pawl / gear clicks at 10 Hz
    clicks = np.zeros(n)
    for i in range(40):
        a = 0.6 if i % 2 else 1.0
        L.place(clicks, L.metal_hit(rng, rng.uniform(2700, 3300), 4, 0.025, 1.3, a), ns(i * 0.1), wrap=True)
    out += clicks * 0.35
    # drum thump each revolution + rope creak
    for i in range(6):
        t0 = i * loop_s / 6
        L.place(out, L.wood_thump(rng, [90, 150, 260], [0.1, 0.08, 0.05], [1, 0.5, 0.3], 0.05, 0.004, 0.25) * 1.2,
                ns(t0), wrap=True)
        cr = L.creak(rng, 0.35, 70, 160, 0.25, pitch=0.9)
        L.place(out, cr, ns(t0 + 0.2), wrap=True)
    rum = colored_noise(n, rng, -5.0)
    out += L.cfilter(rum, lambda z: lp(z, 300), 0.5) * 0.08
    for _ in range(7):
        L.place(out, L.bubble(rng, rng.uniform(900, 2200), 0.02, 1.8, 0.15), rng.integers(0, n), wrap=True)
    return out


@asset("winch_strain")
def winch_strain(rng):
    dur = 1.9
    x = L.stick_slip(rng, dur, [(0, 18), (0.5, 34), (1.1, 46), (1.5, 28), (dur, 20)],
                     [140, 290, 470, 800, 1250], [0.12, 0.1, 0.07, 0.05, 0.04],
                     [1.0, 0.8, 0.5, 0.3, 0.15], jitter=0.2, roughness=0.5)
    n = x.size
    t = tvec(n)
    sq = np.sin(2 * np.pi * dsp.phase_cycles(1750 * (1 + 0.03 * smooth_noise(n, 3, rng, periodic=False)), n))
    sq *= dsp.env_points([(0, 0), (0.6, 0), (1.0, 1), (1.4, 0.4), (dur, 0)], n) * 0.05
    fib = L.granular(rng, dur, 300, 1500, 6000, [(0, 0), (0.4, 1), (0.8, 1), (1, 0)])
    groan = lp(colored_noise(n, rng, -6, periodic=False), 200) * dsp.env_points([(0, 0), (0.5, 1), (dur, 0)], n) * 0.3
    return L.mono_reverb(x + sq + fib * 0.6 + groan, rt60=0.6, wet=0.12)


@asset("pot_surface")
def pot_surface(rng):
    dur = 2.9
    n = ns(dur)
    t = tvec(n)
    out = np.zeros(n)
    L.place(out, L.whoosh(rng, 0.35, [(0, 400), (0.6, 1800), (1, 900)], [(0, 0), (0.5, 1), (1, 0.5)]) * 0.6, 0)
    L.place(out, L.splash(rng, 0.5) * 0.5, ns(0.2))
    # pouring: dense bubbles thinning out
    tt = 0.25
    while tt < dur - 0.2:
        dens = 140 * math.exp(-(tt - 0.25) / 0.7) + 6
        L.place(out, L.bubble(rng, math.exp(rng.uniform(math.log(350), math.log(1900))),
                              rng.uniform(0.012, 0.05), rng.uniform(1.2, 2.0),
                              rng.uniform(0.1, 0.35) * min(1.0, dens / 40 + 0.3)), ns(tt))
        tt += rng.exponential(1.0 / dens)
    pour = svf(rng.standard_normal(n), 1300 * (1 + 0.3 * smooth_noise(n, 8, rng, periodic=False)), 0.7, "bp")
    pour *= np.where(t < 0.25, 0, np.exp(-(t - 0.25) / 0.65)) * (1 + 0.5 * smooth_noise(n, 15, rng, periodic=False))
    out += pour * 0.5
    for k in range(7):
        L.place(out, L.bubble(rng, rng.uniform(1100, 2400), 0.03, 1.9, 0.25),
                ns(1.5 + k * rng.uniform(0.12, 0.22)))
    return out


@asset("crab_clatter")
def crab_clatter(rng):
    dur = 1.7
    n = ns(dur + 0.3)
    out = np.zeros(n)
    t = 0.0
    while t < 1.0:
        a = rng.uniform(0.4, 1.0) * (1 - t * 0.6)
        shell = L.metal_hit(rng, rng.uniform(1700, 4200), 4, rng.uniform(0.015, 0.035), 1.5, a)
        L.place(out, shell, ns(t))
        if rng.random() < 0.45:
            body = L.wood_thump(rng, [rng.uniform(150, 210), rng.uniform(300, 380), 540], [0.06, 0.05, 0.03],
                                [1, 0.6, 0.3], 0.1, 0.002, 0.15)
            L.place(out, body * a * 1.6, ns(t + 0.003))
        t += rng.exponential(0.035 + t * 0.06)
    # scrabbling legs
    t = 0.45
    while t < dur:
        L.place(out, L.click(rng, rng.uniform(3000, 6500), 0.004, rng.uniform(0.05, 0.18), 1.5), ns(t))
        t += rng.exponential(1 / 45)
    return L.mono_reverb(out, rt60=0.4, wet=0.1)


@asset("chain_rattle")
def chain_rattle(rng):
    return L.mono_reverb(L.chain(rng, 1.4, 50, [(0, 0.5), (0.2, 1.0), (0.9, 0.8), (1.4, 0.15)]), rt60=0.5, wet=0.12)


# ============================================================================
# FISHING
# ============================================================================

@asset("cast_whoosh")
def cast_whoosh(rng):
    n = ns(1.25)
    out = np.zeros(n)
    w = L.whoosh(rng, 0.42, [(0, 450), (0.45, 2600), (1, 700)], [(0, 0), (0.45, 1), (1, 0)], q=1.0)
    L.place(out, w, 0)
    # line zipping off the spool
    zn = ns(0.9)
    tz = tvec(zn)
    rate = 150 * np.exp(-tz / 0.5) + 35
    ph = np.cumsum(rate / SR)
    imp = np.zeros(zn)
    hits = np.nonzero(np.diff(np.floor(ph)) > 0)[0]
    imp[hits] = rng.uniform(0.5, 1.0, hits.size)
    tick = hp(rng.standard_normal(ns(0.002)), 2500) * np.hanning(ns(0.002))
    zip_ = np.convolve(imp, tick)[:zn]
    zip_ = bp(zip_, 3000, 0.7)
    hiss = hp(rng.standard_normal(zn), 4500) * 0.08
    zenv = dsp.env_points([(0, 0), (0.05, 1), (0.9, 0)], zn)
    L.place(out, (zip_ + hiss) * zenv * 0.5, ns(0.2))
    return out


@asset("reel_loop", loop=True)
def reel_loop(rng):
    loop_s = 2.0
    n = ns(loop_s)
    t = tvec(n)
    out = np.zeros(n)
    for i in range(36):  # 18 Hz ratchet
        a = [1.0, 0.7, 0.85][i % 3] * rng.uniform(0.9, 1.1)
        L.place(out, L.metal_hit(rng, 3900 + rng.normal(0, 60), 4, 0.018, 1.4, a), ns(i / 18.0), wrap=True)
        L.place(out, L.click(rng, 2400, 0.004, 0.4 * a, 1.0), ns(i / 18.0), wrap=True)
    whir = colored_noise(n, rng, -2.0)
    whir = L.cfilter(whir, lambda z: hp(bp(z, 480, 2.0), 200, order=4), 0.5) * (0.7 + 0.3 * np.sin(2 * np.pi * 6.0 * t))
    hum = 0.015 * np.sin(2 * np.pi * 108.0 * t) + 0.008 * np.sin(2 * np.pi * 216.0 * t)
    return out * 0.6 + whir * 0.25 + hum


@asset("bobber_plop")
def bobber_plop(rng):
    n = ns(0.6)
    out = np.zeros(n)
    L.place(out, L.bubble(rng, 380, 0.07, 2.4, 1.0), ns(0.004))
    k = ns(0.03)
    out[:k] += hp(rng.standard_normal(k), 1200) * np.exp(-np.arange(k) / (0.004 * SR)) * 0.35
    L.place(out, L.droplets(rng, ns(0.5), 4, 0.06, 0.25, 1200, 2600, 0.2), 0)
    return out


@asset("nibble")
def nibble(rng):
    n = ns(0.3)
    out = np.zeros(n)
    L.place(out, L.bubble(rng, 820, 0.035, 1.9, 1.0), 0)
    L.place(out, L.bubble(rng, 1050, 0.028, 1.7, 0.5), ns(0.085))
    k = ns(0.02)
    out[:k] += hp(rng.standard_normal(k), 2500) * np.exp(-np.arange(k) / (0.003 * SR)) * 0.1
    return out


@asset("bite_splash")
def bite_splash(rng):
    n = ns(1.4)
    out = np.zeros(n)
    L.place(out, L.bubble(rng, 240, 0.14, 1.7, 0.9), 0)
    L.place(out, L.splash(rng, 0.7, bright=1.1), ns(0.03))
    return out


@asset("fish_splash")
def fish_splash(rng):
    n = ns(1.8)
    out = np.zeros(n)
    # breaching: spray up
    sp = L.noise_burst(rng, ns(0.3), 0.01, 0.2, f_lo=900, cut_from=8000, cut_to=2500)
    L.place(out, sp * 0.6, 0)
    L.place(out, L.droplets(rng, ns(0.5), 10, 0.05, 0.35, 1000, 2800, 0.15), 0)
    # re-entry
    L.place(out, L.splash(rng, 0.6), ns(0.42))
    return out


def _flop(rng, amp=1.0):
    n = ns(0.35)
    out = np.zeros(n)
    k = ns(0.03)
    out[:k] += lp(rng.standard_normal(k), 5000) * np.exp(-np.arange(k) / (0.004 * SR)) * 1.1
    deck = L.wood_thump(rng, [rng.uniform(140, 170), rng.uniform(270, 320), 480, 760], [0.08, 0.06, 0.04, 0.03],
                        [1, 0.6, 0.4, 0.2], 0.05, 0.003, 0.3)
    L.place(out, deck * 1.4, 0)
    L.place(out, L.squelch(rng, 0.09, rng.uniform(900, 1500), 0.7), ns(0.004))
    return out * amp


@asset("fish_flop_1")
def fish_flop_1(rng):
    out = np.zeros(ns(0.8))
    L.place(out, _flop(rng, 1.0), 0)
    L.place(out, _flop(rng, 0.45), ns(0.17))
    L.place(out, L.droplets(rng, ns(0.6), 4, 0.02, 0.3, 1400, 2800, 0.08, dur=(0.008, 0.02)), 0)
    return out


@asset("fish_flop_2")
def fish_flop_2(rng):
    out = np.zeros(ns(1.1))
    for t, a in ((0.0, 0.8), (0.21, 1.0), (0.36, 0.5), (0.62, 0.35)):
        L.place(out, _flop(rng, a), ns(t + rng.uniform(-0.01, 0.01)))
    return out


# ============================================================================
# DREDGE
# ============================================================================

@asset("dredge_drop")
def dredge_drop(rng):
    n = ns(2.6)
    out = np.zeros(n)
    L.place(out, L.metal_hit(rng, 205, 8, 0.9, 1.6, 1.0, dur=1.2), 0)
    L.place(out, L.metal_hit(rng, 470, 6, 0.5, 1.4, 0.6, dur=0.8), ns(0.008))
    L.place(out, L.splash(rng, 1.3) * 0.9, ns(0.06))
    L.place(out, L.chain(rng, 1.4, 70, [(0, 1.0), (1.4, 0.15)]) * 0.45, ns(0.25))
    for k in range(8):
        L.place(out, L.bubble(rng, rng.uniform(150, 350), rng.uniform(0.06, 0.12), 1.5, 0.3 * (1 - k / 9)),
                ns(0.5 + 0.17 * k))
    return L.mono_reverb(out, rt60=0.9, wet=0.1)


@asset("dredge_up")
def dredge_up(rng):
    dur = 2.8
    n = ns(dur + 0.3)
    t = tvec(n)
    out = np.zeros(n)
    L.place(out, L.chain(rng, 2.4, 22, [(0, 0.5), (2.4, 0.9)]) * 0.5, 0)
    tt = 0.0
    while tt < 1.3:  # bubbles rising before it surfaces
        L.place(out, L.bubble(rng, rng.uniform(250, 1100), rng.uniform(0.03, 0.09), 1.6, rng.uniform(0.1, 0.35)), ns(tt))
        tt += rng.exponential(1 / 40)
    L.place(out, L.whoosh(rng, 0.4, [(0, 500), (0.5, 2200), (1, 900)], [(0, 0), (0.4, 1), (1, 0.4)]) * 0.5, ns(1.25))
    drain = svf(rng.standard_normal(n), 1500, 0.7, "bp") * np.where(t < 1.35, 0, np.exp(-(t - 1.35) / 0.6))
    out += drain * 0.45
    L.place(out, L.droplets(rng, ns(1.6), 22, 0.0, 1.4, 900, 2600, 0.2), ns(1.4))
    L.place(out, L.metal_hit(rng, 320, 6, 0.4, 1.4, 0.6, dur=0.6), ns(2.3))
    return out


@asset("sonar_ping")
def sonar_ping(rng):
    dur = 3.4
    n = ns(dur)
    t = tvec(n)
    f = 930.0 * (1 - 0.004 * (1 - np.exp(-t / 0.5)))
    ph = dsp.phase_cycles(f, n)
    tone = np.sin(2 * np.pi * ph) + 0.12 * np.sin(4 * np.pi * ph) + 0.04 * np.sin(6 * np.pi * ph)
    env = np.clip(t / 0.008, 0, 1) * np.where(t < 0.12, 1.0, np.exp(-(t - 0.12) / 0.32))
    x = tone * env
    echo = np.zeros(n)
    e = lp(x, 2200) * 0.17
    L.place(echo, e, ns(1.15))
    x = x + echo
    return L.mono_reverb(x, rt60=2.8, wet=0.45, predelay=0.03, hf_ratio=0.25, er=0.3)


@asset("glimmer")
def glimmer(rng):
    n = ns(2.2)
    out = np.zeros(n)
    scale = [2349.3, 2637.0, 2960.0, 3520.0, 3951.1, 4698.6, 5274.0, 5919.9]
    t = 0.0
    for i in range(9):
        f = scale[min(len(scale) - 1, int(i * 0.9 + rng.integers(0, 2)))]
        p = L.modal_bank(L.impulses(ns(0.9), [0.0], [1.0]), [f, f * 2.76], [1.0, 0.2],
                         [rng.uniform(0.35, 0.7), 0.15])
        tr = 1 + 0.3 * np.sin(2 * np.pi * 14 * tvec(p.size))
        L.place(out, p * tr * rng.uniform(0.4, 1.0), ns(t))
        t += rng.uniform(0.05, 0.11)
    sh = L.granular(rng, 1.2, 900, 6000, 14000, [(0, 0), (0.2, 1), (1, 0)])
    L.place(out, sh * 0.35, ns(0.05))
    return L.mono_reverb(out, rt60=1.6, wet=0.35, hf_ratio=0.6)


# ============================================================================
# TOWN
# ============================================================================

@variants("step_wood", 4)
def step_wood(rng, i):
    var = [1.0, 0.92, 1.08, 0.86][i - 1]
    fr = [f * var * rng.uniform(0.97, 1.03) for f in (98, 165, 245, 410, 720, 1180)]
    t60 = [0.2, 0.13, 0.09, 0.06, 0.04, 0.03]
    am = [1.0, 0.8, 0.6, 0.38, 0.22, 0.12]
    n = ns(0.5)
    out = np.zeros(n)
    heel = L.wood_thump(rng, fr, t60, am, click=0.25, soft=0.002, n_s=0.4)
    L.place(out, heel, 0)
    toe = L.wood_thump(rng, [f * 1.07 for f in fr], [d * 0.8 for d in t60], [a * 0.9 for a in am],
                       click=0.15, soft=0.0015, n_s=0.3)
    L.place(out, toe * rng.uniform(0.4, 0.6), ns(rng.uniform(0.04, 0.07)))
    L.place(out, L.squelch(rng, 0.05, 2200, 0.08), ns(0.01))  # webbed-foot pat
    if i in (2, 4):
        L.place(out, L.creak(rng, 0.14, 180, 320, 0.08, pitch=1.3), ns(0.05))
    return out


@variants("step_sand", 3)
def step_sand(rng, i):
    n = ns(0.45)
    out = np.zeros(n)
    c1 = L.granular(rng, 0.16, 5500, 1200, 7000, [(0, 0), (0.15, 1), (0.6, 0.5), (1, 0)], grain=0.00025)
    L.place(out, c1, 0)
    c2 = L.granular(rng, 0.14, 3500, 1500, 6500, [(0, 0), (0.3, 1), (1, 0)], grain=0.0002)
    L.place(out, c2 * 0.6, ns(0.07 + 0.02 * i))
    k = ns(0.06)
    thud = lp(rng.standard_normal(k), 160) * np.exp(-np.arange(k) / (0.015 * SR)) * 0.8
    L.place(out, thud, 0)
    return out


@variants("step_stone", 3)
def step_stone(rng, i):
    n = ns(0.35)
    out = np.zeros(n)
    base = [1250, 1100, 1400][i - 1]
    tap = L.modal_bank(L.impulses(n, [0], [1.0]), [base, base * 1.73, base * 2.6, 380],
                       [0.6, 0.4, 0.25, 0.5], [0.03, 0.022, 0.016, 0.05])
    out += tap
    k = ns(0.006)
    out[:k] += bp(rng.standard_normal(k), 3000, 0.7) * np.exp(-np.arange(k) / (0.001 * SR)) * 1.0
    k = ns(0.05)
    out[:k] += lp(rng.standard_normal(k), 220) * np.exp(-np.arange(k) / (0.01 * SR)) * 0.5
    for _ in range(rng.integers(2, 5)):
        L.place(out, L.click(rng, rng.uniform(3000, 7000), 0.004, rng.uniform(0.1, 0.3), 1.5),
                ns(rng.uniform(0.01, 0.06)))
    L.place(out, L.click(rng, base * 1.1, 0.01, 0.4, 1.5), ns(rng.uniform(0.035, 0.06)))  # toe
    return out


@asset("door_open")
def door_open(rng):
    n = ns(1.6)
    out = np.zeros(n)
    L.place(out, L.metal_hit(rng, 2100, 5, 0.06, 1.3, 0.8), 0)
    L.place(out, L.metal_hit(rng, 1700, 5, 0.08, 1.3, 0.6), ns(0.05))
    sq = L.stick_slip(rng, 1.0, [(0, 160), (0.3, 420), (0.6, 330), (1.0, 220)],
                      [880, 1520, 2350, 3300, 160, 270], [0.03, 0.025, 0.02, 0.015, 0.08, 0.06],
                      [1.0, 0.8, 0.5, 0.3, 0.6, 0.4], jitter=0.06, roughness=0.2,
                      env_pts=[(0, 0), (0.1, 1), (0.7, 0.8), (1.0, 0)])
    L.place(out, sq * 0.5, ns(0.12))
    air = L.whoosh(rng, 0.8, [(0, 300), (0.5, 600), (1, 300)], [(0, 0), (0.5, 1), (1, 0)], q=0.6)
    L.place(out, air * 0.25, ns(0.25))
    return L.mono_reverb(out, rt60=0.5, wet=0.12)


@asset("door_close")
def door_close(rng):
    n = ns(1.0)
    out = np.zeros(n)
    sq = L.stick_slip(rng, 0.28, [(0, 300), (0.28, 180)], [880, 1500, 2300], [0.03, 0.02, 0.02],
                      [1, 0.7, 0.4], jitter=0.06)
    L.place(out, sq * 0.3, 0)
    slam = L.wood_thump(rng, [82, 135, 228, 385, 640, 980], [0.28, 0.2, 0.13, 0.09, 0.06, 0.04],
                        [1.0, 0.85, 0.6, 0.4, 0.25, 0.12], click=0.3, soft=0.003, n_s=0.6)
    L.place(out, slam, ns(0.26))
    L.place(out, L.metal_hit(rng, 2300, 5, 0.05, 1.3, 0.5), ns(0.275))
    L.place(out, L.metal_hit(rng, 1900, 4, 0.04, 1.3, 0.25), ns(0.31))  # latch rattle
    return L.mono_reverb(out, rt60=0.55, wet=0.14)


@asset("shop_bell")
def shop_bell(rng):
    dur = 2.2
    m1 = L.bell_modes(rng, 2350, length=0.45, bright=1.15)
    m2 = L.bell_modes(rng, 2960, length=0.4, bright=1.1)
    st1 = [(0.0, 1.0), (0.075, 0.55), (0.16, 0.7), (0.23, 0.4), (0.33, 0.45), (0.42, 0.28), (0.53, 0.25),
           (0.66, 0.15), (0.8, 0.1)]
    st2 = [(0.03, 0.6), (0.12, 0.5), (0.2, 0.35), (0.29, 0.3), (0.4, 0.2), (0.5, 0.18), (0.63, 0.1)]
    x = L.ring_bell(rng, m1, st1, dur) + 0.8 * L.ring_bell(rng, m2, st2, dur)
    return L.mono_reverb(x * dsp.fade(np.ones(x.size), 0, 0.4), rt60=0.6, wet=0.15)


@asset("gull_1")
def gull_1(rng):
    x = L.gull_kyow(rng, 1.0, 0.58)
    return L.mono_reverb(x, rt60=0.9, wet=0.12, hf_ratio=0.5)


@asset("gull_2")
def gull_2(rng):
    out = np.zeros(ns(1.8))
    t = 0.0
    fp = 1380.0
    for k in range(7):
        d = 0.13 - 0.006 * k
        L.place(out, L.gull_ha(rng, fp, d, 1.0 - 0.07 * k), ns(t))
        t += d + 0.07 - 0.004 * k
        fp *= 0.97
    return L.mono_reverb(out, rt60=0.9, wet=0.12, hf_ratio=0.5)


@asset("gull_3")
def gull_3(rng):
    out = np.zeros(ns(2.4))
    long_ = L.gull_note(rng, 0.85, [(0, 0.6), (0.06, 0.95), (0.4, 1.0), (0.7, 0.85), (1.0, 0.6)],
                        1620, [(0, 3300), (0.5, 3000), (1.0, 2200)], [(0, 4600), (1.0, 3700)], rough=0.22,
                        amp_pts=[(0, 0), (0.05, 0.9), (0.5, 1.0), (0.85, 0.7), (1, 0)])
    L.place(out, long_, 0)
    t = 1.0
    for k in range(3):
        kow = L.gull_note(rng, 0.2, [(0, 0.75), (0.25, 1.0), (1.0, 0.62)], 1350 - 60 * k,
                          [(0, 2900), (1, 2100)], [(0, 4000), (1, 3400)], rough=0.25)
        L.place(out, kow * (0.9 - 0.12 * k), ns(t))
        t += 0.27
    return L.mono_reverb(out, rt60=0.9, wet=0.12, hf_ratio=0.5)


@asset("seal_bark")
def seal_bark(rng):
    out = np.zeros(ns(1.4))
    for k, (f, d) in enumerate(((270, 0.2), (255, 0.21), (238, 0.25))):
        L.place(out, L.seal_bark_note(rng, d, f, 1.0 - 0.1 * k), ns(k * 0.37 + rng.uniform(0, 0.03)))
    return L.mono_reverb(out, rt60=0.8, wet=0.15)


@asset("crab_click")
def crab_click(rng):
    out = np.zeros(ns(0.3))
    for t, a in ((0.0, 1.0), (0.065, 0.75)):
        c = L.modal_bank(L.impulses(ns(0.1), [0], [1]), [2600, 4150, 5900], [1, 0.6, 0.35],
                         [0.025, 0.018, 0.012])
        c[:ns(0.003)] += hp(rng.standard_normal(ns(0.003)), 3000) * 0.6
        L.place(out, c * a, ns(t))
    return out


@asset("buoy_bell")
def buoy_bell(rng):
    m = L.bell_modes(rng, 640, length=1.5, bright=0.9)
    x = L.ring_bell(rng, m, [(0.0, 1.0), (0.82, 0.7), (2.1, 0.45)], 7.0)
    x = dsp.fade(x, 0, 1.5)
    return L.mono_reverb(x, rt60=2.2, wet=0.25, hf_ratio=0.4)


@asset("foghorn")
def foghorn(rng):
    dur = 4.2
    n = ns(dur)
    t = tvec(n)
    f0 = dsp.env_points([(0, 118), (0.25, 150), (2.6, 151), (2.95, 92), (dur, 88)], n)
    f0 *= 1 + 0.003 * smooth_noise(n, 4, rng, periodic=False)
    src = L._harmonic_source(f0, n, 40, 0.75, 0.0, rng)
    grunt = np.clip((t - 2.6) / 0.3, 0, 1)
    src *= 1 + 0.5 * grunt * np.sin(np.pi * dsp.phase_cycles(f0, n))  # subharmonic grunt
    src += grunt * lp(rng.standard_normal(n), 900) * 0.4
    env = dsp.env_points([(0, 0), (0.3, 1.0), (2.6, 0.95), (3.0, 0.8), (3.7, 0.4), (dur, 0)], n)
    x = dsp.eq(src * env, [("hp", 60, 0.7, 0), ("peak", 300, 1.5, 6), ("peak", 650, 2.0, 4),
                           ("lp", 2800, 0.7, 0), ("lp", 3500, 0.7, 0)])
    x = L.mono_reverb(x, rt60=3.6, wet=0.45, predelay=0.05, hf_ratio=0.3, er=0.3)
    out = np.zeros(x.size + ns(0.7))
    out[:x.size] += x
    out[ns(0.62):ns(0.62) + x.size] += lp(x, 900) * 0.25
    return out


@asset("thunder_1")
def thunder_1(rng):
    return L.thunder(rng, 7.5, close=1.0)


@asset("thunder_2")
def thunder_2(rng):
    return L.thunder(rng, 7.0, close=0.0)


@asset("splash_small")
def splash_small(rng):
    return L.splash(rng, 0.35, bright=1.1)


# ============================================================================
# UI & CLAY FOLEY
# ============================================================================

@asset("ui_click")
def ui_click(rng):
    out = np.zeros(ns(0.12))
    L.place(out, L.pop(rng, 430, 170, 0.075, amp=1.0), 0)
    L.place(out, L.squelch(rng, 0.05, 1100, 0.25), 0)
    L.place(out, L.click(rng, 3200, 0.004, 0.15, 1.0), 0)
    return out


@asset("ui_hover")
def ui_hover(rng):
    out = np.zeros(ns(0.04))
    L.place(out, L.pop(rng, 2500, 1900, 0.02, amp=1.0), 0)
    L.place(out, L.click(rng, 5000, 0.003, 0.2, 1.5), 0)
    return out


@asset("ui_open")
def ui_open(rng):
    out = np.zeros(ns(0.18))
    n = ns(0.1)
    t = tvec(n)
    f = 230 + 420 * (1 - np.exp(-t / 0.025))
    L.place(out, L.glide_sine(f, (1 - np.exp(-t / 0.002)) * np.exp(-t / 0.03)), 0)
    L.place(out, L.squelch(rng, 0.06, 900, 0.3), 0)
    L.place(out, L.pop(rng, 900, 1250, 0.04, amp=0.35), ns(0.045))
    return out


@asset("ui_close")
def ui_close(rng):
    out = np.zeros(ns(0.16))
    L.place(out, L.pop(rng, 640, 200, 0.1, tau=0.025, amp=1.0), 0)
    L.place(out, L.squelch(rng, 0.06, 800, 0.3), 0)
    return out


@asset("ui_error")
def ui_error(rng):
    out = np.zeros(ns(0.55))
    for t, f, a in ((0.0, 196.0, 1.0), (0.14, 164.8, 0.85)):
        n = ns(0.35)
        tt = tvec(n)
        fm = 1 + 0.06 * np.exp(-tt / 0.02)
        x = dsp.modal_tv([f, f * 2.32, f * 4.1], [1.0, 0.3, 0.08], [0.28, 0.1, 0.05], n, fm, attack=0.002)
        L.place(x, L.squelch(rng, 0.04, 600, 0.15), 0)
        L.place(out, x * a, ns(t))
    return out


def _coin_hit(rng, base, amp):
    ratios = [1.0, 1.53, 2.21, 2.87, 3.62]
    fr = [base * r * rng.uniform(0.99, 1.01) for r in ratios]
    x = L.modal_bank(L.impulses(ns(0.3), [0], [1]), fr, [1.0, 0.7, 0.5, 0.35, 0.2],
                     [0.11, 0.08, 0.06, 0.045, 0.03])
    x[:ns(0.002)] += hp(rng.standard_normal(ns(0.002)), 4000) * 0.4
    return x * amp


@variants("coin", 3)
def coin(rng, i):
    out = np.zeros(ns(0.6))
    if i == 1:
        b = rng.uniform(3100, 3400)
        for t, a in ((0, 1.0), (0.058, 0.4), (0.09, 0.18)):
            L.place(out, _coin_hit(rng, b, a), ns(t))
    elif i == 2:
        b1, b2 = 3500, 2850
        for t, a, b in ((0, 1.0, b1), (0.004, 0.8, b2), (0.07, 0.35, b2), (0.11, 0.15, b1)):
            L.place(out, _coin_hit(rng, b, a), ns(t))
    else:
        t = 0.0
        for k in range(5):
            L.place(out, _coin_hit(rng, rng.uniform(2700, 3900), rng.uniform(0.5, 1.0) * (1 - 0.12 * k)), ns(t))
            t += rng.uniform(0.035, 0.075)
    return out


@asset("register")
def register(rng):
    n = ns(2.0)
    out = np.zeros(n)
    key = L.wood_thump(rng, [130, 260, 450], [0.06, 0.05, 0.03], [1, 0.6, 0.3], 0.3, 0.002, 0.2)
    L.place(out, key * 1.0, 0)
    for k in range(5):  # ratchet "cha"
        L.place(out, L.metal_hit(rng, rng.uniform(1500, 2800), 5, 0.035, 1.4, 0.55 - 0.05 * k), ns(0.012 + k * 0.021))
    slide_n = ns(0.28)
    ts = tvec(slide_n)
    slide = bp(rng.standard_normal(slide_n), 950, 0.8) * (0.6 + 0.4 * np.sin(2 * np.pi * 38 * ts) ** 2)
    slide *= dsp.env_points([(0, 0), (0.03, 1), (0.25, 0.7), (0.28, 0)], slide_n)
    L.place(out, slide * 0.35, ns(0.12))
    stop = L.metal_hit(rng, 540, 6, 0.15, 1.3, 0.5)
    L.place(out, stop, ns(0.4))
    L.place(out, L.wood_thump(rng, [110, 210, 340], [0.08, 0.06, 0.04], [1, .6, .3], 0.1, 0.003, 0.2) * 0.9, ns(0.4))
    m = L.bell_modes(rng, 1950, length=0.55, bright=1.35)
    ching = L.ring_bell(rng, m, [(0.0, 1.0)], 1.6)
    L.place(out, ching * 0.9, ns(0.15))
    return L.mono_reverb(out, rt60=0.5, wet=0.12)


@asset("page_turn")
def page_turn(rng):
    dur = 0.55
    out = np.zeros(ns(dur + 0.1))
    w = L.whoosh(rng, dur, [(0, 2400), (0.5, 1200), (1, 2800)], [(0, 0), (0.3, 1), (0.75, 0.6), (1, 0)], q=0.7)
    L.place(out, w * 0.5, 0)
    cr = L.granular(rng, dur, 1800, 2000, 9000, [(0, 0.3), (0.2, 1), (0.6, 0.4), (0.9, 0.9), (1, 0)], grain=0.0002)
    L.place(out, cr * 1.2, 0)
    k = ns(0.03)
    flap = lp(rng.standard_normal(k), 350) * np.exp(-np.arange(k) / (0.006 * SR))
    L.place(out, flap * 0.6, ns(dur * 0.85))
    return out


@asset("dialogue_next")
def dialogue_next(rng):
    out = np.zeros(ns(0.08))
    L.place(out, L.pop(rng, 820, 560, 0.05, amp=1.0), 0)
    L.place(out, L.squelch(rng, 0.03, 1500, 0.12), 0)
    return out


@asset("item_get")
def item_get(rng):
    out = np.zeros(ns(3.2))
    for k, m in enumerate((86, 90, 93, 98)):  # D6 F#6 A6 D7
        f = float(dsp.midi_hz(m))
        L.place(out, I.celesta(f, 0.4, 0.85, rng), ns(k * 0.065))
        L.place(out, 0.6 * I.glock(f, 0.4, 0.7, rng), ns(k * 0.065))
    g = glimmer(rng)
    L.place(out, g * 0.35, ns(0.2))
    return L.mono_reverb(out, rt60=1.2, wet=0.2, hf_ratio=0.6)


@asset("stamp")
def stamp(rng):
    out = np.zeros(ns(0.5))
    desk = L.wood_thump(rng, [108, 190, 330, 560, 900], [0.14, 0.1, 0.07, 0.05, 0.03], [1, .75, .5, .3, .15],
                        0.15, 0.003, 0.45)
    L.place(out, desk, 0)
    k = ns(0.02)
    L.place(out, bp(rng.standard_normal(k), 1600, 0.8) * np.exp(-np.arange(k) / (0.003 * SR)) * 0.5, 0)
    L.place(out, L.squelch(rng, 0.05, 600, 0.35), 0)
    return out


@variants("clay_squish", 3)
def clay_squish(rng, i):
    dur = [0.38, 0.5, 0.3][i - 1]
    n = ns(dur + 0.1)
    out = np.zeros(n)
    sq = L.squelch(rng, dur, [700, 520, 900][i - 1], 1.0)
    L.place(out, sq, 0)
    t = tvec(ns(dur))
    thick = lp(rng.standard_normal(t.size), 260) * np.sin(np.pi * t / dur) ** 2 * \
        (1 + 0.6 * smooth_noise(t.size, 30, rng, periodic=False))
    L.place(out, thick * 0.6, 0)
    fs = dsp.env_points([(0, 280), (dur, 820 if i != 2 else 380)], t.size)
    sweep = svf(rng.standard_normal(t.size), fs, 6.0, "bp") * np.sin(np.pi * t / dur) * 0.6
    L.place(out, sweep, 0)
    for _ in range(rng.integers(2, 5)):
        L.place(out, L.bubble(rng, rng.uniform(260, 650), rng.uniform(0.02, 0.05), 1.5, rng.uniform(0.15, 0.4)),
                ns(rng.uniform(0.02, dur * 0.9)))
    return out


# ============================================================================
# AMBIENCES (stereo loops)
# ============================================================================

def _scatter(rng, n, count, min_gap=0.0):
    ts = np.sort(rng.uniform(0, n / SR, count))
    return ts


def _distant(x, cut=3500.0):
    return lp(x, cut)


@asset("amb_harbor_day", kind="ambience", loop=True)
def amb_harbor_day(rng):
    S = 32.0
    n = ns(S)
    bed = L.water_bed(n, rng, cut=650, swell_rate=0.12, depth=0.7) * 0.32
    ev = np.zeros((2, n))
    for t in _scatter(rng, n, int(S * 1.3)):
        L.place(ev, dsp.pan(L.lap_event(rng, rng.uniform(0.3, 1.0)), rng.uniform(-0.7, 0.7)), ns(t), wrap=True)
    far = np.zeros((2, n))
    calls = [L.gull_kyow(rng, 1.0), L.gull_kyow(rng, 0.92), None, L.gull_kyow(rng, 1.05)]
    for k, t in enumerate(np.sort(rng.uniform(0, S, 5))):
        if k == 2:
            g = np.zeros(ns(1.2))
            tt = 0.0
            for j in range(4):
                L.place(g, L.gull_ha(rng, 1300 * 0.97 ** j, 0.12, 1 - 0.1 * j), ns(tt))
                tt += 0.19
        else:
            g = L.gull_kyow(rng, rng.uniform(0.9, 1.08))
        g = _distant(g, rng.uniform(3000, 4500)) * rng.uniform(0.25, 0.5)
        L.place(far, dsp.pan(g, rng.uniform(-0.85, 0.85)), ns(t), wrap=True)
    for t in rng.uniform(0, S, 4):
        L.place(far, dsp.pan(L.creak(rng, rng.uniform(0.7, 1.3), 35, 110, 0.12, pitch=0.7),
                             rng.uniform(-0.6, 0.6)), ns(t), wrap=True)
    for t in rng.uniform(0, S, 6):  # halyard tinks on a mast
        L.place(far, dsp.pan(_distant(L.metal_hit(rng, rng.uniform(1300, 1700), 5, 0.4, 1.3, 0.08), 6000),
                             0.5), ns(t), wrap=True)
    far = L.loop_reverb(far, rt60=1.4, wet=0.35, hf_ratio=0.4)
    ev = L.loop_reverb(ev, rt60=0.6, wet=0.12)
    w = L.wind(n, rng, center=520, gust=0.5, gust_rate=0.09) * 0.07
    return bed + ev * 0.55 + far + w


@asset("amb_harbor_night", kind="ambience", loop=True)
def amb_harbor_night(rng):
    S = 30.0
    n = ns(S)
    bed = L.water_bed(n, rng, cut=480, swell_rate=0.1, depth=0.7) * 0.3
    ev = np.zeros((2, n))
    for t in _scatter(rng, n, int(S * 0.9)):
        L.place(ev, dsp.pan(L.lap_event(rng, rng.uniform(0.25, 0.8)), rng.uniform(-0.7, 0.7)), ns(t), wrap=True)
    ev = dsp.circular(ev, lambda z: lp(z, 3000), 0.5)
    far = np.zeros((2, n))
    m = L.bell_modes(rng, 610, length=1.6, bright=0.85)
    for t0, strikes in ((3.0, [(0, 1.0), (0.9, 0.6)]), (17.0, [(0, 0.8)]), (24.5, [(0, 0.7), (0.75, 0.5)])):
        b = L.ring_bell(rng, m, strikes, 7.0)
        L.place(far, dsp.pan(_distant(b, 2600) * 0.35, -0.35), ns(t0), wrap=True)
    L.place(far, dsp.pan(L.creak(rng, 1.2, 30, 90, 0.1, pitch=0.6), 0.4), ns(11.0), wrap=True)
    far = L.loop_reverb(far, rt60=2.6, wet=0.5, hf_ratio=0.35)
    w = L.wind(n, rng, center=360, gust=0.45, gust_rate=0.07) * 0.06
    return bed + ev * 0.5 + far + w


@asset("amb_sea_calm", kind="ambience", loop=True)
def amb_sea_calm(rng):
    S = 30.0
    n = ns(S)
    bed = L.water_bed(n, rng, cut=1100, swell_rate=0.16, depth=0.9, slope=-3.5) * 0.4
    sw = np.zeros((2, n))
    for t in np.arange(6) * (S / 6) + rng.uniform(-1, 1, 6):
        d = rng.uniform(2.5, 4.0)
        s = L.slosh(rng, d, rng.uniform(500, 900), 1.0)
        L.place(sw, dsp.pan(s, rng.uniform(-0.6, 0.6)), ns(t % S), wrap=True)
    ev = np.zeros((2, n))
    for t in _scatter(rng, n, int(S * 0.8)):
        L.place(ev, dsp.pan(L.lap_event(rng, rng.uniform(0.3, 0.8)), rng.uniform(-0.3, 0.3)), ns(t), wrap=True)
    far = np.zeros((2, n))
    g = _distant(L.gull_kyow(rng, 0.95), 3000) * 0.25
    L.place(far, dsp.pan(g, 0.7), ns(rng.uniform(5, 25)), wrap=True)
    far = L.loop_reverb(far, rt60=1.5, wet=0.4)
    w = L.wind(n, rng, center=700, gust=0.6, gust_rate=0.1, whistle=0.04, whistle_f=1100) * 0.11
    return bed + sw * 0.35 + ev * 0.4 + far + w


@asset("amb_sea_storm", kind="ambience", loop=True)
def amb_sea_storm(rng):
    S = 28.0
    n = ns(S)
    w = L.wind(n, rng, center=650, q=0.5, gust=0.95, gust_rate=0.18, whistle=0.3, whistle_f=950,
               low=0.6) * 0.5
    rain = L.rain_bed(n, rng, density=2600, hiss=0.8) * 0.2
    roar = L.water_bed(n, rng, cut=1500, swell_rate=0.22, depth=1.0, slope=-3.0) * 0.45
    ev = np.zeros((2, n))
    for k, t in enumerate((2.0, 11.5, 20.5)):
        c = L.wave_crash(rng, rng.uniform(1.0, 1.35))
        L.place(ev, dsp.pan(c, [-0.5, 0.45, -0.1][k]), ns(t + rng.uniform(-0.8, 0.8)), wrap=True)
    for t in rng.uniform(0, S, 5):
        L.place(ev, dsp.pan(_wave_slap(rng, rng.uniform(0.7, 1.1), rng.uniform(70, 95)) * 0.6,
                            rng.uniform(-0.4, 0.4)), ns(t), wrap=True)
    for t in rng.uniform(0, S, 3):
        L.place(ev, dsp.pan(L.creak(rng, rng.uniform(0.9, 1.4), 30, 90, 0.3, pitch=0.55), rng.uniform(-0.5, 0.5)),
                ns(t), wrap=True)
    th = L.thunder(rng, 7.0, close=0.0) * 0.45
    L.place(ev, dsp.pan(th, 0.2), ns(15.5), wrap=True)
    ev = L.loop_reverb(ev, rt60=1.2, wet=0.15)
    return w + rain + roar + ev * 0.42


@asset("amb_rain_roof", kind="ambience", loop=True)
def amb_rain_roof(rng):
    S = 24.0
    n = ns(S)
    out = np.zeros((2, n))
    m = ns(0.06)
    tm = tvec(m)
    count = int(520 * S)
    times = rng.uniform(0, S, count)
    for t0 in times:
        a = rng.random() ** 2.2
        f = math.exp(rng.uniform(math.log(1900), math.log(7500)))
        d = rng.uniform(0.008, 0.03)
        ping = np.sin(2 * np.pi * f * tm) * np.exp(-6.9 * tm / d)
        ping += 0.5 * np.sin(2 * np.pi * f * rng.uniform(1.3, 1.9) * tm) * np.exp(-6.9 * tm / (d * 0.6))
        if a > 0.5:  # heavier drop: dull tonk of the panel
            ping += 0.6 * np.sin(2 * np.pi * rng.uniform(380, 900) * tm) * np.exp(-6.9 * tm / 0.05)
        ping[:3] += rng.uniform(-1, 1, 3)
        L.place(out, dsp.pan(ping * a, rng.uniform(-0.85, 0.85)), ns(t0), wrap=True)
    out *= 0.22
    hiss = np.stack([colored_noise(n, rng, -2.0) for _ in range(2)])
    hiss = dsp.circular(hiss, lambda z: bp(z, 3800, 0.5), 0.3) * 0.05
    drum = np.stack([colored_noise(n, rng, -6.0) for _ in range(2)])
    drum = dsp.circular(drum, lambda z: hp(lp(z, 240), 60), 0.5) * 0.12
    outside = np.stack([colored_noise(n, rng, -3.0) for _ in range(2)])
    outside = dsp.circular(outside, lambda z: lp(z, 900), 0.5) * 0.05
    drips = np.zeros((2, n))
    t = 0.3
    while t < S - 0.05:
        d = L.modal_bank(L.impulses(ns(0.4), [0], [1]), [1780, 2650, 4100], [1.0, 0.4, 0.2], [0.12, 0.08, 0.05])
        L.place(d, L.bubble(rng, rng.uniform(900, 1300), 0.04, 1.6, 0.4), 0)
        L.place(drips, dsp.pan(d * rng.uniform(0.15, 0.3), 0.6), ns(t), wrap=True)
        t += rng.uniform(0.55, 0.95)
    x = out + hiss + drum + outside + drips
    return L.loop_reverb(x, rt60=0.5, wet=0.15, hf_ratio=0.5)


@asset("amb_shop", kind="ambience", loop=True)
def amb_shop(rng):
    S = 30.0
    n = ns(S)
    t = tvec(n)
    room = np.stack([colored_noise(n, rng, -6.0) for _ in range(2)])
    room = dsp.circular(room, lambda z: hp(lp(z, 320), 70), 0.5) * 0.12
    hum = (0.010 * np.sin(2 * np.pi * 100.0 * t) + 0.007 * np.sin(2 * np.pi * 100.5 * t)
           + 0.004 * np.sin(2 * np.pi * 200.0 * t) + 0.002 * np.sin(2 * np.pi * 300.0 * t))
    hum *= 1 + 0.2 * np.sin(2 * np.pi * t / 6.0)  # 5 cycles per loop
    clock = np.zeros((2, n))
    for k in range(30):
        f = 2500 if k % 2 == 0 else 2150
        tick = L.modal_bank(L.impulses(ns(0.15), [0], [1]), [f, f * 1.6, 420], [0.5, 0.3, 0.4], [0.02, 0.015, 0.04])
        L.place(clock, dsp.pan(tick * 0.05, -0.55), ns(k * 1.0), wrap=True)
    outside = np.zeros((2, n))
    ob = L.water_bed(n, rng, cut=500, swell_rate=0.1, depth=0.6) * 0.2
    for tt in _scatter(rng, n, 18):
        L.place(outside, dsp.pan(L.lap_event(rng, rng.uniform(0.3, 0.7)), rng.uniform(0.2, 0.8)), ns(tt), wrap=True)
    for tt in (6.0, 19.5):
        L.place(outside, dsp.pan(L.gull_kyow(rng, rng.uniform(0.9, 1.05)) * 0.45, 0.6), ns(tt + rng.uniform(-1, 1)),
                wrap=True)
    outside = dsp.circular(outside + ob, lambda z: lp(lp(z, 700), 900), 1.0) * 0.6
    misc = np.zeros((2, n))
    L.place(misc, dsp.pan(L.creak(rng, 0.7, 60, 140, 0.08, pitch=0.9), -0.2), ns(13.0), wrap=True)
    L.place(misc, dsp.pan(L.metal_hit(rng, 3100, 4, 0.12, 1.5, 0.03), 0.3), ns(24.0), wrap=True)  # ice settles
    x = room + np.stack([hum, hum]) + clock + outside + misc
    return L.loop_reverb(x, rt60=0.55, wet=0.18, hf_ratio=0.5)


# ============================================================================
# build
# ============================================================================

AMB_LUFS = -24.0


def best_roll(x, win_s=0.05, step_s=0.002):
    """Rotate a seamless loop so the seam sits where the 50 ms windows either
    side match best and no transient straddles it (rotation keeps it seamless)."""
    n = x.shape[-1]
    w = ns(win_s)
    m = x if x.ndim == 1 else x.mean(axis=0)
    p2 = x ** 2 if x.ndim == 1 else (x ** 2).mean(axis=0)
    e = np.concatenate([p2, p2[:w]])
    c = np.concatenate([[0.0], np.cumsum(e)])
    step = max(1, ns(step_s))
    idx = np.arange(w, n + 1, step)
    after = (c[np.minimum(idx + w, c.size - 1)] - c[idx]) / w
    before = (c[idx] - c[idx - w]) / w
    diff = np.abs(10 * np.log10((after + 1e-12) / (before + 1e-12)))
    d = np.abs(np.diff(np.concatenate([m, m[:1]])))
    jump = d[(idx - 1) % n] / (np.percentile(d, 99) + 1e-12)
    loud = 10 * np.log10((after + before) / 2 + 1e-12)
    score = diff + 2.0 * jump + 0.05 * (loud - loud.min())
    k = int(idx[int(np.argmin(score))]) % n
    return np.roll(x, -k, axis=-1)


# ----------------------------------------------------------------------------
# perceived-loudness balancing for one-shots
# ----------------------------------------------------------------------------

# (regex on asset name, target LUFS).  First match wins.
LOUDNESS_TARGETS = [
    (r"step_(wood|sand|stone)_\d$", -26.0),
    (r"ui_hover$", -30.0),
    (r"(ui_click|ui_open|ui_close|ui_error|dialogue_next|page_turn)$", -24.0),  # ui_error: not in brief, UI group
    (r"(coin_\d|register|item_get|stamp)$", -20.0),
    (r"(gull_\d|seal_bark|crab_click)$", -24.0),
    (r"(buoy_bell|foghorn|boat_horn)$", -18.0),
    (r"(splash_small|bobber_plop|nibble)$", -24.0),
    (r"(bite_splash|fish_splash|fish_flop_\d)$", -20.0),
    (r"splash_big$", -17.0),  # not in brief: between bite_splash (-20) and wave_crash_big (-14)
    (r"(pot_drop|pot_surface|crab_clatter|chain_rattle|dredge_drop|dredge_up|winch_strain)$", -19.0),
    (r"(wave_slap_\d|hull_creak_\d)$", -21.0),
    (r"(wave_crash_big|thunder_\d)$", -14.0),
    (r"(ice_crack|ice_hammer_\d)$", -19.0),
    (r"(cast_whoosh|sonar_ping|glimmer)$", -22.0),
    (r"(door_open|door_close|shop_bell)$", -21.0),
    (r"clay_squish_\d$", -24.0),
]
ONESHOT_CEILING_DBTP = -1.0
SHORT_SOUND_S = 1.0
LIMIT_MAX_GR_DB = 4.0
LIMIT_LAST_RESORT_GR_DB = 7.0


def loudness_target(name):
    import re
    for pat, tgt in LOUDNESS_TARGETS:
        if re.match(pat, name):
            return tgt
    return None


def _k_weight(x):
    import pyloudnorm as pyln
    meter = pyln.Meter(SR)
    y = np.asarray(x, dtype=float).copy()
    for f in meter._filters.values():
        y = f.apply_filter(y)
    return y


def momentary_max_lufs(x, win_s=0.4):
    """Loudest 400 ms K-weighted window (mono), zero-padded if shorter."""
    y = _k_weight(x)
    w = ns(win_s)
    if y.size < w:
        y = np.pad(y, (0, w - y.size))
    c = np.concatenate([[0.0], np.cumsum(y * y)])
    ms = (c[w:] - c[:-w]) / w
    return float(-0.691 + 10 * np.log10(ms.max() + 1e-20))


def oneshot_loudness(x):
    x = np.asarray(x, dtype=float)
    if x.ndim == 2:
        x = x.mean(axis=0)
    return dsp.lufs(x) if x.size >= ns(SHORT_SOUND_S) else momentary_max_lufs(x)


def _gain_limit(x, target, ceiling_dbtp, max_gr):
    """Static gain to `target`, look-ahead limiting at most `max_gr` dB of
    transient; returns (y, reached)."""
    lim_ceiling = ceiling_dbtp - 0.6  # sample-peak ceiling; true-peak guard below
    g = target - oneshot_loudness(x)
    y = x * dsp.undb(g)
    if dsp.true_peak_db(y) > ceiling_dbtp:
        for _ in range(6):
            gr = dsp.peak_db(x) + g - lim_ceiling
            if gr > max_gr:
                g -= gr - max_gr
            y = dsp.limiter(x * dsp.undb(g), lim_ceiling, lookahead_ms=2.0, release_ms=60.0)[0]
            err = target - oneshot_loudness(y)
            if abs(err) < 0.1 or gr >= max_gr:
                break
            g += err
    y = _tp_guard(y, ceiling_dbtp)
    return y, abs(oneshot_loudness(y) - target) <= 0.3


def lookahead_comp(x, thresh_db, ratio=3.0, look_ms=3.0, release_ms=120.0, knee_db=6.0):
    """Look-ahead peak compressor: the detector sees transients `look_ms` early
    (centred max filter), so peaks are reduced together with the body and the
    peak-to-loudness ratio actually drops (unlike an attack-time compressor)."""
    import scipy.ndimage as ndi
    W = max(1, ns(look_ms * 1e-3))
    env = ndi.maximum_filter1d(np.abs(x), 2 * W + 1, mode="nearest")
    over = dsp.db(env) - thresh_db
    gr = np.where(over <= -knee_db / 2, 0.0,
                  np.where(over >= knee_db / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee_db / 2) ** 2 / (2 * knee_db)))
    gr = dsp._smooth_gr(gr, 0.0, math.exp(-1.0 / (release_ms * 1e-3 * SR)))  # instant attack, slow release
    from scipy.ndimage import uniform_filter1d
    gr = uniform_filter1d(gr, 2 * W + 1, mode="nearest")  # de-zipper (still ahead of the peak)
    return x * dsp.undb(-gr)


def _zero_mean(x):
    """Remove residual mean of a short one-shot with a smooth (Hann) bump, so no
    step is introduced at the ends."""
    m = float(np.mean(x))
    if abs(m) < 2e-4 or x.size < 64:
        return x
    w = np.hanning(x.size)
    return x - m * w / w.mean()


def match_loudness(x, target, ceiling_dbtp=ONESHOT_CEILING_DBTP, max_gr=LIMIT_MAX_GR_DB):
    """Bring a one-shot to `target` LUFS with true peak <= ceiling.
    1) static gain (+ at most `max_gr` dB of look-ahead limiting on transients);
    2) if that can't reach the target (very peaky sounds: thunder crack over a
       quiet rumble, coin clinks), progressively deeper 4:1 look-ahead
       compression (short release for clicks) before the limiter.  Whatever is
       still short after the deepest setting is left short (reported)."""
    y, ok = _gain_limit(x, target, ceiling_dbtp, max_gr)
    if ok:
        return y
    short = x.size < ns(SHORT_SOUND_S)
    rel = 12.0 if short else 120.0
    pk = dsp.peak_db(x)
    best, best_err = y, abs(oneshot_loudness(y) - target)
    for mg in (max_gr, LIMIT_LAST_RESORT_GR_DB):  # second pass: allow a bit more limiting
        for depth in (6, 9, 12, 15, 18, 21, 24, 27, 30):
            c = lookahead_comp(x, thresh_db=pk - depth, ratio=4.0, release_ms=rel)
            y, ok = _gain_limit(c, target, ceiling_dbtp, mg)
            err = abs(oneshot_loudness(y) - target)
            if err < best_err:
                best, best_err = y, err
            if ok:
                return best
    return best


def finish(x, kind, loop, name=None):
    x = np.asarray(x, dtype=float)
    if kind == "ambience":
        x = dsp.circular(x, lambda z: dsp.dc_block(z, 15.0), 2.0)
        x = dsp.normalize_lufs(x, AMB_LUFS, -5.0, loop=True)
        return best_roll(x)
    if loop:
        x = dsp.circular(x, lambda z: dsp.dc_block(z, 15.0), 1.0)
        return best_roll(_tp_guard(dsp.normalize_peak(x, -3.0)))
    x = dsp.dc_block(x, 15.0)
    x = dsp.trim_silence(x, -62.0, 0.0, 0.01, 0.01)
    tgt = loudness_target(name) if name else None
    if tgt is None:
        return _tp_guard(dsp.normalize_peak(x, -3.0))
    x = _zero_mean(dsp.normalize_peak(x, -3.0))
    return _tp_guard(_zero_mean(match_loudness(x, tgt)), ONESHOT_CEILING_DBTP)


def _tp_guard(x, max_tp=-1.5):
    """Keep inter-sample (true) peaks of sharp transients below max_tp dBTP."""
    tp = dsp.true_peak_db(x)
    return x * dsp.undb(max_tp - tp) if tp > max_tp else x


def render(name):
    fn, kind, loop, _ = ASSETS[name]
    rng = dsp.rng_for("sfx", name)
    return finish(fn(rng), kind, loop, name)


def _job(args):
    try:
        return _job_inner(args)
    except Exception:  # report every failure at the end instead of dying on the first
        import traceback
        return {"error": args[0], "trace": traceback.format_exc()}


def _job_inner(args):
    name, sfx_dir, out_dir, png = args
    fn, kind, loop, _ = ASSETS[name]
    x = render(name)
    path = os.path.join(sfx_dir, name + ".wav")
    dsp.write_wav(path, x)
    y = dsp.read_audio(path)
    y = y[0] if y.shape[0] == 1 else y
    entry, diag = dsp.describe(path, y, kind, loop)
    if entry["lufs"] is not None and not math.isfinite(entry["lufs"]):
        entry["lufs"] = None
    tgt = loudness_target(name) if not loop and kind == "sfx" else None
    if tgt is not None:
        # report one-shots with the same measure they are balanced by
        diag["lufs_integrated"] = entry["lufs"]
        diag["loudness_rule"] = ("integrated" if y.shape[-1] >= ns(SHORT_SOUND_S)
                                 else "max momentary (400 ms)")
        diag["loudness_target"] = tgt
        entry["lufs"] = round(oneshot_loudness(y), 2)
    if png:
        dsp.spectrogram_png(y, os.path.join(out_dir, "sfx", name + ".png"), name)
    return {"entry": entry, "diag": diag}


def build(sfx_dir, out_dir, only=None, jobs=8, png=False):
    names = [n for n in ASSETS if only is None or n in only]
    if not names:
        return []
    os.makedirs(sfx_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "sfx"), exist_ok=True)
    args = [(n, sfx_dir, out_dir, png) for n in names]
    if jobs <= 1 or len(names) == 1:
        results = [_job(a) for a in args]
    else:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            results = list(ex.map(_job, args))
    errors = [r for r in results if "error" in r]
    results = [r for r in results if "error" not in r]
    for r in results:
        e, d = r["entry"], r["diag"]
        extra = ""
        if e["loop"]:
            extra = f" seam rmsΔ {d['rms_diff_db']:.2f} dB ratio {d['seam_ratio']:.2f}"
        print(f"  {e['file']:24s} {e['kind']:8s} {e['seconds']:6.2f}s  LUFS {e['lufs']!s:>7}  "
              f"peak {e['peak_db']:6.2f}{extra}")
    if errors:
        for r in errors:
            print(f"FAILED {r['error']}:\n{r['trace']}")
        raise RuntimeError(f"{len(errors)} SFX failed: {[r['error'] for r in errors]}")
    return results


if __name__ == "__main__":
    ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
    SFX_DIR = os.path.join(ROOT, "Game", "Assets", "Saltmoss", "Audio", "Sfx")
    OUT = os.path.join(HERE, "out")
    argv = sys.argv[1:]
    png = "--png" in argv
    argv = [a for a in argv if a != "--png"]
    build(SFX_DIR, OUT, only=argv or None, jobs=max(1, (os.cpu_count() or 4) - 2), png=png)
