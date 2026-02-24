import logging
import time
import uiautomation as auto
from datetime import datetime
from config import BrowserConfig
from lists_apps import get_icon_base64

logger = logging.getLogger("BrowserScanner")

def custom_find_all(control, predicate, depth=0, max_depth=BrowserConfig.MAX_SEARCH_DEPTH):
    """
    Recursively find all descendant controls matching the predicate.
    Workaround for missing FindAll method in some uiautomation versions.
    """
    results = []
    if depth > max_depth:
        return results
    
    try:
        children = control.GetChildren()
        for child in children:
            if predicate(child):
                results.append(child)
            
            # Recursively search
            results.extend(custom_find_all(child, predicate, depth + 1, max_depth))
    except Exception as e:
        # Some controls might not allow GetChildren or have access issues
        pass
        
    return results

def extract_url_from_browser_window(window, browser_name):
    """
    Attempt to extract URL from browser window using UI Automation.
    Returns URL string if found, None otherwise.
    """
    try:
        import uiautomation as auto
        
        # Strategy 1: Find Address Bar by Name/AutomationId (Browser specific)
        # Chrome/Edge: The address bar usually has a specific Name or AutomationId
        address_bar = None
        
        # Try to find by name first (Common in Chrome/Edge English versions)
        address_bar = window.EditControl(Name='Address and search bar')
        if not address_bar.Exists(0):
            address_bar = window.EditControl(AutomationId='urlbar') # Firefox
        if not address_bar.Exists(0):
            address_bar = window.EditControl(Name='Search or enter web address') # Brave/Edge fallback
            
        if address_bar.Exists(0):
            try:
                # Use ValuePattern if available
                if hasattr(address_bar, 'GetValuePattern'):
                    p = address_bar.GetValuePattern()
                    if p: return p.Value
                return address_bar.Name
            except:
                pass

        # Strategy 2: Fallback to recursive search if specific controls not found
        try:
            edits = custom_find_all(
                window, 
                lambda c: c.ControlTypeName in ['EditControl', 'ComboBoxControl'] and (c.Name or c.Value), 
                max_depth=BrowserConfig.MAX_SEARCH_DEPTH
            )
            
            for edit in edits:
                value = None
                try:
                    if hasattr(edit, 'GetValuePattern'):
                        p = edit.GetValuePattern()
                        if p: value = p.Value
                except: pass
                
                if not value: value = edit.Name

                if value and (':' in value or '.' in value) and not any(p in value.lower() for p in BrowserConfig.EXCLUDED_BUTTON_PATTERNS):
                    if value.startswith('http') or '.com' in value or '.org' in value or '.net' in value:
                        return value
        except Exception:
            pass
        
        # Strategy 3: Check window name for URL patterns
        window_name = window.Name
        if window_name and ('http://' in window_name or 'https://' in window_name):
             for part in window_name.split(' - '):
                 if 'http://' in part or 'https://' in part:
                     return part.strip()
        
        return None
    except Exception as e:
        logger.debug(f"URL extraction failed for {browser_name}: {e}")
        return None

def get_profile_info(window, proc):
    """
    Extracts profile directory and name from process and window attributes.
    """
    profile_dir = "Default"
    profile_name = None
    
    # 1. Try cmdline for stable ID
    try:
        cmdline = proc.cmdline()
        for arg in cmdline:
            if '--profile-directory=' in arg:
                profile_dir = arg.split('=')[1]
                break
    except:
        pass
        
    # 2. Try window name for friendly name (Heuristic)
    name = window.Name
    if name:
        parts = [p.strip() for p in name.split(' - ')]
        if len(parts) >= 3:
            profile_name = parts[-2]
            
    if not profile_name:
        profile_name = profile_dir
        
    return profile_dir, profile_name

def get_favicon_url(url, title):
    """
    Generate a favicon URL based on the tab's URL or title.
    Uses Google's S2 converter service.
    """
    domain = None
    
    # Try to extract domain from URL
    if url and (url.startswith('http') or '://' in url):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url if '://' in url else 'http://' + url)
            domain = parsed.netloc
        except:
            pass
            
    # Heuristic for common sites if URL is missing
    if not domain and title:
        low_title = title.lower()
        if 'whatsapp' in low_title: domain = 'whatsapp.com'
        elif 'youtube' in low_title: domain = 'youtube.com'
        elif 'gmail' in low_title: domain = 'gmail.com'
        elif 'facebook' in low_title: domain = 'facebook.com'
        elif 'github' in low_title: domain = 'github.com'
        elif 'google' in low_title: domain = 'google.com'
        elif 'slack' in low_title: domain = 'slack.com'
        elif 'linkedin' in low_title: domain = 'linkedin.com'
        elif 'twitter' in low_title or ' x ' in low_title: domain = 'twitter.com'
        elif 'instagram' in low_title: domain = 'instagram.com'
        elif 'stack overflow' in low_title: domain = 'stackoverflow.com'
        elif 'microsoft' in low_title: domain = 'microsoft.com'
        elif 'chatgpt' in low_title or 'openai' in low_title: domain = 'chat.openai.com'
        
    if domain:
        return f"https://www.google.com/s2/favicons?sz=64&domain={domain}"
    
    return ""

def get_active_browsers():
    """
    Scans for open browsers and gets ALL tabs using UI Automation.
    Returns structured data with tab details including URLs and timestamps.
    """
    # Initialize COM for this thread
    try:
        import ctypes
        ctypes.windll.ole32.CoInitialize(None)
    except:
        pass

    logger.debug("get_active_browsers() CALLED")
    browsers = {}
    youtube_open = False
    current_time = datetime.now().isoformat()
    
    try:
        auto.SetGlobalSearchTimeout(BrowserConfig.UI_SEARCH_TIMEOUT_MS / 1000) # helper takes seconds
        desktop = auto.GetRootControl()
        
        # Find all top-level windows
        windows = desktop.GetChildren()
        
        # Cache for browser icons to avoid multiple extractions
        browser_icon_cache = {}
        
        for window in windows:
            if not window.ClassName and not window.Name:
                continue

            # Identify Browser by Process Name (highly reliable)
            browser_name = None
            browser_config = None
            pid = window.ProcessId
            
            try:
                import psutil
                proc = psutil.Process(pid)
                proc_name = proc.name().lower()
                
                if 'chrome.exe' in proc_name: browser_name = 'Chrome'
                elif 'msedge.exe' in proc_name: browser_name = 'Edge'
                elif 'firefox.exe' in proc_name: browser_name = 'Firefox'
                elif 'brave.exe' in proc_name: browser_name = 'Brave'
                
                if browser_name:
                    browser_config = BrowserConfig.BROWSERS.get(browser_name)
                    # Use profile info to differentiate
                    profile_dir, profile_name = get_profile_info(window, proc)
                    
                    # Extract or used cached icon
                    if pid not in browser_icon_cache:
                        try:
                            browser_icon_cache[pid] = get_icon_base64(window.NativeWindowHandle, proc.exe())
                        except:
                            browser_icon_cache[pid] = ""
                    
                    browser_icon = browser_icon_cache[pid]
            except Exception as e:
                logger.debug(f"Browser process error for PID {pid}: {e}")
                continue

            # Fallback for UIA windows that might not resolve to common browser names easily
            if not browser_name:
                for b_name, config in BrowserConfig.BROWSERS.items():
                    if config['class_name'] == window.ClassName:
                        if config['name_pattern'] in window.Name or b_name.lower() in window.Name.lower():
                             browser_name = b_name
                             browser_config = config
                             profile_name = "Default"
                             browser_icon = "" # Hard to get from window handle alone without path sometimes
                             break
            
            if not browser_name:
                continue

            browser_base_name = browser_name
            # Create a unique display name for this browser instance/profile
            browser_display_name = f"{browser_base_name} ({profile_name})" if profile_name != "Default" else browser_base_name

            # Store browser icon in a metadata dict
            if "icon_meta" not in browsers: browsers["icon_meta"] = {}
            if browser_display_name not in browsers["icon_meta"] or browser_icon:
                browsers["icon_meta"][browser_display_name] = browser_icon

            logger.debug(f"Processing {browser_display_name} window: {window.Name}")
            
            # Extract generic window URL (probably active tab)
            window_url = extract_url_from_browser_window(window, browser_base_name)
            
            tabs_found = []
            
            # Find Tabs using recursive search
            try:
                # Look for TabItemControl
                tabs = custom_find_all(
                    window, 
                    lambda c: c.ControlTypeName == 'TabItemControl', 
                    max_depth=7
                )
                
                # If no TabItems, try finding Buttons that look like tabs (fallback)
                if not tabs:
                     btns = custom_find_all(
                         window,
                         lambda c: c.ControlTypeName == 'ButtonControl',
                         max_depth=5
                     )
                     # Filter buttons based on config
                     for btn in btns:
                         name = btn.Name
                         if name and len(name) > 2 and not any(p in name.lower() for p in BrowserConfig.EXCLUDED_BUTTON_PATTERNS):
                              # Treat as potential tab
                              tabs.append(btn)

                # Process found controls
                seen_titles = set()
                
                for tab in tabs:
                    title = tab.Name
                    if not title: continue
                    
                    # Clean title
                    clean = title
                    if browser_config:
                        clean = clean.replace(browser_config['suffix'], "")
                        if profile_name != "Default":
                             clean = clean.replace(f" - {profile_name}", "")
                    
                    # Dedup
                    if clean in seen_titles: continue
                    seen_titles.add(clean)
                    
                    # Skip empty or trivial titles
                    if len(clean) < 2: continue

                    # Construct tab object
                    # Note: Detecting which tab corresponds to 'window_url' is hard.
                    # We usually assume active tab has the URL.
                    # For now, we set URL to None for non-active tabs unless we can extract it from the tab object itself (rare)
                    
                    # Heuristic: If tab title matches window title (minus suffix), it's likely the active one
                    is_active = clean in window.Name
                    tab_url = window_url if is_active else None
                    
                    # Resolve favicon
                    favicon = get_favicon_url(tab_url, clean)

                    tab_obj = {
                        "title": clean,
                        "url": tab_url,
                        "timestamp": current_time,
                        "browser": browser_base_name,
                        "profile": profile_name,
                        "icon": favicon if favicon else (browser_icon or ""),
                        "is_active": is_active
                    }
                    tabs_found.append(tab_obj)
                    
                    if "youtube" in clean.lower():
                        youtube_open = True

            except Exception as e:
                logger.error(f"Error extracting tabs for {browser_name}: {e}")

            # Fallback if no tabs found: Use window title as single tab
            if not tabs_found:
                win_name = window.Name
                clean = win_name
                if browser_config:
                     clean = clean.replace(browser_config['suffix'], "")
                
                tab_url = window_url
                favicon = get_favicon_url(tab_url, clean)

                tab_obj = {
                    "title": clean,
                    "url": tab_url,
                    "timestamp": current_time,
                    "browser": browser_base_name,
                    "profile": profile_name,
                    "icon": favicon if favicon else (browser_icon or ""),
                    "is_active": True
                }
                tabs_found.append(tab_obj)
                if "youtube" in clean.lower():
                    youtube_open = True
            
            if browser_display_name not in browsers:
                browsers[browser_display_name] = []
            
            # Merge to avoid duplicates across multiple windows of the same profile
            # (Though UIA usually handles this within a single window traversal)
            browsers[browser_display_name].extend(tabs_found)

    except ImportError:
        logger.warning("uiautomation not installed. Using basic detection.")
        return get_active_browsers_basic()
    except Exception as e:
        logger.error(f"UIA Error: {e}. Falling back.")
        return get_active_browsers_basic()
    
    if not browsers:
        return get_active_browsers_basic()

    return browsers, youtube_open

def get_active_browsers_basic():
    """Fallback: win32gui implementation"""
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
            clean_title = title
            
            for browser, config in BrowserConfig.BROWSERS.items():
                if config['suffix'].lower() in lower_title:
                    browser_name = browser
                    clean_title = title.replace(config['suffix'], "")
                    break
            
            if browser_name:
                if browser_name not in browsers:
                    browsers[browser_name] = []
                
                tab_obj = {
                    "title": clean_title,
                    "url": None,
                    "timestamp": current_time,
                    "browser": browser_name
                }
                browsers[browser_name].append(tab_obj)

            if "youtube" in lower_title:
                youtube_open = True
    
    try:
        win32gui.EnumWindows(enum_window_callback, None)
    except Exception as e:
        pass
        
    return browsers, youtube_open
