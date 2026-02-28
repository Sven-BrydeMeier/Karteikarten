"""
Methode 7: prettymaps-inspiriert — Aquarell-Style
Pastellfarben: Sand-Beige Insel, blaues Meer, Grünflächen.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

BG = "#FAF6EE"
WATER = "#AAD3DF"
LAND = "#F2E8D5"
GREEN = "#C8E6C2"
ROAD_MAIN_COL = "#4A4A4A"
ROAD_MINOR_COL = "#8A8A8A"
COAST_EDGE = "#6B6B5E"

fig, ax = plt.subplots(figsize=(12, 20), facecolor=BG)
ax.set_facecolor(WATER)

# Insel Sylt — Sand/Beige
coast_poly = Polygon(COASTLINE, closed=True, facecolor=LAND,
                     edgecolor=COAST_EDGE, linewidth=0.8, zorder=2)
ax.add_patch(coast_poly)

# Grünflächen (Heide, Parks)
green_areas = [
    # Braderuper Heide
    [(8.350, 54.940), (8.360, 54.940), (8.365, 54.945),
     (8.360, 54.950), (8.350, 54.950), (8.345, 54.945)],
    # Kampener Vogelkoje
    [(8.338, 54.950), (8.345, 54.950), (8.345, 54.955), (8.338, 54.955)],
    # Rantum Becken
    [(8.305, 54.853), (8.320, 54.852), (8.330, 54.858),
     (8.325, 54.865), (8.310, 54.862), (8.305, 54.858)],
    # Morsum Kliff
    [(8.405, 54.870), (8.415, 54.870), (8.420, 54.874),
     (8.415, 54.878), (8.405, 54.876)],
]
for ga in green_areas:
    gp = Polygon(ga, closed=True, facecolor=GREEN, edgecolor="#8AB880",
                 linewidth=0.2, alpha=0.5, zorder=2)
    ax.add_patch(gp)

# Hindenburgdamm
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color=ROAD_MAIN_COL, linewidth=2.0, zorder=4,
        solid_capstyle="round")

# Hauptstraßen
for road in [ROAD_L24, ROAD_EW_MAIN]:
    rx, ry = zip(*road)
    ax.plot(rx, ry, color=ROAD_MAIN_COL, linewidth=1.3, zorder=4,
            solid_capstyle="round")

# Nebenstraßen
for street in ALL_MINOR_STREETS:
    sx, sy = zip(*street)
    ax.plot(sx, sy, color=ROAD_MINOR_COL, linewidth=0.35, zorder=3,
            solid_capstyle="round")

# Gebäude-Andeutung in Westerland
np.random.seed(42)
for _ in range(80):
    bx = 8.287 + np.random.random() * 0.030
    by = 54.896 + np.random.random() * 0.018
    size = 0.0008 + np.random.random() * 0.0008
    building = plt.Rectangle((bx, by), size, size * 0.6,
                              facecolor="#D4C5A9", edgecolor="#B0A080",
                              linewidth=0.15, zorder=3, alpha=0.6)
    ax.add_patch(building)

# Ortsnamen
for name, (lon, lat) in PLACES.items():
    ax.text(lon, lat, name, fontsize=5, color="#5A5A4A", ha="center",
            fontfamily="serif", fontstyle="italic", zorder=5)

# Pin
ax.plot(*PIN, marker="v", color="#CC3333", markersize=13, zorder=10)
ax.annotate(PIN_LABEL, PIN, textcoords="offset points", xytext=(8, 10),
            fontsize=7, color="#CC3333", fontweight="bold", fontfamily="serif",
            zorder=10)

# Titel
ax.set_title("SYLT", fontsize=34, fontweight="bold", color="#3A3A2A", pad=20,
             fontfamily="serif")
ax.text(0.5, -0.01, "prettymaps-inspiriert  \u00b7  Aquarell Style",
        transform=ax.transAxes, ha="center", fontsize=8, color="#888870",
        fontfamily="serif")

ax.set_xlim(8.27, 8.48)
ax.set_ylim(54.73, 55.07)
ax.set_aspect(1.7)
ax.set_axis_off()

out = os.path.join(os.path.dirname(__file__), "output", "07_prettymaps_sylt.png")
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print(f"Gespeichert: {out}")
