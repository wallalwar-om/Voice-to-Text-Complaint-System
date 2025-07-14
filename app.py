from flask import Flask, render_template, request, redirect, Response, url_for, session
import base64
import os
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

MONGO_URI = os.getenv('MONGO_URI')
client = MongoClient(MONGO_URI)

DATABASE = os.getenv('DATABASE')
db = client[DATABASE]
coll = db['complaints']

#Insert Default Superadmin once
admin_username = os.getenv('DEFAULT_ADMIN_USERNAME')
admin_password = os.getenv('DEFAULT_ADMIN_PASSWORD')
if not db.admins.find_one({"username": admin_password}):
    db.admins.insert_one({
        "username": admin_username,
        "password": admin_password,
        "role": "superadmin"
    })

@app.route('/')
def home():

    complaints = db.complaints.find().sort('date', -1).limit(5)
    total_complaints = db.complaints.count_documents({})

    return render_template('home.html', complaints=complaints, total_complaints=total_complaints)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        from datetime import datetime
        category = request.form.get('category')
        base64_audio = request.form.get('recordedAudio')
        audio_file = request.files.get('audio_file')
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if base64_audio:
            header, encoded = base64_audio.split(",", 1)
            audio_data = base64.b64decode(encoded)

            doc = {
                "category": category,
                "recording": audio_data,
                "recording_type": "base64",
                "date": current_date,
                "text": "text",
                "status": "pending"
            }
            coll.insert_one(doc)

        if audio_file:
            binary_data = audio_file.read()

            doc = {
                "category": category,
                "recording": binary_data,
                "filename": audio_file.filename,
                "recording_type": "binary",
                "date": current_date,
                "text": "text",
                "status": "pending"
            }
            coll.insert_one(doc)
        return redirect(url_for('register', submitted='true'))
    
    return render_template('register.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == "POST":
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        admin = db.admins.find_one({"username": username, "password": password})
        if admin:
            session['admin'] = username
            session['role'] = admin.get('role', 'admin')
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid Credentials!")

    return render_template('admin_login.html')

@app.route('/admin/dashboard', methods=['GET'])
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    category = request.args.get('category')

    if category:
        complaints = list(db.complaints.find({'category': category}))
        total_complaints = len(complaints)
    else:
        complaints = list(db.complaints.find())
        total_complaints = db.complaints.count_documents({})

    return render_template(
        'admin_dashboard.html',
        complaints=complaints,
        total_complaints=total_complaints,
        selected_category=category
    )

@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if 'admin' not in session or session.get('role') != 'superadmin':
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        confirm_password = request.form['confirm_password'].strip()

        if db.admins.find_one({"username": username}):
            return render_template('admin_register.html', error="Username already exists.")

        if password != confirm_password:
            return render_template('admin_register.html', error="Passwords do not match.")

        db.admins.insert_one({
            "username": username,
            "password": password,
            "role": "admin"
        })
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/audio/<complaint_id>')
def serve_audio(complaint_id):
    try:
        complaint = db.complaints.find_one({"_id": ObjectId(complaint_id)})

        if not complaint:
            return "Complaint not found", 404

        audio_data = complaint.get("recording")
        recording_type = complaint.get("recording_type", "binary")

        if recording_type == "base64":
            audio_data = base64.b64decode(audio_data)

        return Response(audio_data, mimetype='audio/mp3')
    except Exception as e:
        return str(e), 500
    

@app.route('/admin/status/<complaint_id>', methods=['POST'])
def update_status(complaint_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    complaint = db.complaints.find_one({"_id": ObjectId(complaint_id)})
    if complaint:
        new_status = "Resolved" if complaint.get("status") != "Resolved" else "Pending"
        db.complaints.update_one(
            {"_id": ObjectId(complaint_id)},
            {"$set": {"status": new_status}}
        )
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<complaint_id>', methods=['POST'])
def delete_complaint(complaint_id):
    if 'admin' not in session or session.get('role') != 'superadmin':
        return redirect(url_for('admin_login'))

    db.complaints.delete_one({"_id": ObjectId(complaint_id)})
    return redirect(url_for('admin_dashboard'))
