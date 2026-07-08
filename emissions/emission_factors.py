"""
Emission factors — Bordeaux Urban Digital Twin
Rule-Based, Proof-of-Concept coefficients (see emission_engine_spec.md). Not a
calibrated physical model: fixed speed, average fleet mix, 1 km per vehicle pass.

CO2 source (verified via web search, not from memory — see spec §4.1):
  EEA press release "Average CO2 emissions from new cars and new vans"
  https://www.eea.europa.eu/en/newsroom/news/average-co2-emissions-from-new-cars-and-new-vans
  EU-wide average for new passenger cars, 2024 (provisional, WLTP): 106.8 g CO2/km
  (106.4 g/km in 2023). A France-specific breakdown was not available without
  downloading the full EEA microdataset (`mob_emissions_1`), which is out of scope
  for this PoC phase (see spec §4.1) — so the EU-wide figure is used, as the spec
  explicitly allows. This is also a "new car" average (Type-Approval, WLTP), not
  the average of the actual circulating fleet (which typically runs higher, since
  older cars stay on the road) — flagged in the dashboard disclaimer too.

NOx / PM: still placeholders pending EEA/EMEP Guidebook Tier 1 verification
(spec §4.2/§4.3) — average mixed-EU-fleet exhaust figures, not sensor- or
zone-specific.
"""

EMISSION_FACTORS_G_PER_KM = {
    "CO2": 106.8,   # g/km — EEA, EU-wide average, new passenger cars, 2024 (provisional, WLTP)
    "NOx": 0.35,    # g/km — average mixed EU passenger car fleet, TODO verify vs EEA/EMEP Guidebook Tier 1
    "PM":  0.02,    # g/km — average mixed EU passenger car fleet (exhaust only), TODO verify
}

UNIT_DISTANCE_KM = 1.0  # assumed distance per vehicle pass at a sensor


def estimate_emissions(vehicle_count: float) -> dict:
    """Returns {"CO2": grams, "NOx": grams, "PM": grams} for one vehicle-count value."""
    return {
        pollutant: vehicle_count * factor * UNIT_DISTANCE_KM
        for pollutant, factor in EMISSION_FACTORS_G_PER_KM.items()
    }


# Bus source (verified via web search, not from memory):
#   EMEP/EEA air pollutant emission inventory guidebook 2023 (Update 2025),
#   https://www.eea.europa.eu/en/analysis/publications/emep-eea-guidebook-2023/part-b-sectoral-guidance-chapters/1-energy/1-a-combustion/1-a-3-b-i/@@download/file
#   Tables 3-23 (CO2/NOx) & 3-24 (PM), category "Urban Diesel Buses Standard
#   15-18 t" (a standard single-unit diesel city bus, matching TBM's fleet),
#   Euro V. Each figure is the average of the table's two listed sub-conditions
#   (COPERT speed bins). Euro V — not the newest Euro VI — is used as a realistic
#   mid-fleet-age representative, since TBM's actual Euro-class mix isn't
#   published and a real operating fleet mixes several vintages. Diesel buses
#   are much heavier per-km emitters than a passenger car — this is a separate
#   dict, never a substitute for EMISSION_FACTORS_G_PER_KM (car).
BUS_EMISSION_FACTORS_G_PER_KM = {
    "CO2": 726.5,   # g/km — avg(699.459, 753.461)
    "NOx": 7.39,    # g/km — avg(8.087, 6.692)
    "PM":  0.094,   # g/km — avg(0.151, 0.0364)
}


# Energy consumption (verified via web search, not from memory):
#
# Fuel -> energy conversion: EU Renewable Energy Directive (EU) 2018/2001,
# Annex III "Energy content of transport fuels" (fetched directly from the
# Official Journal text, CELEX:32018L2001) — FOSSIL FUELS table:
#   Petrol: 43 MJ/kg / 32 MJ/l    Diesel: 43 MJ/kg / 36 MJ/l
#
# Car: ODYSSEE-MURE (EU energy-efficiency monitoring project, co-funded by the
#   European Commission), "New cars specific consumption by country" —
#   EU27 average for new *thermal* (non-EV) cars, 2023: 5.6 l/100km
#   (https://www.odyssee-mure.eu/publications/efficiency-by-sector/transport/specific-consumption-new-cars-country.html).
#   Same "new vehicle, not full circulating fleet" caveat as EMISSION_FACTORS_G_PER_KM's
#   CO2 figure. Converted using the average of petrol/diesel energy content
#   (34 MJ/l) since "thermal" mixes both fuels and no EU-wide split was found:
#   0.056 l/km x 34 MJ/l = 1.904 MJ/km.
#
# Bus: urban diesel bus fuel consumption is consistently cited around
#   24-30 l/100km in independent industry sources (e.g. jv-technoton.com
#   eco-driving case study: 25-30 l/100km; a diesel bus at ~60 km/h average
#   speed: 24 l/100km) — midpoint 27 l/100km used. Cross-check: dividing our
#   own BUS_EMISSION_FACTORS_G_PER_KM["CO2"] (726.5 g/km, EEA/EMEP Guidebook)
#   by a standard diesel CO2 factor (~2.68 kg CO2/l) implies ~27.1 l/100km —
#   independent agreement with the web-sourced range, good consistency check.
#   27 l/100km x 36 MJ/l (diesel) = 9.72 MJ/km.
ENERGY_MJ_PER_KM = {
    "car": 1.90,   # MJ/km — 0.056 l/km (EU new thermal car avg, 2023) x 34 MJ/l
    "bus": 9.72,   # MJ/km — 0.27 l/km (urban diesel bus avg) x 36 MJ/l
}
