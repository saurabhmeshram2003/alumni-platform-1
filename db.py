import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/alumni_db')
client = MongoClient(MONGO_URI)

db_name = MONGO_URI.split('/')[-1].split('?')[0]
if not db_name:
    db_name = 'alumni_db'
    
db = client[db_name]
