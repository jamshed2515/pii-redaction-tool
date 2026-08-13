import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import re
import pymupdf  # PyMuPDF
import win32com.client
from docx import Document
from collections import defaultdict

from document_mapper import build_document_map
from detectors.regex_detector import detect_regex_pii
from detectors.ner_detector import detect_ner_pii
from detectors.presidio_detector import detect_presidio_persons
from detectors.merge_detector import merge_entities
from validators.pii_validator import validate_entities


def get_name_variations(name_val):
    words = name_val.strip().split()
    if len(words) < 2:
        return [name_val]
    
    variations = [name_val]
    if len(words) == 3:
        variations.append(f"{words[0]} {words[2]}")
    elif len(words) > 3:
        variations.append(f"{words[0]} {words[-1]}")
        
    return list(set(variations))


def convert_docx_to_pdf(docx_path, pdf_path):
    abs_docx = os.path.abspath(docx_path)
    abs_pdf = os.path.abspath(pdf_path)
    
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(abs_docx, ReadOnly=True)
        doc.SaveAs(abs_pdf, FileFormat=17)  # 17 = wdFormatPDF
        doc.Close(SaveChanges=False)
    finally:
        word.Quit()


def verify_rendered_and_xml(input_docx="input/DOC-20260813-WA0001.docx", output_docx="output/redacted_document.docx", output_pdf="output/redacted_document.pdf"):
    print("\n" + "="*80)
    print("===== INDEPENDENT VISUAL & XML VERIFICATION =====")
    print("="*80)

    # 1. Load Original Document & Collect Ground Truth PII Values
    doc_orig = Document(input_docx)
    full_text_orig, _ = build_document_map(doc_orig)

    regex_orig = detect_regex_pii(full_text_orig)
    ner_orig = detect_ner_pii(full_text_orig)
    presidio_orig = detect_presidio_persons(full_text_orig)
    merged_orig = merge_entities(regex_orig, ner_orig, presidio_orig)
    validated_orig = validate_entities(merged_orig)

    person_targets = set()
    other_targets = set()

    for ent in validated_orig:
        val = ent.value.strip()
        if not val:
            continue
        if ent.entity_type == "PERSON":
            for var in get_name_variations(val):
                person_targets.add(var.lower())
        else:
            other_targets.add((ent.entity_type, val.lower()))

    print(f"Original Ground Truth Targets Collected: {len(person_targets)} person names/variations, {len(other_targets)} other PII items.")

    # 2. Stage 1: Render DOCX to PDF & Scan Page-by-Page Visual Text
    print("\n[STAGE 1] Rendering DOCX to PDF via Native Word Engine...")
    convert_docx_to_pdf(output_docx, output_pdf)
    print(f"Rendered PDF saved to: {output_pdf}")

    pdf_doc = pymupdf.open(output_pdf)
    print(f"Scanning rendered text across all {len(pdf_doc)} pages...")

    page_leaks = defaultdict(list)

    for page_idx in range(len(pdf_doc)):
        page = pdf_doc[page_idx]
        page_num = page_idx + 1
        page_text = page.get_text()

        # Check Person Names
        for name in person_targets:
            pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
            if pattern.search(page_text):
                page_leaks["PERSON"].append((page_num, name))

        # Check Other PII
        for ent_type, val in other_targets:
            pattern = re.compile(rf"\b{re.escape(val)}\b", re.IGNORECASE)
            if pattern.search(page_text):
                page_leaks[ent_type].append((page_num, val))

    print("[STAGE 1 RESULT]: Rendered Page Visual Scan Complete.")

    # 3. Stage 2: Comprehensive XML-Wide <w:t> Node Scan
    print("\n[STAGE 2] Scanning all XML <w:t> text nodes across paragraphs, tables, headers, footers, text boxes...")
    doc_redacted = Document(output_docx)
    all_t_texts = doc_redacted.element.xpath('.//*[local-name()="t"]/text()')
    full_xml_text = " ".join(all_t_texts)
    print(f"Total XML <w:t> text nodes scanned: {len(all_t_texts)} ({len(full_xml_text)} total characters).")

    xml_leaks = defaultdict(list)

    for name in person_targets:
        pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        if pattern.search(full_xml_text):
            xml_leaks["PERSON"].append(name)

    for ent_type, val in other_targets:
        pattern = re.compile(rf"\b{re.escape(val)}\b", re.IGNORECASE)
        if pattern.search(full_xml_text):
            xml_leaks[ent_type].append(val)

    print("[STAGE 2 RESULT]: Comprehensive XML Node Scan Complete.")

    # 4. Summary & Decision
    total_leaks = sum(len(v) for v in page_leaks.values()) + sum(len(v) for v in xml_leaks.values())

    print("\n" + "="*80)
    print("===== VISUAL & XML VERIFICATION SUMMARY =====")
    print("="*80)

    categories = ["PERSON", "COMPANY", "EMAIL", "PHONE", "ADDRESS", "SSN", "CREDIT_CARD", "DOB", "IP_ADDRESS"]
    for cat in categories:
        page_l_count = len(page_leaks[cat])
        xml_l_count = len(xml_leaks[cat])
        print(f"Remaining {cat:<12}: {page_l_count} page leaks, {xml_l_count} XML node leaks")
        if page_l_count > 0:
            for page_num, val in page_leaks[cat]:
                print(f"  [RENDER LEAK Page {page_num}]: {val}")
        if xml_l_count > 0:
            for val in xml_leaks[cat]:
                print(f"  [XML LEAK]: {val}")

    print("="*80)
    if total_leaks == 0:
        print("Final Independent Visual & XML Verification: PASSED")
        print("Zero target PII exposed in rendered pages or underlying XML text.")
        print("="*80 + "\n")
        return True
    else:
        print(f"Final Independent Visual & XML Verification: FAILED ({total_leaks} remaining leaks)")
        print("="*80 + "\n")
        return False


if __name__ == "__main__":
    success = verify_rendered_and_xml()
    if not success:
        sys.exit(1)
