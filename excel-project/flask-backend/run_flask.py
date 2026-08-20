from app import app, init_db

with app.app_context():
    init_db()

print("Starting Excel Schools on http://0.0.0.0:5000 (LAN)")
print("Other devices: http://<this-computer-IPv4>:5000  (allow TCP 5000 in the firewall)")
app.run(host="0.0.0.0", port=5000, debug=True)
