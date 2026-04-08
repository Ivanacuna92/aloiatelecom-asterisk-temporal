#!/usr/bin/env python3
"""
AGI: Notificar al backend que la llamada terminó (hangup).
POST /api/v1/blaster/queue/{queue_entry_id}/hangup

Uso: AGI(blaster_queue_hangup.py,${QUEUE_ENTRY_ID},${DURATION},${RECORDING_FILE})
"""
import sys, json, urllib.request

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

    queue_id = env.get("agi_arg_1", "")
    duration = env.get("agi_arg_2", "0")
    recording_file = env.get("agi_arg_3", "")

    if not queue_id:
        agi_verbose("[BLASTER_QH] No queue_id provided")
        return

    try:
        url = f"{BACKEND_URL}/blaster/queue/{queue_id}/hangup"
        payload = {
            "duration": int(duration) if duration else 0,
            "hangup_cause": env.get("agi_arg_4", "normal"),
            "recording_file": recording_file if recording_file else None
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)
        agi_verbose(f"[BLASTER_QH] Hangup sent for queue {queue_id}")
    except Exception as e:
        agi_verbose(f"[BLASTER_QH] Error: {str(e)}")

if __name__ == "__main__":
    main()
