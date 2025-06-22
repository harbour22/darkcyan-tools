import subprocess
import sys
import requests
from pathlib import Path
import socket
from collections import deque

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

# Run command, stream output to terminal + capture
process = subprocess.Popen(
    command,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    universal_newlines=True
)

for line in process.stdout:
    print(line, end="")       # stream to terminal
    last_lines.append(line)   # capture for Slack

process.wait()
return_code = process.returncode

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

# Exit with same code as subprocess
sys.exit(return_code)
