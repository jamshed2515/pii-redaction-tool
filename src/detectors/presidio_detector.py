from presidio_analyzer import AnalyzerEngine

from models import PIIEntity


# ============================================================
# PRESIDIO ANALYZER
# ============================================================

analyzer = AnalyzerEngine()


# ============================================================
# PRESIDIO PERSON DETECTOR
# ============================================================

def detect_presidio_persons(text):

    entities = []

    type_mapping = {
        "PERSON": "PERSON",
        "LOCATION": "ADDRESS",
        "DATE_TIME": "DOB",
        "ORGANIZATION": "COMPANY",
        "EMAIL_ADDRESS": "EMAIL",
        "PHONE_NUMBER": "PHONE",
        "US_SSN": "SSN",
        "CREDIT_CARD": "CREDIT_CARD",
        "IP_ADDRESS": "IP_ADDRESS"
    }

    results = analyzer.analyze(
        text=text,
        language="en",
        entities=list(type_mapping.keys())
    )

    for result in results:

        # Get the exact text detected by Presidio
        value = text[result.start:result.end]

        # ----------------------------------------------------
        # CRITICAL:
        # Never allow Presidio to return an entity that
        # crosses a paragraph/newline boundary.
        # ----------------------------------------------------

        if "\n" in value or "\r" in value:
            continue

        value = value.strip()

        if not value:
            continue

        start = result.start
        end = start + len(value)

        if text[start:end] != value:
            continue

        mapped_type = type_mapping.get(result.entity_type, result.entity_type)

        entities.append(
            PIIEntity(
                entity_type=mapped_type,
                value=value,
                start=start,
                end=end,
                confidence=result.score
            )
        )

    return entities
