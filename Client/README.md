# Employee Monitoring Client

This is the desktop agent for the Employee Monitoring System. It collects activity data (screenshots, running apps, browser usage) and sends it to the backend.

## Installation

1.  **Dependencies**:
    Ensure you have Python 3.8+ installed.
    Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration**:
    The client interacts with the backend API.
    By default, it expects the backend to be running at `http://localhost:8000/api/v1`.
    You can modify `config.py` if the backend URL is different.

## Running the Client

Run the main script:
```bash
python main.py
```

### First Run
On the first run, the client will display a login window.
Enter your **Employee Credentials** (Email/Password) as created by the administrator.
*Note: You cannot register a new account from the client. An admin must create an account for you via the API or Admin Panel (if supported).*

### Background Service
Once logged in, the application runs in the background.
It connects to the server every few seconds to check for commands (e.g., "Take Screenshot").

## Troubleshooting

-   **Heartbeat Failed**: If the client exits or prints "Heartbeat failed", your session token might be expired. Restart the client to log in again.
-   **Connection Error**: Ensure the backend server is running and accessible.
