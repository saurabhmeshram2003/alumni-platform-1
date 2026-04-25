import os
import secrets
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(16))
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/alumni_db')
    
    # Mail settings
    MAIL_SERVER         = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT           = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS        = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USE_SSL        = os.getenv('MAIL_USE_SSL', 'False') == 'True'
    MAIL_USERNAME       = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD       = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER') or os.getenv('MAIL_USERNAME')
    
    # Upload folder
    UPLOAD_FOLDER = os.path.join('static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
