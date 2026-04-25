from app import create_app
from extensions import mongo
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    result = mongo.db.users.update_one(
        {'email': 'admin@gmail.com'},
        {'$set': {
            'role': 'admin', 
            'is_approved': True, 
            'password': generate_password_hash('Saurabh@123')
        }}
    )
    print('Modified:', result.modified_count, 'Matched:', result.matched_count)







