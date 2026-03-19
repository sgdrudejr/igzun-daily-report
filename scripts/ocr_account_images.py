#!/usr/bin/env python3
import json, shutil, sys, re
from pathlib import Path

try:
    from PIL import Image
    import pytesseract
except Exception as e:
    print('OCR deps missing:', e)
    sys.exit(2)

ROOT = Path('/Users/seo/.openclaw/workspace/igzun-daily-report')
INBOX = ROOT / 'data/account_snapshot_inbox'
IMG_DIR = INBOX / 'incoming_images'
TXT_DIR = INBOX / 'ocr_text'
PROCESSED = INBOX / 'processed'
FAILED = INBOX / 'failed'


def preprocess(img_path: Path):
    img = Image.open(img_path).convert('L')
    # simple contrast/resize path
    w, h = img.size
    if w < 1600:
        scale = 1600 / max(w, 1)
        img = img.resize((int(w*scale), int(h*scale)))
    return img


def ocr_image(path: Path):
    img = preprocess(path)
    txt = pytesseract.image_to_string(img, lang='kor+eng')
    txt = re.sub(r'\r\n?', '\n', txt)
    txt = re.sub(r'\n{3,}', '\n\n', txt)
    return txt.strip()


def main():
    images = sorted([p for p in IMG_DIR.iterdir() if p.is_file() and p.suffix.lower() in {'.png','.jpg','.jpeg','.heic','.webp'}])
    if not images:
        print('no incoming images')
        return
    for img in images:
        try:
            txt = ocr_image(img)
            out = TXT_DIR / (img.stem + '.txt')
            out.write_text(txt)
            shutil.move(str(img), str(PROCESSED / img.name))
            print('ocr ok', img.name)
        except Exception as e:
            shutil.move(str(img), str(FAILED / img.name))
            print('ocr fail', img.name, e)

if __name__ == '__main__':
    main()
