from docx import Document
import os
import re
import sys
from collections import defaultdict

from document_mapper import build_document_map

from detectors.regex_detector import detect_regex_pii
from detectors.ner_detector import detect_ner_pii
from detectors.presidio_detector import detect_presidio_persons
from detectors.merge_detector import merge_entities

from validators.pii_validator import validate_entities

from pseudonymizer import Pseudonymizer

from document_redactor import redact_document
from models import PIIEntity


# ============================================================
# FILES
# ============================================================

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
input_file = os.path.join(project_root, "input", "Red Herring Prospectus (1).docx")
output_file = os.path.join(project_root, "output", "redacted_document.docx")


# ============================================================
# LOAD ORIGINAL DOCUMENT
# ============================================================

# IMPORTANT:
# This SAME Document object is used for:
# 1. Building the document map
# 2. Detecting PII
# 3. Redacting PII
#
# This keeps the document blocks and actual Word elements
# synchronized.

doc = Document(input_file)


# ============================================================
# BUILD CANONICAL DOCUMENT MAP
# ============================================================

full_text, document_blocks = build_document_map(doc)

print(
    "Total text blocks:",
    len(document_blocks)
)

print(
    "Total characters:",
    len(full_text)
)


# ============================================================
# DETECTION
# ============================================================

regex_entities = detect_regex_pii(
    full_text
)

ner_entities = detect_ner_pii(
    full_text
)

presidio_entities = detect_presidio_persons(
    full_text
)


# ============================================================
# DETECTION SUMMARY
# ============================================================

print("\n===== DETECTION SUMMARY =====")

print(
    "Regex detections:",
    len(regex_entities)
)

print(
    "NER detections:",
    len(ner_entities)
)

print(
    "Presidio PERSON detections:",
    len(presidio_entities)
)


# ============================================================
# MERGE DETECTIONS
# ============================================================

merged_entities = merge_entities(
    regex_entities,
    ner_entities,
    presidio_entities
)

print(
    "Merged candidates:",
    len(merged_entities)
)


# ============================================================
# VALIDATION
# ============================================================

validated_entities = validate_entities(
    merged_entities,
    full_text=full_text
)

print(
    "Validated entities:",
    len(validated_entities)
)


# ============================================================
# NAME VARIATIONS & PROPAGATION
# ============================================================

def get_name_variations(name_val):
    words = name_val.strip().split()
    if len(words) < 2:
        return [name_val]
    
    variations = [name_val]
    
    # Generate common variations (e.g. First Last)
    if len(words) == 3:
        variations.append(f"{words[0]} {words[2]}")
    elif len(words) > 3:
        variations.append(f"{words[0]} {words[-1]}")
        
    return list(set(variations))


def get_company_variations(company_val):
    cleaned = company_val.strip()
    words = cleaned.split()
    if len(words) < 2:
        return [cleaned]
    
    variations = [cleaned]
    
    base_words = []
    for w in words:
        if w.lower() not in {"private", "limited", "ltd", "inc", "incorporated", "llp", "pvt", "corp", "corporation"}:
            base_words.append(w)
            
    if base_words:
        base_name = " ".join(base_words)
        variations.append(base_name)
        for w in base_words:
            if len(w) >= 4 and w.lower() not in {"group", "company", "holdings", "services", "infra", "park", "motors"}:
                variations.append(w)
                
    return list(set(variations))


# Keep a copy of the original validated list for final verification
original_validated_list = list(validated_entities)

# 1. Build list of values/variations to search and propagate
propagation_targets = []
variation_parent_map = {}

for ent in validated_entities:
    val = ent.value.strip()
    if not val:
        continue
    val_lower = val.lower()
    
    if ent.entity_type == "PERSON":
        for var in get_name_variations(val):
            var_lower = var.lower()
            propagation_targets.append({
                "value": var,
                "type": "PERSON",
                "parent_val": val
            })
            if var_lower not in variation_parent_map:
                variation_parent_map[var_lower] = val_lower
    elif ent.entity_type == "COMPANY":
        for var in get_company_variations(val):
            var_lower = var.lower()
            propagation_targets.append({
                "value": var,
                "type": "COMPANY",
                "parent_val": val
            })
            if var_lower not in variation_parent_map:
                variation_parent_map[var_lower] = val_lower
    else:
        propagation_targets.append({
            "value": val,
            "type": ent.entity_type,
            "parent_val": val
        })
        variation_parent_map[val_lower] = val_lower

# Sort targets by length descending to prioritize matching longer/fuller names first
propagation_targets.sort(key=lambda x: len(x["value"]), reverse=True)

# 2. Find all matches in full_text and check for overlaps
from detectors.merge_detector import overlap

new_propagated = []

for target in propagation_targets:
    target_val = target["value"]
    target_type = target["type"]
    
    # Use word boundary search with flexible whitespace and tab matching
    pattern_str = r"\b" + r"[\s\t]*".join(re.escape(w) for w in target_val.split()) + r"\b"
    pattern = re.compile(pattern_str, re.IGNORECASE)
    
    for m in pattern.finditer(full_text):
        m_start = m.start()
        m_end = m.end()

        # Expand company match to include trailing corporate suffix if present
        if target_type == "COMPANY":
            rest_text = full_text[m_end:]
            suffix_match = re.match(r'^(?:\s+(?:Private\s+Limited|Limited|Ltd\.?|Pvt\.?\s+Ltd\.?|LLP|Inc\.?|Corporation))', rest_text, re.IGNORECASE)
            if suffix_match:
                m_end += suffix_match.end()

        m_val = full_text[m_start:m_end]
        
        cand = PIIEntity(
            entity_type=target_type,
            value=m_val,
            start=m_start,
            end=m_end,
            confidence=1.0
        )
        
        has_overlap = False
        for existing in validated_entities + new_propagated:
            if overlap(cand, existing):
                has_overlap = True
                break
                
        if not has_overlap:
            new_propagated.append(cand)

# Append propagated entities and sort in document order
validated_entities.extend(new_propagated)
validated_entities.sort(key=lambda x: x.start)

print(
    "Total entities after propagation:",
    len(validated_entities)
)


# ============================================================
# PSEUDONYMIZER
# ============================================================

pseudonymizer = Pseudonymizer(mode="placeholder")

# Pre-populate pseudonymizer to map variations to the same parent pseudonym
for ent in validated_entities:
    val_lower = ent.value.strip().lower()
    parent_val_lower = variation_parent_map.get(val_lower, val_lower)
    
    # Assign parent replacement first
    parent_rep = pseudonymizer.get_replacement(ent.entity_type, parent_val_lower)
    
    # Map the variation value to the same replacement
    key = (ent.entity_type, val_lower)
    if key not in pseudonymizer.mapping:
        pseudonymizer.mapping[key] = parent_rep


# ============================================================
# REDACTION
# ============================================================

# IMPORTANT:
# Pass the SAME `doc` object that was used to create
# `document_blocks`.

redaction_result = redact_document(
    doc=doc,
    output_file=output_file,
    entities=validated_entities,
    pseudonymizer=pseudonymizer,
    document_blocks=document_blocks,
)


# ============================================================
# EXTRACT REDACTION RESULTS
# ============================================================

replacement_map = redaction_result[
    "replacement_map"
]

successfully_applied = redaction_result[
    "successfully_applied"
]

unmatched_entities = redaction_result[
    "unmatched_entities"
]

skipped_overlaps = redaction_result[
    "skipped_overlaps"
]


# ============================================================
# REDACTION SUMMARY
# ============================================================

print("\n===== REDACTION COMPLETE =====")

print(
    "Output file:",
    output_file
)

print(
    "Validated entities:",
    len(validated_entities)
)

print(
    "Successfully applied:",
    successfully_applied
)

print(
    "Unique replacements:",
    len(replacement_map)
)

print(
    "Unmatched entities:",
    len(unmatched_entities)
)

print(
    "Skipped overlapping entities:",
    skipped_overlaps
)


# ============================================================
# UNMATCHED ENTITIES
# ============================================================

if unmatched_entities:

    print(
        "\n===== UNMATCHED ENTITIES ====="
    )

    for entity, reason in unmatched_entities[:30]:

        print(
            f"{reason}: "
            f"{entity.entity_type} -> "
            f"{entity.value}"
        )


# ============================================================
# REPLACEMENT SUMMARY
# ============================================================

print(
    "\n===== REPLACEMENT SUMMARY ====="
)

for key, replacement in replacement_map.items():

    entity_type, original_value = key

    print(
        f"{entity_type} -> {replacement}"
    )


# ============================================================
# FINAL PII LEAK CHECK
# ============================================================

print("\n===== FINAL PII LEAK CHECK =====")

# Reload saved redacted document
doc_after = Document(output_file)
full_text_after, blocks_after = build_document_map(doc_after)

leaks = defaultdict(list)

# Set of names and other validated values to check
person_names_to_check = set()
other_pii_to_check = set()

for ent in original_validated_list:
    val = ent.value.strip()
    if not val:
        continue
    if ent.entity_type == "PERSON":
        for var in get_name_variations(val):
            person_names_to_check.add(var.lower())
    else:
        for line in val.splitlines():
            line_clean = line.strip().lower()
            if ent.entity_type == "ADDRESS":
                line_clean = re.sub(r'^(?:the\s+registered\s+office\s+of\s+our\s+company\s+located\s+at|the\s+corporate\s+office\s+of\s+our\s+company\s+located\s+at|having\s+its\s+registered\s+office\s+at|registered\s+office|corporate\s+office|correspondence\s+address|contact\s+address|our\s+manufacturing\s+facility\s+located\s+at)\s*', '', line_clean, flags=re.IGNORECASE).strip()
            if len(line_clean) > 8 and not line_clean.startswith("registered office") and not line_clean.startswith("corporate office"):
                other_pii_to_check.add((ent.entity_type, line_clean))

# Check for presence in full_text_after
for name in person_names_to_check:
    if len(name.strip()) > 3:
        pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        if pattern.search(full_text_after):
            leaks["PERSON"].append(name)

for ent_type, val in other_pii_to_check:
    if len(val.strip()) > 5:
        pattern = re.compile(rf"\b{re.escape(val)}\b", re.IGNORECASE)
        if pattern.search(full_text_after):
            # Check if this exact text string was already replaced by an entity placeholder
            if not re.search(r"^[A-Z]+_\d{3}$", val.strip()):
                leaks[ent_type].append(val)

# Also run detectors on the redacted text
after_regex = detect_regex_pii(full_text_after)
after_ner = detect_ner_pii(full_text_after)
after_presidio = detect_presidio_persons(full_text_after)
after_merged = merge_entities(after_regex, after_ner, after_presidio)
after_validated = validate_entities(after_merged)

for ent in after_validated:
    val_lower = ent.value.strip().lower()
    # Skip checking if it matches the replacement pseudonym format like PERSON_001
    if re.match(r"^[A-Z]+_\d{3}$", ent.value):
        continue
    
    # Check if this matches any of the original validated values or their variations
    is_genuine_leak = False
    if ent.entity_type == "PERSON":
        if val_lower in person_names_to_check:
            is_genuine_leak = True
    else:
        for o_type, o_val in other_pii_to_check:
            if o_type == ent.entity_type and o_val == val_lower:
                is_genuine_leak = True
                break
                
    if is_genuine_leak and val_lower not in leaks[ent.entity_type]:
        leaks[ent.entity_type].append(val_lower)

# Print verification results
remaining_count = sum(len(v) for v in leaks.values())

for pii_type in ["PERSON", "COMPANY", "EMAIL", "PHONE", "ADDRESS", "SSN", "CREDIT_CARD", "DOB", "IP_ADDRESS"]:
    print(f"Remaining {pii_type}: {len(leaks[pii_type])}")
    if leaks[pii_type]:
        for val in leaks[pii_type]:
            print(f"  Leaked: {val}")

if remaining_count == 0:
    print("\n===== REDACTION COMPLETE =====")
    print("Output file:", output_file)
    print("Final verification: PASSED")
else:
    print("\n===== REDACTION FAILED =====")
    print(f"Remaining PII: {remaining_count}")
    print("Final verification: FAILED")
    sys.exit(1)