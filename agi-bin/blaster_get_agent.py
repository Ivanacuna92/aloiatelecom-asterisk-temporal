#!/usr/bin/env python3
"""
AGI: Enviar DTMF al backend y leer respuesta para transferencias.

Hace POST a /api/v1/blaster/ivr-webhook con los datos de la llamada,
lee la respuesta JSON y setea variables de Asterisk para que el dialplan
decida si transferir a agente, número externo, departamento o colgar.

Variables que setea:
  AGENT_EXT        - Extensión del agente (si transfer_agent)
  TRANSFER_NUMBER  - Número externo (si transfer_to_number)
  DEPT_EXT         - Extensión de departamento (si transfer_department)
  QUEUE_ENTRY_ID   - ID del registro en BlasterCallQueue
  HOLD_REQUIRED    - "1" si debe poner MOH al cliente
  TRANSFER_REQUIRED - "1" si debe transferir a número externo

Uso en dialplan:
  AGI(blaster_get_agent.py,${CAMPAIGN_NAME},${PHONE_NUMBER},${UNIQUEID},${DTMF_RESULT},answered,${DURATION})
"""
import sys
import json
import urllib.request

BACKEND_URL = "http://157.173.199.200:8000/api/v1"


def agi_send(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
    return sys.stdin.readline().strip()


def agi_set_variable(name, value):
    agi_send(f'SET VARIABLE {name} "{value}"')


def agi_verbose(msg, level=1):
    agi_send(f'VERBOSE "{msg}" {level}')


def main():
    # Leer headers AGI
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

    agi_verbose(f"[BLASTER_GA] Campaign={campaign_id} Phone={phone} DTMF={dtmf_option}")

    # Inicializar variables por defecto
    agi_set_variable("AGENT_EXT", "")
    agi_set_variable("TRANSFER_NUMBER", "")
    agi_set_variable("DEPT_EXT", "")
    agi_set_variable("QUEUE_ENTRY_ID", "")
    agi_set_variable("HOLD_REQUIRED", "0")
    agi_set_variable("TRANSFER_REQUIRED", "0")

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

        with urllib.request.urlopen(req, timeout=15) as resp:
            response_body = resp.read().decode("utf-8")

        result = json.loads(response_body)
        agi_verbose(f"[BLASTER_GA] Backend response: {json.dumps(result)[:200]}")

        if not result.get("success"):
            agi_verbose(f"[BLASTER_GA] Backend returned success=false")
            return

        # --- Transferencia a agente interno ---
        if result.get("hold_required"):
            agi_set_variable("HOLD_REQUIRED", "1")
            queue_id = result.get("queue_entry_id", "")
            agi_set_variable("QUEUE_ENTRY_ID", str(queue_id))

            agent_ext = result.get("agent_extension", "")
            if agent_ext:
                agi_set_variable("AGENT_EXT", str(agent_ext))
                agi_verbose(f"[BLASTER_GA] Agent transfer: ext={agent_ext} queue={queue_id}")
            else:
                agi_verbose(f"[BLASTER_GA] Hold required but no agent available")

        # --- Transferencia a número externo ---
        if result.get("transfer_required"):
            agi_set_variable("TRANSFER_REQUIRED", "1")
            transfer_num = result.get("transfer_number", "")
            if transfer_num:
                agi_set_variable("TRANSFER_NUMBER", str(transfer_num))
                agi_verbose(f"[BLASTER_GA] External transfer to: {transfer_num}")

        # --- Transferencia a departamento ---
        dept_ext = result.get("department_extension", "")
        if dept_ext:
            agi_set_variable("DEPT_EXT", str(dept_ext))
            agi_verbose(f"[BLASTER_GA] Department transfer to: {dept_ext}")

        agi_verbose("[BLASTER_GA] Variables set OK")

    except Exception as e:
        agi_verbose(f"[BLASTER_GA] Error: {str(e)}")


if __name__ == "__main__":
    main()
