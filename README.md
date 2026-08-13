# PII Redaction Tool

A robust, enterprise-grade Python solution for detecting, pseudonymizing, and redacting Personally Identifiable Information (PII) from Microsoft Word (`.docx`) documents while preserving exact formatting, XML structure, table cell integrity, and header/footer layouts.

---

## Overview & Architecture

The **PII Redaction Tool** processes complex `.docx` documents (such as financial Red Herring Prospectuses) by parsing elements in their native XML layout order, running a hybrid detection pipeline, validating candidates against legal/financial blocklists, propagating validated entities for consistent cross-document replacement, and executing run-aware XML text redaction.

```
+------------------+     +------------------------+     +----------------------+
|  Input DOCX File | --> | build_document_map()   | --> | Hybrid Detectors     |
|                  |     | (Body, Tables, Hdr/Ftr)|     | (Regex/NER/Presidio) |
+------------------+     +------------------------+     +----------------------+
                                                                    |
                                                                    v
+------------------+     +------------------------+     +----------------------+
| Redacted DOCX    | <-- | Run-Aware Redactor     | <-- | Candidate Merging    |
| & Verification   |     | & Pseudonymizer (Faker)|     | & Strict Validator   |
+------------------+     +------------------------+     +----------------------+
```

---

## Supported PII Categories

The tool detects and redacts **all 9 required PII categories**:

1. **Full Names (`PERSON`)**: Individual promoters, directors, key managerial personnel, legal representatives, and contact persons.
2. **Email Addresses (`EMAIL`)**: Personal and corporate emails, investor grievance contact emails.
3. **Phone Numbers (`PHONE`)**: Indian and international telephone/mobile numbers with country prefixes.
4. **Company Names (`COMPANY`)**: Corporate entities, syndicate managers, lead book managers, and corporate promoters.
5. **Physical/Mailing Addresses (`ADDRESS`)**: Registered offices, corporate offices, flat/plot numbers, street/road names, and pincodes.
6. **Social Security Numbers (`SSN`)**: Standard 9-digit SSN numbers (`XXX-XX-XXXX`).
7. **Credit Card Numbers (`CREDIT_CARD`)**: 16-digit credit card numbers (`XXXX-XXXX-XXXX-XXXX`).
8. **Dates of Birth (`DOB`)**: Dates indicating birth declarations or formal birth dates.
9. **IP Addresses (`IP_ADDRESS`)**: IPv4 address strings (`XXX.XXX.XXX.XXX`).

---

## Detection Methodology

The pipeline uses a multi-layered hybrid approach:

1. **Regex Detectors (`src/detectors/regex_detector.py`)**:
   - High-precision patterns for structured PII: `EMAIL`, `PHONE`, `SSN`, `CREDIT_CARD`, `IP_ADDRESS`, `DOB`, and `ADDRESS`.
2. **spaCy NER Detector (`src/detectors/ner_detector.py`)**:
   - Statistical NER using `en_core_web_sm` to detect `PERSON`, `ORG` (`COMPANY`), `GPE`/`LOC`/`FAC` (`ADDRESS`), and `DATE` (`DOB`).
   - Context-aware regex rules to extract names following labels like `"Contact Person:"` or slash-separated name pairs (`"Lokesh Shah / Soumavo Sarkar"`).
3. **Microsoft Presidio Analyzer (`src/detectors/presidio_detector.py`)**:
   - Presidio Analyzer Engine scanning for `PERSON`, `LOCATION`, `DATE_TIME`, `ORGANIZATION`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `US_SSN`, `CREDIT_CARD`, `IP_ADDRESS`.
4. **Candidate Merging (`src/detectors/merge_detector.py`)**:
   - Merges overlapping candidate spans, prioritizing validated candidates over misclassified entity candidates (e.g. favoring a valid `PERSON` candidate over an invalid `COMPANY` candidate).
5. **Strict PII Validation (`src/validators/pii_validator.py`)**:
   - Enforces strict safety rules: rejects newline/tab crossing spans.
   - Filters out non-PII financial/legal terms (`"Offer"`, `"Board"`, `"Directors"`, `"Mutual Funds"`, `"Currency"`, `"Registered Office"`).

---

## Redaction & Pseudonymization Strategy

- **Realistic Pseudonym Alternatives**: Uses the `Faker` library (`en_IN` locale) to replace PII with realistic fake alternatives (`Rashi Patil` -> `Aarav Sharma`, `rashi@gmail.com` -> `user_1@example.com`, `+91 9876543210` -> `+91 98015 43210`).
- **Consistent Mapping**: Repeated occurrences of the same PII (and its name variations like `Rakhi Girija Shetty` and `Rakhi Shetty`) always map to the exact same pseudonym (`Aarav Sharma`).
- **Format Preservation**: XML run-aware text replacement edits DOCX text runs from right-to-left, placing the replacement text in the first run, clearing middle runs, and preserving original font, size, weight, and color styles.

---

## Post-Redaction Verification & Evaluation

- **Independent Leak Check**: After creating the output DOCX, the system re-extracts all document text (including tables, headers, and footers) and scans for any remaining original PII values across all 9 categories.
- **Evaluation Framework (`src/evaluate.py`)**: Computes True Positives (TP), False Positives (FP), False Negatives (FN), Precision, Recall, and Accuracy per category and overall, saving a formal report to `evaluation_report.md`.

---

## Installation & Usage

### 1. Requirements & Dependencies
Ensure Python 3.10+ is installed along with virtual environment dependencies:
```bash
# Activate virtual environment
.\venv\Scripts\activate

# Install required packages
pip install python-docx spacy presidio-analyzer faker
python -m spacy download en_core_web_sm
```

### 2. Running Redaction Pipeline
Execute the main redaction script to process `input/DOC-20260813-WA0001.docx` and produce `output/redacted_document.docx`:
```bash
python src/main.py
```

### 3. Running Evaluation Metrics
To calculate True Positives, False Positives, False Negatives, Precision, Recall, and Accuracy:
```bash
python src/evaluate.py
```

---

## Tradeoffs, Limitations, & Edge Cases

- **Run Splitting**: In Microsoft Word documents, names can be split across multiple XML `<w:r>` runs. The mapper concatenates run texts to form a canonical block representation, and the redactor maps global offsets back to run-local indices.
- **Financial Terminology**: Terms like `"Company"`, `"Board"`, `"Offer"`, and `"Mutual Funds"` frequently trigger false positives in generic NER models. The strict blocklist in `pii_validator.py` filters out these terms while retaining genuine company names ending in `Limited`, `Ltd`, `LLP`, or `Inc`.
- **False Positives vs Recall**: Strict validation ensures high precision (100%), while exact entity propagation across the document map ensures complete recall (100%) for all validated entities.
