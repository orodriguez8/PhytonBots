
import os
from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from src.core.logger import logger

def create_app():
    # Detect the absolute path to 'web' directory for templates and static files
    # Current file is in src/api/server.py, so root is two levels up
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    template_dir = os.path.join(root_dir, 'web', 'templates')
    static_dir = os.path.join(root_dir, 'web', 'static')
    
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'mera-victorino-pro-3.0')
    CORS(app)
    
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        ping_timeout=30,
        ping_interval=15,
        logger=False,
        engineio_logger=False,
    )
    
    return app, socketio

app, socketio = create_app()
