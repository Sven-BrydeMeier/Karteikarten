"""
Methode 3: city-roads / anvaka Style — Ultra-minimalistisch
Nur Straßenlinien, kein Rahmen, kein Text — reiner Kunst-Minimalismus.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

fig, ax = plt.subplots(figsize=(12, 18), facecolor="white")
ax.set_facecolor("white")

# Alle Straßen gleich dünn — der city-roads Look
all_roads = [ROAD_MAIN_NS, ROAD_EW_WESTERLAND, HINDENBURGDAMM] + ALL_MINOR_STREETS
for road in all_roads:
    rx, ry = zip(*road)
    ax.plot(rx, ry, color="black", linewidth=0.4, solid_capstyle="round")

# Pin — ganz dezent
ax.plot(*PIN, "o", color="red", markersize=6, zorder=10)

# Minimaler Text
ax.text(0.5, 0.01, "SYLT", transform=ax.transAxes, ha="center",
        fontsize=22, color="black", fontweight="bold", fontfamily="sans-serif")

ax.set_xlim(8.15, 8.90)
ax.set_ylim(54.73, 55.07)
ax.set_aspect(1.7)
ax.set_axis_off()

out = "/home/user/Karteikarten/street_map_art/output/03_city_roads_sylt.png"
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Gespeichert: {out}")
