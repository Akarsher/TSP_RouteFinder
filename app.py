import os
from typing import List, Tuple

from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
import folium
import requests
import polyline

from tsp_solver import solve_tsp_held_karp
from google_distance import build_distance_matrix

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

MAX_POINTS = 20
GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_MAPS_API_KEY not set. Put it in .env or your environment.")


def parse_coordinates(form) -> List[Tuple[float, float]]:
    lats = form.getlist("lat[]")
    lons = form.getlist("lon[]")
    coords: List[Tuple[float, float]] = []
    for lat_str, lon_str in zip(lats, lons):
        if lat_str.strip() == "" or lon_str.strip() == "":
            continue
        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError:
            raise ValueError("Latitude/Longitude must be numeric.")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Latitude must be [-90,90], Longitude must be [-180,180].")
        coords.append((lat, lon))
    if len(coords) < 2:
        raise ValueError("Please enter at least 2 valid coordinate pairs.")
    if len(coords) > MAX_POINTS:
        raise ValueError(f"Please limit to {MAX_POINTS} points.")
    return coords


def add_markers_in_order(m: folium.Map, coords: List[Tuple[float, float]], order: List[int]):
    for visit_idx, node in enumerate(order[:-1], start=1):
        lat, lon = coords[node]
        if visit_idx == 1:
            # Start point
            icon = folium.Icon(color="green", icon="play")
            label = f"Start: ({lat:.4f}, {lon:.4f})"
        else:
            # Intermediate stop
            icon = folium.Icon(color="blue", icon="flag")
            label = f"Stop {visit_idx}: ({lat:.4f}, {lon:.4f})"
        folium.Marker([lat, lon], popup=label, tooltip=label, icon=icon).add_to(m)

    # Closing node = back to start
    last_node = order[-1]
    lat, lon = coords[last_node]
    folium.Marker(
        [lat, lon],
        popup="Return to Start",
        tooltip="Return to Start",
        icon=folium.Icon(color="red", icon="home")
    ).add_to(m)


def draw_directions_polyline(m: folium.Map, start: Tuple[float, float], end: Tuple[float, float]):
    """Uses the new Routes API for driving path."""
    url = f"https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": "routes.polyline.encodedPolyline"
    }
    body = {
        "origin": {"location": {"latLng": {"latitude": start[0], "longitude": start[1]}}},
        "destination": {"location": {"latLng": {"latitude": end[0], "longitude": end[1]}}},
        "travelMode": "DRIVE",
    }

    resp = requests.post(url, headers=headers, json=body)
    if resp.status_code != 200:
        return
    data = resp.json()
    if "routes" not in data or not data["routes"]:
        return

    poly = data["routes"][0]["polyline"]["encodedPolyline"]
    path = polyline.decode(poly)  # list of (lat, lon)
    folium.PolyLine(path, weight=4, opacity=0.8, color="blue").add_to(m)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            coords = parse_coordinates(request.form)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("index"))

        # Build driving distance matrix (km)
        dist = build_distance_matrix(coords)

        # Check for unreachable pairs
        for i in range(len(dist)):
            for j in range(len(dist)):
                if dist[i][j] == float('inf'):
                    flash("Some locations are unreachable by road. Please adjust your inputs.", "error")
                    return redirect(url_for("index"))

        # Solve TSP
        total_cost_km, order = solve_tsp_held_karp(dist)

        # Build Folium map
        m = folium.Map(location=coords[order[0]], zoom_start=10, control_scale=True)

        # Add markers
        add_markers_in_order(m, coords, order)

        # Draw path
        leg_distances = []
        for i in range(len(order) - 1):
            a = order[i]
            b = order[i + 1]
            draw_directions_polyline(m, coords[a], coords[b])
            leg_distances.append(dist[a][b])

        # Auto-zoom map to fit all points
        m.fit_bounds([coords[node] for node in order])

        route_html = m._repr_html_()

        # Prepare itinerary INCLUDING return to start
        itinerary = [
            {
                "visit": i + 1,
                "node": node,
                "lat": coords[node][0],
                "lon": coords[node][1],
                "leg_km": (0.0 if i == 0 else round(leg_distances[i - 1], 3))
            }
            for i, node in enumerate(order)
        ]

        return render_template(
            "results.html",
            route_html=route_html,
            total_km=round(total_cost_km, 3),
            itinerary=itinerary,
        )

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
