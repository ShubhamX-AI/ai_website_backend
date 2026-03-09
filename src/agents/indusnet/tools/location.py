import asyncio

from livekit.agents import function_tool, RunContext

from src.agents.indusnet.constants import (
    TOPIC_UI_LOCATION_REQUEST,
    TOPIC_NEARBY_OFFICES,
)


class LocationToolsMixin:
    """Tools for GPS location request and distance/directions calculation."""

    @function_tool
    async def request_user_location(self, context: RunContext):
        """
        Ask the frontend to share the user's current GPS location.
        The browser will prompt the user for permission. Returns the location
        status once the frontend responds (success, denied, or unsupported).
        Wait for this tool's result before calling calculate_distance_to_destination.
        """
        self.logger.info("📍 Requesting user location from frontend")

        # Reset previous state and the event flag so we wait for a fresh reply
        self._location_status = None
        self._user_lat = None
        self._user_lng = None
        self._location_accuracy = None
        self._location_event.clear()

        # Tell the frontend to fire the Geolocation API.
        # The frontend listens on topic 'ui.location_request' OR checks data.type === 'location_request'.
        await self._publish_data_packet(
            {"type": "location_request"},
            TOPIC_UI_LOCATION_REQUEST,
        )

        # Wait up to 15 s for the frontend to respond
        try:
            await asyncio.wait_for(self._location_event.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            return "Location request timed out. The user may not have responded to the browser prompt."

        if self._location_status == "success":
            accuracy_note = (
                f" (accuracy: ±{self._location_accuracy:.0f} m)"
                if self._location_accuracy is not None
                else ""
            )

            # Get location of the user
            location = await self.google_map_service.get_current_location(
                self._user_lat, self._user_lng
            )
            self._user_address = (
                location.get("formatted_address", f"{self._user_lat},{self._user_lng}")
                if location
                else f"{self._user_lat},{self._user_lng}"
            )
            return (
                f"Location obtained: lat={self._user_lat}, lng={self._user_lng}{accuracy_note}. "
                f"Address of the user: {self._user_address}. "
                "You can now call calculate_distance_to_destination."
            )
        elif self._location_status == "denied":
            return "The user denied location access or the request timed out on the browser side. Cannot calculate distance without location."
        elif self._location_status == "unsupported":
            return "The user's browser does not support Geolocation. Cannot calculate distance."
        else:
            return "Unknown location status received from the frontend."

    @function_tool
    async def calculate_distance_to_destination(
        self, context: RunContext, destination: str
    ):
        """
        Calculate the driving distance and estimated travel time from the user's
        current GPS location to a destination address or landmark.

        IMPORTANT: You MUST call request_user_location first and confirm a
        'success' status before calling this tool.

        Args:
            destination: The destination address or place name (e.g., "Indus Net Technologies, Kolkata").
        """
        if (
            self._location_status != "success"
            or self._user_lat is None
            or self._user_lng is None
        ):
            return (
                "I don't have the user's location yet. "
                "Please call request_user_location first and ensure access was granted."
            )

        self.logger.info(
            f"📐 Calculating distance from ({self._user_lat}, {self._user_lng}) to '{destination}'"
        )

        try:
            result = await self.google_map_service.get_directions(
                origin_lat=self._user_lat,
                origin_lng=self._user_lng,
                destination=destination,
            )

            if not result:
                return f"Could not geocode '{destination}'. Please check the address and try again."

            if "error" in result:
                return f"The destination '{result['formatted_address']}' was found, but: {result['error']}."

            formatted_address = result["formatted_address"]
            distance_text = result["distance_text"]
            duration_text = result["duration_text"]
            polyline = result["polyline"]

            self.logger.info(
                f"✅ Distance to '{formatted_address}': {distance_text} ({duration_text})"
            )

            # Publish polyline to the frontend
            await self._publish_data_packet(
                {
                    "type": "map.polyline",
                    "data": {
                        "polyline": polyline,
                        "origin": self._user_address,
                        "destination": formatted_address,
                        "travelMode": "driving",
                        "distance": distance_text,
                        "duration": duration_text,
                    },
                },
                TOPIC_UI_LOCATION_REQUEST,
            )
            self._set_last_ui_snapshot(
                snapshot_type="distance_map",
                title="Distance and route",
                summary=(
                    f"Displayed route to {formatted_address}: {distance_text}, about {duration_text} by car."
                ),
                details={
                    "origin": self._user_address,
                    "destination": formatted_address,
                    "distance": distance_text,
                    "duration": duration_text,
                },
                source_tool="calculate_distance_to_destination",
            )

            return (
                f"The destination '{formatted_address}' is approximately {distance_text} away "
                f"and will take around {duration_text} by car from your current location."
            )

        except Exception as e:
            self.logger.error(f"❌ Distance calculation failed: {e}")
            return "An error occurred while calculating the distance. Please try again."
