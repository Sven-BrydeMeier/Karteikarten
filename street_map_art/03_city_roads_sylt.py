"""
Methode 3: city-roads / anvaka — Ultra-minimalistisch
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import sylt_geodata as geo
from plot_helpers import plot_streets

fig, ax = plt.subplots(figsize=(12, 20), facecolor="white")
ax.set_facecolor("white")

hd_x, hd_y = zip(*geo.HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color="black", linewidth=0.35, solid_capstyle="round")

plot_streets(ax, geo,
             color_major="black", color_medium="black", color_minor="#555555",
             lw_major=0.5, lw_medium=0.3, lw_minor=0.15)

ax.plot(*geo.PIN, "o", color="red", markersize=5, zorder=10)

ax.text(0.5, 0.008, "SYLT", transform=ax.transAxes, ha="center",
        fontsize=20, color="black", fontweight="bold", fontfamily="sans-serif")

ax.set_xlim(8.27, 8.48)
ax.set_ylim(54.73, 55.07)
ax.set_aspect(1.7)
ax.set_axis_off()

out = os.path.join(os.path.dirname(__file__), "output", "03_city_roads_sylt.png")
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Gespeichert: {out}")
