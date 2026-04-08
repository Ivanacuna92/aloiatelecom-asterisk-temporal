#!/usr/bin/env python3
"""
AGI: Notificar al backend el resultado de una llamada progresiva.
Actualiza el CallAttempt con el status final y ended_at.

Uso en dialplan:
  AGI(progressive_hangup.py,${CALL_ATTEMPT_ID},${DIALSTATUS},${DIAL_DURATION},${RECORDING_FILE})
"""
import sys
import json
import urllib.request
from datetime import datetime, timezone

BACKEND_URL = "http://157.173.199.200:8000/api/v1"

def agi_send(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
    return sys.stdin.readline().strip()

def agi_verbose(msg, level=1):
    agi_send(f'VERBOSE "{msg}" {level}')

def main():
    env = {}
    while True:
        line = sys.stdin.readline().strip()
        if not line:
            break
        if ":" in line:
            key, val = line.split(":", 1)
            env[key.strip()] = val.strip()

    call_attempt_id = env.get("agi_arg_1", "")
    dial_status = env.get("agi_arg_2", "FAILED")
    duration = env.get("agi_arg_3", "0")
    recording_file = env.get("agi_arg_4", "")

    agi_verbose(f"[PROG_HANGUP] Attempt: {call_attempt_id}, Status: {dial_status}, Duration: {duration}s")

    # Mapear DIALSTATUS de Asterisk a status del backend
    status_map = {
        "ANSWER": "answered",
        "NOANSWER": "no_answer",
        "NO ANSWER": "no_answer",
        "BUSY": "busy",
        "CONGESTION": "failed",
        "CHANUNAVAIL": "failed",
        "CANCEL": "no_answer",
        "FAILED": "failed",
    }
    mapped_status = status_map.get(dial_status.upper(), "failed")

    try:
        url = f"{BACKEND_URL}/dialer/attempts/{call_attempt_id}"
        payload = {
            "status": mapped_status,
            "disposition": dial_status.upper(),
            "talk_duration": int(duration) if duration else 0,
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }
        if recording_file:
            payload["recording_file"] = recording_file

        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)
        agi_verbose(f"[PROG_HANGUP] Attempt {call_attempt_id} updated to {mapped_status} with ended_at")
    except Exception as e:
        agi_verbose(f"[PROG_HANGUP] Error: {str(e)}")

if __name__ == "__main__":
    main()
