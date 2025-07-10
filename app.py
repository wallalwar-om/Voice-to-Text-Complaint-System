from flask import Flask, render_template, request, redirect, url_for
import os, base64

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        base64_audio = request.form.get('recordedAudio')
        audio_file = request.files.get('audio_file')

        if base64_audio:
            header, encoded = base64_audio.split(",", 1)
            audio_data = base64.b64decode(encoded)
            with open(os.path.join(UPLOAD_FOLDER, "recorded_audio.webm"), "wb") as f:
                f.write(audio_data)

        if audio_file:
            audio_file.save(os.path.join(UPLOAD_FOLDER, audio_file.filename))

        return redirect(url_for('register', submitted='true'))
    return render_template('register.html')
