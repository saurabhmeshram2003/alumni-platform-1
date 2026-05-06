from flask_pymongo import PyMongo
from flask_login import LoginManager
from flask_mail import Mail

mongo = PyMongo()
login_manager = LoginManager()
mail = Mail()
