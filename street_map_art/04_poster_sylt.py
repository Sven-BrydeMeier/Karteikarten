"""
Methode 4: Poster / map-posterizer — Dunkel mit Rahmen
Elegante Beschriftung, Hindenburgdamm-Label.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

BG = "#1C1C1C"
FG = "#FFFFFF"

fig, ax = plt.subplots(figsize=(12, 20), facecolor=BG)
ax.set_facecolor(BG)

# Insel-Fläche
coast_poly = Polygon(COASTLINE, closed=True, facecolor="#222222",
                     edgecolor="#444444", linewidth=0.4, zorder=1)
ax.add_patch(coast_poly)

# Hindenburgdamm
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color=FG, linewidth=1.8, zorder=3, solid_capstyle="round")

# Hauptstraßen
for road in [ROAD_L24, ROAD_EW_MAIN]:
    rx, ry = zip(*road)
    ax.plot(rx, ry, color=FG, linewidth=1.2, zorder=3, solid_capstyle="round")

# Nebenstraßen
for street in ALL_MINOR_STREETS:
    sx, sy = zip(*street)
    ax.plot(sx, sy, color="#666666", linewidth=0.35, zorder=2, solid_capstyle="round")

# Ortsnamen
for name, (lon, lat) in PLACES.items():
    ax.text(lon, lat, name.upper(), fontsize=4.5, color="#555555", ha="center",
            fontfamily="sans-serif", fontweight="bold", zorder=4)

# Pin
ax.plot(*PIN, marker="v", color="#FF6B6B", markersize=14, zorder=10)
ax.annotate(PIN_LABEL, PIN, textcoords="offset points", xytext=(8, 10),
            fontsize=7, color="#FF6B6B", fontweight="bold", zorder=10)

ax.set_xlim(8.27, 8.48)
ax.set_ylim(54.73, 55.07)

# Titel-Block unten
ax.text(0.5, 0.04, "S Y L T", transform=ax.transAxes, ha="center",
        fontsize=38, color=FG, fontweight="bold", fontfamily="sans-serif")
ax.text(0.5, 0.023, "D E U T S C H L A N D", transform=ax.transAxes, ha="center",
        fontsize=13, color="#666666", fontfamily="sans-serif")
ax.text(0.5, 0.008, "54\u00b054'N  8\u00b018'E", transform=ax.transAxes, ha="center",
        fontsize=9, color="#444444", fontfamily="sans-serif")

ax.set_aspect(1.7)
ax.set_axis_off()

out = os.path.join(os.path.dirname(__file__), "output", "04_poster_sylt.png")
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor=BG, edgecolor="none")
plt.close(fig)
print(f"Gespeichert: {out}")
