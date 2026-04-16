import json
import os
import subprocess
import threading
import time
from flask import Flask, render_template_string, jsonify, request
from biome_notifier import start_notifier

app = Flask(__name__)

# --- Cấu hình mặc định ---
CONFIG_PATH = "./config.json"
APP_CONFIG = {}

def load_config():
    global APP_CONFIG
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            APP_CONFIG = json.load(f)
    else:
        # Cấu hình mẫu nếu chưa có
        APP_CONFIG = {
            "anti_AFK": False,
            "notifier": {
                "push_current_biome_notification": True,
                "rare_biome_actions": {"toast": True, "vibrate": True},
                "webhook": {"enable": False, "url": ""},
                "private_server_link": "",
                "webhook_notification": {"NORMAL": False, "RAINY": True, "GLITCHED": True}
            }
        }
        save_config()

def save_config():
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(APP_CONFIG, f, indent=4)

load_config()

# --- Quản lý luồng (Workers) ---
status = {
    "auto_biome": "Disabled",
    "last_biome": "UNKNOWN"
}

def run_notifier():
    # Gọi hàm từ file biome_notifier.py của bạn
    start_notifier(APP_CONFIG["notifier"])

# Chạy notifier ngầm ngay khi start
threading.Thread(target=run_notifier, daemon=True).start()

# --- Giao diện HTML (Gộp chung vào file cho tiện) ---
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>SolMacro UI</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; background: #121212; color: white; padding: 20px; }
        .card { background: #1e1e1e; padding: 15px; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        h1 { color: #00e676; text-align: center; }
        .status { font-weight: bold; color: #ffab40; }
        button { 
            background: #00e676; border: none; padding: 10px 20px; 
            border-radius: 5px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 10px;
        }
        input[type="text"] { 
            width: 90%; padding: 10px; margin: 10px 0; border-radius: 5px; border: 1px solid #333; background: #2c2c2c; color: white;
        }
    </style>
</head>
<body>
    <h1>SolMacro Control</h1>
    
    <div class="card">
        <h3>Trạng thái hệ thống</h3>
        <p>Auto Biome: <span class="status">{{ status.auto_biome }}</span></p>
        <p>Biome hiện tại: <span class="status">{{ status.last_biome }}</span></p>
        <button onclick="toggleAction('biome')">Bật/Tắt Auto Biome</button>
    </div>

    <div class="card">
        <h3>Cấu hình Webhook</h3>
        <input type="text" id="webhook_url" placeholder="Nhập Discord Webhook URL" value="{{ config.notifier.webhook.url }}">
        <button onclick="saveWebhook()">Lưu Webhook</button>
    </div>

    <script>
        function toggleAction(type) {
            fetch('/api/toggle/' + type).then(() => location.reload());
        }
        function saveWebhook() {
            let url = document.getElementById('webhook_url').value;
            fetch('/api/save_webhook', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url})
            }).then(() => alert('Đã lưu!'));
        }
    </script>
</body>
</html>
'''

# --- API Routes ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, status=status, config=APP_CONFIG)

@app.route('/api/toggle/biome')
def toggle_biome():
    if status["auto_biome"] == "Disabled":
        status["auto_biome"] = "Enabled"
        # Thêm logic kích hoạt worker ở đây nếu cần
    else:
        status["auto_biome"] = "Disabled"
    return jsonify(success=True)

@app.route('/api/save_webhook', methods=['POST'])
def save_webhook():
    data = request.json
    APP_CONFIG["notifier"]["webhook"]["url"] = data['url']
    APP_CONFIG["notifier"]["webhook"]["enable"] = True
    save_config()
    return jsonify(success=True)

if __name__ == '__main__':
    print("UI đang chạy tại: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000)
