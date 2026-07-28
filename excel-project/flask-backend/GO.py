from flask import Flask, jsonify
from flask_cors import CORS
app = Flask(__name__)
CORS(app)
app.config.update(SCHOOL_NAME='Excel Group of Schools', SCHOOL_MOTTO='Wea Sono la Cremma Della Terra')
@app.route('/')
def h(): return f"<h1>{app.config['SCHOOL_NAME']}</h1><p>{app.config['SCHOOL_MOTTO']}</p><p style='color:green'><b>✓ RUNNING</b></p>"
@app.route('/api/sync/handshake')
def hs(): return jsonify({"status":"ok","school_name":app.config['SCHOOL_NAME'],"school_motto":app.config['SCHOOL_MOTTO']})
@app.route('/sync')
def s(): return "<h1>Sync Center (Bursar)</h1><p>Ready for https://crm.egs.ac.zw</p>"
if __name__ == "__main__": print("\n=== STARTING SERVER ===\nhttp://127.0.0.1:5000\nhttp://127.0.0.1:5000/sync\nhttp://127.0.0.1:5000/api/sync/handshake\n"); app.run(host="127.0.0.1", port=5000, debug=False)
