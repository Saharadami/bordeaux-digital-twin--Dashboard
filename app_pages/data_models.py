import streamlit as st
import pandas as pd

DOMAIN_META = {
    "Mobility":       {"icon": "🚗", "color": "#e8593c"},
    "Weather":        {"icon": "🌤️", "color": "#3b8bd4"},
    "AirQuality":     {"icon": "🌬️", "color": "#1d9e75"},
    "Water":          {"icon": "💧", "color": "#0077b6"},
    "Energy":         {"icon": "⚡", "color": "#f4a261"},
    "Buildings":      {"icon": "🏢", "color": "#ba7517"},
    "Population":     {"icon": "👥", "color": "#9b59b6"},
    "Environment":    {"icon": "🌿", "color": "#3b6d11"},
    "Sensors":        {"icon": "📡", "color": "#e74c3c"},
    "Online DataSet": {"icon": "🌐", "color": "#c0392b"},
}

RELATIONS = [
    ("Mobility", "Mobility", "P1", 7,
     "Internal traffic network relationships",
     ["• Traffic sensors count vehicles and measure speed → congestion index per road segment",
      "• Congestion index feeds travel time on 16 metropolitan corridors",
      "• Parking occupancy influences surrounding road traffic (cruising effect)",
      "• Bike station availability creates modal shift: no bikes → more cars on road",
      "• SAEIV public transport delays push passengers to private vehicles",
      "• Transit stop locations near intersections create local congestion",
      "• Road network topology determines routing and travel time calculation"],
     ["ci_trafi_l", "pc_capte_p", "pc_capte_ponct_p", "ci_tpstj_a", "ci_courb_a", "parkings-donnees-techniques-2026", "ci_vcub_p", "sv_vehic_p", "sv_arret_p"],
     "road_id, sensor_id, station_id, timestamp"),

    ("Mobility", "Weather", "P1", 3,
     "Weather conditions directly affect traffic flow",
     ["• Rain → drivers slow down, accident risk increases, congestion rises",
      "• Fog or ice → visibility reduction → speed drops, especially on ring road",
      "• High temperatures → cycling uncomfortable → VCub usage drops → more cars"],
     ["wh_forecast_1", "wh_hist_1", "ci_trafi_l", "ci_tpstj_a", "ci_vcub_p"],
     "iris_code + timestamp"),

    ("Mobility", "AirQuality", "P1", 2,
     "Road traffic is the primary source of urban air pollution",
     ["• High traffic volume × vehicle fleet emission factors → NO2, PM10, PM2.5",
      "• Territorial emissions inventory built from traffic counts + fleet composition"],
     ["ci_trafi_l", "pc_capte_p", "mob_emissions_1", "gir_polluant_jour_1"],
     "road_id → iris_code (spatial aggregation) + year"),

    ("Mobility", "Population", "P1", 2,
     "Population density drives traffic generation",
     ["• Population density per IRIS → traffic generation rate on adjacent roads",
      "• 200m population grid → demand for bike stations (VCub placement optimization)"],
     ["se_iri24_s", "evolution-et-structure", "population-bordeaux-metropole-donnees-carroyees", "ci_trafi_l"],
     "iris_code → road_id (spatial join)"),

    ("Mobility", "Sensors", "P1", 2,
     "Sensors are the physical source of all traffic measurements",
     ["• Loop detectors (pc_capte_p) count vehicles and measure speed per road segment",
      "• 4G pedestrian counters (pc_captp_p) measure foot traffic at counting sites",
      "• Sensor entity = registry; TrafficMeasure = time-series output"],
     ["pc_capte_p", "pc_capte_ponct_p", "pc_captp_p", "ci_trafi_l"],
     "sensor_id (direct FK)"),

    ("Mobility", "Online DataSet", "P1", 4,
     "Online feeds are the real-time ingestion layer for mobility data",
     ["• Real-time traffic curve (ci_courb_a) → TrafficMeasure every 10 minutes",
      "• Real-time travel time (ci_tpstj_a) → TravelTime every 2.5 minutes",
      "• Real-time bike station (ci_vcub_p) → BikeAvailability every 2.5 minutes",
      "• GTFS-RT tram/bus feed → VehiclePosition continuously"],
     ["ci_courb_a", "ci_tpstj_a", "ci_vcub_p", "offres-de-services-bus-tramway-gtfs"],
     "road_id / station_id / vehicle_id + timestamp"),

    ("Weather", "Weather", "P1", 2,
     "ERA5 reanalysis feeds forecast models and seasonal predictions",
     ["• ERA5 reanalysis (cl_era5_1, cl_era5land_1) → historical ground truth → calibrates AROME forecast",
      "• ERA5-Land high-resolution reanalysis → feeds seasonal river discharge forecast model"],
     ["cl_era5_1", "cl_era5land_1", "wh_forecast_1", "wh_seasonal_1"],
     "grid cell + timestamp"),

    ("Weather", "AirQuality", "P1", 3,
     "Meteorological conditions control pollutant dispersion",
     ["• Wind speed/direction → transport and dilution of pollutants from sources",
      "• Temperature inversion → PM10 and NO2 accumulate near ground (winter episodes)",
      "• Meteorological fields are direct inputs to Atmo NA dispersion model"],
     ["wh_forecast_1", "cl_era5_1", "gir_polluant_jour_1", "atmo_mesures_jour_1", "atmo_model_pm10_1"],
     "iris_code + timestamp"),

    ("Weather", "Water", "P1", 3,
     "Precipitation drives Garonne river level and flood risk",
     ["• Upstream precipitation → river level rise at Bordeaux with 6-48 hour lag",
      "• Seasonal discharge forecasts built from ERA5-Land soil moisture and precipitation",
      "• Extreme precipitation → activation of flood zones (AZI atlas)"],
     ["wh_forecast_1", "cl_era5land_1", "cl_riverdischarge_1", "water_vigicrues_garonne_1", "georisques_azi"],
     "timestamp (upstream lag 6h to 48h)"),

    ("Weather", "Energy", "P1", 3,
     "Temperature and solar radiation drive energy demand and production",
     ["• Temperature → heating demand in winter, cooling in summer",
      "• Solar radiation (W/m²) → photovoltaic production on 391k rooftops",
      "• Wind conditions → wind power share → carbon intensity of electricity"],
     ["wh_forecast_1", "wh_hist_1", "eg_poste_monitore_quartier_a", "eg_cada_solaire_s", "part-enr-intensite-ges-conso-tr"],
     "iris_code + timestamp"),

    ("AirQuality", "Population", "P1", 3,
     "Air pollution causes health impacts and raises environmental justice concerns",
     ["• Long-term PM2.5 and NO2 exposure → premature deaths and DALYs",
      "• Gridded AQ model (1km) × IRIS population → exposure mapping per zone",
      "• Median income × pollution levels → environmental justice: lower income = higher exposure"],
     ["gir_polluant_jour_1", "atmo_model_pm10_1", "aq_health_burden_1", "se_iri24_s", "pop_filosofi_1"],
     "iris_code (spatial join grid → IRIS)"),

    ("AirQuality", "Environment", "P1", 3,
     "Urban trees absorb pollutants; industry emits them",
     ["• Urban tree canopy → absorbs PM particles and CO2, reduces ozone formation",
      "• Industrial point sources (IED/E-PRTR) → emit NOx, SO2, PM",
      "• Territorial emissions inventory aggregates all sectors → feeds AQ dispersion model"],
     ["env_treecover_1", "env_industrial_1", "bor_inventaire_polluants_1", "gir_polluant_jour_1"],
     "spatial join (polygon intersection) + territory_code"),

    ("Water", "Environment", "P1", 4,
     "Hydrographic network, flood zones and green infrastructure are deeply interlinked",
     ["• Water body geometry → defines WFD-protected areas for drinking water and nature",
      "• Precipitation + soil moisture → surface runoff → feeds hydrographic network",
      "• Flood zones intersect green spaces → forests and parks act as natural water retention",
      "• Historical natural disasters (CATNAT) validate flood zone extent and return periods"],
     ["to_hydro_s", "water_wfd_protected_1", "georisques_azi", "env_treecover_1", "georisques_catnat"],
     "spatial join (polygon intersection) + commune_code"),

    ("Energy", "Buildings", "P1", 4,
     "Building characteristics determine energy demand; rooftops enable solar production",
     ["• DPE energy class (A-G) + floor surface → residential heating/cooling demand",
      "• Solar cadastre (391k rooftop polygons) → annual PV production potential",
      "• Public PV installations (77 sites) → linked to national energy facility registry",
      "• District heating pipes → buildings within 50m are eligible for connection"],
     ["eg_cada_solaire_s", "eg_reseau_chaleur_l", "eg_equipement_photovoltaique_s", "demande-de-valeurs-foncieres"],
     "building_id → rooftop_id (spatial join) + iris_code"),

    ("Energy", "Population", "P1", 3,
     "Population density and income drive energy consumption patterns",
     ["• Population density per IRIS → residential energy consumption baseline",
      "• Median income (Filosofi) → PV adoption rate analysis",
      "• Population by département (code 33) → gas consumption baseline from GRDF"],
     ["se_iri24_s", "evolution-et-structure", "pop_filosofi_1", "eg_poste_monitore_quartier_a", "igrm-dep"],
     "iris_code + commune_code"),

    ("Buildings", "Population", "P1", 3,
     "Buildings define the spatial fabric in which population lives",
     ["• Every building footprint falls within an IRIS zone → spatial join links building to demographics",
      "• Real estate prices (DVF) × median income (Filosofi) → housing affordability index",
      "• 200m population grid × building footprints → validates building density estimates"],
     ["demande-de-valeurs-foncieres", "se_iri24_s", "pop_filosofi_1", "population-bordeaux-metropole-donnees-carroyees"],
     "iris_code (spatial containment join)"),

    ("Sensors", "AirQuality", "P1", 1,
     "AQ monitoring stations are physical sensors producing air quality measurements",
     ["• Each Atmo NA station: location (Point), sensor_type = 'aq', operational status",
      "• Station measurements (PM2.5, PM10, NO2, O3) → AirQualityMeasure time-series",
      "• Sensor entity = registry; AirQualityMeasure = time-series output"],
     ["atmo_mesures_jour_1", "gir_polluant_jour_1"],
     "sensor_id (direct FK: AirQualityMeasure → Sensor)"),

    ("Sensors", "Water", "P1", 1,
     "Vigicrues hydrological gauge is a physical sensor producing river level data",
     ["• Garonne station O972001001: sensor_type = 'hydro', Point geometry",
      "• Continuously produces river level (cm) and flow (m³/s) → WaterRecord time-series",
      "• Flood alert (green/yellow/orange/red) derived from measurement vs threshold"],
     ["water_vigicrues_garonne_1", "water_vigicrues_alert_1"],
     "sensor_id (direct FK: WaterRecord → Sensor)"),
]

P3_RELATIONS = [
    ("Mobility", "Water", "Flood events close roads and reroute traffic"),
    ("Mobility", "Energy", "EV charging demand creates grid load spikes"),
    ("Mobility", "Buildings", "Traffic noise levels affect property values"),
    ("Mobility", "Environment", "Vehicle emissions stress urban tree canopy"),
    ("Weather", "Population", "Heat vulnerability mapping by population zone"),
    ("Weather", "Environment", "Drought stress on urban trees and green spaces"),
    ("Weather", "Buildings", "Solar irradiation potential linked to DPE improvement"),
    ("Water", "Population", "Flood zone exposure × population density"),
    ("Water", "Energy", "Flood risk to energy infrastructure"),
    ("Water", "Buildings", "Flood damage risk to building stock"),
    ("AirQuality", "Water", "Atmospheric deposition of pollutants on water bodies"),
    ("AirQuality", "Buildings", "Air quality levels influence real estate values"),
    ("Environment", "Population", "Green space accessibility × socio-economic indicators"),
    ("Environment", "Energy", "Tree shading reduces rooftop solar potential"),
    ("Sensors", "Online DataSet", "Physical sensor network feeds real-time online datasets"),
    ("Sensors", "Population", "Pedestrian sensor flow × population zone demographics"),
]

ENTITY_DETAILS = {
    "RoadSegment":      {"layer":"Static","domain":"Mobility","description":"Road network topology — base geometry for traffic assignment and routing","sources":["ci_trafi_l","OSM"],"fields":[("road_id","VARCHAR(50)","PK","Unique road segment identifier"),("osm_id","BIGINT","","OpenStreetMap way ID"),("road_type","VARCHAR(30)","","motorway/primary/secondary/residential"),("speed_limit","INTEGER","","Speed limit km/h"),("length_m","FLOAT","","Segment length meters"),("lanes","INTEGER","","Number of lanes"),("geometry","GEOMETRY","PostGIS","LineString SRID 4326")]},
    "TransitLine":      {"layer":"Static","domain":"Mobility","description":"SAEIV tram and bus line geometry","sources":["sv_chem_l"],"fields":[("line_id","VARCHAR(50)","PK","Unique line identifier"),("line_name","VARCHAR(100)","","Line name"),("line_type","VARCHAR(20)","","tram/bus/BRT"),("operator","VARCHAR(50)","","TBM"),("geometry","GEOMETRY","PostGIS","LineString SRID 4326")]},
    "TransitSegment":   {"layer":"Static","domain":"Mobility","description":"Elementary sections of SAEIV routes","sources":["sv_tronc_l"],"fields":[("segment_id","VARCHAR(50)","PK","Unique segment identifier"),("line_id","VARCHAR(50)","FK → TransitLine","Parent line"),("road_id","VARCHAR(50)","FK → RoadSegment","Underlying road"),("sequence","INTEGER","","Order in line"),("geometry","GEOMETRY","PostGIS","LineString SRID 4326")]},
    "TransitStop":      {"layer":"Static","domain":"Mobility","description":"Physical stop locations on SAEIV network","sources":["sv_arret_p"],"fields":[("stop_id","VARCHAR(50)","PK","Unique stop identifier"),("stop_name","VARCHAR(100)","","Stop name"),("line_id","VARCHAR(50)","FK → TransitLine","Associated line"),("iris_code","VARCHAR(20)","FK → PopulationZone","IRIS zone"),("geometry","GEOMETRY","PostGIS","Point SRID 4326")]},
    "ParkingFacility":  {"layer":"Static","domain":"Mobility","description":"Off-street parking facilities","sources":["st_park_p"],"fields":[("parking_id","VARCHAR(50)","PK","Unique parking identifier"),("name","VARCHAR(100)","","Facility name"),("capacity","INTEGER","","Total spaces"),("type","VARCHAR(30)","","underground/surface/multi-storey"),("geometry","GEOMETRY","PostGIS","Point SRID 4326")]},
    "BikeStation":      {"layer":"Static","domain":"Mobility","description":"Le Vélo (VCub) bike sharing station","sources":["ci_vcub_p"],"fields":[("station_id","VARCHAR(50)","PK","VCub station identifier"),("name","VARCHAR(100)","","Station name"),("capacity","INTEGER","","Total docking racks"),("municipality","VARCHAR(50)","","Municipality"),("geometry","GEOMETRY","PostGIS","Point SRID 4326")]},
    "TrafficMeasure":   {"layer":"TimeSeries","domain":"Mobility","description":"Real-time and historical traffic measurements — EAV pattern per sensor per timestamp","sources":["ci_trafi_l","pc_capte_p","pc_capte_ponct_p","ci_courb_a"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("road_id","VARCHAR(50)","FK → RoadSegment","Road segment"),("sensor_id","VARCHAR(50)","FK → Sensor","Sensor"),("timestamp","TIMESTAMPTZ","TimescaleDB","Partition key"),("measurement_type","VARCHAR(20)","","flow/speed/state"),("vehicle_count","INTEGER","","Vehicles per interval"),("avg_speed_kmh","FLOAT","","Average speed km/h"),("congestion_level","VARCHAR(20)","","FLUID/SLOW/BLOCKED/UNKNOWN")]},
    "TravelTime":       {"layer":"TimeSeries","domain":"Mobility","description":"Real-time travel time on 16 routes — refreshed every 2.5 min","sources":["ci_tpstj_a"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("road_id","VARCHAR(50)","FK → RoadSegment","Route corridor"),("timestamp","TIMESTAMPTZ","TimescaleDB","Measurement timestamp"),("travel_time_s","INTEGER","","Actual travel time seconds"),("ref_time_s","INTEGER","","Free-flow reference seconds"),("route_name","VARCHAR(100)","","Route name")]},
    "VehiclePosition":  {"layer":"TimeSeries","domain":"Mobility","description":"Real-time SAEIV vehicle positions — GTFS-RT compatible","sources":["sv_vehic_p","sv_cours_a","offres-de-services-bus-tramway-gtfs"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("vehicle_id","VARCHAR(50)","","Vehicle identifier"),("line_id","VARCHAR(50)","FK → TransitLine","Line"),("timestamp","TIMESTAMPTZ","TimescaleDB","Position timestamp"),("lat","FLOAT","","Latitude WGS84"),("lon","FLOAT","","Longitude WGS84"),("delay_s","INTEGER","","Delay vs schedule seconds")]},
    "ParkingOccupancy": {"layer":"TimeSeries","domain":"Mobility","description":"Real-time parking occupancy — refreshed every 5 min","sources":["parkings-donnees-techniques-2026"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("parking_id","VARCHAR(50)","FK → ParkingFacility","Parking"),("timestamp","TIMESTAMPTZ","TimescaleDB","Measurement timestamp"),("available_spaces","INTEGER","","Free spaces"),("occupancy_pct","FLOAT","","Occupancy 0.0-1.0"),("status","VARCHAR(20)","","OPEN/FULL/CLOSED")]},
    "BikeAvailability": {"layer":"TimeSeries","domain":"Mobility","description":"Real-time bike availability — refreshed every 2.5 min","sources":["ci_vcub_p"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("station_id","VARCHAR(50)","FK → BikeStation","Station"),("timestamp","TIMESTAMPTZ","TimescaleDB","Measurement timestamp"),("bikes_available","INTEGER","","Available bikes"),("docks_available","INTEGER","","Free docking slots"),("status","VARCHAR(20)","","CONNECTED/MAINTENANCE")]},
    "WeatherRecord":    {"layer":"TimeSeries","domain":"Weather","description":"Hourly weather observations and forecasts — ERA5 + AROME + Open-Meteo","sources":["wh_forecast_1","wh_hist_1","cl_era5land_1","cl_era5_1"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("iris_code","VARCHAR(20)","FK → PopulationZone","Spatial reference"),("timestamp","TIMESTAMPTZ","TimescaleDB","Observation timestamp"),("record_type","VARCHAR(20)","","forecast/observation/reanalysis"),("temperature_c","FLOAT","","Air temperature °C"),("humidity_pct","FLOAT","","Relative humidity %"),("precipitation_mm","FLOAT","","Precipitation mm"),("wind_speed_ms","FLOAT","","Wind speed m/s"),("solar_rad_wm2","FLOAT","","Solar radiation W/m²")]},
    "RiverDischargeForecast":{"layer":"TimeSeries","domain":"Weather","description":"Seasonal river discharge forecasts — Garonne basin","sources":["cl_riverdischarge_1"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("water_id","VARCHAR(50)","FK → WaterBody","River"),("timestamp","TIMESTAMPTZ","TimescaleDB","Forecast timestamp"),("discharge_m3s","FLOAT","","Forecasted discharge m³/s"),("model_name","VARCHAR(50)","","Source climate model")]},
    "AirQualityMeasure":{"layer":"TimeSeries","domain":"AirQuality","description":"Daily air quality measurements from Atmo NA stations","sources":["gir_polluant_jour_1","atmo_mesures_jour_1"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("sensor_id","VARCHAR(50)","FK → Sensor","AQ station"),("iris_code","VARCHAR(20)","FK → PopulationZone","Spatial reference"),("timestamp","TIMESTAMPTZ","TimescaleDB","Measurement timestamp"),("pm25_ugm3","FLOAT","","PM2.5 µg/m³"),("pm10_ugm3","FLOAT","","PM10 µg/m³"),("no2_ugm3","FLOAT","","NO2 µg/m³"),("o3_ugm3","FLOAT","","O3 µg/m³"),("atmo_index","INTEGER","","ATMO index 1-10")]},
    "WaterRecord":      {"layer":"TimeSeries","domain":"Water","description":"Real-time Garonne river level — station O972001001","sources":["water_vigicrues_garonne_1","water_vigicrues_alert_1"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("sensor_id","VARCHAR(50)","FK → Sensor","Hydrological station"),("timestamp","TIMESTAMPTZ","TimescaleDB","Observation timestamp"),("river_level_cm","FLOAT","","Water level cm NGF"),("flow_m3s","FLOAT","","River flow m³/s"),("flood_alert","VARCHAR(10)","","green/yellow/orange/red")]},
    "EnergyConsumption":{"layer":"TimeSeries","domain":"Energy","description":"30-min electricity consumption and solar production — Enedis Bastide pilot","sources":["eg_poste_monitore_quartier_a","bilan-electrique-demi-heure-en-jplus4"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("iris_code","VARCHAR(20)","FK → PopulationZone","Spatial reference"),("timestamp","TIMESTAMPTZ","TimescaleDB","30-min interval start"),("consumption_kwh","FLOAT","","Electricity consumed kWh"),("solar_prod_kwh","FLOAT","","Solar production kWh"),("net_kwh","FLOAT","","Net = consumption − production")]},
    "GridCarbonIntensity":{"layer":"TimeSeries","domain":"Energy","description":"Hourly carbon intensity of French electricity grid — RTE eco2mix","sources":["part-enr-intensite-ges-conso-tr"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("timestamp","TIMESTAMPTZ","TimescaleDB","Hourly interval"),("carbon_gco2kwh","FLOAT","","Carbon intensity gCO2eq/kWh"),("renewable_pct","FLOAT","","Renewable share %")]},
    "GasConsumption":   {"layer":"TimeSeries","domain":"Energy","description":"Daily gas consumption — département level","sources":["conso-jour-nat-eldgrd-grt","igrm-dep"],"fields":[("id","BIGSERIAL","PK","Auto-increment"),("timestamp","TIMESTAMPTZ","TimescaleDB","Measurement timestamp"),("dept_code","VARCHAR(5)","","Département code — 33 for Gironde"),("consumption_gwh","FLOAT","","Gas consumption GWh"),("renewable_pct","FLOAT","","Renewable gas share %")]},
    "Sensor":           {"layer":"Static","domain":"Sensors","description":"Registry of all physical sensors — traffic, AQ, hydro, pedestrian, EM wave","sources":["pc_capte_p","rt_ondeelectro_p","pc_captp_p"],"fields":[("sensor_id","VARCHAR(50)","PK","Unique sensor identifier"),("sensor_type","VARCHAR(30)","","traffic/aq/hydro/em_wave/pedestrian"),("name","VARCHAR(100)","","Sensor name"),("road_id","VARCHAR(50)","FK → RoadSegment","Associated road"),("iris_code","VARCHAR(20)","FK → PopulationZone","Associated IRIS zone"),("status","VARCHAR(20)","","active/inactive/maintenance"),("geometry","GEOMETRY","PostGIS","Point SRID 4326")]},
    "PopulationZone":   {"layer":"Static","domain":"Population","description":"IRIS 2024 boundaries — primary spatial unit for all aggregations","sources":["se_iri24_s"],"fields":[("iris_code","VARCHAR(20)","PK","INSEE IRIS 2024 code"),("iris_name","VARCHAR(100)","","IRIS zone name"),("commune_code","VARCHAR(10)","","INSEE commune code"),("geometry","GEOMETRY","PostGIS","Polygon SRID 4326")]},
    "PopulationStats":  {"layer":"Aggregated","domain":"Population","description":"Census demographics and social indicators per IRIS","sources":["evolution-et-structure","historique-populations","pop_filosofi_1"],"fields":[("iris_code","VARCHAR(20)","FK → PopulationZone","IRIS reference"),("year","INTEGER","","Reference year"),("population","INTEGER","","Total residents"),("density_km2","FLOAT","","Density per km²"),("median_income","FLOAT","","Median household income €"),("poverty_rate","FLOAT","","Poverty rate %")]},
    "PopulationGrid":   {"layer":"Aggregated","domain":"Population","description":"Population at 200m grid resolution — 2015","sources":["population-bordeaux-metropole-donnees-carroyees"],"fields":[("cell_id","VARCHAR(50)","PK","Grid cell identifier"),("population","INTEGER","","Resident population"),("geometry","GEOMETRY","PostGIS","200m × 200m Polygon SRID 4326")]},
    "Building":         {"layer":"Static","domain":"Buildings","description":"Building footprints with DPE energy class","sources":["demande-de-valeurs-foncieres-geolocalisee-bordeaux-metropole"],"fields":[("building_id","VARCHAR(50)","PK","Unique building identifier"),("iris_code","VARCHAR(20)","FK → PopulationZone","IRIS zone"),("height_m","FLOAT","","Building height meters"),("dpe_class","CHAR(1)","","Energy class A-G"),("build_year","INTEGER","","Year of construction"),("surface_m2","FLOAT","","Floor surface m²"),("geometry","GEOMETRY","PostGIS","Polygon SRID 4326")]},
    "LandTransaction":  {"layer":"Aggregated","domain":"Buildings","description":"Geolocated real estate transactions — DVF 2014 to present","sources":["demande-de-valeurs-foncieres-geolocalisee-bordeaux-metropole"],"fields":[("transaction_id","VARCHAR(50)","PK","Unique transaction ID"),("iris_code","VARCHAR(20)","FK → PopulationZone","IRIS zone"),("date","DATE","","Transaction date"),("price_eur","FLOAT","","Price €"),("surface_m2","FLOAT","","Property surface m²"),("price_per_m2","FLOAT","","Price per m² €/m²"),("geometry","GEOMETRY","PostGIS","Point SRID 4326")]},
    "SolarRooftop":     {"layer":"Static","domain":"Energy","description":"Rooftop solar potential — 391k polygons","sources":["eg_cada_solaire_s"],"fields":[("rooftop_id","VARCHAR(50)","PK","Unique rooftop identifier"),("building_id","VARCHAR(50)","FK → Building","Associated building"),("area_m2","FLOAT","","Usable rooftop area m²"),("annual_kwh","FLOAT","","Estimated annual PV production kWh"),("geometry","GEOMETRY","PostGIS","Polygon SRID 4326")]},
    "HeatNetworkPipe":  {"layer":"Static","domain":"Energy","description":"Urban district heating network — 2463 segments","sources":["eg_reseau_chaleur_l"],"fields":[("pipe_id","VARCHAR(50)","PK","Unique pipe identifier"),("type","VARCHAR(30)","","primary/secondary/service"),("diameter","FLOAT","","Pipe diameter mm"),("geometry","GEOMETRY","PostGIS","LineString SRID 4326")]},
    "PhotovoltaicSite": {"layer":"Static","domain":"Energy","description":"Public PV installations — 77 sites","sources":["eg_equipement_photovoltaique_s"],"fields":[("pv_id","VARCHAR(50)","PK","Unique PV site identifier"),("iris_code","VARCHAR(20)","FK → PopulationZone","IRIS zone"),("capacity_kw","FLOAT","","Installed capacity kWp"),("install_year","INTEGER","","Year of installation"),("geometry","GEOMETRY","PostGIS","Polygon SRID 4326")]},
    "EnergyFacility":   {"layer":"Aggregated","domain":"Energy","description":"National electricity production and storage registry — 2025","sources":["registre-national-installation-production-stockage-electricite-agrege-311225"],"fields":[("facility_id","VARCHAR(50)","PK","Unique facility identifier"),("iris_code","VARCHAR(20)","FK → PopulationZone","IRIS zone"),("energy_source","VARCHAR(30)","","solar/wind/hydro/nuclear/gas"),("capacity_mw","FLOAT","","Installed capacity MW"),("comm_date","DATE","","Commissioning date")]},
    "WaterBody":        {"layer":"Static","domain":"Water","description":"Hydrographic network — rivers, canals, water surfaces","sources":["to_hydro_s","water_wfd_centrelines_1"],"fields":[("water_id","VARCHAR(50)","PK","Unique water body identifier"),("name","VARCHAR(100)","","Water body name"),("type","VARCHAR(30)","","river/canal/lake/estuary"),("geometry","GEOMETRY","PostGIS","Polygon or LineString SRID 4326")]},
    "FloodZone":        {"layer":"Static","domain":"Water","description":"Official flood risk zones — AZI — Garonne basin","sources":["georisques_azi"],"fields":[("zone_id","VARCHAR(50)","PK","Unique flood zone identifier"),("commune_code","VARCHAR(10)","","INSEE commune code"),("risk_level","VARCHAR(20)","","HIGH/MEDIUM/LOW"),("return_period_y","INTEGER","","Flood return period years"),("geometry","GEOMETRY","PostGIS","Polygon SRID 4326")]},
    "ProtectedWaterArea":{"layer":"Static","domain":"Water","description":"WFD protected areas — drinking water and bathing zones","sources":["water_wfd_protected_1"],"fields":[("area_id","VARCHAR(50)","PK","Unique area identifier"),("water_id","VARCHAR(50)","FK → WaterBody","Associated water body"),("protection_type","VARCHAR(30)","","drinking_water/bathing/nature"),("geometry","GEOMETRY","PostGIS","Polygon SRID 4326")]},
    "BathingWaterQuality":{"layer":"Aggregated","domain":"Water","description":"Annual bathing water quality — EU Directive","sources":["water_bathing_1"],"fields":[("site_id","VARCHAR(50)","PK","Bathing site identifier"),("year","INTEGER","","Assessment year"),("status","VARCHAR(20)","","Excellent/Good/Sufficient/Poor"),("geometry","GEOMETRY","PostGIS","Point SRID 4326")]},
    "NaturalDisaster":  {"layer":"Aggregated","domain":"Water","description":"Historical natural disaster decrees — CATNAT","sources":["georisques_catnat"],"fields":[("disaster_id","VARCHAR(50)","PK","Unique disaster record"),("commune_code","VARCHAR(10)","","INSEE commune code"),("disaster_type","VARCHAR(50)","","flood/storm/drought/earthquake"),("start_date","DATE","","Disaster start"),("end_date","DATE","","Disaster end")]},
    "GreenSpace":       {"layer":"Static","domain":"Environment","description":"Urban green infrastructure — Copernicus HRL Tree Cover","sources":["env_treecover_1"],"fields":[("space_id","SERIAL","PK","Auto-increment"),("space_type","VARCHAR(50)","","forest/park/garden/street_tree"),("canopy_pct","FLOAT","","Canopy coverage %"),("area_m2","FLOAT","","Area m²"),("geometry","GEOMETRY","PostGIS","Polygon SRID 4326")]},
    "IndustrialSite":   {"layer":"Static","domain":"Environment","description":"Industrial emission point sources — IED and E-PRTR","sources":["env_industrial_1"],"fields":[("site_id","VARCHAR(50)","PK","Unique site identifier"),("name","VARCHAR(100)","","Facility name"),("nace_code","VARCHAR(10)","","NACE activity code"),("geometry","GEOMETRY","PostGIS","Point SRID 4326")]},
    "EmissionsInventory":{"layer":"Aggregated","domain":"Environment","description":"Territorial pollutant emission inventory — all sectors — annual","sources":["bor_inventaire_polluants_1","env_ghg_1","mob_emissions_1"],"fields":[("territory_code","VARCHAR(20)","FK → PopulationZone","Spatial reference"),("year","INTEGER","","Reference year"),("sector","VARCHAR(50)","","transport/residential/industrial/agriculture"),("nox_tonnes","FLOAT","","NOx tonnes"),("pm10_tonnes","FLOAT","","PM10 tonnes"),("co2_tonnes","FLOAT","","CO2 equivalent tonnes")]},
    "TreeCoverDensity": {"layer":"Aggregated","domain":"Environment","description":"Urban tree canopy density — updated every 3 years","sources":["env_treecover_1"],"fields":[("cell_id","VARCHAR(50)","PK","Grid cell identifier"),("year","INTEGER","","Assessment year"),("canopy_pct","FLOAT","","Canopy cover 0-100 %"),("geometry","GEOMETRY","PostGIS","10m grid Polygon SRID 4326")]},
    "AirQualityModel":  {"layer":"Aggregated","domain":"AirQuality","description":"Gridded AQ dispersion model — PM10 annual mean 1km","sources":["atmo_model_pm10_1","aq_interp_series_1"],"fields":[("cell_id","VARCHAR(50)","PK","Grid cell identifier"),("year","INTEGER","","Modelling year"),("pm10_ugm3","FLOAT","","Annual mean PM10 µg/m³"),("pm25_ugm3","FLOAT","","Annual mean PM2.5 µg/m³"),("no2_ugm3","FLOAT","","Annual mean NO2 µg/m³"),("geometry","GEOMETRY","PostGIS","1km grid Polygon SRID 4326")]},
    "HealthImpact":     {"layer":"Aggregated","domain":"AirQuality","description":"Burden of disease from air pollution — DALYs and premature deaths","sources":["aq_health_burden_1"],"fields":[("region_code","VARCHAR(20)","","NUTS region code"),("year","INTEGER","","Reference year"),("pollutant","VARCHAR(20)","","PM25/NO2/O3"),("dalys","FLOAT","","DALYs lost"),("premature_deaths","INTEGER","","Premature deaths")]},
    "ClimateProjection":{"layer":"Aggregated","domain":"Weather","description":"Long-term climate projections — CMIP6 2015-2100","sources":["wh_climate_1"],"fields":[("cell_id","VARCHAR(50)","PK","Grid cell identifier"),("scenario","VARCHAR(20)","","SSP1/SSP2/SSP5"),("decade","INTEGER","","Reference decade"),("temp_delta_c","FLOAT","","Temperature change °C"),("precip_delta_pct","FLOAT","","Precipitation change %")]},
    "SeasonalForecast": {"layer":"Aggregated","domain":"Weather","description":"Multi-model seasonal forecasts — 6-month horizon","sources":["wh_seasonal_1","cl_riverdischarge_1"],"fields":[("forecast_id","VARCHAR(50)","PK","Unique forecast identifier"),("water_id","VARCHAR(50)","FK → WaterBody","River reference"),("issue_date","DATE","","Forecast issue date"),("valid_month","INTEGER","","Target month"),("discharge_m3s","FLOAT","","Forecasted discharge m³/s")]},
    "GHGConcentration": {"layer":"Aggregated","domain":"Weather","description":"Atmospheric GHG from satellite — CO2 and CH4","sources":["cl_co2_1","cl_ch4_1"],"fields":[("cell_id","VARCHAR(50)","PK","Grid cell identifier"),("date","DATE","","Observation date"),("co2_ppm","FLOAT","","CO2 ppm"),("ch4_ppb","FLOAT","","CH4 ppb")]},
    "TransitLineStop":  {"layer":"Junction","domain":"Mobility","description":"Links transit stops to nearby public places","sources":["sv_arret_p_sv_lipub_a"],"fields":[("stop_id","VARCHAR(50)","FK → TransitStop","Stop reference"),("place_id","VARCHAR(50)","","Public place identifier"),("distance_m","FLOAT","","Distance meters")]},
    "TerminalStop":     {"layer":"Junction","domain":"Mobility","description":"Links passenger info terminals to transit stops","sources":["sv_bornesae_a_sv_arret_p"],"fields":[("terminal_id","VARCHAR(50)","","Terminal identifier"),("stop_id","VARCHAR(50)","FK → TransitStop","Associated stop")]},
    "TransitDiversion": {"layer":"Junction","domain":"Mobility","description":"Links SAEIV diversions to affected road segments","sources":["sv_devia_l","sv_tronc_devia_l"],"fields":[("diversion_id","VARCHAR(50)","PK","Unique diversion identifier"),("line_id","VARCHAR(50)","FK → TransitLine","Affected line"),("road_id","VARCHAR(50)","FK → RoadSegment","Alternative road"),("start_date","DATE","","Start date"),("end_date","DATE","","End date"),("type","VARCHAR(20)","","planned/emergency")]},
}

LAYER_COLORS = {"Static":"#3498db","TimeSeries":"#e74c3c","Aggregated":"#f39c12","Junction":"#95a5a6"}
LAYER_LABELS = {"Static":"Static Reference","TimeSeries":"Time-Series","Aggregated":"Aggregated / Stats","Junction":"Junction Tables"}


def show_relation_detail(f, t):
    rel = next((r for r in RELATIONS if (r[0]==f and r[1]==t) or (r[0]==t and r[1]==f)), None)
    if not rel:
        return
    f2, t2, p, count, short, bullets, datasets, join = rel
    fM = DOMAIN_META.get(f2, {"color":"#888","icon":"📂"})
    tM = DOMAIN_META.get(t2, {"color":"#888","icon":"📂"})
    isSelf = f2 == t2
    border = fM["color"] if isSelf else tM["color"]

    st.markdown(
        f"<div style='border-left:4px solid {border};padding-left:14px;margin-bottom:10px;'>"
        f"<strong style='font-size:15px'>{fM['icon']} {f2} "
        f"{'↔ (internal)' if isSelf else '→ '+tM['icon']+' '+t2}</strong>"
        f"<span style='background:#e8f5e9;color:#2e7d32;font-size:10px;font-weight:bold;"
        f"padding:2px 8px;border-radius:10px;margin-left:8px;'>P1 · {count} relations</span>"
        f"</div>",
        unsafe_allow_html=True
    )
    st.caption(f"*{short}*")
    for b in bullets:
        st.markdown(f"&nbsp;&nbsp;{b}")
    st.markdown(f"**Datasets:** " + " · ".join([f"`{d}`" for d in datasets]))
    st.markdown(f"**Join key:** `{join}`")


def render_matrix():
    domains = list(DOMAIN_META.keys())
    st.caption("Click a **P1** button to see the full relationship explanation below")

    if "selected_pair" not in st.session_state:
        st.session_state["selected_pair"] = None

    cols = st.columns([2] + [1]*len(domains))
    with cols[0]:
        st.markdown("")
    for i, d in enumerate(domains):
        meta = DOMAIN_META[d]
        with cols[i+1]:
            st.markdown(
                f"<div style='writing-mode:vertical-rl;color:{meta['color']};font-size:10px;"
                f"font-weight:bold;padding:4px 2px;'>{meta['icon']}{d[:7]}</div>",
                unsafe_allow_html=True
            )

    for d1 in domains:
        row = st.columns([2] + [1]*len(domains))
        meta1 = DOMAIN_META[d1]
        with row[0]:
            st.markdown(
                f"<span style='color:{meta1['color']};font-weight:bold;font-size:11px;'>"
                f"{meta1['icon']} {d1}</span>",
                unsafe_allow_html=True
            )
        for j, d2 in enumerate(domains):
            p1 = next((count for f,t,p,count,*_ in RELATIONS
                       if p=="P1" and ((f==d1 and t==d2) or (f==d2 and t==d1))), 0)
            p3 = next((1 for f,t,_ in P3_RELATIONS
                       if (f==d1 and t==d2) or (f==d2 and t==d1)), 0)
            with row[j+1]:
                if d1 == d2:
                    p1_self = next((count for f,t,p,count,*_ in RELATIONS
                                    if p=="P1" and f==d1 and t==d1), 0)
                    if p1_self > 0:
                        if st.button(f"P1·{p1_self}", key=f"m_{d1}_{d2}",
                                     use_container_width=True, type="primary"):
                            st.session_state["selected_pair"] = (d1, d2)
                    else:
                        st.markdown("<div style='text-align:center;color:#ccc;'>—</div>",
                                    unsafe_allow_html=True)
                elif p1 > 0:
                    if st.button(f"P1·{p1}", key=f"m_{d1}_{d2}",
                                 use_container_width=True):
                        st.session_state["selected_pair"] = (d1, d2)
                elif p3 > 0:
                    st.markdown("<div style='text-align:center;color:#f57f17;"
                                "font-size:10px;'>P3</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='text-align:center;color:#eee;'>·</div>",
                                unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("🟩 **P1·N** Core · 🟦 **P1·N** Internal · 🟨 **P3** Future · · No relationship")

    pair = st.session_state.get("selected_pair")
    if pair:
        st.divider()
        show_relation_detail(pair[0], pair[1])


def render_entities():
    col1, col2 = st.columns(2)
    with col1:
        layer_filter = st.selectbox("Filter by layer",
                                    ["All"] + list(LAYER_LABELS.keys()),
                                    key="ent_layer")
    with col2:
        domain_filter = st.selectbox("Filter by domain",
                                     ["All"] + list(DOMAIN_META.keys()),
                                     key="ent_domain")
    st.divider()
    count = 0
    for entity_name, meta in ENTITY_DETAILS.items():
        if layer_filter != "All" and meta.get("layer") != layer_filter:
            continue
        if domain_filter != "All" and meta.get("domain") != domain_filter:
            continue
        count += 1
        layer = meta.get("layer", "")
        lc = LAYER_COLORS.get(layer, "#888")
        ll = LAYER_LABELS.get(layer, layer)
        domain = meta.get("domain", "")
        dm = DOMAIN_META.get(domain, {"color":"#888","icon":"📂"})

        st.markdown(
            f"<div style='border-left:4px solid {lc};padding-left:12px;margin-bottom:4px;'>"
            f"<strong style='font-size:15px'>{entity_name}</strong>"
            f"<span style='font-size:11px;color:{lc};background:{lc}18;"
            f"padding:2px 8px;border-radius:10px;margin-left:8px;'>{ll}</span>"
            f"<span style='font-size:11px;color:{dm['color']};margin-left:6px;'>"
            f"{dm['icon']} {domain}</span></div>",
            unsafe_allow_html=True
        )
        if meta.get("description"):
            st.caption(meta["description"])
        if meta.get("sources"):
            st.caption("**Sources:** " + " · ".join(f"`{s}`" for s in meta["sources"]))

        rows = []
        for fname, ftype, flag, desc in meta.get("fields", []):
            if flag == "PK":            label = f"🔑 {fname}"
            elif "FK" in flag:          label = f"🔗 {fname}"
            elif flag == "PostGIS":     label = f"📐 {fname}"
            elif flag == "TimescaleDB": label = f"⏱️ {fname}"
            else:                       label = fname
            rows.append({"Field": label, "Type": ftype, "Note": flag, "Description": desc})

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown("---")

    if count == 0:
        st.info("No entities match the selected filters.")


def render():
    tab1, tab2 = st.tabs(["📊 Relation Matrix", "📋 Entity Details"])
    with tab1:
        render_matrix()
    with tab2:
        render_entities()