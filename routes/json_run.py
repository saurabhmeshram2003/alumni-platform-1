from pymongo import MongoClient
import json

# connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["alumniDB"]
collection = db["alumni"]

# load your JSON (paste or load file)
with open("data.json") as f:
    data = json.load(f)

# insert into database
collection.insert_many(data)

print("Data inserted successfully!")