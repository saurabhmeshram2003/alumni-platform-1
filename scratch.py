from app import create_app
from extensions import mongo

app = create_app()
with app.app_context():
    for member in mongo.db.users.find():
        s = member.get('skills')
        if not isinstance(s, list):
            print(f"User {member['_id']} has invalid skills: {type(s)} -> {s}")
