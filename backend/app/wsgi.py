from asgiref.wsgi import WsgiToAsgi
from backend.app.main import app

application = WsgiToAsgi(app)