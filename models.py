from extensions import mongo
from bson import ObjectId
from werkzeug.security import generate_password_hash
from datetime import datetime


def _db():
    """
    Safe accessor for mongo.db — raises RuntimeError with a clear
    message if MONGO_URI was not set in the environment.
    """
    if mongo.db is None:
        raise RuntimeError(
            "MongoDB is not connected. "
            "Ensure MONGO_URI is set in the Railway / Render environment variables."
        )
    return mongo.db


class User:
    @staticmethod
    def collection():
        return _db().users

    @staticmethod
    def create(name, email, password, role, graduation_year, department,
               company=None, skills=None, linkedin=None,
               proof_type=None, proof_file=None,
               otp=None, otp_expiry=None):
        hashed = generate_password_hash(password)
        user = {
            'name': name,
            'email': email,
            'password': hashed,
            'role': role,
            'graduation_year': graduation_year,
            'department': department,
            'company': company,
            'skills': skills or [],
            'linkedin': linkedin,
            'proof_type': proof_type,
            'proof_file': proof_file,
            'profile_image': 'default.png',
            'created_at': datetime.utcnow(),
            'is_approved': False if role == 'alumni' else True,
            # OTP email verification fields
            'verified': False,
            'otp': otp,
            'otp_expiry': otp_expiry,
            'otp_resend_at': None,
        }
        result = User.collection().insert_one(user)
        return result.inserted_id

    @staticmethod
    def find_by_email(email):
        return User.collection().find_one({'email': email})

    @staticmethod
    def find_by_id(user_id):
        return User.collection().find_one({'_id': ObjectId(user_id)})


# ─────────────────────────────────────────────────────────────────
# PendingUser  —  temporary store BEFORE OTP verification
# Operates on the  pending_users  collection.
# Users are promoted to  users  collection on successful OTP verify.
# ─────────────────────────────────────────────────────────────────
class PendingUser:
    @staticmethod
    def collection():
        return _db().pending_users

    @staticmethod
    def create(name, email, password, role, graduation_year, department,
               company=None, skills=None, linkedin=None,
               proof_type=None, proof_file=None,
               otp=None, otp_expiry=None):
        """Save a new pending registration (password already hashed by caller)."""
        doc = {
            'name':            name,
            'email':           email,
            'password':        password,        # pre-hashed
            'role':            role,
            'graduation_year': graduation_year,
            'department':      department,
            'company':         company,
            'skills':          skills or [],
            'linkedin':        linkedin,
            'proof_type':      proof_type,
            'proof_file':      proof_file,
            'profile_image':   'default.png',
            'created_at':      datetime.utcnow(),
            'is_approved':     False if role == 'alumni' else True,
            'verified':        False,
            'otp':             otp,
            'otp_expiry':      otp_expiry,
            'otp_resend_at':   None,
        }
        PendingUser.collection().replace_one({'email': email}, doc, upsert=True)

    @staticmethod
    def find_by_email(email):
        return PendingUser.collection().find_one({'email': email})

    @staticmethod
    def promote_to_users(email):
        """
        Move verified pending user into the users collection.
        Strips OTP fields, sets verified=True, then deletes from pending_users.
        Returns the inserted _id, or None if not found.
        """
        doc = PendingUser.collection().find_one({'email': email})
        if not doc:
            return None
        doc.pop('_id', None)              # let MongoDB assign a new _id
        doc['verified']      = True
        doc['otp']           = None
        doc['otp_expiry']    = None
        doc['otp_resend_at'] = None
        result = _db().users.insert_one(doc)
        PendingUser.collection().delete_one({'email': email})
        return result.inserted_id

    @staticmethod
    def update_otp(email, new_otp, new_expiry):
        PendingUser.collection().update_one(
            {'email': email},
            {'$set': {
                'otp':           new_otp,
                'otp_expiry':    new_expiry,
                'otp_resend_at': datetime.utcnow(),
            }}
        )

    @staticmethod
    def delete(email):
        PendingUser.collection().delete_one({'email': email})


# Flask-Login wrapper
class UserMixin:
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.name = user_data.get('name')
        self.email = user_data.get('email')
        self.role = user_data.get('role')
        self.is_approved = user_data.get('is_approved', True)
        self.profile_image = user_data.get('profile_image', 'default.png')
        self.company = user_data.get('company')
        self.department = user_data.get('department')
        self.graduation_year = user_data.get('graduation_year')
        self.skills = user_data.get('skills', [])
        self.linkedin = user_data.get('linkedin')
        self.proof_type = user_data.get('proof_type')
        self.proof_file = user_data.get('proof_file')
        # Bio (support both field names)
        self.bio = user_data.get('bio') or user_data.get('biography_summary', '')
        self.biography_summary = self.bio
        # Extended alumni fields
        self.class_batch = user_data.get('class_batch', '')
        self.current_working_company = user_data.get('current_working_company', '')
        self.past_experience = user_data.get('past_experience', [])
        self.education = user_data.get('education', [])
        self.certificates = user_data.get('certificates', [])
        self.position = user_data.get('position', '')

    def is_authenticated(self):
        return True
    def is_active(self):
        return self.is_approved
    def is_anonymous(self):
        return False
    def get_id(self):
        return self.id


from extensions import login_manager

@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = User.find_by_id(user_id)
        if user_data:
            return UserMixin(user_data)
    except Exception:
        pass
    return None
