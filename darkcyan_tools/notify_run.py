import argparse
import subprocess
import requests
import sys
from pathlib import Path
import importlib.util
import socket

def load_secrets():
    secrets_path = Path.home() / ".darkcyan" / "darkcyan_secrets.py"
    if not secrets_path.is_file():
        print(f"Secrets file not found: {secrets_path}", file=sys.stderr)
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("darkcyan_secrets", str(secrets_path))
    secrets = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(secrets)
    return secrets

def send_slack_notification(webhook_url, message):
    payload = {"text": message}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to send Slack notification: {e}", file=sys.stderr)

def get_last_lines(text, num_lines=20):
    lines = text.strip().splitlines()
    return "\n".join(lines[-num_lines:]) if lines else "(no output)"

def main():
    parser = argparse.ArgumentParser(description="Run a command and notify Slack when done.")
    parser.add_argument("command", help="The shell command to run.")
    args = parser.parse_args()

    secrets = load_secrets()
    webhook_url = getattr(secrets, "SLACK_WEBHOOK_URL", None)
    if not webhook_url:
        print("SLACK_WEBHOOK_URL not found in secrets file.", file=sys.stderr)
        sys.exit(1)

    hostname = socket.gethostname()

    print(f"[{hostname}] Running command: {args.command}")
    result = subprocess.run(args.command, shell=True, capture_output=True, text=True)

    status = "✅ Success" if result.returncode == 0 else "❌ Failed"
    output_tail = get_last_lines(result.stdout)

    message = (
        f"*notify-run* on `{hostname}`:\n"
        f"`{args.command}`\n"
        f"*Status:* {status}\n"
        f"*Exit code:* {result.returncode}\n"
        f"```{output_tail}```"
    )
    send_slack_notification(webhook_url, message)

    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
