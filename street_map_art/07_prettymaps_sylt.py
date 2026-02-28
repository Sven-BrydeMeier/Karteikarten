"""
Methode 7: prettymaps-inspiriert — Aquarell-Style
Pastellfarben für Wasser, Land und Grünflächen.
Ein künstlerischerer, weicherer Look.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyBboxPatch
from matplotlib.collections import PatchCollection
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

# Farben
BG = "#FAF6EE"       # Warmes Papier-Weiß
WATER = "#AAD3DF"     # Wasser-Blau
LAND = "#F2E8D5"      # Sand-Beige (Sylt!)
GREEN = "#C8E6C2"     # Grünflächen
ROAD_MAIN = "#4A4A4A"
ROAD_MINOR = "#8A8A8A"
COAST_EDGE = "#6B6B5E"

fig, ax = plt.subplots(figsize=(12, 18), facecolor=BG)
ax.set_facecolor(WATER)  # Alles "Wasser" als Hintergrund

# Festland-Andeutung rechts (für Hindenburgdamm-Ende)
mainland = Polygon(
    [(8.78, 54.78), (8.92, 54.78), (8.92, 54.87), (8.78, 54.87)],
    closed=True, facecolor=LAND, edgecolor=COAST_EDGE, linewidth=0.5
)
ax.add_patch(mainland)

# Insel Sylt — Sand/Beige
coast_poly = Polygon(COASTLINE, closed=True, facecolor=LAND,
                     edgecolor=COAST_EDGE, linewidth=1.0, zorder=2)
ax.add_patch(coast_poly)

# Grünflächen-Andeutung (Parks / Heide)
green_areas = [
    # Braderuper Heide
    [(8.3500, 54.9450), (8.3600, 54.9450), (8.3650, 54.9500),
     (8.3600, 54.9550), (8.3500, 54.9550), (8.3450, 54.9500)],
    # Kampener Vogelkoje
    [(8.3350, 54.9480), (8.3420, 54.9480), (8.3420, 54.9530), (8.3350, 54.9530)],
    # Rantum Becken
    [(8.3100, 54.8500), (8.3300, 54.8500), (8.3400, 54.8600),
     (8.3200, 54.8700), (8.3100, 54.8600)],
]
for ga in green_areas:
    green_poly = Polygon(ga, closed=True, facecolor=GREEN, edgecolor="#8AB880",
                         linewidth=0.3, alpha=0.6, zorder=2)
    ax.add_patch(green_poly)

# Hindenburgdamm
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color=ROAD_MAIN, linewidth=2.5, zorder=4,
        solid_capstyle="round")
# Gleise-Andeutung (gestrichelt daneben)
ax.plot(hd_x, [y + 0.002 for y in hd_y], color="#888888", linewidth=0.8,
        linestyle="--", zorder=3, alpha=0.5)

# Hauptstraßen
ns_x, ns_y = zip(*ROAD_MAIN_NS)
ax.plot(ns_x, ns_y, color=ROAD_MAIN, linewidth=1.8, zorder=4,
        solid_capstyle="round")

ew_x, ew_y = zip(*ROAD_EW_WESTERLAND)
ax.plot(ew_x, ew_y, color=ROAD_MAIN, linewidth=1.3, zorder=4,
        solid_capstyle="round")

# Nebenstraßen
for street in ALL_MINOR_STREETS:
    sx, sy = zip(*street)
    ax.plot(sx, sy, color=ROAD_MINOR, linewidth=0.5, zorder=3,
            solid_capstyle="round")

# Gebäude-Andeutung (kleine Rechtecke in Westerland)
np.random.seed(42)
for i in range(60):
    bx = 8.290 + np.random.random() * 0.035
    by = 54.895 + np.random.random() * 0.020
    size = 0.001 + np.random.random() * 0.001
    building = plt.Rectangle((bx, by), size, size * 0.6,
                              facecolor="#D4C5A9", edgecolor="#B0A080",
                              linewidth=0.2, zorder=3, alpha=0.7)
    ax.add_patch(building)

# Ortsnamen
for name, (lon, lat) in PLACES.items():
    ax.text(lon, lat, name, fontsize=6, color="#5A5A4A", ha="center",
            fontfamily="serif", fontstyle="italic", zorder=5)

# Pin
ax.plot(*PIN, marker="v", color="#CC3333", markersize=14, zorder=10)
ax.annotate(PIN_LABEL, PIN, textcoords="offset points", xytext=(10, 10),
            fontsize=8, color="#CC3333", fontweight="bold", fontfamily="serif",
            zorder=10)

# Titel
ax.set_title("SYLT", fontsize=36, fontweight="bold", color="#3A3A2A", pad=20,
             fontfamily="serif")
ax.text(0.5, -0.015, "prettymaps-inspiriert  ·  Aquarell Style", transform=ax.transAxes,
        ha="center", fontsize=9, color="#888870", fontfamily="serif")

ax.set_xlim(8.15, 8.90)
ax.set_ylim(54.73, 55.07)
ax.set_aspect(1.7)
ax.set_axis_off()

out = "/home/user/Karteikarten/street_map_art/output/07_prettymaps_sylt.png"
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print(f"Gespeichert: {out}")
