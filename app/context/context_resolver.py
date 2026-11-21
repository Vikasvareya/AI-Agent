from app.context.base_context_resolver import BaseContextResolver
from app.context.conversation_context import ConversationContext
from app.context.entity_extractor import EntityExtractor
from app.context.pronoun_resolver import PronounResolver
from app.planner.intents.timezone_resolver import TimezoneResolver
import re


class ContextResolver(BaseContextResolver):
    """
    Coordinates conversational context resolution.

    Responsibilities:
    - Resolve pronouns
    - Detect new entities
    - Update conversation state
    """

    def __init__(self):
        self.context = ConversationContext()

        self.entity_extractor = EntityExtractor()

        self.pronoun_resolver = PronounResolver()

    def resolve(
        self,
        prompt: str,
    ) -> str:
        normalized = prompt.strip()
        lower = normalized.lower()

        unrelated_patterns = (
            r"\b(?:weather|forecast|stock|news|sports)\b",
            r"\bwhat\s+is\s+the\s+weather\b",
        )
        if any(re.search(pattern, lower) for pattern in unrelated_patterns):
            self.context.last_action = None
            self.context.last_tool = None
            self.context.last_location = None
            return normalized

        if re.fullmatch(r"(?:use\s+(?:the\s+)?tool|run\s+(?:the\s+)?tool|execute\s+(?:the\s+)?tool)\.?", lower):
            if (
                self.context.last_action == "current_time"
                and self.context.last_location
            ):
                return f"What time is it in {self.context.last_location}?"
            if self.context.last_action == "current_time":
                return "Please specify a location or timezone for the time request."
            return "Please specify what tool you want me to use."

        if re.search(r"\btell\s+me\s+(?:the\s+)?time\s+there\b", lower):
            if self.context.last_action == "current_time" and self.context.last_location:
                return f"What time is it in {self.context.last_location}?"
            return "Please specify a location for the time request."

        follow_up_match = re.match(
            r"^(?:and\s+|what\s+about\s+|now\s+)(.+)$",
            lower,
            flags=re.IGNORECASE,
        )
        if follow_up_match and self.context.last_action == "current_time":
            location_text = follow_up_match.group(1).strip().rstrip("?.!, ")
            resolved = TimezoneResolver().resolve(
                f"What time is it in {location_text}"
            )
            if resolved.location:
                self.context.last_location = resolved.location
                self.context.last_tool = "time"
                return f"What time is it in {resolved.location}?"
            if resolved.clarification:
                return resolved.clarification

        resolved_prompt = self.pronoun_resolver.resolve(
            prompt,
            self.context,
        )
        entity = self.entity_extractor.extract(
            resolved_prompt,
        )
        if entity:
            self.context.last_entity = entity

        time_request = re.search(
            r"\b(?:what\s+time|current\s+time|time\s+is\s+it|tell\s+me\s+the\s+time|what\s+is\s+the\s+date)\b",
            lower,
        )
        if time_request:
            resolved = TimezoneResolver().resolve(resolved_prompt)
            self.context.last_action = "current_time"
            self.context.last_tool = "time"
            if resolved.location:
                self.context.last_location = resolved.location

        return resolved_prompt