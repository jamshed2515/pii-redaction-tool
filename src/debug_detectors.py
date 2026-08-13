from docx import Document

from document_mapper import build_document_map
from detectors.ner_detector import detect_ner_pii
from detectors.presidio_detector import detect_presidio_persons


input_file = "input/DOC-20260813-WA0001.docx"

doc = Document(input_file)

full_text, document_blocks = build_document_map(doc)

ner_entities = detect_ner_pii(full_text)
presidio_entities = detect_presidio_persons(full_text)


print("===== NER MULTILINE =====")

count = 0

for entity in ner_entities:
    if "\n" in entity.value or "\r" in entity.value:
        print(
            repr(entity.value),
            entity.start,
            entity.end
        )
        count += 1

print("NER multiline count:", count)


print("\n===== PRESIDIO MULTILINE =====")

count = 0

for entity in presidio_entities:
    if "\n" in entity.value or "\r" in entity.value:
        print(
            repr(entity.value),
            entity.start,
            entity.end
        )
        count += 1

print("Presidio multiline count:", count)


print("\n===== TOTALS =====")

print("NER:", len(ner_entities))
print("Presidio:", len(presidio_entities))
