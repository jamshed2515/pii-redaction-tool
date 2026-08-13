import re


PERSON_BLOCKLIST = {
    "offer",
    "board",
    "directors",
    "promoters",
    "company",
    "currency",
    "fiscals",
    "supa",
    "scrr",
    "scra",
    "reference rate",
    "selling shareholder",
    "key managerial personnel",
    "mutual funds",
    "bidder",
    "upi bidders",
    "bid amount",
    "pre-offer",
    "secondary transfer",
    "mauje palve khurd",
    "bapat marg",
}


PERSON_INVALID_WORDS = {
    "taluka",
    "khed",
    "facility",
    "park",
    "private",
    "limited",
    "ltd",
    "corporation",
    "company",
    "industrial",
    "shareholder",
    "bidder",
    "bidders",
    "amount",
    "related",
    "funds",
    "complex",
    "east",
    "west",
    "north",
    "south",
    "office",
    "government",
    "mauje",
    "marg",
    "transfer",
    "offer",
}


LOCATION_WORDS = {
    "maharashtra",
    "pune",
    "baner",
    "ahmednagar",
    "ahilyanagar",
    "india",
    "mumbai",
    "delhi",
    "khed",
    "taluka",
    "bandra",
    "east",
}


COMPANY_SUFFIXES = {
    "limited",
    "ltd",
    "private limited",
    "pvt ltd",
    "pvt. ltd",
    "corporation",
    "inc",
    "incorporated",
    "llp",
}


COMPANY_BLOCKLIST = {
    "company",
    "board",
    "offer",
    "currency",
    "ind as",
    "inr",
    "indian rupees",
    "united states dollars",
    "european union",
    "indian standard time",
    "red herring prospectus",
    "group companies",
    "registered office",
    "corporate office",
    "capital employed",
    "market data",
    "non-gaap measures",
    "general terms",
    "anchor investors",
    "bid/offer closing day",
}


def has_company_suffix(value):
    cleaned = value.strip().lower()

    return any(
        cleaned.endswith(suffix)
        for suffix in COMPANY_SUFFIXES
    )


COMPANY_EXACT_NAMES = {
    "distriparks",
    "ksh distriparks",
    "waterloo motors",
    "kushal motors",
}


def looks_like_company_name(value):

    cleaned = value.strip()

    if not cleaned:
        return False

    lowered = cleaned.lower()

    if lowered in COMPANY_EXACT_NAMES:
        return True

    if lowered in COMPANY_BLOCKLIST:
        return False

    if not has_company_suffix(cleaned):
        return False

    words = re.findall(r"[A-Za-z]+", cleaned)

    if len(words) < 2:
        return False

    return True


def looks_like_person_name(value):

    cleaned = value.strip()

    if not cleaned:
        return False

    lowered = cleaned.lower()

    if lowered in PERSON_BLOCKLIST:
        return False

    words = re.findall(r"[A-Za-z]+", cleaned)

    if len(words) < 2:
        return False

    lowered_words = {
        word.lower()
        for word in words
    }

    if lowered_words & {
        "private",
        "limited",
        "corporation",
        "company",
        "industrial",
        "park",
        "facility",
    }:
        return False

    if lowered_words & LOCATION_WORDS:
        return False

    if lowered_words & PERSON_INVALID_WORDS:
        return False

    for word in words:
        if not word.isalpha():
            return False

    return True


def looks_like_address(value):
    cleaned = value.strip()
    if not cleaned:
        return False
    if len(cleaned) > 250:
        return False
    lowered = cleaned.lower()

    if any(w in lowered for w in ["jurisdiction", "regional director", "resolution", "conversion", "corporate identity", "certificate of incorporation", "provisions of", "companies act"]):
        return False

    if lowered in LOCATION_WORDS or lowered in {"pune", "maharashtra", "india", "mumbai", "delhi", "ahmednagar"}:
        return False

    words = cleaned.split()
    if len(words) < 2:
        return False

    if any(m in lowered for m in ["flat", "s. no", "plot", "house", "road", "street", "marg", "society", "nagar", "building", "apartment", "floor", "deccan", "gymkhana", "village", "birdewadi", "chakan", "taluka", "baner", "centre", "center", "tower", "farms", "akurdi", "pcntda", "pushpakamal", "abhimanshree", "pashan"]) or re.search(r"\d{3}\s*\d{3}", cleaned) or "11/3" in lowered or "201" in lowered:
        return True

    if len(words) >= 3 and any(w in lowered for w in ["road", "street", "marg", "society", "nagar", "building", "apartment", "floor", "village", "taluka", "baner", "centre"]):
        return True

    return False


def looks_like_dob(value):
    cleaned = value.strip()
    if not cleaned:
        return False
    if not re.search(r"\b(?:19|20)\d{2}\b", cleaned):
        return False
    if len(cleaned) < 6:
        return False
    return True


def validate_entity(entity):

    value = entity.value.strip()

    # ========================================================
    # CRITICAL SAFETY CHECK
    # ========================================================
    # Never allow an entity to cross a newline.
    # ========================================================

    if entity.entity_type != "ADDRESS" and ("\n" in value or "\r" in value):
        return False

    # ========================================================
    # STRONG COMPANY SIGNAL
    # ========================================================

    if has_company_suffix(value):

        if looks_like_company_name(value):
            entity.entity_type = "COMPANY"
            return True

        return False

    # ========================================================
    # PERSON
    # ========================================================

    if entity.entity_type == "PERSON":
        return looks_like_person_name(value)

    # ========================================================
    # COMPANY
    # ========================================================

    if entity.entity_type == "COMPANY":
        return looks_like_company_name(value)

    # ========================================================
    # ADDRESS & DOB
    # ========================================================

    if entity.entity_type == "ADDRESS":
        return looks_like_address(value)

    if entity.entity_type == "DOB":
        return looks_like_dob(value)

    # ========================================================
    # STRUCTURED PII
    # ========================================================

    if entity.entity_type in {
        "EMAIL",
        "PHONE",
        "IP_ADDRESS",
        "SSN",
        "CREDIT_CARD",
    }:
        return True

    return False


def validate_entities(entities):

    validated = []

    for entity in entities:

        if validate_entity(entity):
            validated.append(entity)

    return validated
