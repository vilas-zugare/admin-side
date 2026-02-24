import time
import threading
import pyautogui
import psutil
import base64
import io
import json
import logging
import os
import requests
import win32gui
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime

from api_client import APIClient
from config import Config
from lists_apps import get_running_applications
from streamer import start_stream_service

# Setup logging for this module
from logging.handlers import RotatingFileHandler

# Create logger
logger = logging.getLogger("Background")
logger.setLevel(logging.DEBUG)

# File handler
try:
    log_file = Config.LOG_FILE
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
except Exception as e:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.error(f"Failed to setup file logging in background: {e}")

class BackgroundService:
    def __init__(self, screen_lock=None):
        self.api = APIClient()
        self.running = True
        self.screen_lock = screen_lock if screen_lock else threading.Lock()
        self.streamer = None
        logger.info(f"BackgroundService initialized for user: {self.api.headers.get('Authorization')[:15]}...")

    def start(self):
        self.last_heartbeat = time.time()
        self.last_command_poll = time.time()
        
        # Start Heartbeat Thread
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        # Start Command Polling Thread
        threading.Thread(target=self.command_loop, daemon=True).start()
        
        # Keep main thread alive and monitor health
        while self.running:
            self.check_health()
            time.sleep(5)

    def check_health(self):
        """Monitors the health of background threads."""
        now = time.time()
        # If no heartbeat for 120s, something is wrong
        if now - self.last_heartbeat > 120:
            logger.error(f"Heartbeat thread seems stuck! (Last: {now - self.last_heartbeat:.1f}s ago). Restarting...")
            os._exit(401)
        
        # If no command polling for 120s, something is wrong
        if now - self.last_command_poll > 120:
            logger.error(f"Command loop seems stuck! (Last: {now - self.last_command_poll:.1f}s ago). Restarting...")
            os._exit(500)

    def heartbeat_loop(self):
        while self.running:
            self.last_heartbeat = time.time()
            success = self.api.heartbeat()
            if not success:
               # Token likely expired or invalid
               logger.warning("Heartbeat failed (401). Stopping service.")
               self.running = False
               # We need to signal main thread to restart UI.
               # Since this is a thread, we can't easily restart UI from here directly without callbacks.
               # But setting running=False will stop other loops.
               # To be robust, we might exit the process and let a supervisor restart, 
               # or rely on `main.py` logic if we invoke a restart callback.
               # For this Python script:
               os._exit(401) # Exit with specific code that main.py could potentially listen to if it was wrapping this.
               # Actually, `main.py` calls `start_background` which blocks.
               # If we exit process, user has to restart app.
               # Better: `main.py` should loop.
            time.sleep(10)

    def command_loop(self):
        while self.running:
            self.last_command_poll = time.time()
            try:
                commands = self.api.get_commands()
                for cmd in commands:
                    # Run each command in a separate thread to avoid blocking
                    logger.info(f"Dispatching command {cmd.get('command')} to thread...")
                    threading.Thread(target=self.process_command, args=(cmd,), daemon=True).start()
            except Exception as e:
                logger.error(f"Error in command loop: {e}")
            time.sleep(5)

    def process_command(self, cmd):
        command_type = cmd.get("command")
        command_id = cmd.get("id")
        
        try:
            if command_type == "TAKE_SCREENSHOT":
                self.take_screenshot(command_id)
            elif command_type == "GET_RUNNING_APPS":
                self.get_running_apps(command_id)
            elif command_type == "GET_BROWSER_STATUS":
                self.get_browser_status(command_id)
            elif command_type == "SEND_NOTIFICATION":
                self.show_notification(cmd.get("payload", {}), command_id)
            elif command_type == "START_LIVE_STREAM":
                self.start_live_stream()
            elif command_type == "STOP_LIVE_STREAM":
                self.stop_live_stream()
            
            # ACK Command
            self.api.ack_command(command_id, "EXECUTED")
        except Exception as e:
            logger.error(f"Error executing command {command_id}: {e}")
            self.api.ack_command(command_id, "FAILED")

    def take_screenshot(self, command_id):
        # Capture screenshot
        try:
            screenshot = pyautogui.screenshot()
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode()
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return

        url = f"{self.api.base_url}/client/screenshot/upload"
        
        payload = {
            "command_id": command_id,
            "image_base64": img_str
        } 
        
        logger.debug(f"UPLOADING SCREENSHOT to {url}")
        try:
             resp = requests.post(url, json=payload, headers=self.api.headers)
             logger.debug(f"UPLOAD RESULT: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Upload failed: {e}")

    def get_running_apps(self, command_id):
        # Get only user-visible applications (foreground apps with windows)
        apps = []
        try:
            # Use the new lists_apps functionality to get user-visible applications only
            visible_apps = get_running_applications()
            
            # Format the data for upload
            for app in visible_apps:
                apps.append({
                    "name": app['name'],
                    "pid": app['pid'],
                    "title": app['title'],
                    "exe_path": app['exe_path'],
                    "duration": app['duration'],
                    "icon": app['icon'],
                    "is_active": app.get('is_active', False)
                })
            
            logger.info(f"Found {len(apps)} user-visible applications")
        except Exception as e:
            logger.error(f"Error getting apps: {e}")
        
        # Upload
        url = f"{self.api.base_url}/client/apps/upload"
        payload = {
            "command_id": command_id,
            "apps": apps
        }
        logger.debug(f"UPLOADING APPS ({len(apps)}) to {url}")
        try:
            resp = requests.post(url, json=payload, headers=self.api.headers)
            logger.debug(f"Result: {resp.status_code}")
        except Exception as e:
            logger.error(f"App upload failed: {e}")

    def start_live_stream(self):
        """Starts the screen streamer if not already running."""
        if self.streamer and self.streamer.running:
            logger.info("Streamer already running.")
            return

        try:
            token = Config.load_token()
            if not token:
                logger.error("No token found for streamer.")
                return
                
            from streamer import start_stream_service
            self.streamer = start_stream_service(Config.API_BASE_URL, token, self.screen_lock)
            logger.info("Screen streamer service started via command.")
        except Exception as e:
            logger.error(f"Failed to start streamer: {e}")

    def stop_live_stream(self):
        """Stops the screen streamer."""
        if self.streamer:
            self.streamer.stop()
            self.streamer = None
            logger.info("Screen streamer service stopped via command.")
        else:
            logger.info("No streamer active to stop.")

    def get_browser_status(self, command_id):
        """Captures browser status and tab details."""
        browsers = {}
        youtube_open = False
        method_used = "Basic"
        
        try:
            # Try enhanced detection first
            from browser import get_active_browsers
            logger.info("Attempting enhanced browser detection...")
            browsers, youtube_open = get_active_browsers()
            if browsers:
                method_used = "Enhanced"
        except Exception as e:
            logger.warning(f"Enhanced browser detection failed: {e}")

        # If enhanced failed or returned nothing, use basic win32 fallback
        if not browsers:
            logger.info("Using basic win32 fallback for browser detection...")
            browsers, youtube_open = self._get_browser_status_basic_logic()

        # Determine summary browser string
        if not browsers:
            browser_summary = "None detected"
        elif len(browsers) == 1:
            browser_summary = list(browsers.keys())[0]
        else:
            browser_summary = f"Multiple ({', '.join(browsers.keys())})"

        # Upload
        url = f"{self.api.base_url}/client/browser/upload"
        payload = {
            "command_id": command_id,
            "browser": browser_summary,
            "youtube_open": youtube_open,
            "details": {
                "sessions": browsers,
                "meta": {
                    "method": method_used,
                    "scanned_at": datetime.now().isoformat()
                }
            }
        }
        
        logger.info(f"PREPARING BROWSER PAYLOAD: {payload['browser']} - {len(browsers)} browsers in sessions")
        logger.debug(f"FULL BROWSER DETAILS: {payload['details']}")
        
        logger.info(f"UPLOADING BROWSER STATUS ({method_used}) to {url}")
        try:
            resp = requests.post(url, json=payload, headers=self.api.headers)
            logger.debug(f"Upload Result: {resp.status_code}")
        except Exception as e:
            logger.error(f"Browser upload failed: {e}")

    def _get_browser_status_basic_logic(self):
        """Helper for win32gui fallback that matches the 'sessions' format."""
        browsers = {}
        youtube_open = False
        current_time = datetime.now().isoformat()
        
        def enum_window_callback(hwnd, _):
            nonlocal youtube_open
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if not title: return
                
                lower_title = title.lower()
                browser_name = None
                
                if "chrome" in lower_title: browser_name = "Chrome"
                elif "edge" in lower_title: browser_name = "Edge"
                elif "firefox" in lower_title: browser_name = "Firefox"
                elif "brave" in lower_title: browser_name = "Brave"
                
                if browser_name:
                    if browser_name not in browsers: browsers[browser_name] = []
                    browsers[browser_name].append({
                        "title": title,
                        "url": None, # Basic detection can't get URLs
                        "timestamp": current_time,
                        "browser": browser_name
                    })
                
                if "youtube" in lower_title:
                    youtube_open = True
        
        try:
            win32gui.EnumWindows(enum_window_callback, None)
        except:
            pass
            
        return browsers, youtube_open



    def show_notification(self, payload, command_id):
        title = payload.get("title", "Notification")
        message = payload.get("message", "Message from Admin")
        
        def show():
            root = tk.Tk()
            root.title(title)
            root.overrideredirect(True)
            root.attributes('-topmost', True)
            
            bg_color = "#1f2937" 
            text_color = "#f3f4f6"
            blue_color = "#2563eb"
            emerald_color = "#10b981"
            
            root.configure(bg=bg_color)
            w, h = 450, 320
            ws, hs = root.winfo_screenwidth(), root.winfo_screenheight()
            root.geometry('%dx%d+%d+%d' % (w, h, (ws/2)-(w/2), (hs/2)-(h/2)))
            
            frame = tk.Frame(root, bg=bg_color, highlightbackground="#4b5563", highlightthickness=2)
            frame.pack(fill=tk.BOTH, expand=True)

            tk.Label(frame, text=title, bg=bg_color, fg=blue_color, font=("Segoe UI", 14, "bold"), pady=10).pack(fill=tk.X)
            tk.Label(frame, text=message, bg=bg_color, fg=text_color, font=("Segoe UI", 10), wraplength=400).pack(pady=10, padx=20)
            
            # Reply Section
            reply_frame = tk.Frame(frame, bg=bg_color, padx=20)
            reply_frame.pack(fill=tk.X, pady=10)
            
            reply_entry = tk.Entry(reply_frame, bg="#374151", fg="white", insertbackground="white", 
                                  relief=tk.FLAT, font=("Segoe UI", 10))
            reply_entry.pack(fill=tk.X, pady=(0, 10), ipady=8)
            reply_entry.insert(0, "Type your reply...")
            reply_entry.bind("<FocusIn>", lambda e: reply_entry.delete(0, tk.END) if reply_entry.get() == "Type your reply..." else None)

            def send_reply():
                reply_text = reply_entry.get().strip()
                if reply_text and reply_text != "Type your reply...":
                    success = self.api.send_notification_reply(command_id, reply_text)
                    if success:
                        logger.info(f"Reply sent for command {command_id}")
                root.destroy()

            btn_frame = tk.Frame(frame, bg=bg_color)
            tk.Button(btn_frame, text="REPLY", command=send_reply, bg=emerald_color, fg="white", 
                      font=("Segoe UI", 9, "bold"), relief=tk.FLAT, width=15).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="IGNORE", command=root.destroy, bg="#4b5563", fg="white", 
                      font=("Segoe UI", 9, "bold"), relief=tk.FLAT, width=15).pack(side=tk.LEFT, padx=5)
            btn_frame.pack(pady=15)
            
            root.focus_force()
            root.mainloop()
            
        threading.Thread(target=show, daemon=True).start()
