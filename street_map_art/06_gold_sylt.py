"""
Methode 6: Gold auf Schwarz — Luxus-Edition
Goldene Straßenlinien auf schwarzem Grund.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

GOLD_BRIGHT = "#DAA520"
GOLD_MEDIUM = "#B8860B"
GOLD_DARK = "#8B6914"
GOLD_FAINT = "#5C4510"
BG = "#000000"

fig, ax = plt.subplots(figsize=(12, 20), facecolor=BG)
ax.set_facecolor(BG)

# Insel subtil
coast_poly = Polygon(COASTLINE, closed=True, facecolor="#0A0800",
                     edgecolor=GOLD_DARK, linewidth=0.5, zorder=1)
ax.add_patch(coast_poly)

# Hindenburgdamm
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color=GOLD_BRIGHT, linewidth=2.0, zorder=3,
        solid_capstyle="round")

# Hauptstraßen
for road in [ROAD_L24, ROAD_EW_MAIN]:
    rx, ry = zip(*road)
    ax.plot(rx, ry, color=GOLD_BRIGHT, linewidth=1.5, zorder=3,
            solid_capstyle="round")

# Nebenstraßen
for street in ALL_MINOR_STREETS:
    sx, sy = zip(*street)
    ax.plot(sx, sy, color=GOLD_FAINT, linewidth=0.4, zorder=2,
            solid_capstyle="round")

# Ortsnamen
for name, (lon, lat) in PLACES.items():
    ax.text(lon, lat, name, fontsize=4.5, color=GOLD_DARK, ha="center",
            fontfamily="serif", fontstyle="italic", zorder=4)

# Pin
ax.plot(*PIN, marker="v", color="#FF3333", markersize=15, zorder=10)
ax.annotate(PIN_LABEL, PIN, textcoords="offset points", xytext=(8, 10),
            fontsize=7, color="#FF3333", fontweight="bold", zorder=10)

# Titel
ax.text(0.5, 0.97, "S Y L T", transform=ax.transAxes, ha="center",
        fontsize=42, color=GOLD_BRIGHT, fontweight="bold", fontfamily="serif")
ax.text(0.5, 0.957, "\u2014 DEUTSCHLAND \u2014", transform=ax.transAxes, ha="center",
        fontsize=13, color=GOLD_DARK, fontfamily="serif")
ax.text(0.5, 0.008, "54.9\u00b0N  8.3\u00b0E", transform=ax.transAxes, ha="center",
        fontsize=8, color=GOLD_FAINT, fontfamily="serif")

ax.set_xlim(8.27, 8.48)
ax.set_ylim(54.73, 55.07)
ax.set_aspect(1.7)
ax.set_axis_off()

out = os.path.join(os.path.dirname(__file__), "output", "06_gold_sylt.png")
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print(f"Gespeichert: {out}")
