from flask import Flask, request,send_file, render_template, jsonify
from pdf2image import convert_from_bytes
from reportlab.pdfgen import canvas
from datetime import datetime
from PIL import Image
from openai import OpenAI

import pytesseract
import io
import os

openai_client = OpenAI(
  api_key=os.environ['OPENAI_API_KEY'],  # this is also the default, it can be omitted
)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

pdf_images = []
text_list = []
repeate_copy = 3

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit_integer', methods=['POST'])
def submit_integer():
    data = request.get_json()
    number = data.get('number')
    global repeate_copy
    repeate_copy = number
    if not isinstance(number, int):
        return jsonify({'message': 'Invalid input. Must be an integer.'}), 400

    return jsonify({'message': f'You set repeate copies: {number}.'})


@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    global pdf_images
    pdf_images = []
    file = request.files['pdf']
    pages = convert_from_bytes(file.read())
    pdf_images = pages
    img_io = io.BytesIO()
    pages[0].save(img_io, format='PNG')
    img_io.seek(0)
    with open('static/page.png', 'wb') as f:
        f.write(img_io.read())
    return jsonify({'status': 'ok'})

@app.route('/run_ocr', methods=['POST'])
def run_ocr():
    data = request.json
    x, y, w, h = data['x'], data['y'], data['w'], data['h']
    page_num = data.get('page', 0)
    image = pdf_images[page_num]
    region = image.crop((x, y, x + w, y + h))
    text = pytesseract.image_to_string(region)
    text_list.append(text)
    print("now text_list size is : " + str(len(text_list)))
    return jsonify({'text': text.strip()})


@app.route('/query_openai', methods=['GET'])
def query_openai(): 
    now = datetime.now()
    timestamp_string = now.strftime("%Y-%m-%d%H-%M-%S")
    prompt = f'generate {repeate_copy} sample homework questions like following, put a new line between each answer:'

    if not prompt or len(text_list) == 0:
        return jsonify({"error": "Prompt and OCR text are required"}), 400
    
    ai_response = ""
    
    for ocr_text in text_list:
        try:
            full_prompt = f"{prompt}\n{ocr_text}"
            print("---------------------------------------------")
            print(full_prompt)
            response = openai_client.responses.create(
                model="gpt-4.1",
                input=full_prompt
            )
            print("---------------------------------------------")
            print(response.output_text)
            print("---------------------------------------------")
            ai_response += "\n" + response.output_text + "\n"
        except Exception as e:
            print(e)
    
    try:
        pdf_buffer = io.BytesIO()
        p = canvas.Canvas(pdf_buffer)
        max_width = 500
        y = 800

        for line in ai_response.split('\n'):
            lines = []
            while len(line) > 0:
                if len(line) > 100:
                    lines.append(line[:100])
                    line = line[100:]
                else:
                    lines.append(line)
                    break
        
            for wrapped_line in lines:
                p.drawString(50, y, wrapped_line)
                y -= 15
                if y < 50:
                    p.showPage()
                    y = 800

        p.save()
        pdf_buffer.seek(0)

        return send_file(
                pdf_buffer,
                as_attachment=True,
                download_name="homework_questions_" + timestamp_string + ".pdf",
                mimetype="application/pdf"
                )

    except Exception as e:
        print(e)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
