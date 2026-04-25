"""
upload_alumni_photos.py
========================
Put your alumni photos inside the `alumni_photos/` folder, named exactly
after the alumni (e.g. "Aditi Kashetwar.jpg").

This script will:
  1. Scan the alumni_photos/ directory for image files
  2. Find the matching alumni in MongoDB by name (fuzzy OK)
  3. Copy the image into static/uploads/ with the correct {id}_{filename} format
  4. Update the alumni's profile_image field in MongoDB

Run with:
    source venv/bin/activate
    python upload_alumni_photos.py
"""

import os
import shutil
from pathlib import Path
from difflib import get_close_matches

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

# ─── Config ────────────────────────────────────────────────────────────────────
load_dotenv()

MONGO_URI   = os.getenv('MONGO_URI', 'mongodb://localhost:27017/alumni_db')
DB_NAME     = MONGO_URI.rstrip('/').split('/')[-1].split('?')[0]

PHOTOS_DIR  = Path(__file__).parent / 'alumni_photos'
UPLOADS_DIR = Path(__file__).parent / 'static' / 'uploads'

SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

# ─── Connect ────────────────────────────────────────────────────────────────────
client = MongoClient(MONGO_URI)
db     = client[DB_NAME]

# ─── Load all alumni from DB ────────────────────────────────────────────────────
alumni_docs = list(db.users.find({'role': 'alumni'}, {'_id': 1, 'name': 1, 'profile_image': 1}))
name_to_doc = {doc['name'].strip().lower(): doc for doc in alumni_docs}

print("=" * 60)
print(f"Alumni Photo Uploader")
print(f"Photos folder : {PHOTOS_DIR}")
print(f"Uploads folder: {UPLOADS_DIR}")
print(f"Alumni in DB  : {len(alumni_docs)}")
print("=" * 60)

if not PHOTOS_DIR.exists():
    print("\n❌ alumni_photos/ folder does not exist. Please create it first.")
    exit(1)

photos = [f for f in PHOTOS_DIR.iterdir() if f.suffix.lower() in SUPPORTED_EXTS]

if not photos:
    print("\n⚠️  No images found in alumni_photos/ folder.")
    print("   Add images named like: 'Aditi Kashetwar.jpg'")
    exit(0)

print(f"\nFound {len(photos)} photo(s) in alumni_photos/\n")

matched   = 0
unmatched = []

for photo_path in sorted(photos):
    stem       = photo_path.stem.strip()       # filename without extension
    stem_lower = stem.lower()
    ext        = photo_path.suffix.lower()

    # ── Try exact match first ────────────────────────────────────────────────
    doc = name_to_doc.get(stem_lower)

    # ── Fuzzy match fallback ─────────────────────────────────────────────────
    if not doc:
        candidates = get_close_matches(stem_lower, name_to_doc.keys(), n=1, cutoff=0.70)
        if candidates:
            doc = name_to_doc[candidates[0]]
            matched_name = candidates[0]
        else:
            unmatched.append(photo_path.name)
            print(f"  ✗ NO MATCH: {photo_path.name}")
            continue
    else:
        matched_name = stem_lower

    alumni_id  = str(doc['_id'])
    clean_name = doc['name'].replace(' ', '_')
    dest_fname = f"{alumni_id}_{clean_name}{ext}"
    dest_path  = UPLOADS_DIR / dest_fname

    # ── Copy file ────────────────────────────────────────────────────────────
    shutil.copy2(photo_path, dest_path)

    # ── Update MongoDB ────────────────────────────────────────────────────────
    db.users.update_one(
        {'_id': ObjectId(alumni_id)},
        {'$set': {'profile_image': dest_fname}}
    )

    matched += 1
    print(f"  ✓ {photo_path.name:<40} → {doc['name']} ({dest_fname})")

print("\n" + "=" * 60)
print(f"Done!  Matched & uploaded: {matched}  |  Unmatched: {len(unmatched)}")
if unmatched:
    print("\nUnmatched files (check spelling):")
    for u in unmatched:
        print(f"  - {u}")
print("=" * 60)
