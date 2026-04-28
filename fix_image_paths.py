"""Fix profile_image paths: prepend 'profiles/' so templates can find them in uploads/profiles/"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient
client = MongoClient(os.getenv('MONGO_URI'))
db = client.get_database()

alumni = list(db.users.find({'role': 'alumni'}))
updated = 0
for a in alumni:
    img = a.get('profile_image', 'default.png')
    if img and img != 'default.png' and not img.startswith('profiles/'):
        new_img = 'profiles/' + img
        db.users.update_one({'_id': a['_id']}, {'$set': {'profile_image': new_img}})
        print(f"  ✓ {a['name']} → {new_img}")
        updated += 1

print(f"\nDone! Updated: {updated}")
