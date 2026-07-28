from app import app, db

with app.app_context():
    db.create_all()

print("Starting Excel Schools on http://127.0.0.1:5000")
app.run(host="127.0.0.1", port=5000, debug=True)
