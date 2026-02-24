# Build Client EXE & MSI Installer

This guide explains how to bundle the raw Python `Client` folder into a single `.exe` file using **PyInstaller**, and then wrap that executable into a standard Windows `.msi` (or `.exe`) installer using **Inno Setup**.

## Part 1: Build the Executable (PyInstaller)
*Requirements: You must run these commands from a Windows machine.*

1. Open a terminal (PowerShell or CMD) and navigate to the Client folder:
   ```bash
   cd Client
   ```

2. Install the necessary build tools into your Python environment:
   ```bash
   pip install pyinstaller
   ```

3. Run the following command to build the agent into a single hidden executable.
   * `main.py` is the entrypoint file.
   * `--noconfirm` overwrites previous builds.
   * `--onedir` creates a neat directory with everything bundled (faster startup than `--onefile`).
   * `--windowed` hides the console window from the user entirely.
   ```bash
   pyinstaller --noconfirm --onedir --windowed --name "EmployeeAgent" main.py
   ```

4. Once complete, your built files remain in `dist\EmployeeAgent\`. Verify `EmployeeAgent.exe` works by double clicking it.

## Part 2: Create the MSI Installer (Inno Setup)
Inno Setup relies on a `.iss` script to generate professional installers.

1. Download and install **Inno Setup** from [jrsoftware.org](https://jrsoftware.org/isdl.php).

2. In the `Client` folder, create a new file named `installer_script.iss`.
   Copy and paste the script block below into it exactly as written.

   ```pascal
   [Setup]
   AppName=Employee Monitoring Agent
   AppVersion=1.0
   DefaultDirName={autopf}\EmployeeMonitoringAgent
   DefaultGroupName=Employee Monitoring Agent
   UninstallDisplayIcon={app}\EmployeeAgent.exe
   Compression=lzma2
   SolidCompression=yes
   OutputBaseFilename=EmployeeAgent_Installer
   PrivilegesRequired=admin

   [Files]
   ; This grabs everything inside the dist folder you just generated
   Source: "dist\EmployeeAgent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

   [Icons]
   ; Creates a shortcut in the start menu
   Name: "{group}\Employee Agent"; Filename: "{app}\EmployeeAgent.exe"
   
   [Run]
   ; Automatically start the agent after install
   Filename: "{app}\EmployeeAgent.exe"; Description: "Launch Employee Agent"; Flags: nowait postinstall skipifsilent

   [Registry]
   ; Autostart daemon on Windows Boot (Persistence)
   Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "EmployeeMonitoringAgent"; ValueData: """{app}\EmployeeAgent.exe"""; Flags: uninsdeletevalue
   ```

3. Open the `installer_script.iss` file using the Inno Setup Compiler application.
4. Click **Compile** (or `Ctrl+F9`).
5. A new folder named `Output` will be created inside the `Client` directory containing `EmployeeAgent_Installer.exe`.

*Note: While Inno Setup natively outputs `.exe` installer wrappers, they function identically to an `.msi` installer on Windows (with full Add/Remove Programs support).*

If you absolutely demand a true `.msi` extension file for Enterprise group policy deployments (GPO), you can use the **WiX Toolset** or an MSI wrapper utility, but the Inno setup `.exe` provides all typical installer functionality automatically.
