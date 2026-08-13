import re

# ============================================================
# RUN-AWARE TEXT REPLACEMENT
# ============================================================


def replace_text_in_paragraph(paragraph, replacements):
    """
    Replace entity spans while preserving Word run formatting.

    replacements:
        [
            (start, end, replacement),
            ...
        ]

    start/end are positions inside paragraph.text.

    Replacements are applied from right to left.
    """

    if not paragraph.runs:
        return 0

    if not replacements:
        return 0

    # --------------------------------------------------------
    # Build run ranges
    # --------------------------------------------------------

    run_ranges = []

    current_position = 0

    for run in paragraph.runs:

        text = run.text or ""

        start = current_position
        end = start + len(text)

        run_ranges.append({
            "run": run,
            "start": start,
            "end": end,
            "text": text,
        })

        current_position = end

    # --------------------------------------------------------
    # Sort right -> left
    # --------------------------------------------------------

    replacements = sorted(
        replacements,
        key=lambda x: (x[0], x[1]),
        reverse=True
    )

    # --------------------------------------------------------
    # Remove overlapping replacements
    # --------------------------------------------------------

    filtered = []

    previous_start = float("inf")

    for start, end, replacement in replacements:

        if start < 0:
            continue

        if end <= start:
            continue

        if end > current_position:
            continue

        # Overlap with a replacement already selected
        # to the right.
        if end > previous_start:
            continue

        filtered.append(
            (
                start,
                end,
                replacement
            )
        )

        previous_start = start

    # --------------------------------------------------------
    # Apply right -> left
    # --------------------------------------------------------

    applied = 0

    for start, end, replacement in filtered:

        affected_runs = []

        for info in run_ranges:

            if info["end"] <= start:
                continue

            if info["start"] >= end:
                continue

            affected_runs.append(info)

        if not affected_runs:
            continue

        # ====================================================
        # CASE 1:
        # Entity exists entirely inside one run
        # ====================================================

        if len(affected_runs) == 1:

            info = affected_runs[0]

            run = info["run"]

            local_start = start - info["start"]
            local_end = end - info["start"]

            text = run.text or ""

            if (
                local_start < 0
                or local_end > len(text)
                or local_start >= local_end
            ):
                continue

            run.text = (
                text[:local_start]
                + replacement
                + text[local_end:]
            )

            applied += 1

            continue

        # ====================================================
        # CASE 2:
        # Entity spans multiple runs
        # ====================================================

        first = affected_runs[0]
        last = affected_runs[-1]

        first_run = first["run"]
        last_run = last["run"]

        first_local_start = (
            start - first["start"]
        )

        last_local_end = (
            end - last["start"]
        )

        first_text = first_run.text or ""
        last_text = last_run.text or ""

        if (
            first_local_start < 0
            or first_local_start > len(first_text)
            or last_local_end < 0
            or last_local_end > len(last_text)
        ):
            continue

        # Text before the entity
        first_prefix = first_text[
            :first_local_start
        ]

        # Text after the entity
        last_suffix = last_text[
            last_local_end:
        ]

        # If first and last are actually the same run,
        # this should have been handled above.
        if first_run is last_run:
            continue

        # Put replacement into first run
        first_run.text = (
            first_prefix
            + replacement
        )

        # Clear middle runs
        for middle in affected_runs[1:-1]:
            middle["run"].text = ""

        # Keep suffix in final run
        last_run.text = last_suffix

        applied += 1

    return applied


# ============================================================
# REDACTION
# ============================================================


def redact_document(
    doc,
    output_file,
    entities,
    pseudonymizer,
    document_blocks,
):
    """
    Redact validated entities from the SAME Document object
    used by build_document_map().

    The document map contains:

        start
        end
        text
        element

    for every mapped paragraph.
    """

    replacement_map = {}

    # --------------------------------------------------------
    # Store replacements for each document block
    # --------------------------------------------------------

    block_replacements = {
        id(block): []
        for block in document_blocks
    }

    # --------------------------------------------------------
    # Track entities that could not be applied
    # --------------------------------------------------------

    unmatched_entities = []

    # ========================================================
    # MATCH ENTITIES TO DOCUMENT BLOCKS
    # ========================================================

    for entity in entities:

        # ----------------------------------------------------
        # SAFETY CHECK 1
        #
        # A real entity should not contain a newline.
        #
        # NER sometimes produces things such as:
        #
        # "Shanti Gopalkrishnan\nTelephone"
        #
        # That is not a single PII value.
        # ----------------------------------------------------

        if ("\n" in entity.value or "\r" in entity.value) and entity.entity_type != "ADDRESS":

            unmatched_entities.append(
                (
                    entity,
                    "MULTILINE_ENTITY"
                )
            )

            continue

        # ----------------------------------------------------
        # SAFETY CHECK 2
        #
        # Empty / whitespace-only entities
        # ----------------------------------------------------

        if not entity.value.strip():

            unmatched_entities.append(
                (
                    entity,
                    "EMPTY_ENTITY"
                )
            )

            continue

        # ----------------------------------------------------
        # Find containing block
        # ----------------------------------------------------

        matched_block = None

        for block in document_blocks:

            if (
                entity.start >= block["start"]
                and entity.end <= block["end"]
            ):
                matched_block = block
                break

        # ----------------------------------------------------
        # No matching block
        # ----------------------------------------------------

        if matched_block is None:
            overlapping_blocks = [
                b for b in document_blocks
                if not (entity.end <= b["start"] or entity.start >= b["end"])
            ]
            if overlapping_blocks:
                replacement = pseudonymizer.get_replacement(entity.entity_type, entity.value)
                for b in overlapping_blocks:
                    slice_start = max(entity.start, b["start"])
                    slice_end = min(entity.end, b["end"])
                    local_start = slice_start - b["start"]
                    local_end = slice_end - b["start"]
                    if local_end > local_start and local_start >= 0 and local_end <= len(b["text"]):
                        block_replacements[id(b)].append((local_start, local_end, replacement))
                continue

            unmatched_entities.append(
                (
                    entity,
                    "NO_BLOCK"
                )
            )

            continue

        # ----------------------------------------------------
        # Convert global -> local position
        # ----------------------------------------------------

        local_start = (
            entity.start
            - matched_block["start"]
        )

        local_end = (
            entity.end
            - matched_block["start"]
        )

        block_text = matched_block["text"]

        # ----------------------------------------------------
        # Position safety
        # ----------------------------------------------------

        if (
            local_start < 0
            or local_end > len(block_text)
            or local_start >= local_end
        ):

            unmatched_entities.append(
                (
                    entity,
                    "INVALID_POSITION"
                )
            )

            continue

        # ----------------------------------------------------
        # EXACT TEXT VERIFICATION
        # ----------------------------------------------------

        actual_value = block_text[
            local_start:local_end
        ]

        if actual_value != entity.value:

            unmatched_entities.append(
                (
                    entity,
                    "TEXT_MISMATCH"
                )
            )

            continue

        # ----------------------------------------------------
        # Additional whitespace safety
        #
        # Don't allow an entity to silently consume a newline
        # or huge accidental span.
        # ----------------------------------------------------

        if any(
            char in entity.value
            for char in ["\n", "\r"]
        ):

            unmatched_entities.append(
                (
                    entity,
                    "INVALID_WHITESPACE"
                )
            )

            continue

        # ====================================================
        # CREATE STABLE PSEUDONYM
        # ====================================================

        replacement = pseudonymizer.get_replacement(
            entity.entity_type,
            entity.value
        )

        replacement_map[
            (
                entity.entity_type,
                entity.value
            )
        ] = replacement

        # ====================================================
        # STORE REPLACEMENT
        # ====================================================

        block_replacements[
            id(matched_block)
        ].append(
            (
                local_start,
                local_end,
                replacement
            )
        )

    # ========================================================
    # APPLY REPLACEMENTS
    # ========================================================

    successfully_applied = 0
    skipped_overlaps = 0

    for block in document_blocks:

        replacements = block_replacements[
            id(block)
        ]

        if not replacements:
            continue

        # ----------------------------------------------------
        # Sort left -> right
        # ----------------------------------------------------

        replacements = sorted(
            replacements,
            key=lambda x: (x[0], x[1])
        )

        filtered = []

        last_end = -1

        for start, end, replacement in replacements:

            if start < last_end:

                skipped_overlaps += 1

                continue

            filtered.append(
                (
                    start,
                    end,
                    replacement
                )
            )

            last_end = end

        # ----------------------------------------------------
        # Actual paragraph from SAME document
        # ----------------------------------------------------

        paragraph = block["element"]

        applied = replace_text_in_paragraph(
            paragraph,
            filtered
        )

        successfully_applied += applied

    # ========================================================
    # REPEATED ADDRESS PROPAGATION PASS
    # ========================================================

    address_pairs = []
    for (e_type, orig_val), placeholder in replacement_map.items():
        if e_type == "ADDRESS":
            clean_str = re.sub(
                r'^(?:[,\s]*India)?\s*(?:and\s+its\s+)?(?:the\s+registered\s+office\s+of\s+our\s+company\s+located\s+at|the\s+corporate\s+office\s+of\s+our\s+company\s+located\s+at|having\s+its\s+registered\s+office\s+at|registered\s+office:?|corporate\s+office:?|correspondence\s+address:?|contact\s+address:?|our\s+manufacturing\s+facility\s+located\s+at)\s*(?:at\s+)?',
                '',
                orig_val.strip(),
                flags=re.IGNORECASE
            ).strip(" :,.\n\r")
            if len(clean_str) > 8:
                address_pairs.append((clean_str, placeholder))

    # Sort address pairs by length descending so longer addresses are replaced first
    address_pairs.sort(key=lambda x: len(x[0]), reverse=True)

    def process_p(p, target_str, placeholder):
        if not p.text:
            return 0
        pattern = re.compile(re.escape(target_str), re.IGNORECASE)
        matches = list(pattern.finditer(p.text))
        if matches:
            repls = [(m.start(), m.end(), placeholder) for m in matches]
            return replace_text_in_paragraph(p, repls)
        return 0

    def process_table_obj(table, target_str, placeholder):
        cnt = 0
        for r in table.rows:
            for c in r.cells:
                for p in c.paragraphs:
                    cnt += process_p(p, target_str, placeholder)
                for nested_t in c.tables:
                    cnt += process_table_obj(nested_t, target_str, placeholder)
        return cnt

    for clean_str, placeholder in address_pairs:
        # Body paragraphs
        for p in doc.paragraphs:
            process_p(p, clean_str, placeholder)
        # Tables & nested tables
        for t in doc.tables:
            process_table_obj(t, clean_str, placeholder)
        # Headers & footers
        for s in doc.sections:
            for p in s.header.paragraphs:
                process_p(p, clean_str, placeholder)
            for t in s.header.tables:
                process_table_obj(t, clean_str, placeholder)
            for p in s.footer.paragraphs:
                process_p(p, clean_str, placeholder)
            for t in s.footer.tables:
                process_table_obj(t, clean_str, placeholder)

    # ========================================================
    # SAVE
    # ========================================================

    doc.save(output_file)

    # ========================================================
    # RETURN RESULT
    # ========================================================

    return {
        "replacement_map": replacement_map,
        "successfully_applied": successfully_applied,
        "unmatched_entities": unmatched_entities,
        "skipped_overlaps": skipped_overlaps,
    }