import os
import sys
from pathlib import Path

BASE_DIR = str(Path(__file__).resolve().parent.parent)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app


class FixScriptNameMiddleware:
    def __init__(self, app_wsgi):
        self.app_wsgi = app_wsgi

    def __call__(self, environ, start_response):
        environ["SCRIPT_NAME"] = ""
        return self.app_wsgi(environ, start_response)


app.wsgi_app = FixScriptNameMiddleware(app.wsgi_app)
handler = app
