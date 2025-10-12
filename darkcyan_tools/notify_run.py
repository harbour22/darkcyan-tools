import subprocess
import sys
import requests
from pathlib import Path
import socket
from collections import deque
import pty
import os

# Load Pushover API credentials
secrets_path = Path.home() / ".darkcyan" / "darkcyan_secrets.py"
secrets = {}
exec(secrets_path.read_text(), secrets)

pushover_token = secrets.get("PUSHOVER_TOKEN")
pushover_user = secrets.get("PUSHOVER_USER")
pushover_devices = secrets.get("PUSHOVER_DEVICES")  # Optional: comma-separated string or list

if not pushover_token or not pushover_user:
    print("Pushover credentials not found in secrets.")
    sys.exit(1)

# Normalize device list
if pushover_devices:
    if isinstance(pushover_devices, list):
        pushover_devices = ",".join(pushover_devices)
    elif not isinstance(pushover_devices, str):
        print("PUSHOVER_DEVICES must be a string or list.")
        sys.exit(1)

# Command to run
command = sys.argv[1:]
if not command:
    print("Usage: notify-run <command>")
    sys.exit(1)

# Capture last 20 lines
last_lines = deque(maxlen=20)

def read(fd):
    while True:
        try:
            output = os.read(fd, 1024).decode()
        except OSError:
            break
        if not output:
            break
        print(output, end="")
        for line in output.splitlines(keepends=True):
            last_lines.append(line)

pid, fd = pty.fork()
if pid == 0:
    # Child process
    os.execvp(command[0], command)
else:
    # Parent process
    read(fd)
    pid, status = os.waitpid(pid, 0)
    return_code = os.WEXITSTATUS(status)

# Compose Pushover message
hostname = socket.gethostname()
title = f"Command finished on {hostname}"
message = (
    f"Command: {' '.join(command)}\n"
    f"Exit Code: {return_code}\n"
    "Last output:\n"
    f"{''.join(last_lines)}"
)

# Build request payload
data = {
    "token": pushover_token,
    "user": pushover_user,
    "title": title,
    "message": message,
    "expire": 60*60*4,
}

if pushover_devices:
    data["device"] = pushover_devices  # comma-separated list of devices

# Send to Pushover
response = requests.post("https://api.pushover.net/1/messages.json", data=data)

if response.status_code != 200:
    print(f"Pushover notification failed: {response.status_code}, {response.text}")

sys.exit(return_code)
