from app import create_app
from extensions import mongo
app = create_app()
with app.app_context():
    pending = list(mongo.db.pending_users.find({}, {"_id": 0, "email": 1, "otp": 1, "name": 1}))
    print("Pending Users:")
    for p in pending:
        print(p)
