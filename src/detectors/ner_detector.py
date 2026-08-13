import re
import spacy

from models import PIIEntity


nlp = spacy.load("en_core_web_sm")


def detect_contact_persons(text):
    entities = []

    # Pattern 1: Contact person prefix (avoiding newline matching via [^\S\r\n])
    pattern1 = re.compile(
        r"(?i)\bcontact\s+person\s*:\s*"
        r"([A-Za-z]+(?:[^\S\r\n]+[A-Za-z]+)*)"
        r"[^\S\r\n]*/[^\S\r\n]*"
        r"([A-Za-z]+(?:[^\S\r\n]+[A-Za-z]+)*)"
    )

    for match in pattern1.finditer(text):
        first = match.group(1).strip()
        second = match.group(2).strip()
        first_start = match.start(1)
        first_end = first_start + len(first)
        second_start = match.start(2)
        second_end = second_start + len(second)

        if first:
            entities.append(PIIEntity(entity_type="PERSON", value=first, start=first_start, end=first_end, confidence=0.95))
        if second:
            entities.append(PIIEntity(entity_type="PERSON", value=second, start=second_start, end=second_end, confidence=0.95))

    # Pattern 2: Capitalized names separated by a slash (e.g. Lokesh Shah/ Soumavo Sarkar)
    pattern2 = re.compile(
        r"\b([A-Z][A-Za-z]+(?:[^\S\r\n]+[A-Z][A-Za-z]+)+)"
        r"[^\S\r\n]*/[^\S\r\n]*"
        r"([A-Z][A-Za-z]+(?:[^\S\r\n]+[A-Z][A-Za-z]+)+)\b"
    )

    for match in pattern2.finditer(text):
        first = match.group(1).strip()
        second = match.group(2).strip()
        first_start = match.start(1)
        first_end = first_start + len(first)
        second_start = match.start(2)
        second_end = second_start + len(second)

        if first:
            doc_first = nlp(first)
            if any(ent.label_ == "PERSON" for ent in doc_first.ents):
                entities.append(PIIEntity(entity_type="PERSON", value=first, start=first_start, end=first_end, confidence=0.95))

        if second:
            doc_second = nlp(second)
            if any(ent.label_ == "PERSON" for ent in doc_second.ents):
                entities.append(PIIEntity(entity_type="PERSON", value=second, start=second_start, end=second_end, confidence=0.95))

    return entities


def detect_ner_pii(text):

    entities = []

    contact_entities = detect_contact_persons(text)

    entities.extend(contact_entities)

    contact_spans = [
        (entity.start, entity.end)
        for entity in contact_entities
    ]

    doc = nlp(text)

    for entity in doc.ents:

        if "\n" in entity.text or "\r" in entity.text:
            continue

        overlapping = False

        for start, end in contact_spans:
            if (
                entity.start_char < end
                and start < entity.end_char
            ):
                overlapping = True
                break

        if overlapping:
            continue

        if entity.label_ == "PERSON":
            entity_type = "PERSON"

        elif entity.label_ == "ORG":
            entity_type = "COMPANY"

        elif entity.label_ in {"GPE", "LOC", "FAC"}:
            entity_type = "ADDRESS"

        elif entity.label_ == "DATE":
            entity_type = "DOB"

        else:
            continue

        value = entity.text.strip()

        if not value:
            continue

        start = entity.start_char
        end = start + len(value)

        if text[start:end] != value:
            continue

        entities.append(
            PIIEntity(
                entity_type=entity_type,
                value=value,
                start=start,
                end=end,
                confidence=0.85,
            )
        )

    entities.sort(key=lambda entity: entity.start)

    return entities
