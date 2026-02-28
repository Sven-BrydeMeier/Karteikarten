"""
Methode 5: Blueprint-Style — Technische Zeichnung
Blauer Hintergrund, weiße Linien, Gitterraster.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

BG = "#0A2F5C"
FG = "#FFFFFF"
GRID = "#133D6B"
DIM = "#7FAACC"

fig, ax = plt.subplots(figsize=(12, 18), facecolor=BG)
ax.set_facecolor(BG)

# Gitterlinien
for lon in np.arange(8.1, 8.95, 0.05):
    ax.axvline(x=lon, color=GRID, linewidth=0.3, alpha=0.5)
for lat in np.arange(54.7, 55.1, 0.02):
    ax.axhline(y=lat, color=GRID, linewidth=0.3, alpha=0.5)

# Küstenlinie
coast_poly = Polygon(COASTLINE, closed=True, facecolor="#0D3666",
                     edgecolor=DIM, linewidth=1.0, linestyle="--", zorder=2)
ax.add_patch(coast_poly)

# Hindenburgdamm
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color=FG, linewidth=2.5, zorder=3, solid_capstyle="round")

# Hauptstraßen
ns_x, ns_y = zip(*ROAD_MAIN_NS)
ax.plot(ns_x, ns_y, color=FG, linewidth=1.8, zorder=3, solid_capstyle="round")

ew_x, ew_y = zip(*ROAD_EW_WESTERLAND)
ax.plot(ew_x, ew_y, color=FG, linewidth=1.4, zorder=3, solid_capstyle="round")

# Nebenstraßen
for street in ALL_MINOR_STREETS:
    sx, sy = zip(*street)
    ax.plot(sx, sy, color=DIM, linewidth=0.5, zorder=2, solid_capstyle="round")

# Ortsnamen (Monospace)
for name, (lon, lat) in PLACES.items():
    ax.text(lon, lat, name.upper(), fontsize=5, color=DIM, ha="center",
            fontfamily="monospace", zorder=4)

# Pin
ax.plot(*PIN, marker="v", color="#FFD700", markersize=16, zorder=10)
ax.annotate(PIN_LABEL, PIN, textcoords="offset points", xytext=(10, 12),
            fontsize=9, color="#FFD700", fontweight="bold", fontfamily="monospace",
            zorder=10)

# Koordinaten-Beschriftung an den Rändern
for lon in np.arange(8.2, 8.9, 0.1):
    ax.text(lon, 54.735, f"{lon:.1f}°E", fontsize=5, color=DIM, ha="center",
            fontfamily="monospace")
for lat in np.arange(54.75, 55.05, 0.05):
    ax.text(8.16, lat, f"{lat:.2f}°N", fontsize=5, color=DIM, va="center",
            fontfamily="monospace")

# Titel
ax.set_title("SYLT — BLUEPRINT", fontsize=30, fontweight="bold", color=FG,
             pad=20, fontfamily="monospace")
ax.text(0.5, 0.005, "TECHNICAL DRAWING  ·  SCALE 1:50000", transform=ax.transAxes,
        ha="center", fontsize=8, color=DIM, fontfamily="monospace")

ax.set_xlim(8.15, 8.90)
ax.set_ylim(54.73, 55.07)
ax.set_aspect(1.7)
ax.set_axis_off()

out = "/home/user/Karteikarten/street_map_art/output/05_blueprint_sylt.png"
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print(f"Gespeichert: {out}")
