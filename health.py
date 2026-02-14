from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# This will run the Flask server in a separate thread
threading.Thread(target=run_flask, daemon=True).start()