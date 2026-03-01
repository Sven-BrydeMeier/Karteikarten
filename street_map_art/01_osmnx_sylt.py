"""
Methode 1: OSMnx-Style — Schwarz auf Weiß
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import sylt_geodata as geo
from plot_helpers import plot_streets

fig, ax = plt.subplots(figsize=(12, 20), facecolor="white")
ax.set_facecolor("white")

coast_poly = Polygon(geo.COASTLINE, closed=True, facecolor="#F0F0F0",
                     edgecolor="black", linewidth=1.0, zorder=1)
ax.add_patch(coast_poly)

hd_x, hd_y = zip(*geo.HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color="black", linewidth=1.8, zorder=2, solid_capstyle="round")

plot_streets(ax, geo,
             color_major="black", color_medium="#333333", color_minor="#777777",
             lw_major=1.2, lw_medium=0.5, lw_minor=0.2)

ax.plot(*geo.PIN, marker="v", color="red", markersize=14, zorder=10)
ax.annotate(geo.PIN_LABEL, geo.PIN, textcoords="offset points", xytext=(8, 10),
            fontsize=7, color="red", fontweight="bold", zorder=10)

ax.set_title("SYLT", fontsize=38, fontweight="bold", color="black", pad=20,
             fontfamily="sans-serif")
ax.text(0.5, -0.01, "OSMnx Style", transform=ax.transAxes,
        ha="center", fontsize=9, color="gray")

ax.set_xlim(8.27, 8.48)
ax.set_ylim(54.73, 55.07)
ax.set_aspect(1.7)
ax.set_axis_off()

out = os.path.join(os.path.dirname(__file__), "output", "01_osmnx_sylt.png")
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Gespeichert: {out}")
