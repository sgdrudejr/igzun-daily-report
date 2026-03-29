#!/usr/bin/env python3
import re
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image
    import pytesseract
except Exception as exc:
    print("OCR deps missing:", exc)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data/account_snapshot_inbox"
IMG_DIR = INBOX / "incoming_images"
TXT_DIR = INBOX / "ocr_text"
PROCESSED = INBOX / "processed"
FAILED = INBOX / "failed"


def preprocess(img_path: Path):
    img = Image.open(img_path).convert("L")
    width, height = img.size
    if width < 1600:
        scale = 1600 / max(width, 1)
        img = img.resize((int(width * scale), int(height * scale)))
    return img


def ocr_image(path: Path):
    img = preprocess(path)
    text = pytesseract.image_to_string(img, lang="kor+eng")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    for folder in [IMG_DIR, TXT_DIR, PROCESSED, FAILED]:
        folder.mkdir(parents=True, exist_ok=True)
    images = sorted(path for path in IMG_DIR.iterdir() if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".heic", ".webp"})
    if not images:
        print("no incoming images")
        return
    for image in images:
        try:
            text = ocr_image(image)
            out = TXT_DIR / f"{image.stem}.txt"
            out.write_text(text)
            shutil.move(str(image), str(PROCESSED / image.name))
            print("ocr ok", image.name)
        except Exception as exc:
            shutil.move(str(image), str(FAILED / image.name))
            print("ocr fail", image.name, exc)


if __name__ == "__main__":
    main()
