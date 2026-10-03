import os
import sys
import traceback
from pathlib import Path

BASE_DIR = str(Path(__file__).resolve().parent.parent)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from app import app as flask_app
except Exception:
    init_error = traceback.format_exc()
    def flask_app(environ, start_response):
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain; charset=utf-8')])
        return [f"Vercel Startup Error:\n\n{init_error}".encode('utf-8')]

def handler(environ, start_response):
    try:
        return flask_app(environ, start_response)
    except Exception:
        err_msg = traceback.format_exc()
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain; charset=utf-8')])
        return [f"Vercel Invocation Exception:\n\n{err_msg}".encode('utf-8')]

app = handler


