from flask import Flask, render_template
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    # IMPORTANTE: Hugging Face necesita el puerto 7860
    app.run(host='0.0.0.0', port=7860)