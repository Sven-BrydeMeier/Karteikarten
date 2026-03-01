"""
Methode 6: Gold auf Schwarz — Luxus-Edition
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import sylt_geodata as geo
from plot_helpers import plot_streets

GOLD_BRIGHT = "#DAA520"
GOLD_MEDIUM = "#B8860B"
GOLD_DARK = "#8B6914"
GOLD_FAINT = "#5C4510"

fig, ax = plt.subplots(figsize=(12, 20), facecolor="black")
ax.set_facecolor("black")

coast_poly = Polygon(geo.COASTLINE, closed=True, facecolor="#0A0800",
                     edgecolor=GOLD_DARK, linewidth=0.5, zorder=1)
ax.add_patch(coast_poly)

hd_x, hd_y = zip(*geo.HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color=GOLD_BRIGHT, linewidth=2.0, zorder=3,
        solid_capstyle="round")

plot_streets(ax, geo,
             color_major=GOLD_BRIGHT, color_medium=GOLD_MEDIUM, color_minor=GOLD_FAINT,
             lw_major=1.5, lw_medium=0.5, lw_minor=0.2)

for name, (lon, lat) in geo.PLACES.items():
    ax.text(lon, lat, name, fontsize=4.5, color=GOLD_DARK, ha="center",
            fontfamily="serif", fontstyle="italic", zorder=4)

ax.plot(*geo.PIN, marker="v", color="#FF3333", markersize=15, zorder=10)
ax.annotate(geo.PIN_LABEL, geo.PIN, textcoords="offset points", xytext=(8, 10),
            fontsize=7, color="#FF3333", fontweight="bold", zorder=10)

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
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="black")
plt.close(fig)
print(f"Gespeichert: {out}")
