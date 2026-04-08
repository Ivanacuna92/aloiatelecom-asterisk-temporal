#!/usr/bin/env python3
"""
AGI: Notificar al backend el resultado de una llamada predictiva.
Actualiza el CallAttempt con status final y libera al agente.

Uso en dialplan:
  AGI(predictive_hangup.py,${CALL_ATTEMPT_ID},${DIALSTATUS},${AGENT_EXTENSION})
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
    dial_status = env.get("agi_arg_2", "")
    agent_ext = env.get("agi_arg_3", "")

    agi_verbose(f"[PRED_HANGUP] Attempt: {call_attempt_id}, DialStatus: {dial_status}, Agent: {agent_ext}")

    # Si el agente estuvo conectado, la llamada fue contestada exitosamente
    if agent_ext and dial_status in ("ANSWER", ""):
        mapped_status = "completed"
        disposition = "ANSWER"
    else:
        status_map = {
            "ANSWER": "completed",
            "NOANSWER": "no_answer",
            "NO ANSWER": "no_answer",
            "BUSY": "busy",
            "CONGESTION": "failed",
            "CHANUNAVAIL": "failed",
            "CANCEL": "no_answer",
            "FAILED": "failed",
        }
        mapped_status = status_map.get(dial_status.upper(), "completed" if agent_ext else "failed")
        disposition = dial_status.upper() if dial_status else "UNKNOWN"

    try:
        # Actualizar call_attempt
        url = f"{BACKEND_URL}/dialer/attempts/{call_attempt_id}"
        payload = {
            "status": mapped_status,
            "disposition": disposition,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=5)
        agi_verbose(f"[PRED_HANGUP] Attempt {call_attempt_id} -> {mapped_status}/{disposition}")
    except Exception as e:
        agi_verbose(f"[PRED_HANGUP] Error updating attempt: {e}")

    # Liberar agente (volver a AVAILABLE)
    if agent_ext:
        try:
            url = f"{BACKEND_URL}/dialer/debug/connected-agents"
            req = urllib.request.Request(url, method="GET")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=3) as resp:
                agents_data = json.loads(resp.read().decode())
            
            for agent in agents_data.get("agents_info", []):
                if str(agent.get("extension")) == str(agent_ext):
                    release_url = f"{BACKEND_URL}/agents/status/"
                    release_data = json.dumps({
                        "status": "AVAILABLE",
                        "agent_id": int(agent["id"])
                    }).encode()
                    release_req = urllib.request.Request(release_url, data=release_data, method="POST")
                    release_req.add_header("Content-Type", "application/json")
                    urllib.request.urlopen(release_req, timeout=3)
                    agi_verbose(f"[PRED_HANGUP] Agent {agent_ext} released to AVAILABLE")
                    break
        except Exception as e:
            agi_verbose(f"[PRED_HANGUP] Error releasing agent: {e}")

if __name__ == "__main__":
    main()
