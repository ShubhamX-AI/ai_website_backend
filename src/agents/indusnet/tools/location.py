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
        Ask the frontend to share the user's exact GPS location via the browser.
        Only call this when the user explicitly asks to use their current/exact/GPS
        location (e.g. "from where I am right now", "use my GPS", "my current location").
        If the user simply tells you a place name, use calculate_distance_to_destination
        directly with origin_place — no need to call this first.
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
        self,
        context: RunContext,
        destination: str,
        origin_place: str | None = None,
        travel_mode: str = "driving",
    ):
        """
        Calculate distance and travel time from an origin to a destination.

        Origin resolution (pick one):
        - If the user mentioned a place name as their starting point
          (e.g. "I am at Park Street", "from Salt Lake"), pass it as `origin_place`.
          The system resolves it to coordinates automatically — no GPS needed.
        - If the user explicitly asked to use their exact/current GPS location
          (e.g. "from my current location", "use my GPS"), leave `origin_place` empty
          and call `request_user_location` first.

        Travel mode (optional, defaults to "driving"):
          "driving" | "walking" | "bicycling" | "transit" | "motorcycle"
          Pick from what the user said; if they said nothing, use "driving".

        Args:
            destination: Destination address or place name.
            origin_place: Origin place name stated by user. Omit to use GPS location.
            travel_mode: How the user wants to travel. Defaults to "driving".
        """
        # ── Resolve origin coordinates ──────────────────────────────────────
        if origin_place:
            # User told us where they are — resolve via SearXNG map search
            self.logger.info(f"🗺️ Resolving origin place via SearXNG: '{origin_place}'")
            places = await self.search_service.search_map(origin_place, limit=1)
            if not places:
                return (
                    f"I couldn't find '{origin_place}' on the map. "
                    "Could you give me a more specific location or city name?"
                )
            origin_lat = places[0]["lat"]
            origin_lng = places[0]["lng"]
            # Use the resolved title as the display address for the map packet
            origin_display = places[0]["title"] or places[0]["address"] or origin_place
        else:
            # Fall back to GPS location captured by request_user_location
            if self._location_status != "success" or self._user_lat is None or self._user_lng is None:
                return (
                    "I don't have your location yet. You can either tell me where you are "
                    "(e.g. 'I'm at Park Street') or allow me to use your GPS location."
                )
            origin_lat = self._user_lat
            origin_lng = self._user_lng
            origin_display = self._user_address or f"{origin_lat},{origin_lng}"

        self.logger.info(
            f"📐 Calculating route from ({origin_lat}, {origin_lng}) to '{destination}' [{travel_mode}]"
        )

        try:
            # Run directions and destination image fetch in parallel — image doesn't need route data
            result, image_urls = await asyncio.gather(
                self.google_map_service.get_directions(
                    origin_lat=origin_lat,
                    origin_lng=origin_lng,
                    destination=destination,
                    travel_mode=travel_mode,
                ),
                self.search_service.search_images(destination, limit=1),
                return_exceptions=True,
            )

            if not result or isinstance(result, BaseException):
                return f"Could not find a route to '{destination}'. Please check the address and try again."

            if "error" in result:
                return f"The destination '{result['formatted_address']}' was found, but: {result['error']}."

            formatted_address = result["formatted_address"]
            distance_text = result["distance_text"]
            duration_text = result["duration_text"]
            polyline = result["polyline"]
            mode_label = result["mode_label"]          # e.g. "on foot", "by bicycle"
            api_mode = result["travel_mode"]            # e.g. "WALK", "BICYCLE"

            self.logger.info(
                f"✅ Route to '{formatted_address}': {distance_text} ({duration_text}) [{api_mode}]"
            )

            destination_image = (image_urls[0] if isinstance(image_urls, list) and image_urls else "")

            # Publish polyline + mode + destination image to the frontend
            await self._publish_data_packet(
                {
                    "type": "map.polyline",
                    "data": {
                        "polyline": polyline,
                        "origin": origin_display,
                        "destination": formatted_address,
                        "travelMode": api_mode.lower(),
                        "distance": distance_text,
                        "duration": duration_text,
                        "destination_image_url": destination_image,
                    },
                },
                TOPIC_UI_LOCATION_REQUEST,
            )
            self._set_last_ui_snapshot(
                snapshot_type="distance_map",
                title="Distance and route",
                summary=(
                    f"Displayed route to {formatted_address}: {distance_text}, "
                    f"about {duration_text} {mode_label}."
                ),
                details={
                    "origin": origin_display,
                    "destination": formatted_address,
                    "distance": distance_text,
                    "duration": duration_text,
                    "travel_mode": api_mode,
                },
                source_tool="calculate_distance_to_destination",
            )

            return (
                f"'{formatted_address}' is approximately {distance_text} away "
                f"and will take around {duration_text} {mode_label}."
            )

        except Exception as e:
            self.logger.error(f"❌ Distance calculation failed: {e}")
            return "An error occurred while calculating the route. Please try again."
