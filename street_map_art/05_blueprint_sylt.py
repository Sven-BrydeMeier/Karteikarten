"""
Methode 5: Blueprint — Technische Zeichnung
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

fig, ax = plt.subplots(figsize=(12, 20), facecolor=BG)
ax.set_facecolor(BG)

# Gitterlinien
for lon in np.arange(8.25, 8.50, 0.02):
    ax.axvline(x=lon, color=GRID, linewidth=0.2, alpha=0.5)
for lat in np.arange(54.73, 55.08, 0.01):
    ax.axhline(y=lat, color=GRID, linewidth=0.2, alpha=0.5)

# Küstenlinie gestrichelt
coast_poly = Polygon(COASTLINE, closed=True, facecolor="#0D3666",
                     edgecolor=DIM, linewidth=0.8, linestyle="--", zorder=2)
ax.add_patch(coast_poly)

# Hindenburgdamm
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color=FG, linewidth=2.0, zorder=3, solid_capstyle="round")

# Hauptstraßen
for road in [ROAD_L24, ROAD_EW_MAIN]:
    rx, ry = zip(*road)
    ax.plot(rx, ry, color=FG, linewidth=1.4, zorder=3, solid_capstyle="round")

# Nebenstraßen
for street in ALL_MINOR_STREETS:
    sx, sy = zip(*street)
    ax.plot(sx, sy, color=DIM, linewidth=0.4, zorder=2, solid_capstyle="round")

# Ortsnamen
for name, (lon, lat) in PLACES.items():
    ax.text(lon, lat, name.upper(), fontsize=4.5, color=DIM, ha="center",
            fontfamily="monospace", zorder=4)

# Pin
ax.plot(*PIN, marker="v", color="#FFD700", markersize=15, zorder=10)
ax.annotate(PIN_LABEL, PIN, textcoords="offset points", xytext=(8, 10),
            fontsize=7, color="#FFD700", fontweight="bold", fontfamily="monospace",
            zorder=10)

# Koordinaten-Achsen
for lon in np.arange(8.28, 8.48, 0.04):
    ax.text(lon, 54.733, f"{lon:.2f}\u00b0E", fontsize=4, color=DIM, ha="center",
            fontfamily="monospace")
for lat in np.arange(54.75, 55.06, 0.05):
    ax.text(8.273, lat, f"{lat:.2f}\u00b0N", fontsize=4, color=DIM, va="center",
            fontfamily="monospace")

# Titel
ax.set_title("SYLT \u2014 BLUEPRINT", fontsize=28, fontweight="bold", color=FG,
             pad=20, fontfamily="monospace")
ax.text(0.5, 0.005, "TECHNICAL DRAWING  \u00b7  SCALE 1:50000", transform=ax.transAxes,
        ha="center", fontsize=7, color=DIM, fontfamily="monospace")

ax.set_xlim(8.27, 8.48)
ax.set_ylim(54.73, 55.07)
ax.set_aspect(1.7)
ax.set_axis_off()

out = os.path.join(os.path.dirname(__file__), "output", "05_blueprint_sylt.png")
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor=BG)
plt.close(fig)
print(f"Gespeichert: {out}")
