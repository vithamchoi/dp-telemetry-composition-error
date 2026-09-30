#!/usr/bin/env python3
"""Generate the paper's figures. Measured data and Monte-Carlo derivations only."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import figstyle as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis import Data, EPSILONS, ALARM_TAU  # noqa: E402

RES = Path(sys.argv[1] if len(sys.argv) > 1 else "../results")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "figures")
OUT.mkdir(parents=True, exist_ok=True)
D = Data(RES)

C = ["#0072B2", "#D55E00", "#009E73", "#E69F00"]
INK, MUTED, GRID = "#1a1a1a", "#6b6b6b", "#dcdcdc"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["DejaVu Serif"],
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8.5,
    "legend.fontsize": 7.2, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "axes.edgecolor": MUTED, "axes.linewidth": 0.6, "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5,
    "axes.axisbelow": True, "figure.dpi": 200,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02, "pdf.fonttype": 42,
})


def tidy(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=2.5, width=0.6)


def save(fig, name):
    fig.savefig(OUT / name)
    plt.close(fig)
    print(f"wrote {OUT / name}")


MECHS = [("laplace", "Aggregate Laplace", C[0]),
         ("perrecord", "Per-record Laplace", C[1]),
         ("rr", "Randomised response", C[2])]

# ===================================================== Fig: release distribution
fig, ax = plt.subplots(figsize=(5.0, 2.55))
eps = 0.5
w = 3.0 * D.rr_support_spacing(eps)   # aligned to the RR lattice
bins = np.arange(0.0, 0.35 + w, w)
for mech, lab, col in MECHS:
    d = D.draws(mech, eps)
    ax.hist(d, bins=bins, histtype="step", linewidth=1.3, color=col, label=lab,
            density=True)
pilot = [r for r in D.pilot_rows() if r["eps"] == eps][0]["dp"]
ax.axvline(D.true_rate, color=INK, linewidth=1.2)
ax.text(0.005, 0.03, "true rate 0%", rotation=90, va="bottom",
        ha="left", fontsize=6.8, color=INK)
ax.axvline(pilot, color=C[1], linewidth=1.2, linestyle=(0, (4, 3)))
ax.text(pilot + 0.007, 8.0, f"actual\nrelease\n{100 * pilot:.2f}%",
        va="center", ha="left", fontsize=6.8, color=C[1])
ax.set_xlabel(r"Released refusal rate at $\varepsilon=0.5$")
ax.set_ylabel("Density")
ax.set_yscale("log")
ax.set_ylim(1e-2, 1e3)
F.place_legend(ax, frameon=False, handlelength=1.5, labelcolor=INK,
          borderaxespad=0.2, fontsize=6.8)
tidy(ax)
fig.tight_layout()
save(fig, "fig_distribution.pdf")

# ===================================================== Fig: SD vs epsilon
fig, ax = plt.subplots(figsize=(5.0, 2.4))
for i, (mech, lab, col) in enumerate(MECHS):
    tab = D.mechanism_table(mech)
    ax.plot(EPSILONS, [100 * tab[e]["sd"] for e in EPSILONS], color=col,
            marker=["o", "s", "^"][i], markersize=3.8, linewidth=1.4,
            markeredgecolor="white", markeredgewidth=0.5, label=lab)
ax.plot(EPSILONS, [100 * D.theory_sd_aggregate(e) for e in EPSILONS],
        color=INK, linewidth=0.9, linestyle=(0, (2, 2)), label="theory")
ax.plot(EPSILONS, [100 * D.theory_sd_perrecord(e) for e in EPSILONS],
        color=INK, linewidth=0.9, linestyle=(0, (2, 2)))
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xticks(EPSILONS)
ax.set_xticklabels([f"{e:g}" for e in EPSILONS])
ax.set_xlabel(r"Privacy budget $\varepsilon$")
ax.set_ylabel("SD of released rate (\\%)".replace("\\%", "%"))
F.place_legend(ax, frameon=False, handlelength=1.6, labelcolor=INK,
          borderaxespad=0.2)
ax.annotate(rf"$\sqrt{{n}} = {D.inflation_factor():.1f}\times$",
            xy=(2.0, 100 * (D.theory_sd_aggregate(2.0) * D.theory_sd_perrecord(2.0)) ** 0.5),
            fontsize=7, color=MUTED, ha="center")
tidy(ax)
fig.tight_layout()
save(fig, "fig_sd.pdf")

# ===================================================== Fig: false alarm rate
fig, ax = plt.subplots(figsize=(5.0, 2.4))
for i, (mech, lab, col) in enumerate(MECHS):
    tab = D.mechanism_table(mech)
    y = [100 * tab[e]["alarm"] for e in EPSILONS]
    ax.plot(EPSILONS, y, color=col, marker=["o", "s", "^"][i], markersize=3.8,
            linewidth=1.4, markeredgecolor="white", markeredgewidth=0.5,
            label=lab)
    up = (i != 2)   # per-record above the marker, randomised response below
    for xi, v in zip(EPSILONS, y):
        if v >= 1.0:
            ax.text(xi, v * (1.35 if up else 0.62), f"{v:.0f}", ha="center",
                    va="bottom" if up else "top", fontsize=6.4, color=col)
ax.set_xscale("log")
ax.set_yscale("symlog", linthresh=0.05)
ax.set_xticks(EPSILONS)
ax.set_xticklabels([f"{e:g}" for e in EPSILONS])
ax.set_ylim(0, 130)
ax.set_xlabel(r"Privacy budget $\varepsilon$")
ax.set_ylabel(rf"P(release $\geq$ {100 * ALARM_TAU:.0f}\%) (\%)".replace("\\%", "%"))
F.place_legend(ax, frameon=False, handlelength=1.6, labelcolor=INK,
          borderaxespad=0.2)
tidy(ax)
fig.tight_layout()
save(fig, "fig_alarm.pdf")

print("\nAll figures generated from:", RES.resolve())
