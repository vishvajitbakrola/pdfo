import os
import uuid
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
from pypdf import PdfWriter
from pdf2docx import Converter

app = Flask(__name__)

# Use /tmp for cloud compatibility (Render/Vercel read-only systems)
UPLOAD_FOLDER = '/tmp/pdf_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB Limit

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_files():
    try:
        mode = request.form.get('mode')
        files = []
        
        # 1. Collect Files
        if mode == 'merge':
            # Collect file_0, file_1, etc.
            keys = sorted([k for k in request.files.keys() if k.startswith('file_')])
            files = [request.files[k] for k in keys]
        else:
            if 'file' in request.files:
                files = [request.files['file']]

        if not files:
            return jsonify({'error': 'No files uploaded'}), 400

        # 2. Save Inputs
        batch_id = str(uuid.uuid4())
        input_paths = []
        
        for f in files:
            filename = secure_filename(f.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{batch_id}_{filename}")
            f.save(save_path)
            input_paths.append(save_path)

        # 3. Define Output
        output_filename = f"Result_{batch_id}.{'pdf' if mode == 'merge' else 'docx'}"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

        # 4. Process (Synchronous)
        if mode == 'merge':
            merger = PdfWriter()
            for path in input_paths:
                merger.append(path)
            merger.write(output_path)
            merger.close()
            
        elif mode == 'convert':
            # Multiprocessing=False prevents server crashes
            cv = Converter(input_paths[0])
            cv.convert(output_path, multi_processing=False)
            cv.close()

        # 5. Cleanup Inputs
        for p in input_paths:
            if os.path.exists(p): os.remove(p)

        # 6. Return Download URL
        return jsonify({
            'status': 'success',
            'download_url': f"/download/{output_filename}"
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File expired", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)