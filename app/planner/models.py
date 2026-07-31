from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.planner.intents.base_intent import BaseIntent


@dataclass
class IntentMatch:
    matched: bool
    confidence: float
    priority: int = 0


@dataclass
class RankedIntent:
    intent: "BaseIntent"
    match: IntentMatch