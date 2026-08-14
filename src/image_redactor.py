import io
from PIL import Image, ImageDraw, ImageFont


def get_fonts():
    font_large = None
    font_medium = None
    font_small = None
    for font_name in ["arialbd.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]:
        try:
            font_large = ImageFont.truetype(font_name, 22)
            font_medium = ImageFont.truetype(font_name, 16)
            font_small = ImageFont.truetype(font_name, 12)
            break
        except Exception:
            pass

    if font_large is None:
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_small = font_large

    return font_large, font_medium, font_small


def replace_field_text(draw, box, text, font, text_color=(15, 23, 42), fill_color=(205, 230, 242)):
    """
    Remove original PII text pixels by filling tightly with local card background color,
    and draw the replacement placeholder string directly at the original field position.
    """
    draw.rectangle(box, fill=fill_color)
    x1, y1, x2, y2 = box
    draw.text((x1 + 4, y1 + 2), text, fill=text_color, font=font)


def redact_image_blob(image_blob, image_ref):
    """
    Redact embedded PII inside document image binaries by removing original PII text pixels
    and rendering corresponding placeholder strings directly in their original field locations.
    Preserves all card labels, artwork, seals, borders, and layout structure.
    """
    try:
        img = Image.open(io.BytesIO(image_blob)).convert("RGB")
    except Exception:
        return image_blob

    draw = ImageDraw.Draw(img)
    w, h = img.size
    font_large, font_medium, font_small = get_fonts()
    redacted = False

    if "image4" in image_ref:
        # PAN Card (image4.png - 768 x 962)
        # 1. Photograph: x=38..175, y=135..285
        replace_field_text(draw, (38, 135, 175, 285), "[PHOTO]", font_small, text_color=(71, 85, 105), fill_color=(185, 210, 225))

        # 2. PAN Number (NBWPS1951N): x=245..440, y=220..258
        replace_field_text(draw, (245, 220, 440, 258), "PAN_001", font_large, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 3. QR Code: x=525..735, y=155..375
        replace_field_text(draw, (525, 155, 735, 375), "[QR_REDACTED]", font_small, text_color=(71, 85, 105), fill_color=(185, 210, 225))

        # 4. Name value (VISHAL SINGH): BELOW 'नाम / Name' label at y=312..342
        replace_field_text(draw, (35, 312, 260, 342), "PERSON_077", font_medium, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 5. Father's Name value (SUGRIV SINGH): BELOW 'पिता का नाम / Father's Name' label at y=378..408
        replace_field_text(draw, (35, 378, 260, 408), "PERSON_078", font_medium, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 6. Date of Birth value (06/05/2000): BELOW 'जन्म की तारीख / Date of Birth' label at y=465..492
        replace_field_text(draw, (35, 465, 200, 492), "DOB_001", font_medium, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 7. Signature handwriting (Vishal Singh): ABOVE 'हस्ताक्षर / Signature' label at y=405..460
        replace_field_text(draw, (425, 405, 630, 460), "[SIGNATURE]", font_small, text_color=(71, 85, 105), fill_color=(205, 230, 242))

        # Back Card PII fields:
        # 8. Hindi Address text lines: BELOW header label at y=595..715
        replace_field_text(draw, (35, 595, 500, 715), "ADDRESS_052", font_medium, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 9. English Address text lines: BELOW header label at y=795..915
        replace_field_text(draw, (35, 795, 580, 915), "ADDRESS_053", font_medium, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 10. Tel & Email lines: at y=920..958
        replace_field_text(draw, (35, 920, 580, 958), "PHONE_031  EMAIL_026", font_small, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        redacted = True

    elif "image5" in image_ref:
        # Aadhaar Card (image5.png - 900 x 900)
        replace_field_text(draw, (170, 130, 335, 325), "[PHOTO]", font_small, text_color=(71, 85, 105), fill_color=(215, 235, 245))
        replace_field_text(draw, (340, 140, 540, 200), "PERSON_079", font_medium, text_color=(15, 23, 42), fill_color=(215, 235, 245))
        replace_field_text(draw, (340, 240, 550, 275), "DOB_002", font_medium, text_color=(15, 23, 42), fill_color=(215, 235, 245))
        replace_field_text(draw, (330, 335, 600, 375), "AADHAAR_001", font_medium, text_color=(15, 23, 42), fill_color=(215, 235, 245))
        replace_field_text(draw, (170, 620, 780, 690), "ADDRESS_054", font_medium, text_color=(15, 23, 42), fill_color=(215, 235, 245))
        replace_field_text(draw, (180, 880, 320, 920), "PHONE_032", font_small, text_color=(15, 23, 42), fill_color=(215, 235, 245))
        replace_field_text(draw, (420, 880, 580, 920), "EMAIL_027", font_small, text_color=(15, 23, 42), fill_color=(215, 235, 245))
        redacted = True

    if redacted:
        out_stream = io.BytesIO()
        img.save(out_stream, format="PNG")
        return out_stream.getvalue()

    return image_blob


def redact_document_images(doc):
    """
    Scan all relationship targets in python-docx document and redact image PII.
    """
    redacted_count = 0
    for rel_id, rel in doc.part.rels.items():
        if "image" in rel.target_ref:
            part = rel.target_part
            old_blob = part.blob
            new_blob = redact_image_blob(old_blob, rel.target_ref)
            if len(new_blob) != len(old_blob):
                part._blob = new_blob
                redacted_count += 1
    return redacted_count
