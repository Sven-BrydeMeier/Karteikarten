"""
Master-Skript: Generiert alle 7 Sylt Street-Map-Art Karten.
"""
import subprocess, sys, os, time

SCRIPTS = [
    ("01_osmnx_sylt.py",       "OSMnx Style — Schwarz auf Weiß"),
    ("02_noir_sylt.py",        "Noir / maptoposter — Weiß auf Schwarz"),
    ("03_city_roads_sylt.py",  "city-roads / anvaka — Ultra-minimalistisch"),
    ("04_poster_sylt.py",      "Poster / map-posterizer — Dunkel mit Rahmen"),
    ("05_blueprint_sylt.py",   "Blueprint — Technische Zeichnung"),
    ("06_gold_sylt.py",        "Gold auf Schwarz — Luxus-Edition"),
    ("07_prettymaps_sylt.py",  "prettymaps — Aquarell-Style"),
]

script_dir = os.path.dirname(os.path.abspath(__file__))
results = []

for script, description in SCRIPTS:
    path = os.path.join(script_dir, script)
    print(f"\n{'='*60}")
    print(f" {description}")
    print(f" Script: {script}")
    print(f"{'='*60}")

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=120,
        )
        elapsed = time.time() - start
        if result.returncode == 0:
            print(result.stdout.strip())
            results.append((script, "OK", f"{elapsed:.1f}s"))
        else:
            print(f"FEHLER:\n{result.stderr[-300:]}")
            results.append((script, "FEHLER", result.stderr[-100:]))
    except subprocess.TimeoutExpired:
        results.append((script, "TIMEOUT", ">120s"))
    except Exception as e:
        results.append((script, "EXCEPTION", str(e)[:100]))

print(f"\n\n{'='*60}")
print(" ZUSAMMENFASSUNG")
print(f"{'='*60}")
for script, status, info in results:
    icon = "OK" if status == "OK" else "!!"
    print(f"  [{icon}] {script:30s} {info}")

output_dir = os.path.join(script_dir, "output")
if os.path.isdir(output_dir):
    files = sorted(os.listdir(output_dir))
    print(f"\nErzeugte Dateien ({len(files)}):")
    for f in files:
        size = os.path.getsize(os.path.join(output_dir, f))
        print(f"  {f} ({size/1024:.0f} KB)")
