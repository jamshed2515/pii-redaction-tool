from models import PIIEntity


# ============================================================
# OVERLAP
# ============================================================

def overlap(entity1, entity2):
    """
    Return True when two entities overlap in the
    canonical document text.
    """

    return (
        entity1.start < entity2.end
        and entity2.start < entity1.end
    )


# ============================================================
# DETECTOR PRIORITY
# ============================================================

def detector_priority(entity):
    """
    Higher priority means the detection is preferred
    when entities overlap.

    Regex is strongest for structured PII such as:
        EMAIL
        PHONE
        IP
        CREDIT CARD
        etc.

    Presidio is preferred over generic NER for PERSON.

    spaCy NER is used as a broader fallback.
    """

    entity_type = entity.entity_type

    confidence = entity.confidence

    # Regex detections normally have confidence 1.0.
    if confidence >= 0.99:
        return 3

    # Presidio PERSON detections generally use ~0.85.
    # We cannot directly know the detector here, so
    # confidence is still used as a secondary signal.
    if confidence >= 0.85:
        return 2

    return 1


# ============================================================
# MERGE
# ============================================================

def merge_entities(
    regex_entities,
    ner_entities,
    presidio_entities,
):
    """
    Merge Regex, spaCy NER and Presidio detections.

    When entities overlap, prefer the strongest detection.

    Priority:

        Regex
          ↓
        Presidio / high-confidence detection
          ↓
        spaCy NER
    """

    all_entities = (
        list(regex_entities)
        + list(presidio_entities)
        + list(ner_entities)
    )

    # --------------------------------------------------------
    # Sort:
    #
    # 1. Higher priority first
    # 2. Higher confidence
    # 3. Earlier position
    # --------------------------------------------------------

    all_entities.sort(
        key=lambda entity: (
            -detector_priority(entity),
            -entity.confidence,
            entity.start,
            -(entity.end - entity.start),
        )
    )

    merged = []

    # ========================================================
    # SELECT NON-OVERLAPPING ENTITIES
    # ========================================================

    for entity in all_entities:

        should_add = True

        for existing in merged:

            if overlap(entity, existing):

                should_add = False
                break

        if should_add:

            merged.append(entity)

    # ========================================================
    # DOCUMENT ORDER
    # ========================================================

    merged.sort(
        key=lambda entity: entity.start
    )

    return merged