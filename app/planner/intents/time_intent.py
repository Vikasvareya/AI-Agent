import re
from app.planner.intents.timezone_resolver import TimezoneResolver
from app.planner.intents.base_intent import BaseIntent
from app.planner.models import IntentMatch
from app.enums.action_type import ActionType
from app.models.plan import Plan



class TimeIntent(BaseIntent):
    """
    Detects time-related queries.
    """

    def matches(
        self,
        prompt: str,
    ) -> IntentMatch:
        normalized = prompt.lower().strip()
        negative_patterns = (
            r"\bhow\s+(do|can)\s+i\s+date\b",
            r"\bwhat\s+should\s+i\s+learn\s+today\b",
        )
        if any(re.search(pattern, normalized) for pattern in negative_patterns):
            matched = False
        else:
            positive_patterns = (
                r"\bwhat\s+time\s+is\s+it\b",
                r"\bwhat\s+time\s+is\s+it\s+in\b",
                r"\bcurrent\s+time\s+in\b",
                r"\bwhat\s+is\s+the\s+date\s+in\b",
                r"\bshow\s+(me\s+)?today'?s\s+date\s+in\b",
                r"\bcurrent\s+(date|time)\b",
                r"\bwhat\s+about\s+(london|new\s+york|jaipur|delhi|kolkata|tokyo|singapore|dubai|utc)\b",
                r"\b(and\s+)?(london|new\s+york|jaipur|delhi|kolkata|tokyo|singapore|dubai|utc)\?\Z",
                r"\bwhat\s+is\s+(the\s+)?(date|time)\b",
                r"\bwhat\s+is\s+today'?s\s+(date|time)\b",
                r"\btoday'?s\s+(date|time)\b",
                r"\bwhat\s+day\s+is\s+today\b",
                r"\bshow\s+me\s+today'?s\s+date\s+(and\s+)?time\b",
                r"\bwhat\s+date\s+(is|was)\s+(tomorrow|yesterday)\b",
            )
            matched = any(
                re.search(pattern, normalized)
                for pattern in positive_patterns
            )

        return IntentMatch(
            matched=matched,
            confidence=0.90 if matched else 0.0,
            priority=90,
        )

    def create_plan(
        self,
        prompt: str,
    ) -> Plan:
        normalized = prompt.lower()
        args: dict = {}
        resolved = TimezoneResolver().resolve(prompt)
        if resolved.location:
            args["location"] = resolved.location
        if resolved.timezone:
            args["timezone"] = resolved.timezone
        if resolved.clarification:
            args["clarification"] = resolved.clarification
        if re.search(r"\btomorrow\b", normalized):
            args["offset_days"] = 1
        elif re.search(r"\byesterday\b", normalized):
            args["offset_days"] = -1
        return Plan(
            action=ActionType.TOOL,
            tool="time",
            args=args,
        )
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
