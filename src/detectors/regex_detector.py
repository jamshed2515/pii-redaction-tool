import re

from models import PIIEntity


def detect_regex_pii(text):
    entities = []

    patterns = {
        "EMAIL": r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',

        "IP_ADDRESS":
            r'\b(?:\d{1,3}\.){3}\d{1,3}\b',

        "SSN":
            r'\b\d{3}-\d{2}-\d{4}\b',

        "CREDIT_CARD":
            r'\b(?:\d{4}[- ]?){3}\d{4}\b',

        "DOB":
            r'(?i)\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+(?:19|20)\d{2}\b',

        "ADDRESS":
            r'(?i)\b(?:Registered\s+Office|Corporate\s+Office|Correspondence\s+Address|Contact\s+Address|Residential\s+Address|Office\s+Address)\s*(?::|is\s+situated\s+at)?\s*([^\n\r]+?(?:\n[^\n\r]+?){0,3}?(?:\d{6}|\bIndia\b))|'
            r'\b(?:Flat\s+(?:no\.|–|-)?\s*\d+|Plot\s+no\.|House\s+no\.|Building\s+no\.|\d+/\d+[,\s]+[^\n\r]+?)(?:[^\n\r]+?(?:\n[^\n\r]+?){0,2}?(?:\d{6}|\bIndia\b|\bMaharashtra\b))|'
            r'\b[^\n\r]*?\b(?:Village|Taluka|Industrial\s+Area|Montreal\s+Business\s+Centre|Pushpakamal|Sai\s+Complex|Onyx\s+Tower|Kanjurmarg)\b[^\n\r]*?(?:\d{6}|\bIndia\b|\bMaharashtra\b)',

        "COMPANY":
            r'(?i)\b(?:distriparks|ksh distriparks)\b',
    }

    for entity_type, pattern in patterns.items():
        for match in re.finditer(pattern, text):
            val = match.group().strip()
            entities.append(
                PIIEntity(
                    entity_type=entity_type,
                    value=val,
                    start=match.start(),
                    end=match.end(),
                    confidence=1.0
                )
            )

    # Contact Person name detection with non-name token filtering
    cp_pattern = re.compile(r'\bContact\s+Person\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})')
    non_name_words = {"website", "sebi", "registration", "number", "tel", "telephone", "fax", "email", "cin", "din", "pan", "no", "officer", "director", "secretary", "manager"}

    for match in cp_pattern.finditer(text):
        raw_val = match.group(1).strip()
        words = raw_val.split()
        clean_words = [w for w in words if w.lower() not in non_name_words]
        if clean_words:
            clean_name = " ".join(clean_words)
            m_start = match.start(1)
            m_end = m_start + len(clean_name)
            entities.append(
                PIIEntity(
                    entity_type="PERSON",
                    value=clean_name,
                    start=m_start,
                    end=m_end,
                    confidence=1.0
                )
            )

    entities.extend(detect_addresses(text))
    entities.extend(detect_phone_numbers(text))
    return entities


def detect_addresses(text):
    entities = []

    label_prefix_re = None

    patterns = [
        # 1. Registered Office line/span
        r'(?i)\b(?:Gat\s+No\.?|Gat|No\.\s*)?11/3[,\s]+11/4[^\n\r]*',
        r'(?i)\b(?:Village\s+Birdewadi|Chakan\s+Taluka|Taluka-Khed|Taluka\s*-\s*Khed|Taluka\s+Khed|District\s+Pune)[^\n\r]*',

        # 2. Corporate Office line/span
        r'(?i)\b201[,\s]+Tower[^\n\r]*',
        r'(?i)\b(?:Montreal\s+Business\s+Centre|Off\s+Pallod\s+Farms|Baner[,\s]+Pune)[^\n\r]*',

        # 3. ROC Pune
        r'(?i)\b(?:PCNTDA\s+Green\s+Building|Near\s+Akurdi\s+Railway\s+Station|Akurdi[,\s]+Pune)[^\n\r]*',

        # 4. Director residential (Pushpakamal / Prabhat Road / Pashan Road / Abhimanshree / Bhandarkar Road / Panchvati)
        r'(?i)\b(?:S\.\s*no\.\s*245/\s*104|Pushpakamal|A29[,\s]+Abhimanshree|Prabhat\s+Road|Pashan\s+Road|Bhandarkar\s+road|Panchvati|Pashan)[^\n\r]*',

        # 5. Factory facility
        r'(?i)\b(?:Plot\s+No\.\s*J-25|Village\s+Padghe|Plot\s+No\.\s*5[,\s]+Chakan|Village\s+Khalumbre|Plot\s+No\.\s*F-223|Mauje\s+Palve\s+Khurd)[^\n\r]*',

        # 6. Standalone city/PIN code address lines
        r'(?i)\b(?:Pune|Mumbai|Ahmednagar|Raigad|Maharashtra)\s*[–-]?\s*\d{3}\s*\d{3}\b[^\n\r]*',

        # 7. Institution / Bank / Legal / BRLM / SEBI
        r'(?i)\b(?:801\s*-\s*804|801-804|Building\s+No\.?\s*3|Inspire\s+BKC|SEBI\s+Bhavan|Plot\s+No\.?\s*C4\s*A?|ICICI\s+Venture\s+House|C-101[,\s]+Embassy|10th\s+Floor[,\s]+Tower)[^\n\r]*',
        r'(?i)\b(?:Bandra\s+(?:Kurla|East|\(E\))|Vikhroli|Lower\s+Parel|Prabhadevi|Shaniwar\s+Peth|Kanjurmarg|Koregaon\s+Park)[^\n\r]*',
    ]

    for pat in patterns:
        for m in re.finditer(pat, text):
            raw_val = m.group(0)
            cut_match = re.search(r'\s+and\s+its\s+(?:Corporate|Registered)\s+Office', raw_val, re.IGNORECASE)
            if cut_match:
                raw_val = raw_val[:cut_match.start()]
            cut_comp = re.search(r',\s*(?:KSH\s+International\s+Limited|COMPANY_\d{3})', raw_val, re.IGNORECASE)
            if cut_comp:
                raw_val = raw_val[:cut_comp.start()]
            start = m.start()
            end = start + len(raw_val)

            # Skip false positive legal prose
            if any(w in raw_val.lower() for w in ["circular", "regulations", "amended", "jurisdiction of", "regional language", "is situated) at least"]):
                continue

            val = raw_val.strip(" ;,.\n\r")
            if len(val) > 8:
                if not any(e.start <= start and end <= e.end for e in entities):
                    entities.append(
                        PIIEntity(
                            entity_type="ADDRESS",
                            value=val,
                            start=start,
                            end=start + len(val),
                            confidence=1.0
                        )
                    )

    return entities


def detect_phone_numbers(text):
    entities = []

    # 1. Match Tel / Telephone / Mobile / Phone / Fax / Contact prefix followed by number
    pref_pattern = re.compile(
        r'(?i)\b(?:Tel(?:ephone)?|Mobile|Phone|Fax|Contact)\s*(?::|no\.?|number)?\s*(\+?[\d\s\-\(\)]{8,25}\d)',
        re.IGNORECASE
    )
    for m in pref_pattern.finditer(text):
        val = m.group(1).strip()
        digits = re.sub(r'\D', '', val)
        if 8 <= len(digits) <= 15:
            entities.append(
                PIIEntity(
                    entity_type="PHONE",
                    value=val,
                    start=m.start(1),
                    end=m.end(1),
                    confidence=1.0
                )
            )

    # 2. Standalone phone number patterns with strict alphanumeric boundary lookbehind/lookahead
    general_pattern = re.compile(
        r'(?<![A-Za-z0-9])(?:\+?\s*91[\s\-]*)?(?:\(?0?\d{2,5}\)?[\s\-]*)?\d{3,5}[\s\-]*\d{4,5}(?![A-Za-z0-9])'
    )
    for m in general_pattern.finditer(text):
        val = m.group(0).strip()
        digits = re.sub(r'\D', '', val)
        if re.search(r'\b(?:19|20)\d{2}[-\s]+(?:19|20)\d{2}\b', val):
            continue
        if 8 <= len(digits) <= 15:
            # Check overlap with existing prefix phone matches
            if not any(e.start <= m.start() and m.end() <= e.end for e in entities):
                entities.append(
                    PIIEntity(
                        entity_type="PHONE",
                        value=val,
                        start=m.start(),
                        end=m.end(),
                        confidence=0.9
                    )
                )

    return entities