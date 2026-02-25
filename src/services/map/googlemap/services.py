import os
import aiohttp
import logging
from typing import Optional, Dict, Any

class GoogleMapService:
    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY", "")
        self.logger = logging.getLogger("google_map_service")

    async def geocode_destination(self, destination: str) -> Optional[Dict[str, Any]]:
        """
        Geocode a destination string to get its latitude, longitude, and formatted address.
        """
        if not self.api_key:
            self.logger.error("Google Maps API key is not configured.")
            return None

        async with aiohttp.ClientSession() as session:
            geo_params = {
                "address": destination,
                "key": self.api_key,
            }
            try:
                async with session.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params=geo_params,
                ) as geo_resp:
                    geo_data = await geo_resp.json()

                if not geo_data.get("results"):
                    self.logger.warning(f"Could not geocode '{destination}'")
                    return None

                result = geo_data["results"][0]
                return {
                    "lat": result["geometry"]["location"]["lat"],
                    "lng": result["geometry"]["location"]["lng"],
                    "formatted_address": result.get("formatted_address", destination)
                }
            except Exception as e:
                self.logger.error(f"Geocoding failed for '{destination}': {e}")
                return None

    async def get_distance_matrix(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> Optional[Dict[str, Any]]:
        """
        Get driving distance and duration between two coordinates.
        """
        if not self.api_key:
            self.logger.error("Google Maps API key is not configured.")
            return None

        async with aiohttp.ClientSession() as session:
            dist_params = {
                "origins": f"{origin_lat},{origin_lng}",
                "destinations": f"{dest_lat},{dest_lng}",
                "key": self.api_key,
                "mode": "driving",
                "units": "metric",
            }
            try:
                async with session.get(
                    "https://maps.googleapis.com/maps/api/distancematrix/json",
                    params=dist_params,
                ) as dist_resp:
                    dist_data = await dist_resp.json()

                if not dist_data.get("rows") or not dist_data["rows"][0].get("elements"):
                    return None

                element = dist_data["rows"][0]["elements"][0]
                if element.get("status") != "OK":
                    self.logger.warning(f"Distance Matrix returned status: {element.get('status')}")
                    return None

                return {
                    "distance_text": element["distance"]["text"],
                    "duration_text": element["duration"]["text"],
                    "status": element.get("status")
                }
            except Exception as e:
                self.logger.error(f"Distance calculation failed: {e}")
                return None

    async def calculate_distance_and_duration(self, origin_lat: float, origin_lng: float, destination: str) -> Optional[Dict[str, Any]]:
        """
        Combined method to geocode destination and calculate distance/duration.
        """
        geo_result = await self.geocode_destination(destination)
        if not geo_result:
            return None

        dist_result = await self.get_distance_matrix(
            origin_lat, origin_lng, 
            geo_result["lat"], geo_result["lng"]
        )

        if not dist_result:
            return {
                "formatted_address": geo_result["formatted_address"],
                "error": "Could not calculate route"
            }

        return {
            "formatted_address": geo_result["formatted_address"],
            "distance_text": dist_result["distance_text"],
            "duration_text": dist_result["duration_text"]
        }


    # Get location of a place using latitude and longitude
    async def get_location(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        """
        Get location of a place using latitude and longitude.
        """
        if not self.api_key:
            self.logger.error("Google Maps API key is not configured.")
            return None

        async with aiohttp.ClientSession() as session:
            geo_params = {
                "latlng": f"{lat},{lng}",
                "key": self.api_key,
            }
            try:
                async with session.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params=geo_params,
                ) as geo_resp:
                    geo_data = await geo_resp.json()

                if not geo_data.get("results"):
                    self.logger.warning(f"Could not get location for '{lat},{lng}'")
                    return None

                result = geo_data["results"][0]
                return {
                    "formatted_address": result.get("formatted_address", f"{lat},{lng}"),
                    "lat": lat,
                    "lng": lng
                }
            except Exception as e:
                self.logger.error(f"Location lookup failed for '{lat},{lng}': {e}")
                return None