"""
Gemeinsame Plot-Hilfsfunktionen für alle Karten-Styles.
Rendert Straßen mit Klassen-abhängigen Linienstärken wenn echte OSM-Daten vorliegen.
"""


def plot_streets(ax, geodata, color_major, color_medium, color_minor,
                 lw_major=1.5, lw_medium=0.6, lw_minor=0.25, zorder=2):
    """Zeichnet alle Straßen auf die Achse.

    Wenn echte OSM-Daten vorliegen (USE_REAL_OSM=True), werden drei
    Straßenklassen mit unterschiedlichen Stärken gerendert.
    Andernfalls werden alle Straßen mit mittlerer Stärke gezeichnet.
    """
    if geodata.USE_REAL_OSM:
        # Echte OSM-Daten: drei Klassen
        for street in geodata.OSM_MAJOR:
            if len(street) >= 2:
                sx, sy = zip(*street)
                ax.plot(sx, sy, color=color_major, linewidth=lw_major,
                        zorder=zorder + 1, solid_capstyle="round")
        for street in geodata.OSM_MEDIUM:
            if len(street) >= 2:
                sx, sy = zip(*street)
                ax.plot(sx, sy, color=color_medium, linewidth=lw_medium,
                        zorder=zorder, solid_capstyle="round")
        for street in geodata.OSM_MINOR:
            if len(street) >= 2:
                sx, sy = zip(*street)
                ax.plot(sx, sy, color=color_minor, linewidth=lw_minor,
                        zorder=zorder, solid_capstyle="round")
    else:
        # Fallback-Gitter: Haupt + Nebenstraßen manuell
        for road in [geodata.ROAD_L24, geodata.ROAD_EW_MAIN]:
            rx, ry = zip(*road)
            ax.plot(rx, ry, color=color_major, linewidth=lw_major,
                    zorder=zorder + 1, solid_capstyle="round")
        for street in geodata.ALL_MINOR_STREETS:
            if len(street) >= 2:
                sx, sy = zip(*street)
                ax.plot(sx, sy, color=color_medium, linewidth=lw_medium * 0.6,
                        zorder=zorder, solid_capstyle="round")
