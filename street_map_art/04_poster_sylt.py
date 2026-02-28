"""
Methode 4: Poster-Style — map-posterizer / MapPosterCreator
Dunkelgrauer Hintergrund, weiße Straßen, eleganter Rahmen und Beschriftung.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyBboxPatch
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

BG = "#1C1C1C"
FG = "#FFFFFF"

fig, ax = plt.subplots(figsize=(12, 18), facecolor=BG)
ax.set_facecolor(BG)

# Insel-Fläche
coast_poly = Polygon(COASTLINE, closed=True, facecolor="#222222",
                     edgecolor="#444444", linewidth=0.5, zorder=1)
ax.add_patch(coast_poly)

# Hindenburgdamm
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color=FG, linewidth=2.0, zorder=3, solid_capstyle="round")
# Label Hindenburgdamm
mid = len(HINDENBURGDAMM) // 2
ax.text(HINDENBURGDAMM[mid][0], HINDENBURGDAMM[mid][1] + 0.008,
        "Hindenburgdamm", fontsize=6, color="#777777", ha="center",
        rotation=-2, fontfamily="sans-serif")

# Hauptstraßen
ns_x, ns_y = zip(*ROAD_MAIN_NS)
ax.plot(ns_x, ns_y, color=FG, linewidth=1.5, zorder=3, solid_capstyle="round")

ew_x, ew_y = zip(*ROAD_EW_WESTERLAND)
ax.plot(ew_x, ew_y, color="#CCCCCC", linewidth=1.2, zorder=3, solid_capstyle="round")

# Nebenstraßen
for street in ALL_MINOR_STREETS:
    sx, sy = zip(*street)
    ax.plot(sx, sy, color="#777777", linewidth=0.4, zorder=2, solid_capstyle="round")

# Ortsnamen
for name, (lon, lat) in PLACES.items():
    ax.text(lon, lat, name.upper(), fontsize=5, color="#555555", ha="center",
            fontfamily="sans-serif", fontweight="bold", zorder=4)

# Pin
ax.plot(*PIN, marker="v", color="#FF6B6B", markersize=15, zorder=10)
ax.annotate(PIN_LABEL, PIN, textcoords="offset points", xytext=(10, 10),
            fontsize=8, color="#FF6B6B", fontweight="bold", zorder=10)

# Poster-Rahmen
ax.set_xlim(8.15, 8.90)
ax.set_ylim(54.73, 55.07)

# Titel-Block unten
ax.text(0.5, 0.04, "S Y L T", transform=ax.transAxes, ha="center",
        fontsize=38, color=FG, fontweight="bold", fontfamily="sans-serif")
ax.text(0.5, 0.023, "D E U T S C H L A N D", transform=ax.transAxes, ha="center",
        fontsize=13, color="#666666", fontfamily="sans-serif")
ax.text(0.5, 0.008, "54°54'N  8°18'E", transform=ax.transAxes, ha="center",
        fontsize=9, color="#444444", fontfamily="sans-serif")

# Trennlinie
ax.axhline(y=54.745, color="#333333", linewidth=0.5, zorder=5)

ax.set_aspect(1.7)
ax.set_axis_off()

out = "/home/user/Karteikarten/street_map_art/output/04_poster_sylt.png"
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor=BG, edgecolor="none")
plt.close(fig)
print(f"Gespeichert: {out}")
