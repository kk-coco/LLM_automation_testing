from flask import Flask
from flask_cors import CORS
from config.db_config import Config
from utils.db import init_db_pool

def create_app():
    app = Flask(__name__)
    # CORS(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.config.from_object(Config)

    # init database
    init_db_pool(app.config)

    # blueprint register
    from app.llm_api import llm_automation
    app.register_blueprint(llm_automation, url_prefix='/api')

    return app
