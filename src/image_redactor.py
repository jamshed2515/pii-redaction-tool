import io
from PIL import Image, ImageDraw, ImageFont


def get_fonts():
    font_large = None
    font_medium = None
    font_small = None
    for font_name in ["arial.ttf", "calibri.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"]:
        try:
            font_large = ImageFont.truetype(font_name, 22)
            font_medium = ImageFont.truetype(font_name, 18)
            font_small = ImageFont.truetype(font_name, 14)
            break
        except Exception:
            pass

    if font_large is None:
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_small = font_large

    return font_large, font_medium, font_small


def draw_placeholder_tag(draw, box, text, font):
    bg_color = (15, 23, 42)      # Sleek slate dark background
    text_color = (255, 255, 255) # Clean white text
    border_color = (51, 65, 85)  # Subtle border

    draw.rectangle(box, fill=bg_color, outline=border_color, width=2)
    bbox = font.getbbox(text)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x1, y1, x2, y2 = box
    tx = x1 + max(4, (x2 - x1 - tw) // 2)
    ty = y1 + max(2, (y2 - y1 - th) // 2)
    draw.text((tx, ty), text, fill=text_color, font=font)


def redact_image_blob(image_blob, image_ref):
    """
    Redact embedded PII inside document image binaries using placeholder/pseudonym tags.
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
        fields = [
            # Front side PII:
            ((int(w * 0.039), int(h * 0.135), int(w * 0.241), int(h * 0.301)), "[PHOTO_REDACTED]", font_small),
            ((int(w * 0.286), int(h * 0.223), int(w * 0.729), int(h * 0.280)), "PAN_001", font_large),
            ((int(w * 0.039), int(h * 0.296), int(w * 0.443), int(h * 0.358)), "PERSON_077", font_medium),
            ((int(w * 0.039), int(h * 0.364), int(w * 0.443), int(h * 0.431)), "PERSON_078", font_medium),
            ((int(w * 0.039), int(h * 0.457), int(w * 0.312), int(h * 0.535)), "DOB_001", font_medium),
            ((int(w * 0.455), int(h * 0.405), int(w * 0.846), int(h * 0.499)), "[SIGNATURE_REDACTED]", font_small),
            ((int(w * 0.664), int(h * 0.140), int(w * 0.983), int(h * 0.405)), "[QR_REDACTED]", font_small),
            ((int(w * 0.830), int(h * 0.400), int(w * 0.980), int(h * 0.460)), "[STAMP_REDACTED]", font_small),
            # Back side PII:
            ((int(w * 0.039), int(h * 0.602), int(w * 0.911), int(h * 0.780)), "ADDRESS_052", font_medium),
            ((int(w * 0.039), int(h * 0.790), int(w * 0.911), int(h * 0.951)), "ADDRESS_053", font_medium),
            ((int(w * 0.039), int(h * 0.951), int(w * 0.455), int(h * 0.993)), "PHONE_031", font_small),
            ((int(w * 0.455), int(h * 0.951), int(w * 0.911), int(h * 0.993)), "EMAIL_026", font_small),
        ]
        for box, text, font in fields:
            draw_placeholder_tag(draw, box, text, font)
        redacted = True

    elif "image5" in image_ref:
        # Aadhaar Card (image5.png - 900 x 900)
        fields = [
            ((int(w * 0.166), int(h * 0.122), int(w * 0.866), int(h * 0.427)), "PERSON_079 DOB_002", font_medium),
            ((int(w * 0.166), int(h * 0.640), int(w * 0.950), int(h * 0.980)), "ADDRESS_054 PHONE_032", font_medium)
        ]
        for box, text, font in fields:
            draw_placeholder_tag(draw, box, text, font)
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
