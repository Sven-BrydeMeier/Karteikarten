"""
Methode 2: Noir / maptoposter — Weiß auf Schwarz
Echte OSM-Küstenlinie, verschiedene Linienstärken.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

fig, ax = plt.subplots(figsize=(12, 20), facecolor="black")
ax.set_facecolor("black")

# Küstenlinie
coast_poly = Polygon(COASTLINE, closed=True, facecolor="#080808",
                     edgecolor="#333333", linewidth=0.6, zorder=1)
ax.add_patch(coast_poly)

# Hindenburgdamm
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color="white", linewidth=2.0, zorder=3, solid_capstyle="round")

# Hauptstraßen
for road in [ROAD_L24, ROAD_EW_MAIN]:
    rx, ry = zip(*road)
    ax.plot(rx, ry, color="white", linewidth=1.5, zorder=3, solid_capstyle="round")

# Nebenstraßen
for street in ALL_MINOR_STREETS:
    sx, sy = zip(*street)
    ax.plot(sx, sy, color="#777777", linewidth=0.4, zorder=2, solid_capstyle="round")

# Ortsnamen
for name, (lon, lat) in PLACES.items():
    ax.text(lon, lat, name, fontsize=5, color="#444444", ha="center",
            fontfamily="sans-serif", zorder=4)

# Pin
ax.plot(*PIN, marker="v", color="#FF4444", markersize=15, zorder=10)
ax.annotate(PIN_LABEL, PIN, textcoords="offset points", xytext=(8, 10),
            fontsize=7, color="#FF4444", fontweight="bold", zorder=10)

# Titel
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
