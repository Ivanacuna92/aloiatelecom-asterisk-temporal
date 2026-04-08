#!/usr/bin/env python3
"""
AGI: Notificar al backend que la llamada se conectó con el agente.
POST /api/v1/blaster/queue/{queue_entry_id}/connected

Uso: AGI(blaster_queue_connected.py,${QUEUE_ENTRY_ID})
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
    if not queue_id:
        agi_verbose("[BLASTER_QC] No queue_id provided")
        return

    try:
        url = f"{BACKEND_URL}/blaster/queue/{queue_id}/connected"
        data = json.dumps({"channel": env.get("agi_channel", "")}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)
        agi_verbose(f"[BLASTER_QC] Connected notification sent for queue {queue_id}")
    except Exception as e:
        agi_verbose(f"[BLASTER_QC] Error: {str(e)}")

if __name__ == "__main__":
    main()
