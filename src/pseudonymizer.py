from collections import defaultdict

try:
    from faker import Faker
    fake = Faker('en_IN')
except ImportError:
    fake = None


class Pseudonymizer:

    def __init__(self, mode="realistic"):
        self.mode = mode
        self.counters = defaultdict(int)
        self.mapping = {}

    def _create_placeholder(self, entity_type):
        self.counters[entity_type] += 1
        return f"{entity_type}_{self.counters[entity_type]:03d}"

    def _generate_realistic(self, entity_type, value):
        self.counters[entity_type] += 1
        idx = self.counters[entity_type]

        if fake:
            if entity_type == "PERSON":
                return fake.name()
            elif entity_type == "EMAIL":
                return f"user_{idx}@example.com"
            elif entity_type == "PHONE":
                return f"+91 98{idx:02d}5 43210"
            elif entity_type == "COMPANY":
                return f"{fake.company()} Ltd."
            elif entity_type == "ADDRESS":
                return f"{idx * 12} Park Street, Pune, Maharashtra 411008"
            elif entity_type == "SSN":
                return f"9{idx:02d}-45-{6780+idx:04d}"
            elif entity_type == "CREDIT_CARD":
                return fake.credit_card_number()
            elif entity_type == "DOB":
                return "1990-01-01"
            elif entity_type == "IP_ADDRESS":
                return f"192.168.1.{idx % 250 + 1}"

        return self._create_placeholder(entity_type)

    def get_replacement(self, entity_type, value):

        # Normalize whitespace so equivalent values use the same replacement.
        normalized_value = " ".join(value.strip().split())
        key = (entity_type, normalized_value.lower())

        if key in self.mapping:
            return self.mapping[key]

        if self.mode == "realistic":
            replacement = self._generate_realistic(entity_type, value)
        else:
            replacement = self._create_placeholder(entity_type)

        self.mapping[key] = replacement
        return replacement

    def get_mapping(self):
        return dict(self.mapping)