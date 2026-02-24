import os
import sys
import winshell
from win32com.client import Dispatch

class StartupManager:
    APP_NAME = "EmployeeMonitoring"
    
    @staticmethod
    def get_startup_path():
        """Returns the path to the current user's Startup folder."""
        # This dynamically detects the startup folder for the current user
        return winshell.startup()

    @staticmethod
    def ensure_startup():
        """Creates a shortcut in the Startup folder if it doesn't exist."""
        try:
            # Detect current executable path
            if getattr(sys, 'frozen', False):
                # We are running in a bundle (PyInstaller)
                current_exe = sys.executable
            else:
                # We are running in a normal Python environment
                # This is useful for testing, but in production this will be the .exe path
                current_exe = os.path.abspath(sys.argv[0])

            startup_folder = StartupManager.get_startup_path()
            shortcut_path = os.path.join(startup_folder, f"{StartupManager.APP_NAME}.lnk")

            # Check if shortcut already exists and points to the right path
            # If we moved the exe, we might want to update it
            
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = current_exe
            shortcut.WorkingDirectory = os.path.dirname(current_exe)
            shortcut.IconLocation = current_exe # Use the exe's icon
            shortcut.Description = "Employee Monitoring System Client"
            shortcut.save()
            
            print(f"Startup shortcut verified at: {shortcut_path}")
            return True
        except Exception as e:
            print(f"Failed to configure startup: {e}")
            return False

if __name__ == "__main__":
    # Test it
    StartupManager.ensure_startup()
