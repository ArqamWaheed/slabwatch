"""Build the DEV post's images from files under results/ (numbers are read, never typed).

  FONT_DIR=<dir with AtkinsonHyperlegible-*.ttf> python scripts/post_images.py <cover.jpg> <before.jpg>
The two arguments are the Google Flow illustrations (cover and "before" scene). Writes docs/images/*.
Meter thumbnails come from data/demo_meters (CC photos, credits in eval/meter_truth.json).
"""
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

OUT = Path("docs/images")
CASING, INK, MUTED, RULE = "#E4E9E1", "#14201A", "#55615A", "#C4CCC0"
LCD, LCD_INK, LIMIT, SAFE, WATCH, BAND = "#C3D1AC", "#1C2914", "#B42318", "#2F6B3E", "#8A5600", "#5F7F64"
FD = Path(os.environ.get("FONT_DIR", ""))


def font(size, bold=False, mono=False):
    names = (["AtkinsonHyperlegibleMono%5Bwght%5D.ttf"] if mono else
             ["AtkinsonHyperlegible-Bold.ttf" if bold else "AtkinsonHyperlegible-Regular.ttf"])
    for n in names:
        if (FD / n).is_file():
            f = ImageFont.truetype(str(FD / n), size)
            if mono:
                try:
                    f.set_variation_by_name("Bold" if bold else "Medium")
                except Exception:  # noqa: BLE001
                    pass
            return f
    return ImageFont.truetype("DejaVuSansMono-Bold.ttf" if mono else
                              ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), size)


def load(p):
    return json.loads(Path(p).read_text())


def fit(im, w, h):
    return ImageOps.fit(im.convert("RGB"), (w, h), Image.LANCZOS, centering=(0.5, 0.45))


def chip(d, xy, text, fill, fg="#FFFFFF", size=26):
    f = font(size, bold=True)
    x, y = xy
    w = d.textlength(text, font=f)
    d.rounded_rectangle((x, y, x + w + 28, y + size + 18), radius=8, fill=fill)
    d.text((x + 14, y + 8), text, font=f, fill=fg)


def cover(src):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    ch = int(w * 420 / 1000)
    top = 0
    im.crop((0, top, w, top + ch)).resize((1600, 672), Image.LANCZOS).save(OUT / "cover.jpg", quality=90)


def before_after(before_src):
    live = load("results/render-live-forecast.json")
    f, dec = live["forecast"], live["decision"]
    W, H = 1600, 900
    img = Image.new("RGB", (W, H), CASING)
    d = ImageDraw.Draw(img)
    left = fit(Image.open(before_src), 780, 700)
    img.paste(left, (20, 180))
    shot = Image.open(OUT / "app-live-col.png").convert("RGB")
    shot.thumbnail((760, 700), Image.LANCZOS)
    panel = Image.new("RGB", (780, 700), "#121815")
    panel.paste(shot, ((780 - shot.width) // 2, (700 - shot.height) // 2))
    img.paste(panel, (820, 180))
    chip(d, (20, 24), "BEFORE: A TORCH, A BILL, A GUESS", LIMIT)
    chip(d, (820, 24), "AFTER: SLABWATCH, LIVE ON RENDER", SAFE)
    sub = font(28)
    d.text((22, 92), "141 units in 19 days. x 30 = 222? Over or not?", font=sub, fill=INK)
    d.text((22, 132), "The bill answers in two weeks.", font=sub, fill=MUTED)
    d.text((822, 92), f"P50 {f['p50']:.0f} units. Chance over 200: about {f['p_cross']:.0%}.", font=sub, fill=INK)
    d.text((822, 132), f"Budget: {dec['daily_budget']:.1f} units/day for {dec['days_left']} days.", font=sub,
           fill=MUTED)
    img.save(OUT / "before-after.jpg", quality=88)


def box(d, xy, title, lines, fill="#FFFFFF", edge=INK, tag=None, tagfill=LIMIT):
    x0, y0, x1, y1 = xy
    d.rounded_rectangle(xy, radius=14, fill=fill, outline=edge, width=3)
    d.text((x0 + 18, y0 + 14), title, font=font(28, bold=True), fill=INK)
    for i, ln in enumerate(lines):
        d.text((x0 + 18, y0 + 56 + i * 30), ln, font=font(21, mono=True), fill=MUTED)
    if tag:
        f = font(18, bold=True)
        w = d.textlength(tag, font=f)
        d.rounded_rectangle((x1 - w - 34, y0 - 16, x1 - 10, y0 + 14), radius=7, fill=tagfill)
        d.text((x1 - w - 22, y0 - 12), tag, font=f, fill="#FFFFFF")


def arrow(d, a, b, dashed=False, label=None, color=INK):
    (x0, y0), (x1, y1) = a, b
    if dashed:
        n = 14
        for i in range(0, n, 2):
            p = (x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n)
            q = (x0 + (x1 - x0) * (i + 1) / n, y0 + (y1 - y0) * (i + 1) / n)
            d.line((p, q), fill=color, width=4)
    else:
        d.line((a, b), fill=color, width=4)
    import math
    ang = math.atan2(y1 - y0, x1 - x0)
    for s in (2.6, -2.6):
        d.line(((x1, y1), (x1 - 18 * math.cos(ang + s / 6), y1 - 18 * math.sin(ang + s / 6))), fill=color, width=4)
    if label:
        f = font(19, mono=True)
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        w = d.textlength(label, font=f)
        d.rectangle((mx - w / 2 - 6, my - 14, mx + w / 2 + 6, my + 12), fill=CASING)
        d.text((mx - w / 2, my - 12), label, font=f, fill=INK)


def plate_system():
    W, H = 1600, 1000
    img = Image.new("RGB", (W, H), CASING)
    d = ImageDraw.Draw(img)
    d.text((48, 34), "SLABWATCH · PLATE I", font=font(20, bold=True), fill=MUTED)
    d.text((48, 64), "Models read and forecast. Code decides.", font=font(46, bold=True), fill=INK)
    box(d, (48, 170, 380, 330), "Meter photo", ["or a typed reading", "or a bill photo"])
    box(d, (450, 170, 800, 330), "Gemma 4", ["gemma-4-26b-a4b-it", "strict JSON or refuse", "MIN_CONFIDENCE 0.6"],
        tag="REFUSES")
    box(d, (870, 170, 1240, 330), "cut_features()", ["day k, units so far", "rate 3 / 7 days", "temps, last bill"],
        tag="CODE")
    box(d, (870, 410, 1240, 600), "GBM + TabPFN", ["11 quantiles of", "final / naive ratio", "calibrated on dev",
                                                  "homes only"], fill=LCD)
    box(d, (1300, 410, 1560, 600), "p_cross()", ["piecewise CDF", "P(final > 200)"], tag="CODE")
    box(d, (1300, 680, 1560, 900), "decide.py", ["safe / watch /", "unsure / act /", "already_over",
                                                  "+ daily budget"], tag="CODE")
    box(d, (450, 680, 1040, 900), "The message", ["\"To stay under 200 you have", " 5.4 units/day for 11 days;",
                                                   " you're running at 7.4.\"", "+ what it assumed"])
    box(d, (48, 680, 380, 900), "Temporal", ["one workflow per cycle", "reading = signal", "alert on escalation"])
    box(d, (48, 410, 380, 600), "Open-Meteo", ["forecast temps", "fallback: 2008-2017", "climatology (shipped)"])
    box(d, (450, 410, 800, 600), "Tiger + Browserbase", ["separate job: FCA", "news, quote-checked,", "hybrid RRF search"],
        fill=CASING, edge=MUTED)
    arrow(d, (380, 250), (450, 250), label="image")
    arrow(d, (800, 250), (870, 250), label="kWh")
    arrow(d, (380, 418), (868, 336), label="temps")
    arrow(d, (625, 600), (625, 680), dashed=True, label="FCA: checked by hand", color=MUTED)
    arrow(d, (1055, 330), (1055, 410), label="features")
    arrow(d, (1240, 505), (1300, 505))
    arrow(d, (1430, 600), (1430, 680))
    arrow(d, (1300, 790), (1040, 790), label="verdict")
    arrow(d, (450, 790), (380, 790), dashed=True, label="ntfy")
    d.rectangle((48, 940, 1560, 942), fill=RULE)
    d.text((48, 952), "Every CODE box can overrule the model before it. Dashed: not wired into the app yet.",
           font=font(24), fill=INK)
    img.save(OUT / "plate-system.png")


def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for n in ("AtkinsonHyperlegible-Regular.ttf", "AtkinsonHyperlegible-Bold.ttf"):
        if (FD / n).is_file():
            font_manager.fontManager.addfont(str(FD / n))
    plt.rcParams.update({"font.family": "Atkinson Hyperlegible" if (FD / "AtkinsonHyperlegible-Regular.ttf").is_file()
                         else "DejaVu Sans", "font.size": 15, "axes.edgecolor": INK, "axes.labelcolor": INK,
                         "xtick.color": INK, "ytick.color": INK, "figure.facecolor": CASING,
                         "axes.facecolor": CASING, "axes.spines.top": False, "axes.spines.right": False})
    return plt


def plate_replay():
    plt = _mpl()
    r = load("results/session-api.json")
    st = r["steps"]
    days = [s["day"] for s in st]
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
    ax.fill_between(days, [s["p10"] for s in st], [s["p90"] for s in st], color=BAND, alpha=0.35,
                    label="P10-P90 band")
    ax.plot(days, [s["p50"] for s in st], color=INK, lw=3, marker="o", label="P50 (middle guess)")
    ax.plot(days, [s["naive"] for s in st], color=MUTED, lw=2, ls="--", marker="s", label="rate x 30 (naive)")
    ax.axhline(200, color=LIMIT, lw=2.5)
    ax.text(25.4, 200, "200", color=LIMIT, va="center", fontweight="bold")
    ax.axhline(r["final_units"], color=INK, lw=1, ls=":")
    ax.text(2.6, r["final_units"] + 1.5, f"actual finish {r['final_units']}", color=INK)
    for s in st:
        c = LIMIT if s["verdict"] == "act" else WATCH
        ax.annotate(f"{s['verdict']}\n{s['p_cross']:.0%}", (s["day"], s["p90"]), textcoords="offset points",
                    xytext=(0, 10), ha="center", color=c, fontweight="bold", fontsize=14)
    ax.set_xlabel("day of the billing cycle (reading taken)")
    ax.set_ylabel("predicted units at the end of the cycle")
    ax.set_xticks(days)
    ax.set_ylim(170, 300)
    ax.set_title(f"House {r['house']}, cycle from {r['cycle_start']}: the hardest call in the set",
                 loc="left", fontsize=22, fontweight="bold", color=INK)
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "plate-replay.png")


def plate_sides():
    plt = _mpl()
    a = load("results/session-aggregate.json")
    cuts = sorted(a["by_cut"], key=int)
    m = [a["by_cut"][c]["side_right_model"] * 100 for c in cuts]
    n = [a["by_cut"][c]["side_right_naive"] * 100 for c in cuts]
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
    x = range(len(cuts))
    ax.bar([i - 0.2 for i in x], n, 0.4, color=RULE, edgecolor=MUTED, label="rate x 30 (naive)")
    ax.bar([i + 0.2 for i in x], m, 0.4, color=SAFE, label="Slabwatch P(over 200) >= 50%")
    for i in x:
        ax.text(i + 0.2, m[i] + 1, f"{m[i]:.0f}%", ha="center", color=SAFE, fontweight="bold")
        ax.text(i - 0.2, n[i] + 1, f"{n[i]:.0f}%", ha="center", color=MUTED)
    ax.set_xticks(list(x), [f"day {c}" for c in cuts])
    ax.set_ylim(50, 100)
    ax.set_ylabel("cycles where the call was on the right side of 200")
    ax.set_title(f"{a['cycles']} real cycles ending 160-240 units, {len(a['houses'])} held-out homes",
                 loc="left", fontsize=22, fontweight="bold", color=INK)
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "plate-sides.png")


def plate_cases():
    """Three day-14 disagreements from results/session-outcomes.json: real cumulative units vs the straight line."""
    import datetime as dt

    import pandas as pd
    plt = _mpl()
    o = load("results/session-outcomes.json")
    rows = {(r["house"], r["cycle_start"]): r for r in o["day14_disagreements"]}
    daily = pd.read_parquet("data/precon/daily.parquet")
    picks = [((24, "2019-03-30"), "April: the AC season starts"), ((14, "2018-10-05"), "October: it cools down"),
             ((36, "2018-11-13"), "November: arithmetic wins")]
    fig, axes = plt.subplots(1, 3, figsize=(18, 7.2), dpi=100, sharey=True)
    for ax, (key, title) in zip(axes, picks):
        r = rows[key]
        start = dt.date.fromisoformat(key[1])
        s = daily[daily.house == key[0]].set_index("date")["kwh"]
        s.index = pd.to_datetime(s.index).date
        cum, tot = [0.0], 0.0
        for i in range(30):
            tot += float(s.get(start + dt.timedelta(days=i), 0.0))
            cum.append(tot)
        ax.plot(range(15), cum[:15], color=INK, lw=3)
        ax.plot(range(14, 31), cum[14:], color=INK, lw=3, ls=":", label="what actually happened")
        ax.plot([14, 30], [cum[14], r["naive"]], color=MUTED, lw=2.5, ls="--", label="arithmetic from day 14")
        ax.vlines(30.6, r["p10"], min(r["p90"], 300), color=BAND, lw=10, alpha=0.6, label="model P10-P90 at day 30")
        ax.plot([30.6], [r["p50"] if r["p50"] < 300 else 300], marker="o", color=INK)
        ax.axhline(200, color=LIMIT, lw=2)
        ax.axvline(14, color=RULE, lw=1)
        ok_m = (r["p_cross"] >= 0.5) == r["crossed"]
        ax.set_title(f"House {key[0]}, from {key[1]}\n{title}", loc="left", fontsize=17, fontweight="bold", color=INK)
        ax.text(1, 285, f"arithmetic: {r['naive']:.0f}\nmodel: {r['p_cross']:.0%} over ({r['verdict']})\nfinal: {r['final']:.0f}",
                fontsize=14, color=INK, va="top")
        ax.text(29.5, 288, "model right" if ok_m else "model wrong", ha="right", fontsize=15, fontweight="bold",
                color=SAFE if ok_m else LIMIT)
        ax.set_xlim(0, 32)
        ax.set_ylim(0, 300)
        ax.set_xlabel("day of the cycle")
    axes[0].set_ylabel("units used so far")
    axes[0].legend(loc="lower right", frameon=False, fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT / "plate-cases.png")


def meters_grid():
    ev = load("results/gemma/meter-eval.json")["per_photo"]
    v1 = load("results/gemma/meter-eval-v1.json")["per_photo"]
    pick = ["m04_397510397_d86b47de21_b.jpg", "m11_8013362749_a2576e462c_b.jpg", "m09_14137596527_73eaea20ab_b.jpg",
            "m16_Digital_Electric_meter_Erorr.jpg", "m15_TNB_Digital_Electrical_Meters.jpg",
            "m03_2927254475_e7366dab4d_b.jpg"]
    W, H, tw, th = 1600, 1080, 500, 380
    img = Image.new("RGB", (W, H), CASING)
    d = ImageDraw.Draw(img)
    d.text((40, 24), "Gemma on 17 CC meter photos: what it read, what it refused", font=font(38, bold=True),
           fill=INK)
    for i, name in enumerate(pick):
        x, y = 40 + (i % 3) * (tw + 30), 100 + (i // 3) * (th + 120)
        img.paste(fit(ImageOps.exif_transpose(Image.open(Path("data/demo_meters") / name)), tw, th), (x, y))
        r, r1 = ev[name], v1[name]
        got = r["model"].get("reading_kwh")
        truth = r["truth_kwh"]
        if r["outcome"] == "correct":
            lab, col = f"read {got:g} = truth", SAFE
        elif r["outcome"] == "wrong":
            lab, col = f"read {got:g}, truth {truth:g} (v1: {r1['model']['reading_kwh']:g})", LIMIT
        elif r["outcome"] in ("refused_ok", "refused"):
            lab, col = "refused", SAFE if r["expect"] == "refuse" else WATCH
        else:
            lab, col = r["outcome"], WATCH
        d.rectangle((x, y + th, x + tw, y + th + 44), fill=col)
        d.text((x + 12, y + th + 8), lab, font=font(24, bold=True), fill="#FFFFFF")
        why = r["model"].get("unreadable_reason") or ""
        if len(why) > 52:
            why = why[:52].rsplit(" ", 1)[0].rstrip(",;:") + "..."
        d.text((x, y + th + 52), why, font=font(18), fill=MUTED)
    img.save(OUT / "meters-grid.jpg", quality=88)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    cover(sys.argv[1])
    before_after(sys.argv[2])
    plate_system()
    plate_replay()
    plate_sides()
    plate_cases()
    meters_grid()
    print(sorted(p.name for p in OUT.iterdir()))
