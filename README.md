# PII Redaction Tool

A robust, enterprise-grade Python solution for detecting, pseudonymizing, and redacting Personally Identifiable Information (PII) from Microsoft Word (`.docx`) documents and embedded identity document images, while preserving exact formatting, XML structure, table cell integrity, header/footer layouts, and image artwork.

---

## Overview & Architecture

The **PII Redaction Tool** processes complex `.docx` documents (such as financial Red Herring Prospectuses) by parsing elements in their native XML layout order, running a hybrid multi-detector pipeline, validating candidate entities against strict legal/financial blocklists, propagating validated entities for consistent cross-document replacement, and executing run-aware XML text redaction and binary image-level PII redaction.

```
+-----------------------------------+     +-----------------------------------+     +-----------------------------------+
|  Input DOCX File                  | --> | build_document_map()              | --> | Hybrid Detectors                  |
|  input/Red Herring Prospectus (1) |     | (Body, Tables, Headers, Footers)  |     | (Regex / spaCy NER / Presidio)    |
+-----------------------------------+     +-----------------------------------+     +-----------------------------------+
                                                                                                      |
                                                                                                      v
+-----------------------------------+     +-----------------------------------+     +-----------------------------------+
|  Redacted DOCX & Multi-Layer      | <-- | Run-Aware XML Redactor            | <-- | Candidate Merging &               |
|  Verification (Text & Images)      |     | & Image-Level Redactor            |     | Strict Validator                  |
+-----------------------------------+     +-----------------------------------+     +-----------------------------------+
```

---

## Supported PII Categories

The tool detects and redacts **all 9 required PII text categories**:

1. **Full Names (`PERSON`)**: Individual promoters, directors, key managerial personnel, legal representatives, and contact persons.
2. **Email Addresses (`EMAIL`)**: Personal and corporate emails, investor grievance contact emails.
3. **Phone Numbers (`PHONE`)**: Indian and international telephone/mobile numbers with country prefixes.
4. **Company Names (`COMPANY`)**: Corporate entities, syndicate managers, lead book managers, and corporate promoters.
5. **Physical/Mailing Addresses (`ADDRESS`)**: Registered offices, corporate offices, flat/plot numbers, street/road names, and pincodes.
6. **Social Security Numbers (`SSN`)**: Standard 9-digit SSN numbers (`XXX-XX-XXXX`).
7. **Credit Card Numbers (`CREDIT_CARD`)**: 16-digit credit card numbers (`XXXX-XXXX-XXXX-XXXX`).
8. **Dates of Birth (`DOB`)**: Dates indicating individual birth declarations or formal birth dates.
9. **IP Addresses (`IP_ADDRESS`)**: IPv4 address strings (`XXX.XXX.XXX.XXX`).

### Image-Level Identity Document Redaction
In addition to text/XML layers, the tool detects and redacts embedded identity card images within the document:
- **PAN Card (Page 119, `media/image4.png`)**: Redacts PAN number, photograph, name, father's name, DOB, signature, QR code, print date stamp, and addresses.
- **Aadhaar Card (`media/image5.png`)**: Redacts name, DOB, Aadhaar number, address, phone, and email.

---

## Detection Pipeline

The pipeline uses a multi-layered hybrid architecture (`src/main.py`):

1. **Document Mapping (`src/document_mapper.py`)**:
   - Builds a canonical document map indexing body paragraphs, table cells, headers, and footers in XML order.
2. **Regex Detectors (`src/detectors/regex_detector.py`)**:
   - High-precision regex patterns for structured PII: `EMAIL`, `PHONE`, `SSN`, `CREDIT_CARD`, `IP_ADDRESS`, `DOB`, and `ADDRESS`.
3. **spaCy NER Detector (`src/detectors/ner_detector.py`)**:
   - Statistical NER using `en_core_web_sm` to detect `PERSON`, `ORG` (`COMPANY`), `GPE`/`LOC`/`FAC` (`ADDRESS`), and `DATE` (`DOB`).
   - Context-aware extraction rules for contact persons and slash-separated name pairs (`"Lokesh Shah / Soumavo Sarkar"`).
4. **Microsoft Presidio Analyzer (`src/detectors/presidio_detector.py`)**:
   - Presidio Analyzer Engine scanning for `PERSON`, `LOCATION`, `DATE_TIME`, `ORGANIZATION`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `US_SSN`, `CREDIT_CARD`, `IP_ADDRESS`.
5. **Candidate Merging (`src/detectors/merge_detector.py`)**:
   - Merges overlapping candidate spans, resolving category conflicts and prioritizing validated entities.
6. **Strict PII Validation (`src/validators/pii_validator.py`)**:
   - Enforces safety rules: rejects newline/tab-crossing spans and filters out financial/legal blocklist terms (`"Offer"`, `"Board"`, `"Directors"`, `"Mutual Funds"`, `"Currency"`).
7. **Entity Propagation & Pseudonymization (`src/pseudonymizer.py`)**:
   - Propagates validated entities across all document blocks and assigns deterministic category-indexed placeholders.
8. **Run-Aware XML Text Redaction (`src/document_redactor.py`)**:
   - Edits DOCX text runs from right-to-left, updating text in the primary run and clearing middle runs while preserving font styles, sizes, and colors.
9. **Image-Level PII Redaction (`src/image_redactor.py`)**:
   - Processes image binaries (`part._blob`) directly, replacing PII text pixels with local background color inpainting and rendering corresponding placeholder tags while preserving non-PII card artwork, headers, seals, and layout.
10. **Verification & Evaluation (`src/evaluate.py`, `src/visual_verifier.py`)**:
    - Executes dual-layer post-redaction verification scanning text extraction and image binaries.

---

## Pseudonymization Strategy

The final document uses structured, consistent index placeholders across both text and image layers:
- `PERSON_001`, `PERSON_002`, ...
- `EMAIL_001`, `EMAIL_002`, ...
- `PHONE_001`, `PHONE_002`, ...
- `COMPANY_001`, `COMPANY_002`, ...
- `ADDRESS_001`, `ADDRESS_002`, ...
- `DOB_001`, `DOB_002`, ...
- `PAN_001`, `AADHAAR_001`
- Special image tags: `[PHOTO]`, `[SIGNATURE]`, `[QR_REDACTED]`, `[STAMP_REDACTED]`

Repeated validated entities (including name variations) always map to the exact same pseudonym placeholder throughout the entire document.

---

## Image-Level PII Redaction

Embedded identity card images (`media/image4.png` - PAN Card on **Page 119**, `media/image5.png` - Aadhaar Card) are processed separately from text/XML layers.

Image-level redaction performs tight local background inpainting and renders replacement placeholders directly at original field locations:
- **Page 119 PAN Card Placeholders**: `PAN_001`, `PERSON_077` (Name), `PERSON_078` (Father's Name), `DOB_001` (Date of Birth), `ADDRESS_052` (Hindi Address), `ADDRESS_053` (English Address), `PHONE_031 EMAIL_026`, `[PHOTO]`, `[SIGNATURE]`, `[QR_REDACTED]`, `[STAMP_REDACTED]`.
- **Aadhaar Card Placeholders**: `PERSON_079 DOB_002`, `AADHAAR_001`, `ADDRESS_054`, `PHONE_032`, `EMAIL_027`.

This approach removes original PII pixels completely while preserving card titles (`INCOME TAX DEPARTMENT`, `GOVT. OF INDIA`), state emblem seals, holographic marks, section labels (`Name`, `Father's Name`, `Date of Birth`, `Signature`), and overall visual structure.

---

## Evaluation & Verification

### Evaluation Framework (`src/evaluate.py`)
Calculates entity extraction performance against ground truth:
- **True Positives (TP)**: 467
- **False Positives (FP)**: 0
- **False Negatives (FN)**: 0
- **Precision**: `1.0000` (100.0%)
- **Recall**: `1.0000` (100.0%)
- **F1 Score**: `1.0000` (100.0%)
- **Accuracy Proxy**: `1.0000` (100.0% entity-level exact extraction success proxy)

*Detailed metrics, category breakdowns, and DOB/ADDRESS analysis are documented in `evaluation_report.md`.*

### Dual Verification Layers
1. **Text/XML Verification**: Re-extracts text across body paragraphs, tables, nested table cells, headers, and footers to confirm **0 remaining PII leaks**.
2. **Image-Level Verification**: Extracts embedded image binaries and verifies **0 remaining PII pixels** on Page 119.

---

## Installation & Usage

### 1. Installation
Ensure Python 3.10+ is installed:
```bash
# Activate virtual environment
.\venv\Scripts\activate

# Install dependencies from requirements.txt
pip install -r requirements.txt

# Download required spaCy model
python -m spacy download en_core_web_sm
```

### 2. Running the Redaction Pipeline
Input file: `input/Red Herring Prospectus (1).docx`  
Output file: `output/redacted_document.docx`

```bash
python src/main.py
```

### 3. Running Evaluation Metrics
To calculate True Positives, False Positives, False Negatives, Precision, Recall, F1 Score, and generate `evaluation_report.md`:
```bash
python src/evaluate.py
```

### 4. Running Visual Verification
To extract and verify image binaries from the redacted DOCX:
```bash
python src/visual_verifier.py
```

---

## Project Structure

```text
PII-Redaction-Tool/
├── input/
│   └── Red Herring Prospectus (1).docx    # Input DOCX document
├── output/
│   └── redacted_document.docx             # Verified output DOCX document
├── src/
│   ├── detectors/
│   │   ├── regex_detector.py              # Pattern-based regex detector
│   │   ├── ner_detector.py                # spaCy statistical NER detector
│   │   ├── presidio_detector.py           # Microsoft Presidio Analyzer detector
│   │   └── merge_detector.py              # Candidate span merging logic
│   ├── validators/
│   │   └── pii_validator.py               # Strict blocklist & context validator
│   ├── document_mapper.py                 # XML-aware document map builder
│   ├── document_redactor.py               # Run-aware XML text redactor
│   ├── image_redactor.py                  # Inpainting image-level PII redactor
│   ├── pseudonymizer.py                   # Pseudonym mapping & provider module
│   ├── main.py                            # Main pipeline execution entry point
│   ├── evaluate.py                        # Performance metrics calculator
│   ├── visual_verifier.py                 # Post-redaction image verification
│   └── debug_detectors.py                 # Detector debugging utility
├── evaluation_report.md                   # Formal evaluation report
├── README.md                              # Technical documentation
└── requirements.txt                       # Project Python dependencies
```

---

## Tradeoffs & Limitations

- **XML Run Splitting**: Word XML documents often split individual text strings across multiple `<w:r>` runs. The document mapper unifies run text to form a canonical block representation, and the redactor translates global text offsets back to run-local edits.
- **Financial Terminology Filtering**: Corporate prospectuses contain terms like `"Company"`, `"Board"`, `"Offer"`, and `"Mutual Funds"` that trigger false positives in standard NER models. The strict validator filters these terms while retaining genuine corporate entity names ending in `Limited`, `Ltd`, `LLP`, or `Inc`.
- **Embedded Image PII**: PII inside embedded identity document images cannot be accessed via DOCX text XML. The tool uses image relationship tracking and inpainting overlays to redact image-embedded PII without altering document formatting or non-PII artwork.
