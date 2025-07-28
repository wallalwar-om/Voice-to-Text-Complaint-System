from flask import Flask, render_template, request, redirect, Response, url_for, session, flash
import os
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
import speech_recognition as sr
from pydub import AudioSegment
from io import BytesIO
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

MONGO_URI = os.getenv('MONGO_URI')
client = MongoClient(MONGO_URI)

DATABASE = os.getenv('DATABASE')
db = client[DATABASE]
coll = db['complaints']


# passing to all templates using context_processor
@app.context_processor
def inject_role():
    role = db.admins.find_one({'role': 'superadmin'})
    return dict(role=role)


@app.route('/register_superadmin', methods=['GET', 'POST'])
def create_superadmin():

    # existing_superadmin = db.admins.find_one({'role': 'superadmin'})
    # if existing_superadmin:
    #     return redirect(url_for('admin_login'))

    if request.method == 'POST':
        sa_username = request.form['username'].strip()
        sa_password = request.form['password'].strip()
        # confirm_password = request.form['confirm_password'].strip()

        # if db.admins.find_one({"username": sa_username}):
        #     return render_template('admin_register.html', error="Username already exists.")

        # if sa_password != confirm_password:
        #     return render_template('admin_register.html', error="Passwords do not match.")

        db.admins.insert_one({
            "username": sa_username,
            "password": sa_password,
            "role": "superadmin"
        })
        return redirect(url_for('admin_login'))

    return render_template('register_superadmin.html')
    

@app.route('/')
def home():

    complaints = db.complaints.find().sort('date', -1).limit(5)
    total_complaints = db.complaints.count_documents({})

    role = db.admins.find_one({'role': 'superadmin'})

    return render_template('home.html', complaints=complaints, total_complaints=total_complaints, role=role)


@app.route('/register', methods=['GET', 'POST'])
def register():

    transcribed_text = None

    if request.method == 'POST':
        category = request.form.get('category')
        audio_file = request.files.get('audio_file')
        language = request.form.get('language', 'en-IN')
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if audio_file:
            binary_data = audio_file.read()

            try:
                audio = AudioSegment.from_file(BytesIO(binary_data))
                wav_io = BytesIO()
                audio.export(wav_io, format="wav")
                wav_io.seek(0)

                r = sr.Recognizer()
                with sr.AudioFile(wav_io) as source:
                    audio_data = r.record(source)
                    transcribed_text = r.recognize_google(audio_data, language=language)
                    
            except Exception as e:
                transcribed_text = f"Error in transcription: {str(e)}"

            doc = {
                "category": category,
                "recording": binary_data,
                "filename": audio_file.filename,
                "recording_type": "binary",
                "date": current_date,
                "text": transcribed_text,
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
        # confirm_password = request.form['confirm_password'].strip()

        # if db.admins.find_one({"username": username}):
        #     return render_template('admin_register.html', error="Username already exists.")

        # if password != confirm_password:
        #     return render_template('admin_register.html', error="Passwords do not match.")

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

        return Response(audio_data, mimetype='audio/*')
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


@app.route('/admin/dashboard/superadmindashboard')
def superadmin_dashboard():
   
    admins = list(db.admins.find())

    # Convert ObjectIds to strings for safe template rendering
    for admin in admins:
        admin['_id'] = str(admin['_id'])

    return render_template('superadmin_dashboard.html', admins=admins, role=session.get('role'))



@app.route('/promote/<admin_id>')
def promote_admin(admin_id):
    db.admins.update_one({"_id": ObjectId(admin_id)}, {"$set": {"role": "superadmin"}})
    flash("Admin promoted to superadmin.")
    return redirect(url_for('superadmin_dashboard'))


@app.route('/delete/<admin_id>')
def delete_admin(admin_id):
    to_delete = db.admins.find_one({"_id": ObjectId(admin_id)})
    if to_delete['role'] == 'superadmin':
        db.admins.delete_one({"_id": ObjectId(admin_id)})
        session.clear()
        return redirect(url_for('home'))
    else:
        db.admins.delete_one({"_id": ObjectId(admin_id)})
        return redirect(url_for('superadmin_dashboard'))