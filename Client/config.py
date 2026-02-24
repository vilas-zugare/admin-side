import os
import uuid
import platform
import subprocess

class Config:
    API_BASE_URL = "http://localhost:8000/api/v1"
    # API_BASE_URL = "https://empmonitoring.duckdns.org/api/v1"
    # API_BASE_URL = "https://nonobstetrically-nonoptical-raymundo.ngrok-free.dev/api/v1"
    
    # Persistent storage for the token and logs
    APP_DATA_DIR = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), "EmployeeMonitoring")
    TOKEN_FILE = os.path.join(APP_DATA_DIR, "client_token.key")
    LOG_FILE = os.path.join(APP_DATA_DIR, "client.log")
    
    @staticmethod
    def _ensure_data_dir():
        if not os.path.exists(Config.APP_DATA_DIR):
            try:
                os.makedirs(Config.APP_DATA_DIR)
            except Exception as e:
                print(f"Error creating data directory: {e}")

    @staticmethod
    def get_device_id():
        try:
            # Use wmic but handle encoding and potential multiple lines
            output = subprocess.check_output('wmic csproduct get uuid', shell=True)
            # Try different decodings to be safe on Windows
            try:
                decoded = output.decode('utf-8')
            except:
                decoded = output.decode('cp1252', errors='ignore')
            
            lines = [l.strip() for l in decoded.split('\n') if l.strip()]
            if len(lines) > 1:
                # UUID is usually the second line (index 1) after the header 'UUID'
                uuid_str = lines[1]
                # Final check: remove any non-alphanumeric characters except hyphens
                import re
                uuid_str = re.sub(r'[^a-zA-Z0-9-]', '', uuid_str)
                return uuid_str
            return platform.node() # Fallback to hostname
        except Exception:
            # Fallback to MAC address based UUID
            return str(uuid.getnode())

    @staticmethod
    def get_device_name():
        return platform.node()

    @staticmethod
    def save_token(token_data):
        Config._ensure_data_dir()
        with open(Config.TOKEN_FILE, "w") as f:
            # In prod, encrypt this
            f.write(token_data)

    @staticmethod
    def load_token():
        Config._ensure_data_dir()
        if os.path.exists(Config.TOKEN_FILE):
            with open(Config.TOKEN_FILE, "r") as f:
                return f.read().strip()
        return None

    @staticmethod
    def clear_token():
        if os.path.exists(Config.TOKEN_FILE):
            os.remove(Config.TOKEN_FILE)

class BrowserConfig:
    MAX_SEARCH_DEPTH = 8
    UI_SEARCH_TIMEOUT_MS = 500
    
    BROWSERS = {
        'Chrome': {
            'class_name': 'Chrome_WidgetWin_1',
            'name_pattern': 'Google Chrome',
            'suffix': ' - Google Chrome'
        },
        'Edge': {
            'class_name': 'Chrome_WidgetWin_1', # Edge uses same class
            'name_pattern': 'Microsoft Edge',
            'suffix': ' - Microsoft Edge'
        },
        'Firefox': {
            'class_name': 'MozillaWindowClass',
            'name_pattern': 'Firefox',
            'suffix': ' — Mozilla Firefox'
        },
        'Brave': {
             'class_name': 'Chrome_WidgetWin_1',
             'name_pattern': 'Brave',
             'suffix': ' - Brave'
        }
    }
    
    EXCLUDED_BUTTON_PATTERNS = [
        'close', 'minimize', 'maximize', 'restore', 'back', 'forward', 'reload', 
        'home', 'extensions', 'profile', 'menu', 'search', 'side panel', 'tab search'
    ]

