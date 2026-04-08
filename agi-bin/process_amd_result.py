#!/usr/bin/env python3
"""
AGI: Procesar resultado de AMD (Answering Machine Detection)
Registra en el backend si la llamada fue contestada por humano o máquina.

Uso en dialplan:
  AGI(process_amd_result.py,${CALL_ATTEMPT_ID},${AMDSTATUS},${AMDCAUSE})
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
    amd_status = env.get("agi_arg_2", "NOTSURE")
    amd_cause = env.get("agi_arg_3", "")

    agi_verbose(f"[AMD] Attempt: {call_attempt_id}, Status: {amd_status}, Cause: {amd_cause}")

    try:
        url = f"{BACKEND_URL}/dialer/attempts/{call_attempt_id}"
        data = json.dumps({
            "amd_status": amd_status,
            "amd_cause": amd_cause
        }).encode()

        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)
        agi_verbose(f"[AMD] Result saved: {amd_status}")
    except Exception as e:
        agi_verbose(f"[AMD] Error: {str(e)}")

if __name__ == "__main__":
    main()
