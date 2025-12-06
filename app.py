import os
import uuid
from flask import Flask, render_template, request, send_from_directory, jsonify
from audio_processor import AudioProcessor
import time
from apscheduler.schedulers.background import BackgroundScheduler
import shutil

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

processor = AudioProcessor(UPLOAD_FOLDER)

def cleanup_uploads():
    """Deletes files in uploads folder older than 10 minutes."""
    now = time.time()
    cutoff = now - 600  # 10 minutes in seconds
    print("Running cleanup task...")
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            if os.path.isfile(file_path):
                file_age = os.path.getmtime(file_path)
                if file_age < cutoff:
                    os.remove(file_path)
                    print(f"Deleted old file: {filename}")
        except Exception as e:
            print(f"Error deleting {filename}: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=cleanup_uploads, trigger="interval", minutes=10)
scheduler.start()

@app.route('/')
def index():
    effects_list = processor.get_effects_list()
    return render_template('index.html', effects=effects_list)

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        return jsonify({'error': 'No audio data provided'}), 400
    
    file = request.files['audio_data']
    filename = f"{uuid.uuid4()}.wav" # Save as wav initially from browser
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    
    return jsonify({'filename': filename})

@app.route('/process', methods=['POST'])
def process_audio():
    data = request.json
    filename = data.get('filename')
    # Support both single 'effect' and list 'effects'
    effects = data.get('effects') or data.get('effect')
    params = data.get('params') or {}

    if not filename or not effects:
        return jsonify({'error': 'Missing filename or effects'}), 400

    try:
        audio = processor.load_audio(filename)
        # Apply effect(s)
        processed_audio = processor.apply_effect(audio, effects, params)
        
        output_filename = f"processed_{uuid.uuid4()}.mp3"
        processor.save_audio(processed_audio, output_filename)
        
        return jsonify({'output_filename': output_filename})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    try:
        # Run cleanup once on startup just in case
        cleanup_uploads() 
        app.run(debug=True, use_reloader=False) # Reloader can duplicate threads
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
