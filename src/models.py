from dataclasses import dataclass


@dataclass
class PIIEntity:
    entity_type: str
    value: str
    start: int
    end: int
    confidence: float