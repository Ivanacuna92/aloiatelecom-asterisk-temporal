#!/usr/bin/env python3
"""
AGI: Marcar llamada como abandonada
Notifica al backend que la llamada fue abandonada (timeout sin agente).

Uso en dialplan:
  AGI(mark_abandoned.py,${CALL_ATTEMPT_ID},${WAIT_TIME})
"""
import sys
import json
import urllib.request

BACKEND_URL = "http://157.173.199.200:8000/api/v1"

def agi_send(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
    return sys.stdin.readline().strip()

def agi_verbose(msg, level=1):
    agi_send(f"VERBOSE \"{msg}\" {level}")

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
    wait_time = env.get("agi_arg_2", "0")

    agi_verbose(f"[ABANDONED] Attempt: {call_attempt_id}, Wait: {wait_time}s")

    try:
        url = f"{BACKEND_URL}/dialer/attempts/{call_attempt_id}"
        data = json.dumps({
            "status": "abandoned",
            "wait_time": int(wait_time) if wait_time else 0,
            "disposition": "ABANDONED"
        }).encode()

        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)
        agi_verbose(f"[ABANDONED] Attempt {call_attempt_id} marked as abandoned")
    except Exception as e:
        agi_verbose(f"[ABANDONED] Error: {str(e)}")

if __name__ == "__main__":
    main()
