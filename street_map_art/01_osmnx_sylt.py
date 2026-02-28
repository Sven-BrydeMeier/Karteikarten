"""
Methode 1: OSMnx-Style — Schwarz auf Weiß
Echte OSM-Küstenlinie, detailliertes Straßennetz.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

fig, ax = plt.subplots(figsize=(12, 20), facecolor="white")
ax.set_facecolor("white")

# Küstenlinie — echtes OSM-Polygon
coast_poly = Polygon(COASTLINE, closed=True, facecolor="#F0F0F0",
                     edgecolor="black", linewidth=1.0, zorder=1)
ax.add_patch(coast_poly)

# Hindenburgdamm
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color="black", linewidth=1.8, zorder=2, solid_capstyle="round")

# Hauptstraßen
for road in [ROAD_L24, ROAD_EW_MAIN]:
    rx, ry = zip(*road)
    ax.plot(rx, ry, color="black", linewidth=1.2, zorder=3, solid_capstyle="round")

# Nebenstraßen
for street in ALL_MINOR_STREETS:
    sx, sy = zip(*street)
    ax.plot(sx, sy, color="#333333", linewidth=0.4, zorder=2, solid_capstyle="round")

# Pin
ax.plot(*PIN, marker="v", color="red", markersize=14, zorder=10)
ax.annotate(PIN_LABEL, PIN, textcoords="offset points", xytext=(8, 10),
            fontsize=7, color="red", fontweight="bold", zorder=10)

# Titel
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
