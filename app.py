# library includes #################################################################################################################################
import os
from datetime import time as dt_time
from datetime import datetime 
from decimal import Decimal
from flask import (
    Flask, jsonify, request, send_from_directory,
    redirect, url_for, session
)
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.extras import RealDictCursor
from tempfile import NamedTemporaryFile
# header includes  #################################################################################################################################
# from data.database_postgres import ()
# from chatbots.diet import get_image_description
# from chatbots.reasoning import respond 
# SETUP            #################################################################################################################################
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Important for sessions

# API CALLS        #################################################################################################################################

@app.route('/')
def index():
    return redirect('/web_files/chatbot.html')
# ---------- NEW: text-only respond(prompt) returning markdown ----------
@app.route('/api/respond', methods=['POST'])
def api_respond():
    """
    Expects JSON: { "prompt": "<text>" }
    Calls respond(prompt) which returns markdown string.
    Returns { success: True, markdown: "<md>" } or { success: False, error: "<msg>" }.
    """
    if not request.is_json:
        return jsonify({'success': False, 'error': 'JSON body required'}), 400
    data = request.get_json(silent=True) or {}
    prompt = (data.get('prompt') or '').strip()
    if respond is None:
        return jsonify({'success': False, 'error': 'respond function not configured'}), 500
    try:
        markdown = respond(prompt)
    except TypeError:
        # If the function signature is different, try positional
        markdown = respond(prompt)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    if not isinstance(markdown, str):
        return jsonify({'success': False, 'error': 'respond() did not return a string'}), 500
    return jsonify({'success': True, 'markdown': markdown})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
    