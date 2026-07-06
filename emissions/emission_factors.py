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
