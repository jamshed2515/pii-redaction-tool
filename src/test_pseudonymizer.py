from pseudonymizer import Pseudonymizer


pseudonymizer = Pseudonymizer()


test_values = [
    ("PERSON", "Sarthak Malvadkar"),
    ("PERSON", "Sarthak Malvadkar"),
    ("PERSON", "Rajesh Kushal Hegde"),
    ("PERSON", "Sarthak Malvadkar"),
    ("EMAIL", "cs.connect@kshinternational.com"),
    ("EMAIL", "cs.connect@kshinternational.com"),
    ("PHONE", "+91 20 4505 3237"),
]


for entity_type, value in test_values:

    replacement = pseudonymizer.get_replacement(
        entity_type,
        value
    )

    print(
        value,
        "->",
        replacement
    )


print("\n===== MAPPING =====")

for key, replacement in pseudonymizer.get_mapping().items():
    print(key, "->", replacement)