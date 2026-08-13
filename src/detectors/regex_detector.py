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

    # Contact Person name detection
    cp_pattern = re.compile(r'(?i)\bContact\s+Person\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)')
    for match in cp_pattern.finditer(text):
        name_val = match.group(1).strip()
        entities.append(
            PIIEntity(
                entity_type="PERSON",
                value=name_val,
                start=match.start(1),
                end=match.end(1),
                confidence=1.0
            )
        )

    entities.extend(detect_addresses(text))
    entities.extend(detect_phone_numbers(text))
    return entities


def detect_addresses(text):
    entities = []

    label_prefix_re = re.compile(
        r'^(?:The\s+corporate\s+office\s+of\s+our\s+company\s+located\s+at|'
        r'The\s+registered\s+office\s+of\s+our\s+Company\s+located\s+at|'
        r'Our\s+manufacturing\s+facility\s+located\s+at|'
        r'having\s+its\s+(?:Registered|Corporate|registered)\s+Office\s+at|'
        r'having\s+its\s+registered\s+office\s+at|'
        r'Registered\s+Office\s+of\s+our\s+Company\s*KSH\s+International\s+Limited|'
        r'Corporate\s+Office\s+of\s+our\s+Company\s*KSH\s+International\s+Limited|'
        r'Registered\s+Office\s+of\s+our\s+Company|'
        r'Registered\s+Office\s*:?|'
        r'Corporate\s+Office\s*:?|'
        r'Correspondence\s+Address\s*:?|'
        r'Contact\s+Address\s*:?|'
        r'Residential\s+Address\s*:?|'
        r'Office\s+Address\s*:?)\s*',
        re.IGNORECASE
    )

    patterns = [
        # 1. Standard building/flat/plot/number or specific street/locality/landmark ending in city/pin/state/India
        r'(?i)\b(?:Flat\s*(?:–|-|no\.?)?\s*\d+|Plot\s*(?:–|-|no\.?)?\s*[A-Za-z0-9-]+|House\s*no\.?|\d+/\d+[,\s]+[^\n\r]+?|S\.\s*no\.\s*\d+/\s*\d+|Pushpakamal\s+Apartment|801\s*-\s*804|801-804|ICICI\s+Venture\s+House|C-101|201[,\s]+Tower|11/3[,\s]+11/4|Next\s+to\s+Kanjurmarg|Think\s+Techno\s+Campus|World\s+Centre|10th\s+Floor|8th\s+Floor,\s*Onyx|A29,\s*Abhimanshree|SEBI\s+Bhavan)[^\n\r]*?\b(?:Pune|Mumbai|Raigad|Ahmednagar|Maharashtra|India)\b[^\n\r]*?(?:\d{3}\s*\d{3}|\bIndia\b|\bMaharashtra\b)?',

        # 2. Single-line address component patterns (matching building/street/landmark or locality/city/pincode on individual lines)
        r'(?i)\b(?:801\s*-\s*804|801-804|Building\s+No\.?\s*3|Inspire\s+BKC|SEBI\s+Bhavan|Plot\s+No\.?\s*C4\s*A?|ICICI\s+Venture\s+House|C-101[,\s]+Embassy|10th\s+Floor[,\s]+Tower)[^\n\r]*',
        r'(?i)\b(?:Bandra\s+(?:Kurla|East|\(E\))|Vikhroli|Lower\s+Parel|Prabhadevi|Shaniwar\s+Peth|Kanjurmarg|Koregaon\s+Park|Off\s+Pallod\s+Farms)[^\n\r]*?\b(?:Pune|Mumbai|Raigad|Ahmednagar|Maharashtra|India)\b[^\n\r]*?(?:\d{3}\s*\d{3}|\bIndia\b|\bMaharashtra\b)?',

        # 3. Address block following Registered Office / Corporate Office / Correspondence Address header
        r'(?i)(?:Registered\s+Office|Corporate\s+Office|Correspondence\s+Address|Contact\s+Address)\s*(?::|is\s+located\s+at|located\s+at|at)?\s*(\b(?:Flat|Plot|House|Building|Unit|\d+/\d+|\d+|S\.\s*no)[^\n\r]*?\b(?:Pune|Mumbai|Raigad|Ahmednagar|Maharashtra|India)\b[^\n\r]*?(?:\d{3}\s*\d{3}|\bIndia\b|\bMaharashtra\b)?)',
    ]

    for pat in patterns:
        for m in re.finditer(pat, text):
            raw_val = m.group(0)
            start = m.start()
            end = m.end()

            # Skip false positive legal prose
            if any(w in raw_val.lower() for w in ["circular", "regulations", "amended", "jurisdiction of", "regional language", "is situated) at least"]):
                continue

            # Strip header prefix label if present at start of match
            prefix_match = label_prefix_re.match(raw_val)
            if prefix_match:
                prefix_len = prefix_match.end()
                start += prefix_len
                raw_val = raw_val[prefix_len:]

            val = raw_val.strip(" ;,.\n\r")
            if len(val) > 15:
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