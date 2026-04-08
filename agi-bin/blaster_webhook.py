#!/usr/bin/env python3
"""
AGI: Enviar webhook del Blaster al backend
Reporta resultado de llamada IVR (DTMF, duración, estado).

Uso en dialplan:
  AGI(blaster_webhook.py,${CAMPAIGN_NAME},${PHONE_NUMBER},${UNIQUEID},${DTMF_RESULT},${CALL_STATUS},${DURATION})
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

    campaign_id = env.get("agi_arg_1", "")
    phone = env.get("agi_arg_2", "")
    call_id = env.get("agi_arg_3", "")
    dtmf_option = env.get("agi_arg_4", "")
    call_status = env.get("agi_arg_5", "answered")
    duration = env.get("agi_arg_6", "0")

    agi_verbose(f"[BLASTER_WH] Campaign: {campaign_id}, Phone: {phone}, DTMF: {dtmf_option}")

    try:
        url = f"{BACKEND_URL}/blaster/ivr-webhook"
        payload = {
            "campaign_id": campaign_id,
            "phone": phone,
            "call_id": call_id,
            "dtmf_option": dtmf_option if dtmf_option else None,
            "call_status": call_status,
            "duration": int(duration) if duration else 0,
            "channel": env.get("agi_channel", "")
        }

        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=10)
        agi_verbose(f"[BLASTER_WH] Webhook sent OK")
    except Exception as e:
        agi_verbose(f"[BLASTER_WH] Error: {str(e)}")

if __name__ == "__main__":
    main()
