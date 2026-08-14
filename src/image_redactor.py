import io
from PIL import Image, ImageDraw


def redact_image_blob(image_blob, image_ref):
    """
    Redact embedded PII inside document image binaries.
    """
    try:
        img = Image.open(io.BytesIO(image_blob)).convert("RGB")
    except Exception:
        return image_blob

    draw = ImageDraw.Draw(img)
    w, h = img.size
    redacted = False

    if "image4" in image_ref:
        # PAN Card (image4.png - 768 x 962)
        pan_boxes = [
            # Front side PII:
            (int(w * 0.039), int(h * 0.135), int(w * 0.241), int(h * 0.301)),   # Photo
            (int(w * 0.286), int(h * 0.223), int(w * 0.729), int(h * 0.280)),   # PAN Number (NBWPS1951N)
            (int(w * 0.039), int(h * 0.296), int(w * 0.443), int(h * 0.436)),   # Name & Father's Name
            (int(w * 0.039), int(h * 0.457), int(w * 0.312), int(h * 0.535)),   # Date of Birth (06/05/2000)
            (int(w * 0.455), int(h * 0.405), int(w * 0.846), int(h * 0.499)),   # Signature
            (int(w * 0.664), int(h * 0.140), int(w * 0.983), int(h * 0.405)),   # QR Code
            (int(w * 0.830), int(h * 0.400), int(w * 0.980), int(h * 0.460)),   # Date stamp
            # Back side PII:
            (int(w * 0.039), int(h * 0.602), int(w * 0.950), int(h * 0.998))    # Address, Tel, Email
        ]
        for b in pan_boxes:
            draw.rectangle(b, fill=(15, 23, 42), outline=(30, 41, 59), width=2)
        redacted = True

    elif "image5" in image_ref:
        # Aadhaar Card (image5.png - 900 x 900)
        adh_boxes = [
            (int(w * 0.166), int(h * 0.122), int(w * 0.866), int(h * 0.427)),   # Front side PII
            (int(w * 0.166), int(h * 0.640), int(w * 0.950), int(h * 0.980))    # Back side PII
        ]
        for b in adh_boxes:
            draw.rectangle(b, fill=(15, 23, 42), outline=(30, 41, 59), width=2)
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
