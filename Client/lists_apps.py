"""
Module to retrieve currently running, user-visible applications on Windows.
Excludes background services and system processes.
Includes support for extracting icons and calculating process duration.
"""

import win32gui
import win32process
import win32con
import win32api
import win32ui
import psutil
import time
import os
import base64
import io
from PIL import Image
from typing import List, Dict, Set


def is_window_visible_and_valid(hwnd: int) -> bool:
    """
    Check if a window is visible and valid for listing.
    Standard "Alt-Tab" style filtering per user request.
    """
    if not win32gui.IsWindowVisible(hwnd):
        return False
    
    title = win32gui.GetWindowText(hwnd)
    if not title or len(title.strip()) == 0:
        return False

    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    
    # Must not be WS_EX_TOOLWINDOW
    if ex_style & win32con.WS_EX_TOOLWINDOW:
        return False

    # Standard "Alt-Tab" style logic:
    # 1. If WS_EX_APPWINDOW is set -> Include.
    # 2. If WS_EX_APPWINDOW is NOT set AND GetWindow(GW_OWNER) == 0 -> Include.
    # 3. Else -> Exclude.
    is_app_window = bool(ex_style & win32con.WS_EX_APPWINDOW)
    has_owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER) != 0
    
    if not (is_app_window or not has_owner):
        return False

    # Maintain Cloaked check for Windows 10/11 UWP apps (Settings, Calculator, etc.)
    # This prevents invisible UWP host windows from appearing.
    try:
        import ctypes
        from ctypes import wintypes
        dwmapi = ctypes.WinDLL("dwmapi")
        DWMWA_CLOAKED = 14
        cloaked = wintypes.DWORD()
        dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        if cloaked.value != 0:
            return False
    except:
        pass
    
    return True


def get_icon_base64(hwnd: int, exe_path: str) -> str:
    """
    Extract the icon for a window or executable and return it as a base64 string.
    """
    hicon = None
    try:
        # Try getting icon from window
        hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)
        if hicon == 0:
            hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)
        
        # Fallback to extracting from .exe file
        if (hicon == 0 or hicon is None) and exe_path and os.path.exists(exe_path):
            large, small = win32gui.ExtractIconEx(exe_path, 0)
            if large:
                hicon = large[0]
                for h in large[1:]: win32gui.DestroyIcon(h)
                for h in small: win32gui.DestroyIcon(h)
            elif small:
                hicon = small[0]
                for h in small[1:]: win32gui.DestroyIcon(h)
        
        if hicon:
            # Convert hicon to bitmap
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, 32, 32)
            hdc_mem = hdc.CreateCompatibleDC()
            hdc_mem.SelectObject(hbmp)
            hdc_mem.DrawIcon((0, 0), hicon)
            
            # Convert bitmap to PIL Image
            bmpinfo = hbmp.GetInfo()
            bmpstr = hbmp.GetBitmapBits(True)
            img = Image.frombuffer('RGBA', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRA', 0, 1)
            
            # Cleanup
            win32gui.ReleaseDC(0, hdc.GetSafeHdc())
            hdc_mem.DeleteDC()
            win32gui.DeleteObject(hbmp.GetHandle())
            
            # Save to base64
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            return "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()
            
    except Exception as e:
        pass
    finally:
        if hicon:
            try: win32gui.DestroyIcon(hicon)
            except: pass
            
    return ""


def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def clean_app_name(filename: str) -> str:
    """Format exe name to be user-friendly (e.g. ms-teams.exe -> MS Teams)."""
    name = os.path.splitext(filename)[0]
    # Handle known cases or common patterns
    name = name.replace('-', ' ').replace('_', ' ')
    if name.lower() == 'chrome': return "Google Chrome"
    if name.lower() == 'ms teams' or name.lower() == 'msteams': return "Microsoft Teams"
    if name.lower() == 'code': return "Visual Studio Code"
    if name.lower() == 'explorer': return "File Explorer"
    
    # Capitalize each word
    return ' '.join(word.capitalize() for word in name.split())


def get_process_info(hwnd: int) -> Dict[str, any]:
    """
    Get enriched process information for a window handle.
    """
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(pid)
        raw_name = process.name()
        exe_path = process.exe() if process.exe() else 'N/A'
        
        # Handle ApplicationFrameHost (UWP apps like Settings, Calculator)
        clean_name = clean_app_name(raw_name)
        if raw_name.lower() == "applicationframehost.exe":
            # For UWP apps, the window title is usually more descriptive than the host process name
            window_title = win32gui.GetWindowText(hwnd)
            if window_title:
                clean_name = window_title

        create_time = process.create_time()
        duration_sec = time.time() - create_time
        
        # Check if this window is currently in the foreground
        is_active = (hwnd == win32gui.GetForegroundWindow())
        
        return {
            'pid': pid,
            'raw_name': raw_name,
            'clean_name': clean_name,
            'exe': exe_path,
            'duration': format_duration(duration_sec),
            'icon': get_icon_base64(hwnd, exe_path),
            'is_active': is_active
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
        return {
            'pid': 0,
            'raw_name': 'Unknown',
            'clean_name': 'Unknown',
            'exe': 'N/A',
            'duration': '00:00:00',
            'icon': "",
            'is_active': False
        }


def get_running_applications() -> List[Dict[str, any]]:
    """
    Get list of currently running, user-visible applications with icons and duration.
    """
    applications = []
    seen_processes = set()
    
    def enum_handler(hwnd, ctx):
        if is_window_visible_and_valid(hwnd):
            title = win32gui.GetWindowText(hwnd)
            info = get_process_info(hwnd)
            
            # Avoid duplicate main windows for same process/title
            unique_key = (info['raw_name'], title)
            if unique_key not in seen_processes:
                seen_processes.add(unique_key)
                applications.append({
                    'title': title,
                    'name': info['clean_name'],
                    'pid': info['pid'],
                    'exe_path': info['exe'],
                    'duration': info['duration'],
                    'icon': info['icon'],
                    'is_active': info['is_active']
                })
    
    win32gui.EnumWindows(enum_handler, None)
    # Sort: put active app first, then by name
    applications.sort(key=lambda x: (not x['is_active'], x['name'].lower()))
    return applications


if __name__ == "__main__":
    print("Retrieving user-visible applications with icons and duration...\n")
    apps = get_running_applications()
    for i, app in enumerate(apps, 1):
        print(f"{i}. {app['name']} (Duration: {app['duration']})")
        print(f"   Window: {app['title']}")
        print(f"   Icon: {'[Extracted]' if app['icon'] else '[None]'}")
        print()
