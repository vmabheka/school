#!/usr/bin/env python3
"""Ultra simple launcher - just run this file"""

from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

app.config.update(
    SCHOOL_NAME='Excel Group of Schools',
    SCHOOL_MOTTO='Wea Sono la Cremma Della Terra',
    SECRET_KEY='excel-schools-2024'
)

@app.route('/')
def index():
    return f"<h1>{app.config['SCHOOL_NAME']}</h1><p>{app.config['SCHOOL_MOTTO']}</p><p style='color:green'><b>✓ SERVER IS RUNNING</b></p>"

@app.route('/api/sync/handshake')
def handshake():
    return jsonify({
        "status": "ok",
        "message": "Flask offline sync endpoint is live",
        "school_name": app.config['SCHOOL_NAME'],
        "school_motto": app.config['SCHOOL_MOTTO']
    })

@app.route('/sync')
def sync_center():
    return "<h1>Sync Center</h1><p>Bursar portal active. Ready for handshake with https://crm.egs.ac.zw</p>"

if __name__ == "__main__":
    print("\n" + "="*65)
    print("   EXCEL SCHOOLS - FLASK SERVER STARTING")
    print("="*65)
    print("  This computer: http://127.0.0.1:5000")
    print("  LAN (other devices): find the IPv4 address with 'ipconfig',")
    print("  then clients open http://<IPv4-address>:5000 (firewall must allow TCP 5000)")
    print("  Main App:   http://127.0.0.1:5000")
    print("  Sync:       http://127.0.0.1:5000/sync")
    print("  Handshake:  http://127.0.0.1:5000/api/sync/handshake")
    print("="*65 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
