from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///excel_schools.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'excel-schools-secret-key-2024'
app.config['SCHOOL_NAME'] = 'Excel Group of Schools'
app.config['SCHOOL_MOTTO'] = 'Wea Sono la Cremma Della Terra'

db = SQLAlchemy(app)

@app.route('/')
def index():
    return f"<h1>{app.config['SCHOOL_NAME']}</h1><p>{app.config['SCHOOL_MOTTO']}</p><p>Server is running!</p>"

@app.route('/api/sync/handshake')
def handshake():
    return jsonify({
        "status": "ok",
        "message": "Flask offline sync endpoint is live",
        "version": "2.1.0",
        "school_name": app.config['SCHOOL_NAME'],
        "school_motto": app.config['SCHOOL_MOTTO']
    })

@app.route('/sync')
def sync_page():
    return "<h1>Sync Center</h1><p>Bursar Sync Portal is active</p>"

if __name__ == '__main__':
    print("=" * 60)
    print("  Excel Schools - Starting Server")
    print("=" * 60)
    print("Server running at: http://127.0.0.1:5000")
    print("Handshake: http://127.0.0.1:5000/api/sync/handshake")
    print("Sync Portal: http://127.0.0.1:5000/sync")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5000, debug=False)
