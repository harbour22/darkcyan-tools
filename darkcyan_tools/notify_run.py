import subprocess
import sys
import requests
from pathlib import Path
import socket
from collections import deque
import pty
import os

# Load Slack webhook URL
secrets_path = Path.home() / ".darkcyan" / "darkcyan_secrets.py"
secrets = {}
exec(secrets_path.read_text(), secrets)

webhook_url = secrets.get("SLACK_WEBHOOK")

if not webhook_url:
    print("Slack webhook URL not found in secrets.")
    sys.exit(1)

# Command to run
command = sys.argv[1:]
if not command:
    print("Usage: notify-run <command>")
    sys.exit(1)

# Capture last 20 lines
last_lines = deque(maxlen=20)

# Spawn process attached to pty (pseudo-terminal)
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

# Compose Slack message
hostname = socket.gethostname()
message = (
    f"*Command finished on `{hostname}`*\n"
    f"Command: `{' '.join(command)}`\n"
    f"Exit Code: `{return_code}`\n"
    "Last output:\n"
    "```\n"
    f"{''.join(last_lines)}"
    "```"
)

# Send to Slack
response = requests.post(webhook_url, json={"text": message})

if response.status_code != 200:
    print(f"Slack notification failed: {response.status_code}, {response.text}")

sys.exit(return_code)
