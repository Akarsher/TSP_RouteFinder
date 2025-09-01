import os
import requests
from typing import List, Tuple

def build_distance_matrix(coords: List[Tuple[float, float]]) -> List[List[float]]:
    """
    Build a symmetric distance matrix (km) using Google Routes API (new replacement for Distance Matrix).
    coords: List of (lat, lon)
    Returns: 2D list of distances in km
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY not set in environment")

    url = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "originIndex,destinationIndex,distanceMeters"
    }

    # Build origins and destinations
    origins = [{"waypoint": {"location": {"latLng": {"latitude": lat, "longitude": lon}}}} for lat, lon in coords]
    destinations = origins  # For TSP we need full matrix

    body = {
        "origins": origins,
        "destinations": destinations,
        "travelMode": "DRIVE"
    }

    resp = requests.post(url, headers=headers, json=body)
    resp.raise_for_status()
    data = resp.json()

    n = len(coords)
    dist_km = [[float("inf")] * n for _ in range(n)]

    for row in data:
        i = row["originIndex"]
        j = row["destinationIndex"]
        meters = row.get("distanceMeters")
        if meters is not None:
            dist_km[i][j] = meters / 1000.0

    # Ensure diagonal is 0
    for i in range(n):
        dist_km[i][i] = 0.0

    return dist_km
