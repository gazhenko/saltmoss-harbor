"""Saltmoss Harbor - original score (all synthesized).

One main motif - "The Saltmoss Shanty" - a sea-shanty waltz in D major:

    | D5. C#5 D5 | A5-- F#5 | G5 F#5 E5 | F#5. E5 D5 | ...
      (neighbour turn, leap up a fifth, fall to the third, stepwise home)

It is quoted / varied in every cue: waltz (title), swung 4/4 (town day),
music-box lullaby (night), rolling 6/8 (sea calm), minor 6/8 (storm),
jazzy shop swing, augmented & minor (museum), and the trailer.
"""
from __future__ import annotations

import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dsp  # noqa: E402
import instruments as I  # noqa: E402
from dsp import SR, ns, n2m  # noqa: E402
from score import Grid, Mix, voice, uke_shape, bass_pitch, parse_line  # noqa: E402

# ============================================================================
# the motif (D major, 3/4, durations in eighth notes)
# ============================================================================

MOTIF_A1 = ("D5:3 C#5:1 D5:2 | A5:4 F#5:2 | G5:2 F#5:2 E5:2 | F#5:3 E5:1 D5:2 | "
            "B4:2 D5:2 G5:2 | F#5:3 E5:1 D5:2 | E5:2 F#5:2 G5:2 | A5:6")
CH_A1 = "D D G Bm G D/F# Em7 A"
MOTIF_A2 = ("D5:3 C#5:1 D5:2 | A5:4 F#5:2 | G5:2 A5:2 B5:2 | A5:3 F#5:1 D5:2 | "
            "B4:2 D5:2 G5:2 | F#5:3 E5:1 D5:2 | E5:3 D5:1 C#5:2 | D5:6")
CH_A2 = "D D G Bm7 G D/F# A7 D"
MOTIF_B = ("G5:3 F#5:1 G5:2 | B5:4 G5:2 | A5:2 G5:2 F#5:2 | E5:6 | "
           "F#5:3 E5:1 F#5:2 | A5:4 F#5:2 | G5:2 F#5:2 E5:2 | E5:4 A4:2")
CH_B = "G Em D A Bm F#m G A7"

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def tr_chords(chords, semis, flats=False):
    names = FLAT_NAMES if flats else SHARP_NAMES
    out = []
    for c in chords.split():
        root = c[0] + (c[1] if len(c) > 1 and c[1] in "#b" else "")
        rest = c[len(root):]
        bass = ""
        if "/" in rest:
            rest, b = rest.split("/")
            bass = "/" + names[(n2m(b + "4") + semis) % 12]
        out.append(names[(n2m(root + "4") + semis) % 12] + rest + bass)
    return " ".join(out)


def chords_list(s):
    return s.split()


def shape_vel(notes, base=0.75, spread=0.35, accent_every=None):
    """Musical phrasing: higher notes a bit louder, long notes lean in."""
    if not notes:
        return notes
    ms = np.array([n["m"] for n in notes], float)
    mu = ms.mean()
    out = []
    for n in notes:
        v = base * (1 + spread * (n["m"] - mu) / 12.0)
        v *= 1.0 + 0.08 * min(1.0, n["full"] / 1.2)
        out.append(dict(n, vel=float(np.clip(v * n["vel"] / 0.8, 0.15, 1.1))))
    return out


# ============================================================================
# accompaniment helpers
# ============================================================================

def play_notes(tr, inst, notes, legato=1.0, human=1.0, **kw):
    for n in notes:
        tr.note(inst, n["t"], n["m"], n["dur"] * legato, n["vel"], human=human, **kw)


def strum(tr, t, chord, vel, direction="D", dur=0.6, spread=None, inst=None, skip_top=None, ring=1.0):
    inst = inst or I.uke_note
    notes = list(uke_shape(chord))
    order = notes if direction == "D" else notes[::-1]
    if direction == "U":
        if skip_top is None:
            skip_top = tr.mix.rng.random() < 0.5
        if skip_top:
            order = order[:-1]
    sp = spread if spread is not None else (0.012 if direction == "D" else 0.008)
    t = t + tr.jitter()
    for i, m in enumerate(order):
        v = vel * (1 - 0.05 * i) * (0.72 if direction == "U" else 1.0)
        tr.note(inst, t + i * sp, m, dur - i * sp, v, human=0.15, ring=ring)


def strum_pattern(tr, g, bar, chord, pattern, vel=0.6, dur_units=None):
    """pattern: string over eighth slots, e.g. 'D.DUDU' (3/4) or 'D.DU.UDU' (4/4).
    '.' = no strum."""
    for i, ch in enumerate(pattern):
        if ch in "DU":
            t = g.t(bar, i)
            nxt = next((j for j in range(i + 1, len(pattern)) if pattern[j] in "DU"), len(pattern))
            d = g.t(bar, nxt) - t + 0.03
            accent = 1.0 if i % 2 == 0 else 0.85
            if i == 0:
                accent *= 1.08
            strum(tr, t, chord, vel * accent, ch, dur=d)


def uke_arp(tr, g, bar, chord, pattern=(0, 2, 3, 1, 3, 2), vel=0.5, ring=1.6, step=1.0, inst=None):
    inst = inst or I.uke_note
    notes = sorted(uke_shape(chord))
    for i, idx in enumerate(pattern):
        if idx is None:
            continue
        t = g.t(bar, i * step)
        tr.note(inst, t, notes[idx % len(notes)], g.e * ring * 2, vel * (1.1 if i == 0 else 0.9))


def bass_waltz(tr, g, bar, chord, vel=0.75, fifth=False, walk_to=None):
    m = bass_pitch(chord)
    tr.note(I.bass_pizz, g.t(bar, 0), m, g.e * 3.4, vel, human=0.6)
    if fifth:
        f5 = bass_pitch(chord, which="fifth", center=m + 5)
        tr.note(I.bass_pizz, g.t(bar, 4), f5, g.e * 1.6, vel * 0.8, human=0.6)
    if walk_to:
        tr.note(I.bass_pizz, g.t(bar, 4), walk_to, g.e * 1.6, vel * 0.8, human=0.6)


def acc_chord(tr, t, chord, dur, vel, lo=n2m("F#3"), hi=n2m("E5"), prev=None, n=3, **kw):
    v = voice(chord, lo, hi, prev=prev, n=n)
    for m in v:
        tr.note(I.accordion_note, t, m, dur, vel, human=0.25, **kw)
    return v


def glock_arp(tr, g, bar, chord, pattern, vel=0.4, octave_lo=n2m("D6") - 2, inst=None, step=1.0):
    inst = inst or I.glock
    root = chord_root_m(chord, octave_lo)
    from score import chord_pcs
    pcs = chord_pcs(chord)
    tones = sorted({m for m in range(octave_lo, octave_lo + 15) if m % 12 in pcs})
    for i, idx in enumerate(pattern):
        if idx is None:
            continue
        tr.note(inst, g.t(bar, i * step), tones[idx % len(tones)], g.e, vel * (1.0 if i == 0 else 0.85))


def chord_root_m(chord, lo):
    from score import parse_chord
    root, _, _ = parse_chord(chord)
    return lo + ((root - lo) % 12)


# ============================================================================
# cues
# ============================================================================

MASTER_EQ = [("hp", 28, 0.7, 0), ("peak", 180, 0.8, 1.0), ("hs", 7500, 0.7, 2.5)]

def cue_title():
    """Title theme: the shanty waltz. D major 3/4, 100 bpm, 48 bars = 86.4 s."""
    g = Grid.from_bpm(100, bar=6)
    bars = 48
    mx = Mix("title_theme", bars * g.bar_s, ir=dict(rt60=2.3, predelay=0.025, hf_ratio=0.33, er_level=0.6))
    acc = mx.track("acc_mel", gain_db=-3.5, pan=-0.22, eq=I.ACC_BODY, rev=0.22)
    accp = mx.track("acc_pad", gain_db=-9.0, pan=-0.4, eq=I.ACC_BODY + [("hp", 160, 0.7, 0)], rev=0.3, width=1.0)
    uke = mx.track("uke", gain_db=0.0, pan=0.32, eq=I.UKE_BODY, rev=0.16, rev2=0.12)
    glk = mx.track("glock", gain_db=-8.0, pan=0.18, eq=[("hp", 500, 0.7, 0), ("hs", 9000, 0.7, -2)], rev=0.32)
    bass = mx.track("bass", gain_db=-0.5, pan=0.0, eq=I.BASS_BODY, rev=0.05, human=0.004)

    intro = "D Bm G A"
    turn = "D Bm G A7"
    form = [("intro", intro), ("A1", CH_A1), ("A2", CH_A2), ("B", CH_B), ("A2", CH_A2),
            ("A1w", CH_A1), ("turn", turn)]
    bar = 0
    prev = None
    for sec, chs in form:
        chords = chs.split()
        for i, c in enumerate(chords):
            b = bar + i
            # --- bass
            if sec == "intro":
                if i >= 2:
                    bass_waltz(bass, g, b, c, 0.6)
            elif sec in ("A1w",):
                bass_waltz(bass, g, b, c, 0.6)
            else:
                walk = None
                bass_waltz(bass, g, b, c, 0.78, fifth=(sec in ("B", "A2") and i % 2 == 1))
            # --- uke
            if sec in ("intro", "A1w"):
                uke_arp(uke, g, b, c, vel=0.5)
            elif sec == "A1":
                strum_pattern(uke, g, b, c, "..D.D.", vel=0.5)
            elif sec == "turn":
                strum_pattern(uke, g, b, c, "D.D.D.", vel=0.45)
            else:
                strum_pattern(uke, g, b, c, "D.DUDU", vel=0.55)
            # --- accordion pad / left hand
            if sec in ("intro", "A2", "A1w", "turn"):
                lvl = {"intro": 0.55, "A2": 0.5, "A1w": 0.58, "turn": 0.5}[sec]
                prev = acc_chord(accp, g.t(b, 0), c, g.bar_s * 0.98, lvl, prev=prev, swell=0.25, lo=n2m("D3"), hi=n2m("C5"),
                                 attack=0.12, reeds=((0.0, 1.0), (5.0, 0.6)))
            elif sec in ("A1", "B"):
                for k in (2, 4):
                    prev = acc_chord(accp, g.t(b, k), c, g.e * 1.1, 0.5, prev=prev, attack=0.02,
                                     reeds=((0.0, 1.0), (1200.0, 0.35)))
        # --- melodies
        if sec == "intro":
            nts = g.notes("D6:3 C#6:1 D6:2 | A6:6 | r:6 | r:6", bar0=bar, vel=0.55)
            play_notes(glk, I.glock, nts)
            nts = g.notes("r:6 | r:6 | B5:2 D6:2 G6:2 | F#6:3 E6:1 C#6:2", bar0=bar, vel=0.4)
            play_notes(glk, I.glock, nts)
        elif sec == "A1":
            nts = shape_vel(g.notes(MOTIF_A1, bar0=bar, legato=0.97, vel=0.72))
            play_notes(acc, I.accordion_note, nts)
        elif sec == "A2" and bar < 20:
            nts = shape_vel(g.notes(MOTIF_A2, bar0=bar, vel=0.7), spread=0.25)
            play_notes(glk, I.glock, [dict(n, m=n["m"] + 12) for n in nts])
            # accordion answers with a low sustained counter-line
            cl = g.notes("F#4:6 | F#4:4 A4:2 | B4:6 | D5:6 | D5:6 | A4:6 | G4:3 F#4:1 E4:2 | F#4:6",
                         bar0=bar, legato=0.98, vel=0.5)
            play_notes(acc, I.accordion_note, cl, reeds=((0.0, 1.0), (5.0, 0.6)))
        elif sec == "B":
            nts = shape_vel(g.notes(MOTIF_B, bar0=bar, legato=0.97, vel=0.76))
            play_notes(acc, I.accordion_note, nts, reeds=((0.0, 1.0), (7.0, 0.75), (-1200.0, 0.3)))
            for i, c in enumerate(CH_B.split()):
                glock_arp(glk, g, bar + i, c, (None, None, 2, 1, 0, 1) if i % 2 == 0 else (None, None, 3, 2, 1, 2),
                          vel=0.35)
        elif sec == "A2":
            nts = shape_vel(g.notes(MOTIF_A2, bar0=bar, legato=0.97, vel=0.8))
            play_notes(acc, I.accordion_note, nts, reeds=((0.0, 1.0), (7.0, 0.75), (-1200.0, 0.35)))
            play_notes(glk, I.glock, [dict(n, m=n["m"] + 12, vel=n["vel"] * 0.7) for n in nts])
        elif sec == "A1w":
            nts = shape_vel(g.notes(MOTIF_A1, bar0=bar, vel=0.72), spread=0.2)
            play_notes(glk, I.glock, [dict(n, m=n["m"] + 12) for n in nts])
        elif sec == "turn":
            nts = shape_vel(g.notes("F#5:3 E5:1 D5:2 | D5:3 C#5:1 B4:2 | B4:2 D5:2 G5:2 | E5:3 C#5:1 A4:2",
                                    bar0=bar, legato=0.95, vel=0.6), spread=0.2)
            play_notes(acc, I.accordion_note, nts)
        bar += len(chords)
    assert bar == bars, bar
    out = mx.render(target_lufs=-16.0, master_eq=MASTER_EQ)
    return out, {"bar_s": g.bar_s}


# ---------------------------------------------------------------------------
# shared 4/4 + 6/8 helpers
# ---------------------------------------------------------------------------

def bar_chords(s):
    """'G C|D7 Em' -> [['G'], ['C', 'D7'], ['Em']] (a '|' splits a bar in halves)."""
    return [c.split("|") for c in s.split()]


def chord_at(bars, i, half):
    b = bars[i]
    return b[min(half, len(b) - 1)]


SCALES = {"G": [7, 9, 11, 0, 2, 4, 6], "D": [2, 4, 6, 7, 9, 11, 1], "F": [5, 7, 9, 10, 0, 2, 4],
          "C": [0, 2, 4, 5, 7, 9, 11], "Dm": [2, 4, 5, 7, 9, 10, 1], "Am": [9, 11, 0, 2, 4, 5, 8]}


def diatonic(notes, steps, key):
    """Shift a line by scale steps (e.g. -2 = a diatonic third below)."""
    sc = sorted(SCALES[key])
    out = []
    for n in notes:
        m = n["m"]
        pc = m % 12
        if pc in sc:
            octv, i = divmod(sc.index(pc) + steps, 7)
            nm = (m - pc) + sc[i] + 12 * octv
        else:
            nm = m - (3 if steps < 0 else -4)
        out.append(dict(n, m=nm))
    return out


def bass_44(tr, g, bar, chord, nxt, vel=0.75, walk=False):
    r = bass_pitch(chord)
    if not walk:
        tr.note(I.bass_pizz, g.t(bar, 0), r, g.e * 3.2, vel, human=0.5)
        f5 = bass_pitch(chord, which="fifth", center=r + 3)
        tr.note(I.bass_pizz, g.t(bar, 4), f5, g.e * 3.2, vel * 0.85, human=0.5)
        return
    from score import chord_pcs
    pcs = chord_pcs(chord)
    third = min((m for m in range(r + 1, r + 6) if m % 12 in pcs), default=r + 7)
    fifth = r + 7 if (r + 7) % 12 in pcs else third + 3
    target = bass_pitch(nxt)
    if abs(target - r) > 7:
        target += 12 if target < r else -12
    appr = target + (1 if target < fifth else -1)
    seq = [r, third, fifth, appr]
    for k, m in enumerate(seq):
        tr.note(I.bass_pizz, g.t(bar, 2 * k), m, g.e * 1.8, vel * (1.0 if k % 2 == 0 else 0.86), human=0.5)


def brushes_44(tr, g, bar, vel=0.6, ghosts=True):
    for k in (0, 4):
        t0 = g.t(bar, k)
        tr.put(t0 + tr.jitter(), I.brush_sweep(g.e * 2.0, vel * 0.8, tr.mix.rng), pan=-0.15)
    for k in (2, 6):
        tr.hit(I.brush_tap, g.t(bar, k), vel)
    if ghosts:
        for k in (3, 7):
            tr.hit(I.brush_tap, g.t(bar, k), vel * 0.35)


def shaker_8ths(tr, g, bar, vel=0.5, nslots=8):
    for k in range(nslots):
        tr.hit(I.shaker, g.t(bar, k), vel * (1.0 if k % 2 else 0.6))


def marimba_line(tr, notes, roll_over=0.55, vel_scale=1.0):
    for n in notes:
        if n["full"] >= roll_over:
            k = int(n["full"] / 0.085)
            for j in range(k):
                v = n["vel"] * vel_scale * (1.0 if j == 0 else 0.55 + 0.1 * math.sin(j))
                tr.note(I.marimba, n["t"] + j * 0.085, n["m"], 0.2, v, human=0.25)
        else:
            tr.note(I.marimba, n["t"], n["m"], n["dur"], n["vel"] * vel_scale)


def cue_town_day():
    """Town by day: bouncy swung 4/4 in G, whistle/marimba/uke/brushes.
    112 bpm, 56 bars = 120 s."""
    g = Grid.from_bpm(112, bar=8, swing=0.6)
    bars = 56
    mx = Mix("town_day", bars * g.bar_s, ir=dict(rt60=1.5, predelay=0.015, hf_ratio=0.4, er_level=0.8))
    wh = mx.track("whistle", gain_db=-6.5, pan=-0.12, eq=[("hp", 300, 0.7, 0), ("peak", 2500, 1.0, -1.5)], rev=0.2)
    mar = mx.track("marimba", gain_db=-3.5, pan=0.28, eq=[("hp", 120, 0.7, 0), ("peak", 900, 1.0, -1.0)], rev=0.18)
    uke = mx.track("uke", gain_db=-1.0, pan=-0.3, eq=I.UKE_BODY, rev=0.12, rev2=0.12)
    bass = mx.track("bass", gain_db=-2.5, eq=I.BASS_BODY, rev=0.04, human=0.004)
    br = mx.track("brushes", gain_db=-5.0, pan=0.1, eq=[("hp", 200, 0.7, 0)], rev=0.06, rev2=0.2, human=0.005)
    sh = mx.track("shaker", gain_db=-8.0, pan=0.45, rev=0.05, rev2=0.15, human=0.004)

    TD_A = ("G4:3 F#4:1 G4:2 D5:2 | B4:4 r:2 A4:1 B4:1 | C5:3^ B4:1 C5:2 E5:2 | D5:4 r:2 B4:1 C5:1 | "
            "D5:2 E5:2 D5:2 B4:2 | C5:2 A4:2 F#4:2 D4:2 | G4:1 A4:1 B4:1 D5:1 C5:2 A4:2 | G4:4 r:4")
    CH_TA = "G G C G Em7 D7 G|D7 G"
    TD_A2 = ("G4:3 F#4:1 G4:2 D5:2 | B4:4 r:2 A4:1 B4:1 | C5:3^ B4:1 C5:2 E5:2 | D5:4 r:2 B4:1 C5:1 | "
             "E5:2 D5:2 C5:2 E5:2 | D5:2 B4:2 G4:2 B4:2 | A4:3 B4:1 C5:2 A4:2 | G4:6 r:2")
    CH_TA2 = "G G C G C G D7 G"
    TD_B = ("E5:3 D#5:1 E5:2 B5:2 | G5:4 r:2 F#5:1 E5:1 | D5:3 C#5:1 D5:2 A5:2 | F#5:4 r:2 E5:1 D5:1 | "
            "C5:2 E5:2 G5:2 E5:2 | D5:2 B4:2 G4:2 B4:2 | A4:2 C5:2 E5:2 D5:2 | C5:2 B4:2 A4:2 F#4:2")
    CH_TB = "Em Em D D C G Am7|D7 D7"
    form = [("intro", "G C G D7"), ("A", CH_TA), ("A2", CH_TA2), ("B", CH_TB), ("A2b", CH_TA2),
            ("inter", "G Em C D7"), ("B2", CH_TB), ("A2c", CH_TA2)]
    bar = 0
    all_bars = []
    for sec, chs in form:
        all_bars += [(sec, b) for b in bar_chords(chs)]
    for i, (sec, bc) in enumerate(all_bars):
        nxt = all_bars[(i + 1) % len(all_bars)][1][0]
        c0 = bc[0]
        walk = sec in ("B", "A2b", "B2", "A2c")
        if len(bc) == 1:
            bass_44(bass, g, i, c0, nxt, vel=0.75, walk=walk)
            pat = "D.DU.UDU"
            strum_pattern(uke, g, i, c0, pat, vel=0.5 if sec != "inter" else 0.58)
        else:
            for h, c in enumerate(bc):
                r = bass_pitch(c)
                bass.note(I.bass_pizz, g.t(i, 4 * h), r, g.e * 3.2, 0.75, human=0.5)
                for k, d in ((0, "D"), (2, "D"), (3, "U")):
                    strum(uke, g.t(i, 4 * h + k), c, 0.5, d, dur=g.e * 1.3)
        brushes_44(br, g, i, 0.55 if sec in ("intro", "A") else 0.68, ghosts=True)
        if sec in ("B", "A2b", "B2", "A2c"):
            shaker_8ths(sh, g, i, 0.55)
        if sec == "B2":
            # marimba off-beat comping
            v = voice(c0 if len(bc) == 1 else bc[0], n2m("D4"), n2m("D5"), n=3)
            for k in (3, 7):
                for m in v[1:]:
                    mar.note(I.marimba, g.t(i, k), m, 0.15, 0.42, human=0.3)
    # melodies
    starts = {}
    b = 0
    for sec, chs in form:
        starts.setdefault(sec, b)
        b += len(chs.split())
    wl = lambda line, b0, tr=12, v=0.78: shape_vel(g.notes(line, bar0=b0, legato=0.92, vel=v, transpose=tr), spread=0.15)
    mar.note  # noqa
    # intro riff
    marimba_line(mar, g.notes("r:8 | r:8 | G5:3 F#5:1 G5:2 D6:2 | C6:2 A5:2 F#5:2 D5:2", bar0=starts["intro"], vel=0.6))
    wh.line(I.whistle_line, wl(TD_A, starts["A"]))
    wh.line(I.whistle_line, wl(TD_A2, starts["A2"]))
    marimba_line(mar, diatonic(g.notes(TD_A2, bar0=starts["A2"], vel=0.5), -2, "G"), vel_scale=0.9)
    marimba_line(mar, g.notes(TD_B, bar0=starts["B"], vel=0.72))
    wh.line(I.whistle_line, wl("B5:8 | B5:6 r:2 | A5:8 | A5:6 r:2 | G5:8 | G5:6 r:2 | E5:4 F#5:4 | F#5:6 r:2",
                               starts["B"], tr=0, v=0.5))
    wh.line(I.whistle_line, wl(TD_A2, starts["A2b"]))
    marimba_line(mar, g.notes(TD_A2, bar0=starts["A2b"], vel=0.55))
    marimba_line(mar, g.notes("G5:3 F#5:1 G5:2 D6:2 | B5:4 r:4 | C6:3 B5:1 C6:2 E6:2 | D6:2 C6:2 B5:2 A5:2",
                              bar0=starts["inter"], vel=0.7))
    wh.line(I.whistle_line, wl(TD_B, starts["B2"], tr=0, v=0.72))
    wh.line(I.whistle_line, wl(TD_A2, starts["A2c"]))
    marimba_line(mar, diatonic(g.notes(TD_A2, bar0=starts["A2c"], vel=0.5), -2, "G"), vel_scale=0.9)
    # pickup run into the loop restart
    marimba_line(mar, g.notes("r:5 D5:1 E5:1 F#5:1", bar0=bars - 1, vel=0.55))
    out = mx.render(target_lufs=-16.0, master_eq=MASTER_EQ)
    return out, {"bar_s": g.bar_s}


# ---------------------------------------------------------------------------
# more helpers
# ---------------------------------------------------------------------------

def chord_tones(chord, lo, span=24):
    from score import chord_pcs
    pcs = chord_pcs(chord)
    return [m for m in range(lo, lo + span + 1) if m % 12 in pcs]


def arp(tr, inst, g, bar, chord, pattern, lo, vel=0.5, step=1.0, dur_e=2.0, accent=1.1, **kw):
    tones = chord_tones(chord, lo)
    for i, idx in enumerate(pattern):
        if idx is None:
            continue
        tr.note(inst, g.t(bar, i * step), tones[idx % len(tones)], g.e * dur_e,
                vel * (accent if i == 0 else 1.0), **kw)


def pad_chords(tr, g, bar0, chords, vel, lo=n2m("D3"), hi=n2m("D5"), n=4, bars=1.0, **kw):
    prev = None
    for i, c in enumerate(chords):
        prev = acc_chord(tr, g.t(bar0 + i * bars, 0), c, g.bar_s * bars * 1.0, vel, lo=lo, hi=hi,
                         prev=prev, n=n, **kw)


def guitar_68(tr, g, bar, chord, vel=0.5, inst=None):
    inst = inst or I.nylon_note
    b = bass_pitch(chord, lo=n2m("D2"), hi=n2m("D3"), center=n2m("A2"))
    v = voice(chord, n2m("D3"), n2m("B4"), n=3)
    seq = [b, v[0], v[1], v[2], v[1], v[0]]
    for i, m in enumerate(seq):
        tr.note(inst, g.t(bar, i), m, g.e * (5.5 - i), vel * (1.15 if i in (0, 3) else 0.9))


def bass_68(tr, g, bar, chord, vel=0.7, second="fifth"):
    r = bass_pitch(chord)
    tr.note(I.bass_pizz, g.t(bar, 0), r, g.e * 2.6, vel, human=0.5)
    if second:
        m = bass_pitch(chord, which="fifth", center=r + 3) if second == "fifth" else r
        tr.note(I.bass_pizz, g.t(bar, 3), m, g.e * 2.6, vel * 0.82, human=0.5)


def bodhran_68(tr, g, bar, vel=0.6, fill=False):
    pat = [(0, 1.0, 0.0), (1, 0.35, 0.6), (2, 0.5, 0.3), (3, 0.8, 0.0), (4, 0.35, 0.6), (5, 0.5, 1.0)]
    for e, v, tone in pat:
        tr.hit(I.bodhran, g.t(bar, e), vel * v, tone=tone)
    if fill:
        for k in range(3):
            tr.hit(I.bodhran, g.t(bar, 4 + k * 0.667), vel * (0.5 + 0.15 * k), tone=0.7)


def ostinato_68(tr, g, bar, chord, vel=0.7, pattern=(0, 1, 1, 0, 1, 2)):
    r = bass_pitch(chord, lo=n2m("A1"), hi=n2m("G#2"), center=n2m("D2"))
    tones = [r, r + 12, r + 19]
    accents = [1.0, 0.62, 0.72, 0.92, 0.62, 0.75]
    for i, idx in enumerate(pattern):
        m = tones[idx]
        st = I.strings_note(float(dsp.midi_hz(m)), g.e * 0.75, vel * accents[i], tr.mix.rng, voices=3,
                            attack=0.012, release=0.09, vib=0.04, bright=1.1)
        tr.put(g.t(bar, i) + tr.jitter(0.5), st)


def strings_pad(tr, g, bar0, chords, vel=0.5, lo=n2m("D2"), hi=n2m("D4"), n=3, bars=1.0, attack=0.6, **kw):
    prev = None
    for i, c in enumerate(chords):
        v = voice(c, lo, hi, prev=prev, n=n)
        prev = v
        for m in v:
            st = I.strings_note(float(dsp.midi_hz(m)), g.bar_s * bars, vel, tr.mix.rng, attack=attack, **kw)
            tr.put(g.t(bar0 + i * bars, 0) + tr.jitter(0.5), st)


def timp_roll(tr, g, bar, e0, e1, m, v0=0.25, v1=0.9, rate=0.06):
    t0, t1 = g.t(bar, e0), g.t(bar, e1)
    k = max(2, int((t1 - t0) / rate))
    for j in range(k):
        v = v0 + (v1 - v0) * (j / (k - 1)) ** 1.5
        tr.put(t0 + j * rate + tr.jitter(0.3), I.timpani(float(dsp.midi_hz(m)), v, tr.mix.rng, length=0.7))


# ---------------------------------------------------------------------------
# town night - music-box lullaby
# ---------------------------------------------------------------------------

def cue_town_night():
    """Night in town: music-box / celesta lullaby over a soft accordion pad.
    G major 3/4, 72 bpm, 36 bars = 90 s."""
    g = Grid.from_bpm(72, bar=6)
    bars = 36
    mx = Mix("town_night", bars * g.bar_s, ir=dict(rt60=2.9, predelay=0.03, hf_ratio=0.3, er_level=0.5))
    mb = mx.track("musicbox", gain_db=-3.0, pan=0.12, eq=[("hp", 350, 0.7, 0), ("peak", 4500, 1.0, 2.5)], rev=0.35,
                  human=0.006)
    cel = mx.track("celesta", gain_db=-5.5, pan=-0.25, eq=[("hp", 200, 0.7, 0)], rev=0.35)
    pad = mx.track("acc_pad", gain_db=-10.5, pan=-0.1, eq=I.ACC_BODY + [("hs", 3000, 0.7, -5)], rev=0.4, width=1.0)
    bass = mx.track("bass", gain_db=-0.5, eq=I.BASS_BODY + [("lp", 1500, 0.7, 0)], rev=0.12, human=0.004)
    vc = mx.track("cello", gain_db=-9.0, pan=0.25, eq=I.CELLO_BODY + [("lp", 2500, 0.7, 0)], rev=0.4)

    A1 = ("G5:3 F#5:1 G5:2 | D6:4 B5:2 | C6:2 B5:2 A5:2 | B5:3 A5:1 G5:2 | "
          "E5:2 G5:2 C6:2 | B5:3 A5:1 G5:2 | A5:2 B5:2 C6:2 | D6:6")
    CA1 = "Gmaj7 G6 Cmaj7 Em7 Cmaj7 G/B Am7 D7sus4"
    B = ("C6:3 B5:1 C6:2 | E6:4 C6:2 | D6:2 C6:2 B5:2 | A5:6 | "
         "B5:3 A5:1 B5:2 | D6:4 B5:2 | C6:2 B5:2 A5:2 | A5:4 D5:2")
    CB = "Cmaj7 Am7 G D Em7 Bm7 Cmaj7 D7"
    A2 = ("G5:3 F#5:1 G5:2 | D6:4 B5:2 | C6:2 D6:2 E6:2 | D6:3 B5:1 G5:2 | "
          "E5:2 G5:2 C6:2 | B5:3 A5:1 G5:2 | A5:3 G5:1 F#5:2 | G5:6")
    CA2 = "Gmaj7 G6 Cmaj7 Em7 Cmaj7 G/B D7 Gmaj7"
    OUT = "Em9 Cmaj7 G D Em9 Cmaj7 Am7 D7sus4"
    INTRO = "Gmaj7 Em9 Cmaj7 D7sus4"
    form = [("intro", INTRO), ("A1", CA1), ("B", CB), ("A2", CA2), ("out", OUT)]
    bar = 0
    soft = dict(reeds=((0.0, 1.0), (4.0, 0.5)), attack=0.45, swell=0.3, bright=0.55, release=0.4)
    for sec, chs in form:
        chords = chs.split()
        pad_chords(pad, g, bar, chords, 0.5 if sec != "out" else 0.45, **soft)
        for i, c in enumerate(chords):
            b = bar + i
            if sec != "intro" or i >= 2:
                bass.note(I.bass_pizz, g.t(b, 0), bass_pitch(c), g.e * 5, 0.42)
            if sec == "intro":
                arp(cel, I.celesta, g, b, c, (0, 1, 2, 3, 4, 3), n2m("C5"), vel=0.4, dur_e=3)
            elif sec in ("A1", "A2"):
                arp(cel, I.celesta, g, b, c, (None, None, 1, None, 2, None), n2m("G4"), vel=0.34, dur_e=3)
            elif sec == "B":
                arp(mb, I.music_box, g, b, c, (None, 4, None, 5, None, 6), n2m("C6"), vel=0.3, dur_e=2)
            elif sec == "out":
                arp(cel, I.celesta, g, b, c, (0, None, 2, None, 3, None), n2m("E4"), vel=0.33, dur_e=4)
        if sec == "A1":
            play_notes(mb, I.music_box, shape_vel(g.notes(A1, bar0=bar, vel=0.62), spread=0.2))
        elif sec == "B":
            play_notes(cel, I.celesta, shape_vel(g.notes(B, bar0=bar, vel=0.62, transpose=-12), spread=0.2))
            strings_pad(vc, g, bar, chords, vel=0.35, lo=n2m("C3"), hi=n2m("C4"), n=2, attack=0.9, vib=0.1)
        elif sec == "A2":
            nts = shape_vel(g.notes(A2, bar0=bar, vel=0.62), spread=0.2)
            play_notes(mb, I.music_box, nts)
            play_notes(cel, I.celesta, [dict(n, vel=n["vel"] * 0.6) for n in diatonic(nts, -2, "G")])
        elif sec == "out":
            frag = ("G5:3 F#5:1 G5:2 | D6:6 | r:6 | r:6 | E5:3 D#5:1 E5:2 | B5:6 | r:6 | A5:4 r:2")
            play_notes(mb, I.music_box, g.notes(frag, bar0=bar, vel=0.5))
            strings_pad(vc, g, bar, chords, vel=0.3, lo=n2m("C3"), hi=n2m("C4"), n=2, attack=1.0, vib=0.1)
        bar += len(chords)
    assert bar == bars, bar
    out = mx.render(target_lufs=-16.0, master_eq=MASTER_EQ + [("hs", 5000, 0.7, 2.0)])
    return out, {"bar_s": g.bar_s}


# ---------------------------------------------------------------------------
# sea - calm
# ---------------------------------------------------------------------------

SC_A = ("D5:3 C#5:1 D5:2 | A5:4 F#5:2 | G5:2 F#5:1 E5:3 | D5:6 | "
        "F#5:3 E5:1 D5:2 | B4:2 A4:1 D5:3 | E5:2 F#5:1 G5:2 E5:1 | D5:6")
CH_SA = "D D C G D G A7 D"
SC_A2 = ("D5:3 C#5:1 D5:2 | A5:3 B5:1 A5:2 | C6:2 B5:1 G5:3 | A5:4 G5:1 F#5:1 | "
         "G5:3 F#5:1 E5:2 | F#5:2 E5:1 D5:3 | E5:2 D5:1 C#5:2 A4:1 | D5:6")
CH_SA2 = "D D C D Em Bm A7 D"
SC_B = ("F#5:3 E5:1 F#5:2 | B5:4 A5:2 | G5:3 F#5:1 E5:2 | F#5:6 | "
        "E5:3 D5:1 E5:2 | G5:4 E5:2 | E5:3 G5:3 | A5:4 r:2")
CH_SB = "Bm Bm Em D C Am7 A7 A"


def cue_sea_calm():
    """Open water: rolling 6/8 in D (mixolydian colour), fiddle air over
    accordion, nylon guitar and bass.  dotted-quarter = 60, 60 bars = 120 s."""
    g = Grid(1.0 / 3.0, bar=6)
    bars = 60
    mx = Mix("sea_calm", bars * g.bar_s, ir=dict(rt60=2.6, predelay=0.03, hf_ratio=0.33, er_level=0.5))
    fid = mx.track("fiddle", gain_db=-4.0, pan=0.18, eq=I.FIDDLE_BODY, rev=0.26)
    acc = mx.track("acc_mel", gain_db=-6.0, pan=-0.25, eq=I.ACC_BODY, rev=0.22)
    pad = mx.track("acc_pad", gain_db=-9.0, pan=-0.35, eq=I.ACC_BODY + [("hs", 3500, 0.7, -4)], rev=0.3)
    gtr = mx.track("guitar", gain_db=1.5, pan=0.32, eq=I.NYLON_BODY, rev=0.2)
    bass = mx.track("bass", gain_db=-2.5, eq=I.BASS_BODY, rev=0.05, human=0.004)
    bod = mx.track("bodhran", gain_db=1.0, pan=-0.05, eq=[("hp", 45, 0.7, 0), ("peak", 300, 1.0, -3)],
                   rev=0.08, rev2=0.15, human=0.005)
    glk = mx.track("glock", gain_db=-14.0, pan=0.4, eq=[("hp", 600, 0.7, 0)], rev=0.4)

    BRIDGE = "Bm G D A Bm G C A"
    form = [("intro", "D C G D"), ("A", CH_SA), ("A2", CH_SA2), ("B", CH_SB), ("A3", CH_SA),
            ("bridge", BRIDGE), ("B2", CH_SB), ("out", CH_SA2)]
    starts = {}
    bar = 0
    for sec, chs in form:
        starts[sec] = bar
        chords = chs.split()
        padlvl = {"intro": 0.5, "bridge": 0.55, "out": 0.45}.get(sec, 0.42)
        pad_chords(pad, g, bar, chords, padlvl, lo=n2m("D3"), hi=n2m("B4"), n=3, attack=0.35, swell=0.35,
                   reeds=((0.0, 1.0), (5.0, 0.55)), release=0.3, bright=0.7)
        for i, c in enumerate(chords):
            b = bar + i
            guitar_68(gtr, g, b, c, vel=0.5 if sec not in ("B", "A3", "B2") else 0.42)
            if not (sec == "intro" and i < 2):
                bass_68(bass, g, b, c, 0.62 if sec in ("intro", "bridge") else 0.72,
                        second=None if sec == "bridge" else "fifth")
            if sec in ("B", "A3", "B2"):
                bodhran_68(bod, g, b, 0.45 if sec == "B" else 0.6, fill=(i % 4 == 3))
            if sec == "A3":
                v = voice(c, n2m("F#4"), n2m("E5"), n=3)
                for e in (2, 5):
                    for m in v:
                        acc.note(I.accordion_note, g.t(b, e), m, g.e * 0.8, 0.42, human=0.3, attack=0.015,
                                 reeds=((0.0, 1.0), (1200.0, 0.3)))
        bar += len(chords)
    assert bar == bars, bar
    fl = lambda line, b0, v=0.78, tr=0: shape_vel(g.notes(line, bar0=b0, legato=0.96, vel=v, transpose=tr), spread=0.2)
    fid.line(I.fiddle_line, fl(SC_A, starts["A"]))
    fid.line(I.fiddle_line, fl(SC_A2, starts["A2"]))
    play_notes(acc, I.accordion_note, [dict(n, vel=n["vel"] * 0.55) for n in diatonic(fl(SC_A2, starts["A2"]), -2, "D")],
               reeds=((0.0, 1.0), (5.0, 0.5)))
    play_notes(glk, I.glock, g.notes("r:6 | r:6 | r:6 | D7:1 A6:1 F#6:4 | r:6 | r:6 | r:6 | A6:1 F#6:1 D6:4",
                                     bar0=starts["A2"], vel=0.5))
    play_notes(acc, I.accordion_note, fl(SC_B, starts["B"], v=0.76), reeds=((0.0, 1.0), (8.0, 0.8), (-1200.0, 0.3)))
    fid.line(I.fiddle_line, fl("D6:6 | D6:6 | B5:6 | A5:6 | G5:6 | A5:6 | G5:6 | E5:4 r:2", starts["B"], v=0.55))
    fid.line(I.fiddle_line, fl(SC_A, starts["A3"], v=0.82))
    fid.line(I.fiddle_line, fl("B4:6 | B4:6 | A4:6 | A4:6 | B4:6 | D5:6 | C5:6 | C#5:4 r:2", starts["bridge"], v=0.6))
    play_notes(glk, I.glock, g.notes("F#6:6 | r:6 | r:6 | E6:6 | r:6 | r:6 | r:6 | C#6:6", bar0=starts["bridge"], vel=0.4))
    fid.line(I.fiddle_line, fl(SC_B, starts["B2"], v=0.82))
    play_notes(acc, I.accordion_note, [dict(n, vel=n["vel"] * 0.55) for n in diatonic(fl(SC_B, starts["B2"]), -2, "D")],
               reeds=((0.0, 1.0), (6.0, 0.6)))
    play_notes(acc, I.accordion_note, fl(SC_A2, starts["out"], v=0.6), reeds=((0.0, 1.0), (4.0, 0.5)))
    fid.line(I.fiddle_line, fl("F#5:6 | F#5:6 | E5:6 | F#5:6 | G5:6 | F#5:6 | E5:6 | F#5:4 r:2", starts["out"], v=0.45))
    out = mx.render(target_lufs=-16.0, master_eq=MASTER_EQ)
    return out, {"bar_s": g.bar_s}


# ---------------------------------------------------------------------------
# sea - storm
# ---------------------------------------------------------------------------

ST_A = ("D5:3 C#5:1 D5:2 | A5:4 F5:2 | Bb5:2 A5:1 G5:3 | A5:3 E5:3 | "
        "D5:3 C#5:1 D5:2 | F5:2 E5:1 F5:2 G5:1 | A5:2 G5:1 F5:2 E5:1 | D5:6")
CH_STA = "Dm Dm Gm A Dm Bb A7 Dm"
ST_A2 = ("D5:3 C#5:1 D5:2 | A5:4 F5:2 | Bb5:2 A5:1 G5:3 | A5:3 E5:3 | "
         "F5:3 E5:1 D5:2 | C5:2 D5:1 E5:2 F5:1 | E5:3 C#5:1 A4:2 | D5:6")
CH_STA2 = "Dm Dm Gm A Bb C A Dm"
ST_B = ("F5:3 E5:1 F5:2 | C6:4 A5:2 | Bb5:2 A5:1 G5:3 | A5:6 | "
        "Bb5:3 A5:1 G5:2 | F5:3 E5:1 D5:2 | E5:2 F5:1 G5:2 E5:1 | A5:4 A4:2")
CH_STB = "F F Gm Dm Gm Dm C A"


def cue_sea_storm():
    """Storm: minor-key dramatic shanty in D minor, 6/8.  Low strings
    ostinato, timpani, accordion stabs, fiddle; the B strain turns to F major
    (cozy drama, not horror).  dotted-quarter = 80, 60 bars = 90 s."""
    g = Grid(0.25, bar=6)
    bars = 60
    mx = Mix("sea_storm", bars * g.bar_s, ir=dict(rt60=2.4, predelay=0.02, hf_ratio=0.33, er_level=0.7))
    fid = mx.track("fiddle", gain_db=-3.5, pan=0.2, eq=I.FIDDLE_BODY, rev=0.24)
    acc = mx.track("acc_mel", gain_db=-5.0, pan=-0.22, eq=I.ACC_BODY, rev=0.2)
    stab = mx.track("acc_stab", gain_db=-8.5, pan=-0.35, eq=I.ACC_BODY + [("hp", 200, 0.7, 0)], rev=0.18)
    ost = mx.track("low_str", gain_db=1.0, pan=0.0, eq=I.CELLO_BODY + [("hp", 55, 0.7, 0)], rev=0.2, width=1.0)
    spad = mx.track("str_pad", gain_db=-10.0, pan=0.0, eq=I.CELLO_BODY + [("hp", 90, 0.7, 0)], rev=0.3)
    timp = mx.track("timpani", gain_db=-1.0, pan=0.1, eq=[("hp", 42, 0.7, 0), ("peak", 250, 1.0, -2)], rev=0.25,
                    human=0.004)
    bass = mx.track("bass", gain_db=-6.5, eq=I.BASS_BODY, rev=0.05, human=0.004)
    bod = mx.track("bodhran", gain_db=2.0, pan=-0.08, eq=[("hp", 45, 0.7, 0), ("peak", 300, 1.0, -3)],
                   rev=0.08, rev2=0.15, human=0.004)
    D2, A1 = n2m("D2"), n2m("A1")

    INTRO = "Dm Dm Bb A"
    BREAK = "Dm Bb Gm A"
    form = [("intro", INTRO), ("A", CH_STA), ("A2", CH_STA2), ("B", CH_STB), ("break", BREAK), ("A3", CH_STA),
            ("B2", CH_STB), ("A4", CH_STA2), ("out", BREAK)]
    starts = {}
    bar = 0
    for sec, chs in form:
        starts[sec] = bar
        chords = chs.split()
        for i, c in enumerate(chords):
            b = bar + i
            heavy = sec in ("A3", "B2")
            if sec in ("B", "B2"):
                if i % 2 == 0:
                    strings_pad(spad, g, b, [c, chords[i + 1]], vel=0.6 if sec == "B" else 0.7, n=3, attack=0.25,
                                bars=1.0, vib=0.1, lo=n2m("D2"), hi=n2m("D4"))
                ostinato_68(ost, g, b, c, vel=0.5, pattern=(0, 1, 1, 0, 1, 1))
            elif sec == "break":
                strings_pad(spad, g, b, [c], vel=0.45 + 0.12 * i, n=3, attack=0.4, trem=0.6, vib=0.05)
                ostinato_68(ost, g, b, c, vel=0.55 + 0.1 * i)
            else:
                ostinato_68(ost, g, b, c, vel=0.72 if heavy else 0.62)
            # timpani
            tm = D2 if parse_root(c) in (2, 5, 10) else A1
            if sec == "break":
                timp_roll(timp, g, b, 0, 6, tm, 0.2 + 0.15 * i, 0.4 + 0.15 * i)
            else:
                timp.put(g.t(b, 0) + timp.jitter(0.3), I.timpani(float(dsp.midi_hz(tm)), 0.85 if heavy else 0.72,
                                                                 mx.rng))
                if i % 2 == 1 or heavy:
                    timp.put(g.t(b, 3) + timp.jitter(0.3), I.timpani(float(dsp.midi_hz(tm)), 0.5, mx.rng))
                if i == len(chords) - 1:
                    for k, e in enumerate((3, 4, 5)):
                        timp.put(g.t(b, e), I.timpani(float(dsp.midi_hz(A1)), 0.45 + 0.15 * k, mx.rng))
            # bass doubles roots
            bass_68(bass, g, b, c, 0.7, second="root")
            # accordion stabs
            if sec in ("intro", "A", "A3", "A4", "out") and not (sec == "intro" and i < 2):
                v = voice(c, n2m("A3"), n2m("F5"), n=3)
                for e, vv in ((0, 0.75), (3, 0.6)):
                    for m in v:
                        stab.note(I.accordion_note, g.t(b, e), m, g.e * 0.9, vv, human=0.25, attack=0.01,
                                  release=0.05, reeds=((0.0, 1.0), (9.0, 0.8), (1200.0, 0.35)))
            if sec == "break":
                v = voice(c, n2m("A3"), n2m("F5"), n=3)
                for m in v:
                    stab.note(I.accordion_note, g.t(b, 0), m, g.bar_s * 0.95, 0.55 + 0.1 * i, human=0.2,
                              attack=0.05, shake=0.5, reeds=((0.0, 1.0), (9.0, 0.8)))
            if sec in ("A2", "B", "A3", "B2", "A4"):
                bodhran_68(bod, g, b, 0.62 if heavy else 0.52, fill=(i % 4 == 3))
        bar += len(chords)
    assert bar == bars, bar
    fl = lambda line, b0, v=0.8, tr=0: shape_vel(g.notes(line, bar0=b0, legato=0.92, vel=v, transpose=tr), spread=0.2)
    full = ((0.0, 1.0), (9.0, 0.85), (-1200.0, 0.4))
    fid.line(I.fiddle_line, fl(ST_A, starts["A"]), vib_depth=0.2)
    play_notes(acc, I.accordion_note, fl(ST_A2, starts["A2"]), reeds=full)
    fid.line(I.fiddle_line, [dict(n, vel=n["vel"] * 0.6) for n in diatonic(fl(ST_A2, starts["A2"]), 2, "Dm")])
    fid.line(I.fiddle_line, fl(ST_B, starts["B"], v=0.85))
    play_notes(acc, I.accordion_note, fl(ST_B, starts["B"], v=0.6, tr=-12), reeds=((0.0, 1.0), (6.0, 0.6)))
    fid.line(I.fiddle_line, fl(ST_A, starts["A3"], v=0.9))
    play_notes(acc, I.accordion_note, fl(ST_A, starts["A3"], v=0.65, tr=-12), reeds=full)
    fid.line(I.fiddle_line, fl(ST_B, starts["B2"], v=0.9))
    play_notes(acc, I.accordion_note, fl(ST_B, starts["B2"], v=0.62, tr=-12), reeds=full)
    play_notes(acc, I.accordion_note, fl(ST_A2, starts["A4"], v=0.78), reeds=full)
    fid.line(I.fiddle_line, fl("A5:6 | A5:6 | Bb5:6 | A5:6 | Bb5:6 | C6:6 | C#6:6 | D6:4 r:2", starts["A4"], v=0.5))
    out = mx.render(target_lufs=-16.0, master_eq=MASTER_EQ + [("ls", 140, 0.7, -3.0), ("peak", 2800, 1.0, 1.5)])
    return out, {"bar_s": g.bar_s}


def parse_root(c):
    from score import parse_chord
    return parse_chord(c)[0]


# ---------------------------------------------------------------------------
# shop
# ---------------------------------------------------------------------------

SH_A = ("F5:3 E5:1 F5:2 C6:2 | A5:2 F#5:2 r:2 E5:1 F#5:1 | G5:3 F#5:1 G5:2 Bb5:2 | A5:2 G5:2 E5:2 C5:2 | "
        "E5:3 D#5:1 E5:2 G5:2 | F#5:2 A5:2 C6:2 D6:2 | Bb5:2 A5:1 G5:1 E5:2 C5:2 | F5:4 r:4")
CH_SHA = "Fmaj7 D7 Gm7 C7 Am7 D7 Gm7|C7 F6"
SH_B = ("D5:2 F5:2 A5:2 C6:2 | Db6:4 Bb5:2 G5:2 | C6:3 B5:1 C6:2 G5:2 | F#5:4 r:2 E5:1 F#5:1 | "
        "G5:2 Bb5:2 D6:2 F6:2 | E6:3 D6:1 C6:2 Bb5:2 | A5:2 F5:2 F#5:2 A5:2 | G5:3 E5:1 C5:2 E5:2")
CH_SHB = "Bbmaj7 Bbm6 Am7 D7 Gm7 C7 Fmaj7|D7 Gm7|C7"


def cue_shop():
    """The Salty Puffin shop: jaunty swung marimba tune with plucks, walking
    bass and brushes.  F major 4/4, 120 bpm, 40 bars = 80 s."""
    g = Grid.from_bpm(120, bar=8, swing=0.62)
    bars = 40
    mx = Mix("shop", bars * g.bar_s, ir=dict(rt60=1.1, predelay=0.012, hf_ratio=0.45, er_level=0.9, seed=3))
    mar = mx.track("marimba", gain_db=-2.5, pan=-0.15, eq=[("hp", 150, 0.7, 0)], rev=0.16, rev2=0.12)
    vib = mx.track("vibes", gain_db=-8.0, pan=0.35, eq=[("hp", 300, 0.7, 0)], rev=0.25)
    glk = mx.track("glock", gain_db=-15.0, pan=0.3, eq=[("hp", 600, 0.7, 0)], rev=0.25)
    uke = mx.track("uke", gain_db=-4.0, pan=0.3, eq=I.UKE_BODY, rev=0.1, rev2=0.15)
    gtr = mx.track("guitar", gain_db=-1.0, pan=0.2, eq=I.NYLON_BODY, rev=0.15)
    bass = mx.track("bass", gain_db=-3.5, eq=I.BASS_BODY, rev=0.04, human=0.004)
    br = mx.track("brushes", gain_db=-3.5, pan=0.1, eq=[("hp", 200, 0.7, 0)], rev=0.05, rev2=0.2, human=0.005)
    wb = mx.track("woodblock", gain_db=-1.0, pan=-0.45, rev=0.05, rev2=0.2, human=0.004)

    TURN = "Fmaj7 D7 Gm7 C7"
    form = [("intro", "Fmaj7 Dm7 Gm7 C7"), ("A", CH_SHA), ("A2", CH_SHA), ("B", CH_SHB), ("A3", CH_SHA),
            ("turn", TURN)]
    all_bars = []
    starts = {}
    b = 0
    for sec, chs in form:
        starts[sec] = b
        bc = bar_chords(chs)
        all_bars += [(sec, x) for x in bc]
        b += len(bc)
    assert b == bars
    for i, (sec, bc) in enumerate(all_bars):
        nxt = all_bars[(i + 1) % len(all_bars)][1][0]
        if len(bc) == 1:
            bass_44(bass, g, i, bc[0], nxt, vel=0.72, walk=True)
        else:
            for h, c in enumerate(bc):
                nx = bc[1] if h == 0 else nxt
                r = bass_pitch(c)
                tgt = bass_pitch(nx)
                bass.note(I.bass_pizz, g.t(i, 4 * h), r, g.e * 1.8, 0.72, human=0.5)
                bass.note(I.bass_pizz, g.t(i, 4 * h + 2), tgt + (1 if tgt < r else -1), g.e * 1.8, 0.62, human=0.5)
        # plucks: off-beat "chunk" chords on 2 & 4 (uke), guitar on the swung 'and' sometimes
        for h in range(2):
            c = bc[min(h, len(bc) - 1)]
            strum(uke, g.t(i, 4 * h + 2), c, 0.5, "D", dur=g.e * 0.9, spread=0.006)
            if sec in ("A2", "A3", "B") and h == 1:
                strum(uke, g.t(i, 4 * h + 3), c, 0.35, "U", dur=g.e * 0.6, spread=0.005)
        brushes_44(br, g, i, 0.5 if sec in ("intro", "turn") else 0.6, ghosts=True)
        if sec in ("intro", "A3"):
            for k, f in ((0, 1150.0), (4, 820.0)):
                wb.hit(I.woodblock, g.t(i, k), 0.5, f=f)
        if sec == "B":
            v = voice(bc[0], n2m("E4"), n2m("E5"), n=3)
            for k in (1, 5):
                for m in v:
                    mar.note(I.marimba, g.t(i, k), m, 0.12, 0.33, human=0.3)
    ml = lambda line, b0, v=0.75, tr=0: shape_vel(g.notes(line, bar0=b0, legato=0.9, vel=v, transpose=tr), spread=0.18)
    marimba_line(mar, ml(SH_A, starts["A"]), roll_over=0.7)
    marimba_line(mar, ml(SH_A, starts["A2"]), roll_over=0.7)
    play_notes(glk, I.glock, ml(SH_A, starts["A2"], v=0.45, tr=12))
    play_notes(gtr, I.nylon_note, ml(SH_B, starts["B"], v=0.8, tr=-12))
    marimba_line(mar, ml(SH_A, starts["A3"], v=0.78), roll_over=0.7)
    play_notes(vib, I.vibes, ml(SH_A, starts["A3"], v=0.45, tr=0))
    fill = ("C6:1 B5:1 Bb5:1 A5:1 Ab5:1 G5:1 F#5:1 F5:1 | F#5:2 A5:2 C6:2 D6:2 | "
            "Bb5:2 D6:2 G5:2 Bb5:2 | C6:2 Bb5:1 G5:1 E5:2 C5:2")
    marimba_line(mar, ml(fill, starts["turn"], v=0.66), roll_over=0.9)
    marimba_line(mar, g.notes("F5:2 A5:2 C6:2 E6:2", bar0=starts["intro"] + 3, vel=0.5), roll_over=0.9)
    out = mx.render(target_lufs=-16.0, master_eq=MASTER_EQ)
    return out, {"bar_s": g.bar_s}


# ---------------------------------------------------------------------------
# museum
# ---------------------------------------------------------------------------

MU_A = ("A5:3 G#5:1 A5:4 | E6:6 C6:2 | D6:2 C6:2 B5:2 G5:2 | B5:4 G#5:4 | "
        "A5:3 G#5:1 A5:2 C6:2 | B5:2 A5:2 E5:4 | F5:2 A5:2 C6:2 E6:2 | D6:4 B5:2 G#5:2")
CH_MA = "Am9 Fmaj7#11 Cmaj7/G E7sus4|E7 Am9 Fmaj7#11 Dm9 E7sus4|E7"
MU_B = ("C6:2 E6:2 r:2 D6:1 C6:1 | B5:4 r:2 G5:1 A5:1 | B5:2 D6:2 r:2 C6:1 B5:1 | A5:4 r:4 | "
        "F5:2 A5:2 E6:2 D6:2 | D6:3 C6:1 A5:4 | B5:2 A5:2 G#5:2 E5:2 | B5:8")
CH_MB = "Fmaj7 G6 Em7 Am7 Dm9 Bbmaj7#11 E7 E7"


def cue_museum():
    """Tidewrack Museum: gentle and curious - harp and celesta, soft cello,
    Lydian colours, the motif in A minor.  72 bpm 4/4, 24 bars = 80 s."""
    g = Grid.from_bpm(72, bar=8)
    bars = 24
    mx = Mix("museum", bars * g.bar_s, ir=dict(rt60=3.2, predelay=0.035, hf_ratio=0.3, er_level=0.5, seed=5))
    harp = mx.track("harp", gain_db=0.0, pan=-0.28, eq=I.HARP_BODY, rev=0.35)
    cel = mx.track("celesta", gain_db=-5.0, pan=0.2, eq=[("hp", 250, 0.7, 0)], rev=0.4)
    vc = mx.track("cello", gain_db=-6.0, pan=0.1, eq=I.CELLO_BODY + [("lp", 2800, 0.7, 0)], rev=0.4)
    bass = mx.track("pizz", gain_db=-3.0, pan=-0.05, eq=I.BASS_BODY, rev=0.18, human=0.006)
    vib = mx.track("vibes", gain_db=-7.0, pan=0.4, eq=[("hp", 300, 0.7, 0)], rev=0.45)

    form = [("A", CH_MA), ("B", CH_MB), ("A2", CH_MA)]
    starts = {}
    b = 0
    all_bars = []
    for sec, chs in form:
        starts[sec] = b
        bc = bar_chords(chs)
        all_bars += [(sec, x) for x in bc]
        b += len(bc)
    assert b == bars
    for i, (sec, bc) in enumerate(all_bars):
        for h, c in enumerate(bc):
            e0 = 4 * h
            span = 8 if len(bc) == 1 else 4
            low = bass_pitch(c, lo=n2m("C2"), hi=n2m("B2"), center=n2m("F2"))
            if sec in ("A", "A2"):
                tones = chord_tones(c, n2m("A3") if low % 12 > 4 else n2m("G3"), span=24)
                pat = [0, 1, 2, 3, 4, 3, 2, 1][:span]
                harp.note(I.harp_note, g.t(i, e0), low, g.e * 6, 0.5)
                for k, idx in enumerate(pat):
                    harp.note(I.harp_note, g.t(i, e0 + k), tones[idx % len(tones)], g.e * 3, 0.38 + 0.06 * (k == 0))
                st = I.strings_note(float(dsp.midi_hz(low + 12)), g.e * span, 0.4, mx.rng, attack=0.8, vib=0.1,
                                    voices=3)
                vc.put(g.t(i, e0) + vc.jitter(), st)
            else:
                # curious pizzicato walk + sparse harp chords
                tones = chord_tones(c, n2m("A2"), span=14)
                for k in range(0, span, 2):
                    m = [low, tones[1], tones[2], low + 12][(k // 2) % 4]
                    bass.note(I.bass_pizz, g.t(i, e0 + k), m, g.e * 0.7, 0.55 if k == 0 else 0.42)
                v = voice(c, n2m("E4"), n2m("E5"), n=4)
                for j, m in enumerate(v):
                    harp.note(I.harp_note, g.t(i, e0 + 1) + 0.03 * j, m, g.e * 3, 0.32)
                if h == 0:
                    vib.note(I.vibes, g.t(i, e0 + 4), chord_tones(c, n2m("E5"))[2], g.e * 4, 0.35)
                v2 = voice(c, n2m("C3"), n2m("C4"), n=2)
                for m in v2:
                    st = I.strings_note(float(dsp.midi_hz(m)), g.e * span, 0.33, mx.rng, attack=1.0, vib=0.1, voices=3)
                    vc.put(g.t(i, e0) + vc.jitter(), st)
    cl = lambda line, b0, v=0.66, tr=0: shape_vel(g.notes(line, bar0=b0, legato=0.95, vel=v, transpose=tr), spread=0.18)
    play_notes(cel, I.celesta, cl(MU_A, starts["A"]))
    play_notes(cel, I.celesta, cl(MU_B, starts["B"], v=0.62))
    play_notes(cel, I.celesta, cl(MU_A, starts["A2"], v=0.62))
    play_notes(harp, I.harp_note, cl(MU_A, starts["A2"], v=0.45, tr=-12))
    out = mx.render(target_lufs=-16.0, master_eq=MASTER_EQ)
    return out, {"bar_s": g.bar_s}


# ---------------------------------------------------------------------------
# trailer (72 s, not a loop)
# ---------------------------------------------------------------------------

def cue_trailer():
    """0-12 music box + sea | 12-30 build (uke, whistle, motif) | 30-33 storm
    hit | 33-58 full joyful shanty | 58-68 warm resolve | 68-72 button + bell."""
    L = 72.0
    mx = Mix("trailer", L, loop=False, pre=0.5, tail=0.5,
             ir=dict(rt60=2.4, predelay=0.025, hf_ratio=0.33, er_level=0.6, seed=9))
    sea = mx.track("sea", gain_db=-8.0, eq=[("hp", 80, 0.7, 0)], rev=0.1)
    mb = mx.track("musicbox", gain_db=-4.0, pan=0.1, eq=[("hp", 350, 0.7, 0), ("hs", 9000, 0.7, -3)], rev=0.35)
    acc = mx.track("acc_mel", gain_db=-4.5, pan=-0.22, eq=I.ACC_BODY, rev=0.2)
    pad = mx.track("acc_pad", gain_db=-9.0, pan=-0.35, eq=I.ACC_BODY + [("hs", 3500, 0.7, -3)], rev=0.3)
    stab = mx.track("acc_stab", gain_db=-8.0, pan=-0.3, eq=I.ACC_BODY + [("hp", 200, 0.7, 0)], rev=0.2)
    wh = mx.track("whistle", gain_db=-5.0, pan=-0.05, eq=[("hp", 300, 0.7, 0), ("peak", 2500, 1.0, -1.5)], rev=0.22)
    fid = mx.track("fiddle", gain_db=-6.0, pan=0.22, eq=I.FIDDLE_BODY, rev=0.25)
    uke = mx.track("uke", gain_db=-1.0, pan=0.3, eq=I.UKE_BODY, rev=0.14, rev2=0.1)
    glk = mx.track("glock", gain_db=-10.0, pan=0.2, eq=[("hp", 500, 0.7, 0)], rev=0.32)
    cel = mx.track("celesta", gain_db=-7.0, pan=-0.2, eq=[("hp", 250, 0.7, 0)], rev=0.35)
    bass = mx.track("bass", gain_db=-1.5, eq=I.BASS_BODY, rev=0.05, human=0.004)
    ost = mx.track("low_str", gain_db=0.0, eq=I.CELLO_BODY + [("hp", 55, 0.7, 0)], rev=0.22)
    spad = mx.track("str_pad", gain_db=-9.0, eq=I.CELLO_BODY + [("hp", 70, 0.7, 0)], rev=0.3)
    timp = mx.track("timpani", gain_db=-1.0, pan=0.1, eq=[("hp", 40, 0.7, 0)], rev=0.28, human=0.003)
    bod = mx.track("bodhran", gain_db=0.0, pan=-0.08, eq=[("hp", 45, 0.7, 0), ("peak", 300, 1.0, -3)],
                   rev=0.08, rev2=0.15, human=0.004)
    br = mx.track("brushes", gain_db=-6.0, pan=0.12, eq=[("hp", 200, 0.7, 0)], rev=0.06, rev2=0.2, human=0.004)
    bel = mx.track("bell", gain_db=-6.0, pan=0.05, eq=[("hp", 120, 0.7, 0)], rev=0.35)
    rng = mx.rng
    cues = {"file": "trailer.ogg", "duration": L, "sections": [], "hits": [], "downbeats": []}

    def section(name, start, end, desc):
        cues["sections"].append({"name": name, "start": round(start, 3), "end": round(end, 3), "desc": desc})

    def hit(t, label):
        cues["hits"].append({"t": round(t, 3), "label": label})

    # ---- 0-12: music box + sea ------------------------------------------
    g1 = Grid.from_bpm(90, bar=6, t0=0.0)
    section("intro", 0.0, 12.0, "music box plays the motif over the sea")
    for side, p in ((0, -0.6), (1, 0.6)):
        r2 = dsp.rng_for("trailer-sea", side)
        w = I.sea_wash(16.0, r2, swells=(-1.0 + side * 0.7, 4.6 + side * 0.5, 9.8 - side * 0.4), swell_len=6.5)
        sea.put(0.0, dsp.fade(w, 0.8, 4.0), pan=p)
    play_notes(mb, I.music_box, shape_vel(g1.notes(
        "D6:3 C#6:1 D6:2 | A6:4 F#6:2 | G6:2 F#6:2 E6:2 | F#6:3 E6:1 D6:2 | B5:2 D6:2 G6:2 | A6:6",
        vel=0.6), spread=0.2))
    pad_chords(pad, g1, 2, "G Bm G A".split(), 0.42, lo=n2m("D3"), hi=n2m("C5"), n=3, attack=0.6, swell=0.4,
               reeds=((0.0, 1.0), (4.0, 0.5)), bright=0.6, release=0.4)
    for i, c in enumerate("G A".split()):
        arp(cel, I.celesta, g1, 4 + i, c, (0, 1, 2, 3, 4, 5), n2m("D5"), vel=0.3, dur_e=3)
    for b in range(6):
        cues["downbeats"].append({"t": round(g1.t(b), 3), "section": "intro"})

    # ---- 12-30: build ----------------------------------------------------
    g2 = Grid.from_bpm(90, bar=6, t0=12.0)
    section("build", 12.0, 30.0, "ukulele + whistle enter with the motif; timpani/strings swell at 28 s")
    hit(12.0, "build downbeat (uke + whistle enter)")
    chords = CH_A1.split()
    prev = None
    for i, c in enumerate(chords):
        if i < 4:
            uke_arp(uke, g2, i, c, vel=0.5)
        else:
            strum_pattern(uke, g2, i, c, "D.DUDU", vel=0.52)
        if i >= 2:
            bass_waltz(bass, g2, i, c, 0.7)
        prev = acc_chord(pad, g2.t(i), c, g2.bar_s, 0.45, lo=n2m("D3"), hi=n2m("C5"), prev=prev, swell=0.3,
                         attack=0.15, reeds=((0.0, 1.0), (5.0, 0.6)))
        if i >= 4:
            br.hit(I.brush_tap, g2.t(i, 2), 0.45)
            br.hit(I.brush_tap, g2.t(i, 4), 0.45)
        cues["downbeats"].append({"t": round(g2.t(i), 3), "section": "build"})
    wh.line(I.whistle_line, shape_vel(g2.notes(MOTIF_A1.replace("A5:6", "A5:4 r:2"), legato=0.95, vel=0.75),
                                      spread=0.2))
    play_notes(glk, I.glock, g2.notes("r:6 | r:6 | r:6 | F#6:3 E6:1 D6:2 | r:6 | r:6 | r:6 | A6:6", vel=0.4))
    # bar 8 (28-30): swell into the storm
    t28 = g2.t(8)
    cues["downbeats"].append({"t": round(t28, 3), "section": "build"})
    # crescendo that stops ~150 ms before the hit (a short "suck-out" so 30.0 lands)
    k_roll = int((1.82) / 0.055)
    for j in range(k_roll):
        v = 0.15 + 0.85 * (j / (k_roll - 1)) ** 1.5
        timp.put(t28 + j * 0.055 + timp.jitter(0.3), I.timpani(float(dsp.midi_hz(n2m("A1"))), v, rng, length=0.12))
    for m in (n2m("A2"), n2m("E3"), n2m("A3")):
        st = I.strings_note(float(dsp.midi_hz(m)), 1.78, 0.85, rng, attack=1.5, release=0.07, trem=0.5, vib=0.06)
        spad.put(t28, st)
    v = voice("A7", n2m("A3"), n2m("G5"), n=4)
    for m in v:
        stab.note(I.accordion_note, t28, m, 1.8, 0.7, attack=0.8, swell=0.8, shake=0.4, release=0.04,
                  reeds=((0.0, 1.0), (9.0, 0.8)), human=0.0)
    for k in range(11):
        strum(uke, t28 + k * (1.8 / 11), "A7", 0.35 + 0.04 * k, "D" if k % 2 == 0 else "U", dur=0.16)
    trill = [{"t": t28 + k * 0.125, "dur": 0.12, "m": n2m("A5") + (2 if k % 2 else 0), "vel": 0.55 + 0.02 * k,
              "full": 0.125, "slur": k > 0, "slide": False, "cut": False} for k in range(14)]
    wh.line(I.whistle_line, trill)

    # ---- 30-33: storm hit --------------------------------------------------
    g3 = Grid(0.25, bar=6, t0=30.0)
    section("storm_hit", 30.0, 33.0, "storm hit: timpani, gran cassa, low strings, accordion stabs in D minor")
    hit(30.0, "STORM HIT (big)")
    timp.put(30.0, I.timpani(float(dsp.midi_hz(n2m("D2"))), 1.15, rng, length=1.3))
    timp.put(30.0, I.timpani(float(dsp.midi_hz(n2m("A1"))), 1.0, rng, length=1.0))
    timp.put(30.0, I.gran_cassa(1.2, rng, f=44.0))
    timp.put(30.0, I.gran_cassa(0.9, rng, f=62.0))
    for m in (n2m("D2"), n2m("A2"), n2m("D3"), n2m("F3"), n2m("A3")):
        spad.put(30.0, I.strings_note(float(dsp.midi_hz(m)), 1.4, 1.0, rng, attack=0.01, release=0.6, vib=0.05,
                                      bright=1.3))
    for m in voice("Dm", n2m("A3"), n2m("F5"), n=3) + [n2m("D3")]:
        stab.note(I.accordion_note, 30.0, m, 0.4, 0.95, attack=0.008, human=0.0,
                  reeds=((0.0, 1.0), (9.0, 0.85), (-1200.0, 0.4)))
    for b, c in enumerate(("Dm", "Bb")):
        ostinato_68(ost, g3, b, c, vel=0.85)
        bod.hit(I.bodhran, g3.t(b, 0), 0.9)
        bod.hit(I.bodhran, g3.t(b, 3), 0.75)
        cues["downbeats"].append({"t": round(g3.t(b), 3), "section": "storm_hit"})
    timp.put(g3.t(0, 3), I.timpani(float(dsp.midi_hz(n2m("D2"))), 0.75, rng))
    hit(g3.t(0, 3), "storm accent")
    timp.put(g3.t(1, 0), I.timpani(float(dsp.midi_hz(n2m("D2"))), 0.85, rng))
    hit(g3.t(1, 0), "storm accent")
    for m in voice("Bb", n2m("A3"), n2m("F5"), n=3):
        stab.note(I.accordion_note, g3.t(1, 0), m, 0.3, 0.85, attack=0.008, human=0.0)
    for m in voice("A", n2m("A3"), n2m("F5"), n=3):
        stab.note(I.accordion_note, g3.t(1, 3), m, 0.3, 0.85, attack=0.008, human=0.0)
    for k, e in enumerate((3, 4, 5)):
        timp.put(g3.t(1, e), I.timpani(float(dsp.midi_hz(n2m("A1"))), 0.6 + 0.15 * k, rng))
        hit(g3.t(1, e), "pickup into shanty")
    fid.line(I.fiddle_line, g3.notes("D5:3 C#5:1 D5:2 | Bb5:3 A5:3", vel=0.9, legato=0.9))

    # ---- 33-58: full joyful shanty -----------------------------------------
    g4 = Grid.from_bpm(115.2, bar=6, t0=33.0)
    section("shanty", 33.0, 58.0, "full joyful shanty: motif A2 + B strain, everyone playing")
    hit(33.0, "SHANTY downbeat (D major, tutti)")
    timp.put(33.0, I.timpani(float(dsp.midi_hz(n2m("D2"))), 0.9, rng))
    timp.put(33.0, I.gran_cassa(0.7, rng, f=50.0))
    chs = CH_A2.split() + CH_B.split()
    prev = None
    for i, c in enumerate(chs):
        strum_pattern(uke, g4, i, c, "D.DUDU", vel=0.6)
        bass_waltz(bass, g4, i, c, 0.82, fifth=(i % 2 == 1))
        for k, vv in ((0, 0.75), (2, 0.4), (3, 0.3), (4, 0.55), (5, 0.35)):
            bod.hit(I.bodhran, g4.t(i, k), vv, tone=0.0 if k == 0 else 0.6)
        br.hit(I.brush_tap, g4.t(i, 2), 0.5)
        br.hit(I.brush_tap, g4.t(i, 4), 0.5)
        for k in (2, 4):
            prev = acc_chord(stab, g4.t(i, k), c, g4.e * 1.1, 0.5, prev=prev, attack=0.015,
                             reeds=((0.0, 1.0), (1200.0, 0.3)))
        if i % 4 == 0:
            timp.put(g4.t(i) + 0.003, I.timpani(float(dsp.midi_hz(n2m("D2") if i < 8 else n2m("A1"))), 0.6, rng))
        cues["downbeats"].append({"t": round(g4.t(i), 3), "section": "shanty"})
        if i in (0, 4, 8, 12):
            hit(g4.t(i), "phrase downbeat")
    mel = MOTIF_A2 + " | " + MOTIF_B
    nts = shape_vel(g4.notes(mel, legato=0.95, vel=0.85), spread=0.2)
    play_notes(acc, I.accordion_note, nts, reeds=((0.0, 1.0), (8.0, 0.8), (-1200.0, 0.35)))
    wh.line(I.whistle_line, [dict(n, vel=n["vel"] * 0.8) for n in nts])
    fid.line(I.fiddle_line, [dict(n, vel=n["vel"] * 0.55) for n in diatonic(nts, -2, "D")])
    play_notes(glk, I.glock, [dict(n, m=n["m"] + 12, vel=n["vel"] * 0.6) for n in nts])

    # ---- 58-68: warm resolve -----------------------------------------------
    section("resolve", 58.0, 68.0, "warm resolve: slower, celesta + accordion, ritardando into the button")
    hit(58.0, "resolve downbeat")
    rb = [(58.0, 2.0, "G"), (60.0, 2.0, "D/F#"), (62.0, 2.0, "Em7"), (64.0, 2.0, "A7sus4"), (66.0, 2.0, "A7")]
    for t, d, c in rb:
        cues["downbeats"].append({"t": t, "section": "resolve"})
        v = voice(c, n2m("D3"), n2m("C5"), n=3)
        for m in v:
            pad.note(I.accordion_note, t, m, d, 0.5, human=0.2, attack=0.25, swell=0.2,
                     reeds=((0.0, 1.0), (5.0, 0.6)), release=0.3)
        bass.note(I.bass_pizz, t, bass_pitch(c), 1.6, 0.6)
        tones = chord_tones(c, n2m("D5"), 14)
        for k in range(6):
            cel.note(I.celesta, t + k * d / 6 * (1.0 + 0.12 * (t >= 64) * k / 6), tones[k % len(tones)], 0.6, 0.32)
        for m in voice(c, n2m("D2"), n2m("D4"), n=2):
            spad.put(t, I.strings_note(float(dsp.midi_hz(m)), d, 0.45, rng, attack=0.5, vib=0.1))
    res = [(58.0, 0.62, "B4"), (58.65, 0.62, "D5"), (59.3, 0.68, "G5"), (60.0, 0.98, "F#5"), (61.0, 0.32, "E5"),
           (61.33, 0.66, "D5"), (62.0, 0.62, "E5"), (62.66, 0.62, "F#5"), (63.33, 0.66, "G5"), (64.0, 2.05, "A5"),
           (66.1, 0.95, "G5"), (67.05, 0.35, "E5"), (67.42, 0.5, "C#5")]
    rn = [{"t": t, "dur": d * 0.97, "m": n2m(m), "vel": 0.7, "full": d, "slur": False, "slide": False, "cut": False}
          for t, d, m in res]
    fid.line(I.fiddle_line, rn)
    wh.line(I.whistle_line, [dict(n, m=n["m"] + 12, vel=0.4) for n in rn[-4:]])
    for k, m in enumerate(("A5", "C#6", "E6", "G6", "A6")):
        glk.note(I.glock, 66.6 + k * 0.22, n2m(m), 0.3, 0.35 + 0.05 * k)

    # ---- 68-72: button + bell ----------------------------------------------
    section("button", 68.0, 72.0, "button chord + ship's bell ring-out")
    hit(68.0, "BUTTON (tutti D) + ship's bell")
    hit(68.55, "bell second strike")
    cues["downbeats"].append({"t": 68.0, "section": "button"})
    for m in voice("D", n2m("A3"), n2m("F#5"), n=3) + [n2m("D3"), n2m("D6")]:
        stab.note(I.accordion_note, 68.0, m, 0.32, 0.9, attack=0.008, human=0.0,
                  reeds=((0.0, 1.0), (8.0, 0.8), (-1200.0, 0.3)))
    strum(uke, 68.0, "D", 0.8, "D", dur=1.5)
    bass.note(I.bass_pizz, 68.0, n2m("D2"), 1.2, 0.95, human=0.0)
    timp.put(68.0, I.timpani(float(dsp.midi_hz(n2m("D2"))), 0.95, rng, length=0.8))
    bod.hit(I.bodhran, 68.0, 0.9, human=0.0)
    for m in ("D6", "F#6", "A6", "D7"):
        glk.note(I.glock, 68.0 + 0.04 * ("D6 F#6 A6 D7".split().index(m)), n2m(m), 0.5, 0.45, human=0.0)
    fid.line(I.fiddle_line, [{"t": 68.0, "dur": 0.3, "m": n2m("D5"), "vel": 0.9, "full": 0.3, "slur": False,
                              "slide": False, "cut": False}])
    for m in (n2m("D2"), n2m("D3"), n2m("A3")):
        spad.put(68.0, I.strings_note(float(dsp.midi_hz(m)), 0.35, 0.9, rng, attack=0.01, release=0.4, vib=0.0))
    bel.put(68.02, I.bell(float(dsp.midi_hz(n2m("D5"))), 0.95, dsp.rng_for("bell1"), length=0.9))
    bel.put(68.55, I.bell(float(dsp.midi_hz(n2m("D5"))), 0.7, dsp.rng_for("bell2"), length=0.9))
    out = mx.render(target_lufs=-16.0, master_eq=MASTER_EQ, fade_out=0.9)
    assert out.shape[1] == ns(L), out.shape
    cues["hits"].sort(key=lambda h: h["t"])
    cues["motif_entries"] = [{"t": 0.0, "instrument": "music box"}, {"t": 12.0, "instrument": "whistle"},
                             {"t": 33.0, "instrument": "tutti (accordion/whistle/glock, fiddle harmony)"}]
    cues["note"] = "Times in seconds from the start of trailer.ogg (44.1 kHz, exactly 72.000 s)."
    return out, {"cues": cues}


# ---------------------------------------------------------------------------
# jingles
# ---------------------------------------------------------------------------

def _jmix(name, L, rt=1.8):
    return Mix(name, L, loop=False, pre=0.15, tail=0.2, ir=dict(rt60=rt, predelay=0.02, hf_ratio=0.35, er_level=0.6))


def _jfinish(mx, L):
    out = mx.render(target_lufs=-15.0, ceiling_db=-1.5, master_eq=MASTER_EQ, fade_out=min(0.35, L * 0.2),
                    report=False)
    return out, {}


def jingle_catch_small():
    L = 1.5
    mx = _jmix("jingle_catch_small", L, 1.4)
    uke = mx.track("uke", gain_db=-2.0, pan=-0.2, eq=I.UKE_BODY, rev=0.15)
    glk = mx.track("glock", gain_db=-4.0, pan=0.2, eq=[("hp", 500, 0.7, 0)], rev=0.3)
    mar = mx.track("marimba", gain_db=-3.0, pan=0.0, rev=0.2)
    bass = mx.track("bass", gain_db=-4.0, eq=I.BASS_BODY, rev=0.05)
    strum(uke, 0.0, "A", 0.55, "D", dur=0.35)
    for k, m in enumerate(("A5", "C#6", "E6", "A6")):
        glk.note(I.glock, 0.02 + k * 0.085, n2m(m), 0.2, 0.5 + 0.07 * k, human=0.0)
    strum(uke, 0.38, "D", 0.75, "D", dur=1.0)
    glk.note(I.glock, 0.38, n2m("D7"), 0.8, 0.85, human=0.0)
    mar.note(I.marimba, 0.38, n2m("D6"), 0.5, 0.8, human=0.0)
    mar.note(I.marimba, 0.38, n2m("F#5"), 0.5, 0.6, human=0.0)
    bass.note(I.bass_pizz, 0.38, n2m("D2"), 0.9, 0.85, human=0.0)
    return _jfinish(mx, L)


def jingle_catch_big():
    L = 3.0
    mx = _jmix("jingle_catch_big", L, 2.0)
    acc = mx.track("acc", gain_db=-4.0, pan=-0.2, eq=I.ACC_BODY, rev=0.2)
    wh = mx.track("whistle", gain_db=-5.0, pan=0.05, eq=[("hp", 300, 0.7, 0)], rev=0.22)
    uke = mx.track("uke", gain_db=-2.0, pan=0.3, eq=I.UKE_BODY, rev=0.14)
    glk = mx.track("glock", gain_db=-8.0, pan=0.2, eq=[("hp", 500, 0.7, 0)], rev=0.3)
    bass = mx.track("bass", gain_db=-2.0, eq=I.BASS_BODY, rev=0.05)
    timp = mx.track("timp", gain_db=-2.0, eq=[("hp", 40, 0.7, 0)], rev=0.25)
    rng = mx.rng
    g = Grid(0.11, bar=6)
    nts = g.notes("D5:3 C#5:1 D5:2 | A5:6", vel=0.85, legato=0.95)
    full = ((0.0, 1.0), (8.0, 0.8), (-1200.0, 0.35))
    play_notes(acc, I.accordion_note, nts, reeds=full)
    wh.line(I.whistle_line, nts + [{"t": 1.32, "dur": 1.0, "m": n2m("D6"), "vel": 0.9, "full": 1.0,
                                     "slur": False, "slide": False, "cut": False}])
    for k in range(6):
        strum(uke, k * 0.11 * 2, "D" if k < 3 else "A7", 0.45, "D" if k % 2 == 0 else "U", dur=0.22)
    timp_roll(timp, g, 1, 0, 6, n2m("A1"), 0.2, 0.75, rate=0.05)
    t = 1.32
    for m in voice("D", n2m("F#4"), n2m("F#5"), n=3) + [n2m("D4")]:
        acc.note(I.accordion_note, t, m, 0.9, 0.85, attack=0.01, human=0.0, reeds=full)
    strum(uke, t, "D", 0.85, "D", dur=1.4)
    bass.note(I.bass_pizz, t, n2m("D2"), 1.2, 0.95, human=0.0)
    timp.put(t, I.timpani(float(dsp.midi_hz(n2m("D2"))), 0.95, rng))
    timp.put(t, I.gran_cassa(0.6, rng, f=50.0))
    for k, m in enumerate(("D6", "F#6", "A6", "D7", "F#7")):
        glk.note(I.glock, t + k * 0.06, n2m(m), 0.6, 0.5 + 0.06 * k, human=0.0)
    return _jfinish(mx, L)


def jingle_treasure():
    L = 3.2
    mx = _jmix("jingle_treasure", L, 3.2)
    harp = mx.track("harp", gain_db=-3.0, pan=-0.3, eq=I.HARP_BODY, rev=0.4)
    cel = mx.track("celesta", gain_db=-4.0, pan=0.2, eq=[("hp", 300, 0.7, 0)], rev=0.45)
    mb = mx.track("musicbox", gain_db=-5.0, pan=0.0, eq=[("hp", 400, 0.7, 0)], rev=0.45)
    glk = mx.track("glock", gain_db=-10.0, pan=0.35, eq=[("hp", 800, 0.7, 0)], rev=0.5)
    pad = mx.track("pad", gain_db=-10.0, pan=0.0, eq=I.ACC_BODY + [("hs", 3000, 0.7, -5)], rev=0.5)
    vib = mx.track("vibes", gain_db=-8.0, pan=-0.1, rev=0.45)
    scale = ["D4", "E4", "F#4", "A4", "B4", "D5", "E5", "F#5", "A5", "B5", "D6"]
    for k, m in enumerate(scale):
        harp.note(I.harp_note, k * 0.04, n2m(m), 1.0, 0.4 + 0.03 * k, human=0.0)
    glk.put(0.45, I.shimmer(float(dsp.midi_hz(n2m("A6"))), 0.4, 0.5, mx.rng, notes=7, spread=0.05))
    for m in voice("Dmaj7", n2m("D3"), n2m("D5"), n=4):
        pad.note(I.accordion_note, 0.4, m, 2.2, 0.45, attack=0.4, swell=0.3, reeds=((0.0, 1.0), (4.0, 0.5)),
                 bright=0.6, release=0.6, human=0.0)
    for t, m, v in ((0.62, "D6", 0.6), (0.9, "C#6", 0.5), (1.0, "D6", 0.6), (1.2, "A6", 0.8)):
        mb.note(I.music_box, t, n2m(m), 0.5, v, human=0.0)
        cel.note(I.celesta, t, n2m(m) - 12, 0.5, v * 0.7, human=0.0)
    vib.note(I.vibes, 1.2, n2m("F#5"), 1.5, 0.5, human=0.0)
    vib.note(I.vibes, 1.2, n2m("C#6"), 1.5, 0.4, human=0.0)
    for k, m in enumerate(("A6", "D7", "F#7", "A7")):
        glk.note(I.glock, 1.75 + k * 0.07, n2m(m), 0.4, 0.45, human=0.0)
    return _jfinish(mx, L)


def jingle_upgrade():
    L = 2.5
    mx = _jmix("jingle_upgrade", L, 1.6)
    mar = mx.track("marimba", gain_db=-2.0, pan=0.15, rev=0.2)
    uke = mx.track("uke", gain_db=-2.0, pan=-0.25, eq=I.UKE_BODY, rev=0.14)
    acc = mx.track("acc", gain_db=-6.0, pan=-0.2, eq=I.ACC_BODY, rev=0.2)
    glk = mx.track("glock", gain_db=-8.0, pan=0.25, eq=[("hp", 500, 0.7, 0)], rev=0.3)
    bass = mx.track("bass", gain_db=-3.0, eq=I.BASS_BODY, rev=0.05)
    br = mx.track("brush", gain_db=-8.0, rev=0.1)
    for k, m in enumerate(("D5", "F#5", "A5", "D6")):
        mar.note(I.marimba, k * 0.1, n2m(m), 0.15, 0.6 + 0.08 * k, human=0.0)
    strum(uke, 0.5, "G", 0.65, "D", dur=0.38)
    mar.note(I.marimba, 0.5, n2m("B5"), 0.3, 0.7, human=0.0)
    mar.note(I.marimba, 0.5, n2m("G5"), 0.3, 0.6, human=0.0)
    bass.note(I.bass_pizz, 0.5, n2m("G2"), 0.35, 0.8, human=0.0)
    for m in voice("G", n2m("G4"), n2m("G5"), n=3):
        acc.note(I.accordion_note, 0.5, m, 0.3, 0.6, attack=0.015, human=0.0)
    t = 0.9
    strum(uke, t, "D", 0.8, "D", dur=1.3)
    for m in voice("D", n2m("F#4"), n2m("F#5"), n=3):
        acc.note(I.accordion_note, t, m, 0.9, 0.75, attack=0.015, human=0.0, swell=0.2)
    bass.note(I.bass_pizz, t, n2m("D2"), 1.0, 0.9, human=0.0)
    mar.note(I.marimba, t, n2m("D6"), 0.8, 0.85, human=0.0)
    mar.note(I.marimba, t, n2m("A5"), 0.8, 0.65, human=0.0)
    br.hit(I.brush_tap, t, 0.7, human=0.0)
    for k, m in enumerate(("D6", "F#6", "A6")):
        glk.note(I.glock, t + 0.05 * k, n2m(m), 0.5, 0.55, human=0.0)
    return _jfinish(mx, L)


def jingle_day_start():
    L = 3.2
    mx = _jmix("jingle_day_start", L, 2.0)
    bel = mx.track("bell", gain_db=-3.0, pan=0.15, eq=[("hp", 200, 0.7, 0)], rev=0.3)
    acc = mx.track("acc", gain_db=-3.0, pan=-0.2, eq=I.ACC_BODY, rev=0.22)
    uke = mx.track("uke", gain_db=-3.0, pan=0.3, eq=I.UKE_BODY, rev=0.15)
    bass = mx.track("bass", gain_db=-4.0, eq=I.BASS_BODY, rev=0.05)
    bel.put(0.0, I.bell(float(dsp.midi_hz(n2m("A5"))), 0.85, dsp.rng_for("dsbell1"), length=0.6))
    bel.put(0.36, I.bell(float(dsp.midi_hz(n2m("A5"))), 0.7, dsp.rng_for("dsbell2"), length=0.6))
    g = Grid(0.1, bar=6, t0=0.95)
    nts = g.notes("D5:3 C#5:1 D5:2 | A5:4 F#5:2 | G5:1 F#5:1 E5:1 C#5:1 D5:2", vel=0.75, legato=0.95)
    play_notes(acc, I.accordion_note, nts, reeds=((0.0, 1.0), (7.0, 0.7)))
    strum(uke, g.t(0), "D", 0.55, "D", dur=0.55)
    strum(uke, g.t(1), "D", 0.5, "D", dur=0.55)
    strum(uke, g.t(2), "A7", 0.5, "D", dur=0.38)
    strum(uke, g.t(2, 4), "D", 0.7, "D", dur=1.2)
    bass.note(I.bass_pizz, g.t(0), n2m("D2"), 0.5, 0.7, human=0.0)
    bass.note(I.bass_pizz, g.t(2), n2m("A1"), 0.38, 0.7, human=0.0)
    bass.note(I.bass_pizz, g.t(2, 4), n2m("D2"), 1.0, 0.8, human=0.0)
    for m in voice("D", n2m("F#4"), n2m("D5"), n=3):
        acc.note(I.accordion_note, g.t(2, 4), m, 0.8, 0.5, attack=0.03, human=0.0)
    return _jfinish(mx, L)


def jingle_sale():
    L = 1.0
    mx = _jmix("jingle_sale", L, 1.0)
    glk = mx.track("glock", gain_db=-3.0, pan=0.1, eq=[("hp", 600, 0.7, 0)], rev=0.25)
    cel = mx.track("cel", gain_db=-6.0, pan=-0.15, eq=[("hp", 300, 0.7, 0)], rev=0.25)
    bel = mx.track("bell", gain_db=-10.0, pan=0.25, eq=[("hp", 1000, 0.7, 0)], rev=0.2)
    glk.note(I.glock, 0.0, n2m("E6"), 0.2, 0.7, human=0.0)
    cel.note(I.celesta, 0.0, n2m("E5"), 0.2, 0.5, human=0.0)
    glk.note(I.glock, 0.085, n2m("A6"), 0.6, 0.85, human=0.0)
    cel.note(I.celesta, 0.085, n2m("A5"), 0.6, 0.6, human=0.0)
    bel.put(0.085, I.bell(2637.0, 0.6, dsp.rng_for("salebell"), length=0.25, dur=0.9))
    return _jfinish(mx, L)


def jingle_donation():
    L = 2.2
    mx = _jmix("jingle_donation", L, 2.6)
    harp = mx.track("harp", gain_db=-3.0, pan=-0.25, eq=I.HARP_BODY, rev=0.35)
    cel = mx.track("cel", gain_db=-3.5, pan=0.2, eq=[("hp", 300, 0.7, 0)], rev=0.4)
    pad = mx.track("pad", gain_db=-11.0, eq=I.ACC_BODY + [("hs", 3000, 0.7, -5)], rev=0.4)
    vib = mx.track("vibes", gain_db=-9.0, pan=0.3, rev=0.4)
    for k, m in enumerate(("D4", "F#4", "A4", "D5", "F#5")):
        harp.note(I.harp_note, k * 0.08, n2m(m), 1.5, 0.45 + 0.04 * k, human=0.0)
    for t, m, v in ((0.42, "D6", 0.6), (0.6, "C#6", 0.5), (0.68, "D6", 0.6), (0.86, "A6", 0.75), (1.1, "F#6", 0.6)):
        cel.note(I.celesta, t, n2m(m), 0.6, v, human=0.0)
    for m in voice("Dmaj7", n2m("D3"), n2m("D5"), n=4):
        pad.note(I.accordion_note, 0.1, m, 1.5, 0.45, attack=0.35, swell=0.3, bright=0.6, release=0.5, human=0.0)
    vib.note(I.vibes, 0.86, n2m("A5"), 1.2, 0.45, human=0.0)
    return _jfinish(mx, L)


def jingle_restoration():
    L = 5.0
    mx = _jmix("jingle_restoration", L, 2.2)
    acc = mx.track("acc", gain_db=-4.0, pan=-0.22, eq=I.ACC_BODY, rev=0.2)
    wh = mx.track("whistle", gain_db=-6.0, pan=0.0, eq=[("hp", 300, 0.7, 0)], rev=0.22)
    fid = mx.track("fiddle", gain_db=-7.0, pan=0.22, eq=I.FIDDLE_BODY, rev=0.25)
    uke = mx.track("uke", gain_db=-2.0, pan=0.3, eq=I.UKE_BODY, rev=0.14)
    glk = mx.track("glock", gain_db=-9.0, pan=0.2, eq=[("hp", 500, 0.7, 0)], rev=0.3)
    bass = mx.track("bass", gain_db=-2.0, eq=I.BASS_BODY, rev=0.05)
    bod = mx.track("bodhran", gain_db=0.0, eq=[("hp", 45, 0.7, 0)], rev=0.1, rev2=0.15)
    timp = mx.track("timp", gain_db=-2.0, eq=[("hp", 40, 0.7, 0)], rev=0.25)
    bel = mx.track("bell", gain_db=-6.0, pan=0.1, eq=[("hp", 150, 0.7, 0)], rev=0.35)
    rng = mx.rng
    g = Grid.from_bpm(115.2, bar=6, t0=0.0)
    line = "D5:3 C#5:1 D5:2 | A5:3 B5:1 C#6:2"
    nts = shape_vel(g.notes(line, vel=0.85, legato=0.95), spread=0.2)
    full = ((0.0, 1.0), (8.0, 0.8), (-1200.0, 0.35))
    play_notes(acc, I.accordion_note, nts, reeds=full)
    wh.line(I.whistle_line, [dict(n, vel=n["vel"] * 0.8) for n in nts])
    fid.line(I.fiddle_line, [dict(n, vel=n["vel"] * 0.55) for n in diatonic(nts, -2, "D")])
    for i, c in enumerate(("D", "A7")):
        strum_pattern(uke, g, i, c, "D.DUDU", vel=0.6)
        bass_waltz(bass, g, i, c, 0.8, fifth=(i % 2 == 1))
        for k, vv in ((0, 0.75), (2, 0.4), (4, 0.55)):
            bod.hit(I.bodhran, g.t(i, k), vv)
    timp_roll(timp, g, 1, 2, 6, n2m("A1"), 0.25, 0.85, rate=0.055)
    t = g.t(2)
    for m in voice("D", n2m("F#4"), n2m("F#5"), n=3) + [n2m("D4"), n2m("D6")]:
        acc.note(I.accordion_note, t, m, 1.3, 0.9, attack=0.01, human=0.0, reeds=full, swell=-0.3)
    wh.line(I.whistle_line, [{"t": t, "dur": 1.3, "m": n2m("D6"), "vel": 0.85, "full": 1.3, "slur": False,
                              "slide": False, "cut": False}])
    fid.line(I.fiddle_line, [{"t": t, "dur": 1.3, "m": n2m("F#5"), "vel": 0.7, "full": 1.3, "slur": False,
                              "slide": False, "cut": False}])
    strum(uke, t, "D", 0.9, "D", dur=1.6)
    bass.note(I.bass_pizz, t, n2m("D2"), 1.3, 1.0, human=0.0)
    timp.put(t, I.timpani(float(dsp.midi_hz(n2m("D2"))), 1.0, rng))
    timp.put(t, I.gran_cassa(0.7, rng, f=48.0))
    bod.hit(I.bodhran, t, 0.9, human=0.0)
    for k, m in enumerate(("D6", "F#6", "A6", "D7", "F#7", "A7")):
        glk.note(I.glock, t + 0.05 * k, n2m(m), 0.5, 0.5 + 0.05 * k, human=0.0)
    bel.put(t + 0.02, I.bell(float(dsp.midi_hz(n2m("D5"))), 0.85, dsp.rng_for("rbell1"), length=0.6))
    bel.put(t + 0.5, I.bell(float(dsp.midi_hz(n2m("D5"))), 0.65, dsp.rng_for("rbell2"), length=0.6))
    return _jfinish(mx, L)


# ============================================================================
# build
# ============================================================================

CUES = {
    "title_theme": (cue_title, "music", True),
    "town_day": (cue_town_day, "music", True),
    "town_night": (cue_town_night, "music", True),
    "sea_calm": (cue_sea_calm, "music", True),
    "sea_storm": (cue_sea_storm, "music", True),
    "shop": (cue_shop, "music", True),
    "museum": (cue_museum, "music", True),
    "trailer": (cue_trailer, "music", False),
    "jingle_catch_small": (jingle_catch_small, "jingle", False),
    "jingle_catch_big": (jingle_catch_big, "jingle", False),
    "jingle_treasure": (jingle_treasure, "jingle", False),
    "jingle_upgrade": (jingle_upgrade, "jingle", False),
    "jingle_day_start": (jingle_day_start, "jingle", False),
    "jingle_sale": (jingle_sale, "jingle", False),
    "jingle_donation": (jingle_donation, "jingle", False),
    "jingle_restoration": (jingle_restoration, "jingle", False),
}


def bar_seam(y, bar_s, win=0.05):
    """A music loop restarts on a downbeat, so the first 50 ms is naturally
    louder than the last 50 ms.  Judge the seam against every other bar line
    in the cue: the level step across the seam should be typical."""
    w = ns(win)
    n = y.shape[1]
    nb = int(round(n / (bar_s * SR)))
    steps = []
    for k in range(1, nb):
        i = ns(k * bar_s)
        steps.append(dsp.rms_db(y[:, i:i + w]) - dsp.rms_db(y[:, i - w:i]))
    seam = dsp.rms_db(y[:, :w]) - dsp.rms_db(y[:, -w:])
    steps = np.array(steps)
    ok = bool(seam <= np.percentile(steps, 95) + 3.0)
    return {"seam_step_db": round(float(seam), 2), "barline_step_median_db": round(float(np.median(steps)), 2),
            "barline_step_p95_db": round(float(np.percentile(steps, 95)), 2), "seam_ok": ok}


def _render(args):
    """Worker: render one cue, write it, measure the decoded file."""
    name, music_dir, out_dir = args
    fn, kind, loop = CUES[name]
    x, meta = fn()
    path = os.path.join(music_dir, name + ".ogg")
    dsp.write_ogg(path, x)
    y = dsp.read_audio(path)  # measure what Unity will import
    warn = None
    if y.shape[1] != x.shape[1]:
        warn = f"decoded length {y.shape[1]} != {x.shape[1]}"
    entry, diag = dsp.describe(path, y, kind, loop)
    if loop and meta.get("bar_s"):
        diag.update(bar_seam(y, meta["bar_s"]))
    m = min(x.shape[1], y.shape[1])
    diag["encode_err_db"] = round(dsp.rms_db(y[:, :m] - x[:, :m]), 1)
    if warn:
        diag["warning"] = warn
    if kind == "music" or name == "trailer":
        dsp.spectrogram_png(x, os.path.join(out_dir, "spectrograms", name + ".png"), name)
    if meta.get("cues"):
        dsp.save_json(os.path.join(HERE, "trailer_cues.json"), meta["cues"])
    return {"entry": entry, "diag": diag}


def build(music_dir, out_dir, only=None, jobs=8):
    names = [n for n in CUES if only is None or n in only]
    results = []
    if not names:
        return results
    args = [(n, music_dir, out_dir) for n in names]
    if len(names) == 1 or jobs <= 1:
        it = map(_render, args)
        for r in it:
            results.append(r)
            _print(r)
    else:
        with ProcessPoolExecutor(max_workers=min(jobs, len(names))) as ex:
            for r in ex.map(_render, args):
                results.append(r)
                _print(r)
    return results


def _print(r):
    e, d = r["entry"], r["diag"]
    s = f"{e['file']:26s} {e['seconds']:7.2f}s  LUFS {e['lufs']:6.1f}  peak {e['peak_db']:5.1f}"
    if e["loop"]:
        s += f"  seam ratio {d['seam_ratio']:.2f}"
        if "seam_step_db" in d:
            s += (f"  seam step {d['seam_step_db']:+.1f} dB (bar lines median {d['barline_step_median_db']:+.1f},"
                  f" p95 {d['barline_step_p95_db']:+.1f}) {'OK' if d['seam_ok'] else 'CHECK'}")
    if d.get("warning"):
        s += "  WARNING " + d["warning"]
    print(s, flush=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    a = ap.parse_args()
    build(os.path.join(HERE, "..", "..", "Game", "Assets", "Saltmoss", "Audio", "Music"),
          os.path.join(HERE, "out"), only=a.names or None, jobs=8)
