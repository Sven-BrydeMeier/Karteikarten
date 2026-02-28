"""
Methode 1: OSMnx-Style — Schwarz auf Weiß
Klassische Straßennetz-Darstellung: schwarze Linien auf weißem Grund.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from sylt_geodata import *

fig, ax = plt.subplots(figsize=(12, 18), facecolor="white")
ax.set_facecolor("white")

# Küstenlinie als gefüllte Fläche (hellgrau)
coast_poly = Polygon(COASTLINE, closed=True, facecolor="#F5F5F5",
                     edgecolor="black", linewidth=1.2, zorder=1)
ax.add_patch(coast_poly)

# Hindenburgdamm
hd_x, hd_y = zip(*HINDENBURGDAMM)
ax.plot(hd_x, hd_y, color="black", linewidth=2.0, zorder=2, solid_capstyle="round")

# Hauptstraße Nord-Süd
ns_x, ns_y = zip(*ROAD_MAIN_NS)
ax.plot(ns_x, ns_y, color="black", linewidth=1.5, zorder=3, solid_capstyle="round")

# Ost-West Verbindung
ew_x, ew_y = zip(*ROAD_EW_WESTERLAND)
ax.plot(ew_x, ew_y, color="black", linewidth=1.2, zorder=3, solid_capstyle="round")

# Nebenstraßen
for street in ALL_MINOR_STREETS:
    sx, sy = zip(*street)
    ax.plot(sx, sy, color="black", linewidth=0.5, zorder=2, solid_capstyle="round")

# Pin
ax.plot(*PIN, marker="v", color="red", markersize=14, zorder=10)
ax.annotate(PIN_LABEL, PIN, textcoords="offset points", xytext=(8, 10),
            fontsize=8, color="red", fontweight="bold", zorder=10)

# Titel
ax.set_title("SYLT", fontsize=38, fontweight="bold", color="black", pad=20,
             fontfamily="sans-serif")
ax.text(0.5, -0.02, "OSMnx Style  ·  Schwarz auf Weiß", transform=ax.transAxes,
        ha="center", fontsize=10, color="gray")

ax.set_xlim(8.15, 8.90)
ax.set_ylim(54.73, 55.07)
ax.set_aspect(1.7)
ax.set_axis_off()

out = "/home/user/Karteikarten/street_map_art/output/01_osmnx_sylt.png"
fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Gespeichert: {out}")
