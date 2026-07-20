"""
Diagnostic script — Bordeaux Urban Digital Twin
Run this from the project root:

    python check_pages.py

It tries to import every page module one by one (without running Streamlit)
and reports exactly which ones fail and why. Copy the full output and send it.
"""

import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(__file__))

MODULES_TO_CHECK = [
    "app_pages.overview",
    "app_pages.catalog",
    "app_pages.data_models",
    "app_pages.ontology",
    "app_pages.tram_b",
    "app_pages.simulation",
    "app_pages.collectors_page",
    "app_pages.resources",
    "app_pages.data_model_ontology",
    "app_pages.city_dashboard",
    "app_pages.data_resources",
    "app_pages.map_matching",
]

print("=" * 70)
print("Checking each page module can be imported...")
print("=" * 70)

results = {}

for mod_name in MODULES_TO_CHECK:
    try:
        # Remove from cache if already imported, to get a clean check
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        __import__(mod_name)
        results[mod_name] = ("OK", None)
        print(f"✅ {mod_name}")
    except Exception as e:
        results[mod_name] = ("FAIL", traceback.format_exc())
        print(f"❌ {mod_name}  ->  {type(e).__name__}: {e}")

print("=" * 70)
failed = {k: v for k, v in results.items() if v[0] == "FAIL"}

if not failed:
    print("All modules imported successfully! The problem may be inside a")
    print("render() call itself (e.g. infinite loop) rather than at import time.")
    print("Try running the app now: python -m streamlit run app.py")
else:
    print(f"{len(failed)} module(s) failed to import:\n")
    for mod_name, (status, tb) in failed.items():
        print(f"\n--- {mod_name} ---")
        print(tb)

print("=" * 70)
print("Copy everything above (from the first ==== line) and send it back.")