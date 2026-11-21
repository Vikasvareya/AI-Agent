import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class ResolvedTimezone:
    timezone: str
    label: str
    ambiguous: bool = False
    clarification: str | None = None
    location: str | None = None


class TimezoneResolver:
    LOCATION_ALIASES = {
        "germany": ("Europe/Berlin", "Germany"),
        "deutschland": ("Europe/Berlin", "Germany"),
        "berlin": ("Europe/Berlin", "Berlin"),
        "london": ("Europe/London", "London"),
        "united kingdom": ("Europe/London", "United Kingdom"),
        "uk": ("Europe/London", "United Kingdom"),
        "great britain": ("Europe/London", "Great Britain"),
        "england": ("Europe/London", "England"),
        "new york": ("America/New_York", "New York"),
        "nyc": ("America/New_York", "New York"),
        "california": ("America/Los_Angeles", "California"),
        "los angeles": ("America/Los_Angeles", "Los Angeles"),
        "san francisco": ("America/Los_Angeles", "San Francisco"),
        "jaipur": ("Asia/Kolkata", "Jaipur"),
        "india": ("Asia/Kolkata", "India"),
        "delhi": ("Asia/Kolkata", "Delhi"),
        "kolkata": ("Asia/Kolkata", "Kolkata"),
        "tokyo": ("Asia/Tokyo", "Tokyo"),
        "japan": ("Asia/Tokyo", "Japan"),
        "singapore": ("Asia/Singapore", "Singapore"),
        "dubai": ("Asia/Dubai", "Dubai"),
        "united arab emirates": ("Asia/Dubai", "United Arab Emirates"),
        "uae": ("Asia/Dubai", "United Arab Emirates"),
        "paris": ("Europe/Paris", "Paris"),
        "france": ("Europe/Paris", "France"),
        "rome": ("Europe/Rome", "Rome"),
        "italy": ("Europe/Rome", "Italy"),
        "madrid": ("Europe/Madrid", "Madrid"),
        "spain": ("Europe/Madrid", "Spain"),
        "australia": (None, "Australia"),
        "canada": (None, "Canada"),
        "united states": (None, "United States"),
        "usa": (None, "United States"),
        "us": (None, "United States"),
        "russia": (None, "Russia"),
        "brazil": (None, "Brazil"),
        "mexico": (None, "Mexico"),
        "utc": ("UTC", "UTC"),
    }

    AMBIGUOUS_LOCATIONS = {
        "australia": "Which Australian city or region should I use, such as Sydney, Melbourne, Perth, or Brisbane?",
        "canada": "Which Canadian city or region should I use, such as Toronto, Vancouver, or Calgary?",
        "united states": "Which US city or region should I use, such as New York or California?",
        "usa": "Which US city or region should I use, such as New York or California?",
        "russia": "Which Russian city or region should I use?",
        "brazil": "Which Brazilian city or region should I use?",
        "mexico": "Which Mexican city or region should I use?",
    }

    def resolve(self, prompt: str) -> ResolvedTimezone:
        location = self.extract_location(prompt)
        if location is None:
            return ResolvedTimezone(
                timezone="",
                label="local timezone",
                location=None,
            )

        normalized = location.lower().strip().rstrip("?.!, ")
        iana_match = re.fullmatch(
            r"[A-Za-z_]+(?:/[A-Za-z0-9_+\-]+)+",
            normalized,
        )
        if iana_match:
            if self._valid_timezone(location):
                return ResolvedTimezone(
                    timezone=location,
                    label=location,
                    location=location,
                )
            return ResolvedTimezone(
                timezone="",
                label=location,
                location=location,
                clarification=f"I could not resolve the timezone '{location}'. Please provide a valid IANA timezone such as Europe/Berlin.",
            )

        alias = self.LOCATION_ALIASES.get(normalized)
        if alias:
            timezone, label = alias
            if timezone:
                return ResolvedTimezone(
                    timezone=timezone,
                    label=label,
                    location=label,
                )
            return ResolvedTimezone(
                timezone="",
                label=label,
                ambiguous=True,
                location=label,
                clarification=self.AMBIGUOUS_LOCATIONS.get(normalized),
            )

        if "/" in normalized:
            timezone_candidate = location
            if self._valid_timezone(timezone_candidate):
                return ResolvedTimezone(
                    timezone=timezone_candidate,
                    label=timezone_candidate,
                    location=timezone_candidate,
                )

        return ResolvedTimezone(
            timezone="",
            label=location,
            location=location,
            clarification=(
                f"I could not resolve '{location}' to a timezone. "
                "Please provide a city or IANA timezone name."
            ),
        )

    @staticmethod
    def extract_location(prompt: str) -> str | None:
        patterns = (
            r"\b(?:time|date|day)\s+(?:is\s+)?(?:it\s+)?in\s+(.+?)\??$",
            r"\b(?:time|date)\s+in\s+(.+?)\??$",
            r"\bin\s+([A-Za-z][A-Za-z\s\-]+)\??$",
        )
        for pattern in patterns:
            match = re.search(pattern, prompt.strip(), flags=re.IGNORECASE)
            if match:
                location = match.group(1).strip().rstrip("?.!, ")
                location = re.sub(r"\b(?:please|now)\b$", "", location, flags=re.IGNORECASE).strip()
                if location:
                    return location
        return None

    @staticmethod
    def _valid_timezone(timezone_name: str) -> bool:
        try:
            ZoneInfo(timezone_name)
            return True
        except (ZoneInfoNotFoundError, ValueError):
            return False
