"""
assign_profile_images.py
========================
Matches alumni names → image files in static/images/profiles/
Updates the profile_image field in MongoDB for all alumni.
The image path stored is relative to static/uploads/profiles/
so that the existing url_for('static', filename='uploads/profiles/'+img) works.

We COPY each matched image from static/images/profiles/ to static/uploads/profiles/
so Flask can serve it the same way as user-uploaded images.

Run from project root:
    python assign_profile_images.py
"""

import os, sys, shutil
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/alumni_db')
client = MongoClient(MONGO_URI)
db = client.get_database()

# Source directory: images are stored with exact "Name.jpg" filenames
SRC_DIR = os.path.join(os.path.dirname(__file__), 'static', 'images', 'profiles')
# Destination: where Flask serves uploaded profile images from
DST_DIR = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'profiles')
os.makedirs(DST_DIR, exist_ok=True)

# Build a lookup: normalised_name → actual_filename
def normalise(name):
    return name.lower().replace(' ', '').replace('.', '').replace('_', '')

available = {}
for f in os.listdir(SRC_DIR):
    if f.startswith('.'):
        continue
    stem = os.path.splitext(f)[0]   # e.g. "Aditi Kashetwar"
    available[normalise(stem)] = f

print(f"Found {len(available)} images in {SRC_DIR}\n")

# Fetch all alumni
alumni = list(db.users.find({'role': 'alumni'}, {'_id': 1, 'name': 1, 'profile_image': 1}))

matched   = 0
unmatched = []

for a in alumni:
    name     = a['name']
    norm     = normalise(name)
    img_file = available.get(norm)

    if not img_file:
        # Try partial: match any key that starts with the first two words normalised
        parts = name.lower().split()
        prefix = ''.join(parts[:2]) if len(parts) >= 2 else norm
        for key, val in available.items():
            if key.startswith(prefix):
                img_file = val
                break

    if img_file:
        src = os.path.join(SRC_DIR, img_file)
        # Destination filename: use a clean version of the alumni's name
        safe_name = name.replace(' ', '_').replace('.', '') 
        ext = os.path.splitext(img_file)[1]
        dst_filename = f"profile_{safe_name}{ext}"
        dst = os.path.join(DST_DIR, dst_filename)

        # Copy only if not already there
        if not os.path.exists(dst):
            shutil.copy2(src, dst)

        # Update MongoDB
        db.users.update_one(
            {'_id': a['_id']},
            {'$set': {'profile_image': dst_filename}}
        )
        print(f"  ✓  {name:<40} → {dst_filename}")
        matched += 1
    else:
        unmatched.append(name)
        print(f"  ✗  {name:<40} → no image found (keeping default.png)")

print(f"\n{'='*60}")
print(f"Done!  Matched: {matched} | Unmatched: {len(unmatched)}")
if unmatched:
    print("\nUnmatched alumni (still using default.png):")
    for n in unmatched:
        print(f"  - {n}")
print('='*60)
