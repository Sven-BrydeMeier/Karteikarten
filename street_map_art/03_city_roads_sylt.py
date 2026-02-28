"""
Methode 3: city-roads / anvaka — Ultra-minimalistisch
Nur Straßen, keine Küstenlinie, kein Hintergrund.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

fig, ax = plt.subplots(figsize=(12, 20), facecolor="white")
ax.set_facecolor("white")

# Alle Straßen gleich dünn — der city-roads Look
all_roads = [ROAD_L24, ROAD_EW_MAIN] + ALL_MINOR_STREETS
for road in all_roads:
    rx, ry = zip(*road)
    ax.plot(rx, ry, color="black", linewidth=0.35, solid_capstyle="round")

# Hindenburgdamm — auch dünn
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color="black", linewidth=0.35, solid_capstyle="round")

# Pin — minimal
ax.plot(*PIN, "o", color="red", markersize=5, zorder=10)

# Minimaler Text
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
