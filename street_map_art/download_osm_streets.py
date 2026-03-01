#!/usr/bin/env python3
"""
download_osm_streets.py — Lädt echte OSM-Straßendaten für Sylt herunter.

Verwendung:
    pip install osmnx geopandas
    python download_osm_streets.py

Das Script speichert die Daten als GeoJSON-Dateien, die dann von den
Karten-Skripten automatisch verwendet werden (statt der generierten Gitter).
"""
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, "osm_streets_cache.json")

# Sylt Bounding Box (inkl. Hindenburgdamm)
BBOX_WEST = 8.27
BBOX_SOUTH = 54.73
BBOX_EAST = 8.88
BBOX_NORTH = 55.07


def download_streets():
    """Lädt alle Straßen von Sylt über die Overpass API."""
    try:
        import osmnx as ox
    except ImportError:
        print("FEHLER: osmnx nicht installiert.")
        print("Installiere es mit: pip install osmnx")
        sys.exit(1)

    print("Lade Straßennetz von Sylt (Overpass API)...")
    print(f"Bounding Box: {BBOX_WEST},{BBOX_SOUTH} - {BBOX_EAST},{BBOX_NORTH}")

    try:
        G = ox.graph_from_bbox(
            bbox=(BBOX_WEST, BBOX_SOUTH, BBOX_EAST, BBOX_NORTH),
            network_type="all"
        )
    except Exception as e:
        print(f"FEHLER beim Download: {e}")
        print("Stelle sicher, dass du Internet-Zugang hast und die")
        print("Overpass API (overpass-api.de) erreichbar ist.")
        sys.exit(1)

    print(f"Graph geladen: {len(G.nodes)} Knoten, {len(G.edges)} Kanten")

    # Kanten als GeoDataFrame
    edges = ox.graph_to_gdfs(G, nodes=False)
    print(f"Straßensegmente: {len(edges)}")

    # Zu Koordinaten-Listen konvertieren
    streets_data = {
        "major": [],    # Hauptstraßen (primary, secondary, trunk)
        "medium": [],   # Tertiäre Straßen, Wohnstraßen
        "minor": [],    # Wege, Pfade
    }

    for _, row in edges.iterrows():
        geom = row.geometry
        coords = list(geom.coords)  # [(lon, lat), ...]

        # Straßentyp klassifizieren
        highway = row.get("highway", "")
        if isinstance(highway, list):
            highway = highway[0]

        if highway in ("motorway", "motorway_link", "trunk", "trunk_link",
                        "primary", "primary_link"):
            streets_data["major"].append(coords)
        elif highway in ("secondary", "secondary_link", "tertiary",
                          "tertiary_link", "residential", "living_street",
                          "unclassified"):
            streets_data["medium"].append(coords)
        else:
            streets_data["minor"].append(coords)

    total = sum(len(v) for v in streets_data.values())
    print(f"\nKlassifiziert:")
    print(f"  Hauptstraßen:  {len(streets_data['major'])}")
    print(f"  Nebenstraßen:  {len(streets_data['medium'])}")
    print(f"  Wege/Pfade:    {len(streets_data['minor'])}")
    print(f"  GESAMT:        {total}")

    # Als JSON speichern
    with open(CACHE_FILE, "w") as f:
        json.dump(streets_data, f)

    size_kb = os.path.getsize(CACHE_FILE) / 1024
    print(f"\nGespeichert: {CACHE_FILE} ({size_kb:.0f} KB)")
    print(f"\nJetzt kannst du 'python generate_all.py' ausführen —")
    print(f"die Karten verwenden automatisch die echten OSM-Daten!")


def load_cached_streets():
    """Lädt gecachte Straßendaten, falls vorhanden."""
    if not os.path.exists(CACHE_FILE):
        return None

    with open(CACHE_FILE) as f:
        data = json.load(f)

    # Zu Tupel-Listen konvertieren
    for key in data:
        data[key] = [
            [tuple(p) for p in street]
            for street in data[key]
        ]

    total = sum(len(v) for v in data.values())
    print(f"OSM-Cache geladen: {total} echte Straßensegmente")
    return data


if __name__ == "__main__":
    download_streets()
