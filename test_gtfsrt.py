"""
Test GTFS-RT VehiclePositions feed for Tram B.
Run: python test_gtfsrt.py
"""
import requests

GTFS_RT_URL = (
    "https://bdx.mecatran.com/utw/ws/gtfsfeed/vehicles/bordeaux"
    "?apiKey=opendata-bordeaux-metropole-flux-gtfs-rt"
)

try:
    from google.transit import gtfs_realtime_pb2
except ImportError:
    print("Missing package. Run: pip install gtfs-realtime-bindings")
    exit(1)

print("Fetching GTFS-RT feed...")
r = requests.get(GTFS_RT_URL, timeout=15)
print(f"Status: {r.status_code}, Size: {len(r.content)} bytes")

feed = gtfs_realtime_pb2.FeedMessage()
feed.ParseFromString(r.content)

print(f"Total entities in feed: {len(feed.entity)}")

# Find route_id for Tram B first (route_id = 60, found earlier)
TRAM_B_ROUTE_ID = "60"

all_vehicles = []
tram_b_vehicles = []

for entity in feed.entity:
    if not entity.HasField("vehicle"):
        continue
    v = entity.vehicle
    route_id = v.trip.route_id if v.HasField("trip") else ""
    vid = v.vehicle.id if v.HasField("vehicle") else "?"

    info = {
        "vehicle_id": vid,
        "route_id": route_id,
        "lat": v.position.latitude if v.HasField("position") else None,
        "lon": v.position.longitude if v.HasField("position") else None,
        "bearing": v.position.bearing if v.HasField("position") else None,
        "speed": v.position.speed if v.HasField("position") else None,
        "status": v.current_status if v.HasField("current_status") else None,
        "trip_id": v.trip.trip_id if v.HasField("trip") else "",
    }
    all_vehicles.append(info)
    if route_id == TRAM_B_ROUTE_ID:
        tram_b_vehicles.append(info)

print(f"\nTotal vehicles (all routes): {len(all_vehicles)}")
print(f"Tram B vehicles (route_id={TRAM_B_ROUTE_ID}): {len(tram_b_vehicles)}")

print("\nSample of all route_ids present in feed:")
route_ids_seen = set(v["route_id"] for v in all_vehicles)
print(sorted(route_ids_seen))

print("\nTram B vehicle details:")
for v in tram_b_vehicles:
    print(f"  {v['vehicle_id']}: lat={v['lat']}, lon={v['lon']}, "
          f"speed={v['speed']}, status={v['status']}")

if not tram_b_vehicles and all_vehicles:
    print("\nNo Tram B vehicles found. Showing first 5 vehicles of any route:")
    for v in all_vehicles[:5]:
        print(f"  {v}")
