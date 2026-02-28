"""
Methode 2: Noir / maptoposter-Style — Weiß auf Schwarz
Weiße Straßen auf schwarzem Grund, mit unterschiedlichen Linienstärken.
Inspiriert vom maptoposter "Noir"-Theme.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

fig, ax = plt.subplots(figsize=(12, 18), facecolor="black")
ax.set_facecolor("black")

# Küstenlinie — subtiler Rand
coast_poly = Polygon(COASTLINE, closed=True, facecolor="#0a0a0a",
                     edgecolor="#333333", linewidth=0.8, zorder=1)
ax.add_patch(coast_poly)

# Hindenburgdamm — prominent
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color="white", linewidth=2.5, zorder=3, solid_capstyle="round")

# Hauptstraße
ns_x, ns_y = zip(*ROAD_MAIN_NS)
ax.plot(ns_x, ns_y, color="white", linewidth=2.0, zorder=3, solid_capstyle="round")

# Ost-West
ew_x, ew_y = zip(*ROAD_EW_WESTERLAND)
ax.plot(ew_x, ew_y, color="#DDDDDD", linewidth=1.5, zorder=3, solid_capstyle="round")

# Nebenstraßen
for street in ALL_MINOR_STREETS:
    sx, sy = zip(*street)
    ax.plot(sx, sy, color="#888888", linewidth=0.5, zorder=2, solid_capstyle="round")

# Ortsnamen (dezent)
for name, (lon, lat) in PLACES.items():
    ax.text(lon, lat, name, fontsize=6, color="#555555", ha="center",
            fontfamily="sans-serif", zorder=4)

# Pin
ax.plot(*PIN, marker="v", color="#FF4444", markersize=16, zorder=10)
ax.annotate(PIN_LABEL, PIN, textcoords="offset points", xytext=(10, 12),
            fontsize=9, color="#FF4444", fontweight="bold", zorder=10)

# Titel
ax.text(0.5, 0.97, "S Y L T", transform=ax.transAxes, ha="center",
        fontsize=44, color="white", fontweight="bold", fontfamily="sans-serif")
ax.text(0.5, 0.955, "NOIR", transform=ax.transAxes, ha="center",
        fontsize=14, color="#555555", fontfamily="sans-serif")
ax.text(0.5, 0.01, "54.9°N  8.3°E  ·  maptoposter Style", transform=ax.transAxes,
        ha="center", fontsize=9, color="#444444")

ax.set_xlim(8.15, 8.90)
ax.set_ylim(54.73, 55.07)
ax.set_aspect(1.7)
ax.set_axis_off()

out = "/home/user/Karteikarten/street_map_art/output/02_noir_sylt.png"
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="black")
plt.close(fig)
print(f"Gespeichert: {out}")
