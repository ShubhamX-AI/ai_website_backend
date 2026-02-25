import os
import aiohttp
import logging
from typing import Optional, Dict, Any


class GoogleMapService:
    BASE_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

    # Only request the fields we actually use.
    # This is the key cost-saving feature of the Routes API.
    FIELD_MASK = ",".join([
        "routes.legs.distanceMeters",
        "routes.legs.duration",
        "routes.legs.endLocation",
        "routes.polyline.encodedPolyline",
    ])

    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY", "")
        self.logger = logging.getLogger("google_map_service")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_directions(
        self,
        origin_lat: float,
        origin_lng: float,
        destination: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Uses the Routes API (v2) to get distance, duration, and polyline
        in a single POST request with a field mask so Google only computes
        what we need — faster and cheaper than the old Directions API.
        """
        if not self.api_key:
            self.logger.error("Google Maps API key is not configured.")
            return None

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": self.FIELD_MASK,  # <-- only compute what we need
        }

        body = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": origin_lat,
                        "longitude": origin_lng,
                    }
                }
            },
            "destination": {
                "address": destination  # Routes API accepts raw address directly
            },
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",  # uses live traffic, not available in old API
            "units": "METRIC",
        }

        try:
            session = await self._get_session()
            async with session.post(self.BASE_URL, json=body, headers=headers) as resp:
                data = await resp.json()

            if not data.get("routes"):
                self.logger.warning(
                    f"Routes API returned no routes for '{destination}'. Response: {data}"
                )
                return None

            route = data["routes"][0]
            leg = route["legs"][0]
            duration_seconds = int(leg["duration"].rstrip("s"))  # comes as "123s"

            return {
                "formatted_address": destination,
                "distance_meters": leg["distanceMeters"],
                "distance_text": f"{leg['distanceMeters'] / 1000:.1f} km",
                "duration_seconds": duration_seconds,
                "duration_text": self._format_duration(duration_seconds),
                "polyline": route["polyline"]["encodedPolyline"],
                "end_location": {
                    "lat": leg["endLocation"]["latLng"]["latitude"],
                    "lng": leg["endLocation"]["latLng"]["longitude"],
                },
            }

        except Exception as e:
            self.logger.error(f"Routes API request failed for '{destination}': {e}")
            return None

    async def get_current_location(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        """
        Reverse geocode coordinates to a human-readable address.
        Still uses Geocoding API since Routes API doesn't handle reverse geocoding.
        """
        if not self.api_key:
            self.logger.error("Google Maps API key is not configured.")
            return None

        params = {
            "latlng": f"{lat},{lng}",
            "key": self.api_key,
        }

        try:
            session = await self._get_session()
            async with session.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params=params,
            ) as resp:
                data = await resp.json()

            if not data.get("results"):
                self.logger.warning(f"No reverse geocode result for ({lat}, {lng})")
                return None

            result = data["results"][0]
            return {
                "formatted_address": result.get("formatted_address", f"{lat},{lng}"),
                "lat": lat,
                "lng": lng,
            }

        except Exception as e:
            self.logger.error(f"Reverse geocode failed for ({lat}, {lng}): {e}")
            return None

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Convert raw seconds to a readable string like '1 hr 23 mins'."""
        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60
        if hours:
            return f"{hours} hr {minutes} mins"
        return f"{minutes} mins"