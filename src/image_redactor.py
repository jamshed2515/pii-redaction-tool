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
    draw.text((x1 + 6, y1 + 3), text, fill=text_color, font=font)


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
        # 1. Photograph: x=30..185, y=130..290
        replace_field_text(draw, (30, 130, 185, 290), "[PHOTO]", font_small, text_color=(71, 85, 105), fill_color=(185, 210, 225))

        # 2. PAN Number (NBWPS1951N): x=240..450, y=215..265
        replace_field_text(draw, (240, 215, 450, 265), "PAN_001", font_large, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 3. QR Code: x=510..755, y=135..390
        replace_field_text(draw, (510, 135, 755, 390), "[QR_REDACTED]", font_small, text_color=(71, 85, 105), fill_color=(185, 210, 225))

        # 4. Name value (VISHAL SINGH): Covers y=298..345, x=30..350 (completely erases VISHAL SINGH)
        replace_field_text(draw, (30, 298, 350, 345), "PERSON_077", font_medium, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 5. Father's Name value (SUGRIV SINGH): Covers y=362..410, x=30..350 (completely erases SUGRIV SINGH)
        replace_field_text(draw, (30, 362, 350, 410), "PERSON_078", font_medium, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 6. Date of Birth value (06/05/2000): Covers y=435..488, x=30..240 (completely erases 06/05/2000)
        replace_field_text(draw, (30, 435, 240, 488), "DOB_001", font_medium, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 7. Signature handwriting (Vishal Singh): Covers y=390..465, x=375..630
        replace_field_text(draw, (375, 390, 630, 465), "[SIGNATURE]", font_small, text_color=(71, 85, 105), fill_color=(205, 230, 242))

        # 8. Date stamp (06072020): Covers x=635..755, y=405..455
        replace_field_text(draw, (635, 405, 755, 455), "[STAMP_REDACTED]", font_small, text_color=(71, 85, 105), fill_color=(205, 230, 242))

        # Back Card PII fields:
        # 9. Hindi Address text lines: y=595..725, x=30..520
        replace_field_text(draw, (30, 595, 520, 725), "ADDRESS_052", font_medium, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 10. English Address text lines (Income Tax PAN Services Unit...): y=785..920, x=30..600
        replace_field_text(draw, (30, 785, 600, 920), "ADDRESS_053", font_medium, text_color=(15, 23, 42), fill_color=(205, 230, 242))

        # 11. Tel & Email lines: y=920..960, x=30..600
        replace_field_text(draw, (30, 920, 600, 960), "PHONE_031  EMAIL_026", font_small, text_color=(15, 23, 42), fill_color=(205, 230, 242))

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
