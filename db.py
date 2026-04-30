import os
from pymongo import MongoClient

MONGO_URI = os.environ.get('MONGO_URI')  # Set in Railway environment variables

if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable is not set.")

client = MongoClient(MONGO_URI)
db = client.get_database()  # Reads DB name from the Atlas connection string
