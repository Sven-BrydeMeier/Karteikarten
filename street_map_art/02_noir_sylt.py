"""
Methode 2: Noir / maptoposter — Weiß auf Schwarz
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import sylt_geodata as geo
from plot_helpers import plot_streets

fig, ax = plt.subplots(figsize=(12, 20), facecolor="black")
ax.set_facecolor("black")

coast_poly = Polygon(geo.COASTLINE, closed=True, facecolor="#080808",
                     edgecolor="#333333", linewidth=0.6, zorder=1)
ax.add_patch(coast_poly)

hd_x, hd_y = zip(*geo.HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color="white", linewidth=2.0, zorder=3, solid_capstyle="round")

plot_streets(ax, geo,
             color_major="white", color_medium="#AAAAAA", color_minor="#555555",
             lw_major=1.5, lw_medium=0.5, lw_minor=0.2)

for name, (lon, lat) in geo.PLACES.items():
    ax.text(lon, lat, name, fontsize=5, color="#444444", ha="center",
            fontfamily="sans-serif", zorder=4)

ax.plot(*geo.PIN, marker="v", color="#FF4444", markersize=15, zorder=10)
ax.annotate(geo.PIN_LABEL, geo.PIN, textcoords="offset points", xytext=(8, 10),
            fontsize=7, color="#FF4444", fontweight="bold", zorder=10)

ax.text(0.5, 0.97, "S Y L T", transform=ax.transAxes, ha="center",
        fontsize=42, color="white", fontweight="bold", fontfamily="sans-serif")
ax.text(0.5, 0.958, "N O I R", transform=ax.transAxes, ha="center",
        fontsize=12, color="#444444", fontfamily="sans-serif")
ax.text(0.5, 0.008, "54.9\u00b0N  8.3\u00b0E  \u00b7  maptoposter Style",
        transform=ax.transAxes, ha="center", fontsize=8, color="#333333")

ax.set_xlim(8.27, 8.48)
ax.set_ylim(54.73, 55.07)
ax.set_aspect(1.7)
ax.set_axis_off()

out = os.path.join(os.path.dirname(__file__), "output", "02_noir_sylt.png")
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="black")
plt.close(fig)
print(f"Gespeichert: {out}")
