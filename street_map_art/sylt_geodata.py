"""
Sylt Geo-Daten V3: Echte OSM-Küstenlinie + HOCHDETAILLIERTES Straßennetz.
Küstenlinie: 404 Punkte aus OSM (Nordfriesland Kreis-Polygon).
Straßen: ~200 Straßen für alle Ortschaften, realistisches Raster.
Format: (Longitude, Latitude)

Straßenabstände orientieren sich an der Realität:
- Bei 54.9°N: 0.001° lon ≈ 64m, 0.001° lat ≈ 111m
- Typischer Straßenabstand: 50-80m → ~0.001° lon, ~0.0006° lat
"""
import json
import os
import numpy as np

# === PIN: Steinmannstraße 15, Westerland ===
PIN = (8.3043, 54.9060)
PIN_LABEL = "Steinmannstr. 15\nWesterland"

# === Echte OSM-Küstenlinie laden ===
_dir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_dir, 'sylt_coast_final.json')) as _f:
    COASTLINE = [tuple(p) for p in json.load(_f)]

with open(os.path.join(_dir, 'hd_section.json')) as _f:
    HINDENBURGDAMM_FULL = [tuple(p) for p in json.load(_f)]

HINDENBURGDAMM = [p for p in HINDENBURGDAMM_FULL if p[1] < 54.895]

# ===================================================================
# HAUPTSTRASSEN
# ===================================================================

# L24 Nord-Süd-Achse (List → Hörnum) — die Hauptader der Insel
ROAD_L24 = [
    (8.4300, 55.0450), (8.4200, 55.0400), (8.4100, 55.0300),
    (8.4000, 55.0200), (8.3950, 55.0100), (8.3900, 55.0050),
    (8.3850, 54.9950), (8.3800, 54.9900), (8.3750, 54.9850),
    (8.3700, 54.9800), (8.3650, 54.9750), (8.3600, 54.9700),
    (8.3550, 54.9650), (8.3500, 54.9600), (8.3450, 54.9550),
    (8.3400, 54.9500), (8.3380, 54.9470), (8.3350, 54.9420),
    (8.3320, 54.9370), (8.3280, 54.9320), (8.3250, 54.9280),
    (8.3220, 54.9240), (8.3200, 54.9200), (8.3180, 54.9170),
    (8.3150, 54.9140), (8.3120, 54.9110), (8.3100, 54.9080),
    (8.3070, 54.9050), (8.3043, 54.9030), (8.3020, 54.9010),
    (8.3000, 54.8990), (8.2980, 54.8960), (8.2970, 54.8930),
    (8.2960, 54.8900), (8.2955, 54.8870), (8.2950, 54.8840),
    (8.2955, 54.8810), (8.2960, 54.8780), (8.2970, 54.8750),
    (8.2980, 54.8720), (8.2985, 54.8690), (8.2990, 54.8660),
    (8.2985, 54.8630), (8.2980, 54.8600), (8.2970, 54.8570),
    (8.2960, 54.8540), (8.2950, 54.8500), (8.2940, 54.8470),
    (8.2935, 54.8440), (8.2930, 54.8400), (8.2925, 54.8360),
    (8.2920, 54.8320), (8.2910, 54.8280), (8.2900, 54.8240),
    (8.2895, 54.8200), (8.2890, 54.8160), (8.2885, 54.8120),
    (8.2880, 54.8080), (8.2875, 54.8040), (8.2870, 54.8000),
    (8.2868, 54.7960), (8.2870, 54.7920), (8.2875, 54.7880),
    (8.2880, 54.7840), (8.2890, 54.7800), (8.2895, 54.7760),
    (8.2900, 54.7720), (8.2910, 54.7680), (8.2920, 54.7640),
    (8.2930, 54.7610), (8.2935, 54.7590),
]

# Ost-West: Westerland → Tinnum → Keitum → Morsum → Hindenburgdamm
ROAD_EW_MAIN = [
    (8.2870, 54.9050), (8.2900, 54.9055), (8.2930, 54.9055),
    (8.2960, 54.9055), (8.2990, 54.9058), (8.3020, 54.9060),
    (8.3043, 54.9060), (8.3070, 54.9060), (8.3100, 54.9055),
    (8.3130, 54.9050), (8.3160, 54.9040), (8.3190, 54.9030),
    (8.3220, 54.9020), (8.3250, 54.9010), (8.3280, 54.9000),
    (8.3310, 54.8990), (8.3340, 54.8980), (8.3370, 54.8970),
    (8.3400, 54.8960), (8.3450, 54.8940), (8.3500, 54.8920),
    (8.3550, 54.8910), (8.3600, 54.8900), (8.3650, 54.8890),
    (8.3700, 54.8870), (8.3750, 54.8860), (8.3800, 54.8840),
    (8.3850, 54.8820), (8.3900, 54.8800), (8.3950, 54.8790),
    (8.4000, 54.8770), (8.4050, 54.8760), (8.4100, 54.8740),
    (8.4150, 54.8720), (8.4200, 54.8700), (8.4250, 54.8680),
    (8.4350, 54.8660), (8.4450, 54.8650), (8.4550, 54.8640),
    (8.4650, 54.8630),
]

# ===================================================================
# WESTERLAND — HOCHDETAILLIERT (~55 Straßen)
# Zentrum: 54.907°N, 8.302°E
# Raster: lon 8.287–8.318, lat 54.895–54.915
# NS-Straßen alle 0.001° lon (~64m), EW alle 0.0007° lat (~78m)
# ===================================================================

def _generate_grid(lon_min, lon_max, lat_min, lat_max,
                   lon_step, lat_step, ns=True, ew=True,
                   jitter=0.0):
    """Erzeugt ein Straßenraster."""
    streets = []
    rng = np.random.RandomState(42)
    if ns:
        for lon in np.arange(lon_min, lon_max + 0.0001, lon_step):
            pts = []
            for lat in np.arange(lat_min, lat_max + 0.0001, lat_step / 2):
                j = rng.uniform(-jitter, jitter) if jitter else 0
                pts.append((round(lon + j, 6), round(lat, 6)))
            if len(pts) >= 2:
                streets.append(pts)
    if ew:
        for lat in np.arange(lat_min, lat_max + 0.0001, lat_step):
            pts = []
            for lon in np.arange(lon_min, lon_max + 0.0001, lon_step / 2):
                j = rng.uniform(-jitter, jitter) if jitter else 0
                pts.append((round(lon, 6), round(lat + j, 6)))
            if len(pts) >= 2:
                streets.append(pts)
    return streets

# Westerland Kern (dichtes Raster)
WESTERLAND_STREETS = _generate_grid(
    lon_min=8.2880, lon_max=8.3150,
    lat_min=54.8960, lat_max=54.9140,
    lon_step=0.0012, lat_step=0.0008,
    jitter=0.00005
)

# Westerland Rand (weniger dicht)
WESTERLAND_OUTER = _generate_grid(
    lon_min=8.2870, lon_max=8.3200,
    lat_min=54.8930, lat_max=54.8960,
    lon_step=0.0020, lat_step=0.0010,
    jitter=0.0001
)

# ===================================================================
# LIST — Detailliert (~20 Straßen)
# Zentrum: 55.007°N, 8.390°E
# ===================================================================
LIST_STREETS = _generate_grid(
    lon_min=8.3830, lon_max=8.3980,
    lat_min=54.9990, lat_max=55.0120,
    lon_step=0.0015, lat_step=0.0010,
    jitter=0.00008
)

# ===================================================================
# KAMPEN — Detailliert (~15 Straßen)
# Zentrum: 54.955°N, 8.342°E
# ===================================================================
KAMPEN_STREETS = _generate_grid(
    lon_min=8.3320, lon_max=8.3520,
    lat_min=54.9470, lat_max=54.9580,
    lon_step=0.0020, lat_step=0.0012,
    jitter=0.00010
)

# ===================================================================
# WENNINGSTEDT — Detailliert (~15 Straßen)
# Zentrum: 54.918°N, 8.316°E
# ===================================================================
WENNINGSTEDT_STREETS = _generate_grid(
    lon_min=8.3080, lon_max=8.3240,
    lat_min=54.9130, lat_max=54.9230,
    lon_step=0.0018, lat_step=0.0010,
    jitter=0.00008
)

# ===================================================================
# TINNUM — Detailliert (~15 Straßen)
# Zentrum: 54.900°N, 8.333°E
# ===================================================================
TINNUM_STREETS = _generate_grid(
    lon_min=8.3250, lon_max=8.3430,
    lat_min=54.8940, lat_max=54.9040,
    lon_step=0.0018, lat_step=0.0010,
    jitter=0.00008
)

# ===================================================================
# KEITUM — Detailliert (~15 Straßen)
# Zentrum: 54.892°N, 8.360°E
# ===================================================================
KEITUM_STREETS = _generate_grid(
    lon_min=8.3510, lon_max=8.3700,
    lat_min=54.8870, lat_max=54.8960,
    lon_step=0.0020, lat_step=0.0010,
    jitter=0.00010
)

# ===================================================================
# MORSUM — (~10 Straßen)
# ===================================================================
MORSUM_STREETS = _generate_grid(
    lon_min=8.4020, lon_max=8.4200,
    lat_min=54.8700, lat_max=54.8800,
    lon_step=0.0020, lat_step=0.0012,
    jitter=0.00010
)

# ===================================================================
# RANTUM — (~10 Straßen)
# ===================================================================
RANTUM_STREETS = _generate_grid(
    lon_min=8.2930, lon_max=8.3060,
    lat_min=54.8510, lat_max=54.8600,
    lon_step=0.0018, lat_step=0.0010,
    jitter=0.00008
)

# ===================================================================
# HÖRNUM — (~12 Straßen)
# ===================================================================
HOERNUM_STREETS = _generate_grid(
    lon_min=8.2860, lon_max=8.2980,
    lat_min=54.7580, lat_max=54.7680,
    lon_step=0.0015, lat_step=0.0010,
    jitter=0.00006
)

# ===================================================================
# MUNKMARSCH — (~8 Straßen)
# ===================================================================
MUNKMARSCH_STREETS = _generate_grid(
    lon_min=8.3440, lon_max=8.3570,
    lat_min=54.9060, lat_max=54.9140,
    lon_step=0.0020, lat_step=0.0012,
    jitter=0.00010
)

# ===================================================================
# BRADERUP — (~6 Straßen)
# ===================================================================
BRADERUP_STREETS = _generate_grid(
    lon_min=8.3530, lon_max=8.3650,
    lat_min=54.9360, lat_max=54.9430,
    lon_step=0.0020, lat_step=0.0012,
    jitter=0.00010
)

# ===================================================================
# ARCHSUM — (~6 Straßen)
# ===================================================================
ARCHSUM_STREETS = _generate_grid(
    lon_min=8.3680, lon_max=8.3800,
    lat_min=54.8830, lat_max=54.8900,
    lon_step=0.0020, lat_step=0.0012,
    jitter=0.00010
)

# ===================================================================
# ALLE STRASSEN ZUSAMMEN (Fallback-Gitter)
# ===================================================================
_FALLBACK_STREETS = (
    WESTERLAND_STREETS + WESTERLAND_OUTER +
    LIST_STREETS + KAMPEN_STREETS + WENNINGSTEDT_STREETS +
    TINNUM_STREETS + KEITUM_STREETS + MORSUM_STREETS +
    RANTUM_STREETS + HOERNUM_STREETS + MUNKMARSCH_STREETS +
    BRADERUP_STREETS + ARCHSUM_STREETS
)

# ===================================================================
# OSM-CACHE: Echte Straßen verwenden wenn vorhanden
# Erzeuge mit: python download_osm_streets.py
# ===================================================================
_osm_cache = os.path.join(_dir, 'osm_streets_cache.json')
USE_REAL_OSM = os.path.exists(_osm_cache)

if USE_REAL_OSM:
    with open(_osm_cache) as _f:
        _osm = json.load(_f)
    OSM_MAJOR = [[tuple(p) for p in s] for s in _osm.get("major", [])]
    OSM_MEDIUM = [[tuple(p) for p in s] for s in _osm.get("medium", [])]
    OSM_MINOR = [[tuple(p) for p in s] for s in _osm.get("minor", [])]
    ALL_MINOR_STREETS = OSM_MAJOR + OSM_MEDIUM + OSM_MINOR
    _source = "OSM-Cache (echte Daten)"
else:
    OSM_MAJOR = []
    OSM_MEDIUM = []
    OSM_MINOR = []
    ALL_MINOR_STREETS = _FALLBACK_STREETS
    _source = "Fallback-Gitter (generiert)"

# === ORTSNAMEN ===
PLACES = {
    "List":         (8.3900, 55.0070),
    "Kampen":       (8.3420, 54.9540),
    "Wenningstedt": (8.3160, 54.9185),
    "Westerland":   (8.2980, 54.9060),
    "Tinnum":       (8.3330, 54.9000),
    "Keitum":       (8.3610, 54.8920),
    "Archsum":      (8.3730, 54.8870),
    "Morsum":       (8.4120, 54.8750),
    "Munkmarsch":   (8.3500, 54.9100),
    "Braderup":     (8.3580, 54.9400),
    "Rantum":       (8.2980, 54.8570),
    "Hörnum":       (8.2920, 54.7640),
}

# Statistik
print(f"Straßennetz [{_source}]: {len(ALL_MINOR_STREETS)} Segmente, "
      f"Küste: {len(COASTLINE)} Punkte")
