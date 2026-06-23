# Bordeaux Urban Digital Twin — Data Model & Domain Relationships

**Project:** Bordeaux Urban Digital Twin  
**Author:** Sahar Adami Kozekonan  
**Date:** June 2026

---

## Entity Registry

### Layer 1 — Static Reference

| Entity | Source Datasets | PK | Geometry |
|--------|----------------|-----|----------|
| RoadSegment | ci_trafi_l, OSM | road_id | LINESTRING |
| TransitLine | sv_chem_l | line_id | LINESTRING |
| TransitSegment | sv_tronc_l | segment_id | LINESTRING |
| TransitStop | sv_arret_p | stop_id | POINT |
| ParkingFacility | st_park_p | parking_id | POINT |
| BikeStation | ci_vcub_p | station_id | POINT |
| Building | DVF, DPE | building_id | POLYGON |
| SolarRooftop | eg_cada_solaire_s | rooftop_id | POLYGON |
| HeatNetworkPipe | eg_reseau_chaleur_l | pipe_id | LINESTRING |
| PhotovoltaicSite | eg_equipement_photovoltaique_s | pv_id | POLYGON |
| Sensor | pc_capte_p, rt_ondeelectro_p, pc_captp_p | sensor_id | POINT |
| PopulationZone | se_iri24_s | iris_code | POLYGON |
| GreenSpace | env_treecover_1 | space_id | POLYGON |
| WaterBody | to_hydro_s, water_wfd_centrelines_1 | water_id | POLYGON/LINE |
| FloodZone | georisques_azi | zone_id | POLYGON |
| IndustrialSite | env_industrial_1 | site_id | POINT |
| ProtectedWaterArea | water_wfd_protected_1, env_wfd_protected_1 | area_id | POLYGON |

---

### Layer 2 — Time-Series (TimescaleDB hypertables)

| Entity | Source Datasets | Partition Key | FK |
|--------|----------------|--------------|-----|
| TrafficMeasure | ci_trafi_l, pc_capte_p, pc_capte_ponct_p, ci_courb_a | timestamp | road_id, sensor_id |
| TravelTime | ci_tpstj_a | timestamp | road_id |
| VehiclePosition | sv_cours_a, sv_vehic_p | timestamp | line_id |
| ParkingOccupancy | parkings-donnees-techniques-2026 | timestamp | parking_id |
| BikeAvailability | ci_vcub_p | timestamp | station_id |
| WeatherRecord | wh_forecast_1, wh_hist_1, cl_era5land_1, cl_era5_1 | timestamp | iris_code |
| AirQualityMeasure | gir_polluant_jour_1, atmo_mesures_jour_1 | timestamp | sensor_id, iris_code |
| WaterRecord | water_vigicrues_garonne_1, water_vigicrues_alert_1 | timestamp | sensor_id |
| EnergyConsumption | eg_poste_monitore_quartier_a, bilan-electrique-demi-heure-en-jplus4 | timestamp | iris_code |
| GridCarbonIntensity | part-enr-intensite-ges-conso-tr | timestamp | — |
| GasConsumption | conso-jour-nat-eldgrd-grt, igrm-dep | timestamp | — |
| RiverDischargeForecast | cl_riverdischarge_1 | timestamp | water_id |

---

### Layer 3 — Aggregated / Static Statistics

| Entity | Source Datasets | Granularity |
|--------|----------------|-------------|
| PopulationStats | evolution-et-structure, historique-populations, pop_filosofi_1 | iris_code, year |
| PopulationGrid | population-bordeaux-donnees-carroyees | 200m grid cell |
| AirQualityModel | atmo_model_pm10_1, aq_interp_series_1, aq_pm10_interp_1 | grid, year |
| EmissionsInventory | bor_inventaire_polluants_1, env_ghg_1, mob_emissions_1 | territory, year |
| TreeCoverDensity | env_treecover_1 | polygon, year |
| LandTransaction | demande-de-valeurs-foncieres | point, date |
| EnergyFacility | registre-national-installation-production-stockage | iris_code |
| HealthImpact | aq_health_burden_1 | NUTS region, year |
| NaturalDisaster | georisques_catnat | commune, year |
| BathingWaterQuality | water_bathing_1 | point, year |
| ClimateProjection | wh_climate_1 | grid, decade |
| SeasonalForecast | wh_seasonal_1, cl_riverdischarge_1 | point, month |
| GHGConcentration | cl_co2_1, cl_ch4_1 | grid, day |

---

### Layer 4 — Junction / Relation Tables

| Entity | Source Datasets | Links |
|--------|----------------|-------|
| TransitLineStop | sv_arret_p_sv_lipub_a | TransitLine ↔ TransitStop |
| TerminalStop | sv_bornesae_a_sv_arret_p | Terminal ↔ TransitStop |
| TransitDiversion | sv_devia_l, sv_tronc_devia_l | TransitLine ↔ RoadSegment |

---

## Domain Relationships

### 1. Mobility ↔ Mobility (Internal)

#### P1 — Core

**1.1 TrafficMeasure → TravelTime**
- `ci_trafi_l` + `pc_capte_p` + `pc_capte_ponct_p` → `ci_tpstj_a`
- vehicle_count + avg_speed → congestion_index → travel_time_s
- Join: road_id

**1.2 ParkingOccupancy ↔ TrafficMeasure**
- `parkings-donnees-techniques-2026` ↔ `ci_trafi_l`
- High occupancy → cruising traffic around facility
- Join: spatial (parking geometry WITHIN 500m of road_id)

**1.3 BikeAvailability ↔ TrafficMeasure**
- `ci_vcub_p` ↔ `ci_trafi_l`
- Low bike availability + high congestion → modal shift to private car
- Join: spatial (station geometry WITHIN 500m of road_id)

**1.4 VehiclePosition ↔ TrafficMeasure**
- `sv_vehic_p` + `sv_cours_a` ↔ `ci_trafi_l`
- SAEIV delays → increased private vehicle use on same corridor
- Join: TransitLine geometry OVERLAPS RoadSegment geometry

**1.5 TrafficMeasure → TrafficCurve**
- `pc_capte_p` → `ci_courb_a`
- Aggregated counts by day type → reference traffic curve
- Join: road_id, day_type

**1.6 TransitStop → TrafficMeasure**
- `sv_arret_p` ↔ `ci_trafi_l`
- Stop locations near intersections → local congestion impact
- Join: spatial (stop WITHIN 100m of road segment)

**1.7 RoadTopology → TravelTime**
- `sv_tronc_l` + `sv_chem_l` → `ci_tpstj_a`
- Network topology defines routing and travel time calculation
- Join: segment_id → road_id

#### P2 — Important

**1.8 TransitDiversion → TrafficMeasure**
- `sv_devia_l` + `sv_tronc_devia_l` → `ci_trafi_l`
- Planned/emergency diversions → traffic spike on alternative roads

**1.9 FleetEmissions → TrafficMeasure**
- `mob_emissions_1` ↔ `ci_trafi_l`
- Traffic volume → CO2 fleet emission estimation

#### P3 — Future

| Relationship | Datasets | Note |
|---|---|---|
| TerminalStop → StopAccessibility | sv_bornesae_a_sv_arret_p | Passenger info terminal coverage |
| StopPublicPlace → Accessibility | sv_arret_p_sv_lipub_a | Stop proximity to amenities |

---

### 2. Mobility ↔ Weather

#### P1 — Core

**2.1 WeatherRecord → TrafficMeasure**
- `wh_forecast_1` + `wh_hist_1` → `ci_trafi_l`
- Rain → speed reduction, accident increase → congestion
- Fog/ice → visibility reduction → slowdown
- Join: iris_code (spatial), timestamp

**2.2 WeatherRecord → BikeAvailability**
- `wh_forecast_1` → `ci_vcub_p`
- High temperature + no rain → more bike usage
- Join: timestamp

**2.3 WeatherRecord → TravelTime**
- `wh_forecast_1` → `ci_tpstj_a`
- Adverse weather → increased travel time on all corridors
- Join: timestamp

#### P2 — Important

**2.4 WeatherRecord → ParkingOccupancy**
- `wh_forecast_1` → `parkings-donnees-techniques-2026`
- Heavy rain → covered parking facilities fill faster

**2.5 WeatherRecord → VehiclePosition**
- `wh_forecast_1` → `sv_vehic_p`
- Strong wind → SAEIV tram delays

#### P3 — Future

| Relationship | Note |
|---|---|
| SeasonalForecast → TransportDemand | Long-term mobility planning |
| ClimateProjection → InfrastructureRisk | Road vulnerability to climate change |

---

### 3. Mobility ↔ AirQuality

#### P1 — Core

**3.1 TrafficMeasure → AirQualityMeasure**
- `ci_trafi_l` + `pc_capte_p` → `gir_polluant_jour_1` + `atmo_mesures_jour_1`
- Vehicle count → NO2, PM10, PM2.5 emissions
- Join: road_id → iris_code (spatial), timestamp

**3.2 TrafficMeasure → EmissionsInventory**
- `ci_trafi_l` → `bor_inventaire_polluants_1`
- Traffic volume × emission factor → territorial emissions
- Join: road_id → territory

#### P2 — Important

**3.3 FleetEmissions → AirQualityMeasure**
- `mob_emissions_1` → `gir_polluant_jour_1`
- Fleet composition (Euro standard) → emission factor per vehicle
- Join: year, territory

#### P3 — Future

| Relationship | Note |
|---|---|
| ElectricVehicleShare → AirQuality | As EV penetration increases, NOx decreases |

---

### 4. Mobility ↔ Population

#### P1 — Core

**4.1 PopulationZone → TrafficMeasure**
- `se_iri24_s` + `evolution-et-structure` → `ci_trafi_l`
- Population density → traffic generation rate
- Join: iris_code → road_id (spatial)

**4.2 PopulationGrid → BikeAvailability**
- `population-bordeaux-donnees-carroyees` → `ci_vcub_p`
- Population density at 200m → bike station demand
- Join: spatial (grid cell CONTAINS station)

#### P2 — Important

**4.3 PopulationStats → TransitStop**
- `evolution-et-structure` → `sv_arret_p`
- Socio-professional categories → PT usage patterns
- Join: iris_code → stop geometry

---

### 5. Mobility ↔ Sensors

#### P1 — Core

**5.1 Sensor → TrafficMeasure**
- `pc_capte_p` + `pc_capte_ponct_p` → TrafficMeasure
- Physical sensor location → measurement point
- Join: sensor_id (direct FK)

**5.2 Sensor → PedestrianFlow**
- `pc_captp_p` → pedestrian count data
- 4G pedestrian sensors → foot traffic measurement
- Join: sensor_id, iris_code

---

### 6. Mobility ↔ Online DataSet

#### P1 — Core

**6.1 Online TrafficCurve → TrafficMeasure**
- `ci_courb_a` feeds TrafficMeasure as real-time reference
- Join: road_id, timestamp

**6.2 Online TravelTime → TravelTime**
- `ci_tpstj_a` is the real-time source for TravelTime entity
- Join: road_id, timestamp

**6.3 Online BikeStation → BikeAvailability**
- `ci_vcub_p` is the real-time source for BikeAvailability entity
- Join: station_id, timestamp

**6.4 GTFS-RT → VehiclePosition**
- `offres-de-services-bus-tramway-gtfs` real-time feed → VehiclePosition
- Join: vehicle_id, line_id, timestamp

---

### 7. Weather ↔ AirQuality

#### P1 — Core

**7.1 WeatherRecord → AirQualityMeasure**
- `wh_forecast_1` + `wh_hist_1` → `gir_polluant_jour_1` + `atmo_mesures_jour_1`
- Wind speed/direction → pollutant dispersion or concentration
- Temperature inversion → PM trapping near ground
- Join: iris_code, timestamp

**7.2 WeatherRecord → AirQualityModel**
- `cl_era5_1` + `cl_era5land_1` → `atmo_model_pm10_1`
- Meteorological inputs to air quality dispersion model
- Join: grid cell, timestamp

**7.3 GHGConcentration ↔ WeatherRecord**
- `cl_co2_1` + `cl_ch4_1` ↔ `wh_climate_1`
- Atmospheric GHG concentration → radiative forcing → temperature change
- Join: grid cell, date

---

### 8. Weather ↔ Water

#### P1 — Core

**8.1 WeatherRecord → WaterRecord**
- `wh_forecast_1` + `cl_era5land_1` → `water_vigicrues_garonne_1`
- Precipitation upstream → Garonne river level rise → flood alert
- Join: timestamp (lag 6-48h for upstream propagation)

**8.2 RiverDischargeForecast → WaterRecord**
- `cl_riverdischarge_1` → `water_vigicrues_garonne_1`
- Seasonal discharge forecast → anticipate flood risk
- Join: water_id, timestamp

**8.3 WeatherRecord → FloodZone**
- `wh_forecast_1` → `georisques_azi`
- Precipitation intensity → activation of flood zones
- Join: iris_code → zone_id (spatial)

---

### 9. Weather ↔ Energy

#### P1 — Core

**9.1 WeatherRecord → EnergyConsumption**
- `wh_forecast_1` + `wh_hist_1` → `eg_poste_monitore_quartier_a`
- Temperature → heating/cooling demand
- Solar radiation → PV production
- Join: iris_code, timestamp

**9.2 WeatherRecord → GridCarbonIntensity**
- `wh_forecast_1` → `part-enr-intensite-ges-conso-tr`
- Solar/wind conditions → renewable share → carbon intensity
- Join: timestamp

**9.3 WeatherRecord → SolarRooftop**
- `wh_hist_1` → `eg_cada_solaire_s`
- Historical irradiation → actual vs potential PV production
- Join: iris_code → rooftop geometry (spatial)

---

### 10. AirQuality ↔ Population

#### P1 — Core

**10.1 AirQualityMeasure → HealthImpact**
- `gir_polluant_jour_1` + `atmo_mesures_jour_1` → `aq_health_burden_1`
- PM2.5, NO2, O3 exposure → DALYs, premature deaths
- Join: iris_code, year

**10.2 AirQualityModel → PopulationZone**
- `atmo_model_pm10_1` + `aq_interp_series_1` → `se_iri24_s`
- Gridded AQ model → population exposure mapping
- Join: spatial (grid cell INTERSECTS iris polygon)

**10.3 PopulationStats → AirQualityMeasure**
- `pop_filosofi_1` → `gir_polluant_jour_1`
- Median income → environmental justice analysis
- Join: iris_code

---

### 11. AirQuality ↔ Environment

#### P1 — Core

**11.1 TreeCoverDensity → AirQualityMeasure**
- `env_treecover_1` → `gir_polluant_jour_1`
- Urban tree canopy → PM absorption, CO2 sequestration
- Join: spatial (tree cover polygon INTERSECTS iris)

**11.2 IndustrialSite → EmissionsInventory**
- `env_industrial_1` → `bor_inventaire_polluants_1`
- Industrial point sources → territorial emission contribution
- Join: site_id → territory (spatial)

**11.3 EmissionsInventory → AirQualityMeasure**
- `bor_inventaire_polluants_1` + `env_ghg_1` → `gir_polluant_jour_1`
- Source inventory → background concentration
- Join: territory, year

---

### 12. Water ↔ Environment

#### P1 — Core

**12.1 WaterBody → ProtectedWaterArea**
- `to_hydro_s` + `water_wfd_centrelines_1` → `water_wfd_protected_1` + `env_wfd_protected_1`
- River/canal geometry → designated protection zones
- Join: spatial (water body INTERSECTS protected area)

**12.2 WeatherRecord → WaterBody**
- `cl_era5land_1` → `to_hydro_s`
- Soil moisture, runoff → hydrographic network dynamics
- Join: spatial, timestamp

**12.3 FloodZone → GreenSpace**
- `georisques_azi` → `env_treecover_1`
- Flood zones × green infrastructure → natural water retention
- Join: spatial (flood zone INTERSECTS green space)

**12.4 NaturalDisaster → FloodZone**
- `georisques_catnat` → `georisques_azi`
- Historical disaster events → flood zone validation
- Join: commune_code, year

---

### 13. Energy ↔ Buildings

#### P1 — Core

**13.1 Building → EnergyConsumption**
- DVF + DPE → `eg_poste_monitore_quartier_a`
- DPE class + surface → heating/cooling energy demand
- Join: building_id → iris_code (spatial aggregation)

**13.2 SolarRooftop → EnergyConsumption**
- `eg_cada_solaire_s` → `eg_poste_monitore_quartier_a`
- Rooftop PV potential → local production vs consumption balance
- Join: rooftop_id → iris_code (spatial)

**13.3 PhotovoltaicSite → EnergyFacility**
- `eg_equipement_photovoltaique_s` → `registre-national-installation`
- Public PV installations → national energy facility registry
- Join: pv_id → codeiris

**13.4 HeatNetworkPipe → Building**
- `eg_reseau_chaleur_l` → Building
- District heating pipe proximity → building connection eligibility
- Join: spatial (pipe WITHIN 50m of building)

---

### 14. Energy ↔ Population

#### P1 — Core

**14.1 PopulationZone → EnergyConsumption**
- `se_iri24_s` + `evolution-et-structure` → `eg_poste_monitore_quartier_a`
- Population density + household size → residential energy demand
- Join: iris_code

**14.2 PopulationStats → EnergyFacility**
- `pop_filosofi_1` → `registre-national-installation`
- Median income → PV adoption rate analysis
- Join: iris_code

**14.3 PopulationZone → RenewableGasIndicator**
- `se_iri24_s` → `igrm-dep`
- Population by département → gas consumption baseline
- Join: commune_code → code_officiel_departement=33

---

### 15. Buildings ↔ Population

#### P1 — Core

**15.1 Building → PopulationZone**
- DVF → `se_iri24_s`
- Building footprints located within IRIS zones
- Join: spatial (building WITHIN iris polygon)

**15.2 LandTransaction → PopulationStats**
- `demande-de-valeurs-foncieres` → `pop_filosofi_1`
- Real estate prices × median income → housing affordability
- Join: iris_code, year

**15.3 PopulationGrid → Building**
- `population-bordeaux-donnees-carroyees` → Building
- 200m grid population → building density validation
- Join: spatial (grid cell CONTAINS building centroid)

---

## P3 — Relationships for Future Development

| From | To | Datasets | Note |
|------|-----|----------|------|
| Mobility | Water | ci_trafi_l, georisques_azi | Flood → road closures |
| Mobility | Energy | ci_trafi_l, part-enr | EV charging demand spike |
| Mobility | Buildings | ci_trafi_l, DVF | Traffic noise → property value |
| Mobility | Environment | ci_trafi_l, env_treecover_1 | Traffic emissions → tree stress |
| Weather | Population | wh_forecast_1, se_iri24_s | Heat vulnerability by zone |
| Weather | Environment | cl_era5land_1, env_treecover_1 | Drought stress on urban trees |
| Water | Population | georisques_azi, se_iri24_s | Flood zone × population exposure |
| Water | Energy | water_vigicrues_garonne_1, eg_reseau_chaleur_l | Flood risk to energy infrastructure |
| AirQuality | Water | aq_interp_series_1, water_wfd_protected_1 | Air deposition on water bodies |
| AirQuality | Buildings | gir_polluant_jour_1, DVF | Air quality → property values |
| Environment | Population | env_treecover_1, pop_filosofi_1 | Green space access × income |
| Environment | Energy | env_treecover_1, eg_cada_solaire_s | Tree shading → solar potential reduction |
| Sensors | Online | pc_capte_p, ci_courb_a | Sensor network feeds online datasets |
| Sensors | Population | pc_captp_p, se_iri24_s | Pedestrian flow × population zone |

---

## Summary

| Layer | Entities | Source Datasets |
|-------|----------|----------------|
| Static Reference | 17 | 28 datasets |
| Time-Series | 12 | 22 datasets |
| Aggregated/Static Stats | 13 | 21 datasets |
| Junction Tables | 3 | 3 datasets |
| **Total** | **45** | **71 datasets** |

| Priority | Relationships | Description |
|----------|--------------|-------------|
| P1 | 35 | Core — implement in Phase 2 |
| P2 | 8 | Important — implement in Phase 3 |
| P3 | 14 | Future development |
| **Total** | **57** | |

