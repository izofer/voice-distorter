import os
import uuid
from flask import Flask, render_template, request, send_from_directory, jsonify
from audio_processor import AudioProcessor

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

processor = AudioProcessor(UPLOAD_FOLDER)

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
    app.run(debug=True)
