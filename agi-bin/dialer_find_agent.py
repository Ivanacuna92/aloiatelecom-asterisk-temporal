#!/usr/bin/env python3
"""
AGI: Buscar agente disponible para llamada predictiva
Consulta al backend API para encontrar un agente disponible
y devuelve la extensión para hacer bridge.

Uso en dialplan:
  AGI(dialer_find_agent.py,${CAMPAIGN_ID},${CALL_ATTEMPT_ID})

Establece:
  AGENT_EXTENSION = extensión del agente (vacío si no hay)
"""
import sys
import json
import urllib.request
import urllib.error

BACKEND_URL = "http://157.173.199.200:8000/api/v1"

def agi_send(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
    return sys.stdin.readline().strip()

def agi_set_variable(name, value):
    agi_send(f"SET VARIABLE {name} {value}")

def agi_verbose(msg, level=1):
    agi_send(f"VERBOSE \"{msg}\" {level}")

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

    # Argumentos
    args = env.get("agi_arg_1", ""), env.get("agi_arg_2", "")
    campaign_id = args[0]
    call_attempt_id = args[1]

    agi_verbose(f"[FIND_AGENT] Campaign: {campaign_id}, Attempt: {call_attempt_id}")

    try:
        # Consultar backend para agente disponible
        url = f"{BACKEND_URL}/dialer/debug/connected-agents"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        # Buscar agente disponible con extensión
        agents = data.get("agents_info", [])
        agent_ext = ""

        for agent in agents:
            if agent.get("status") == "AVAILABLE" and agent.get("extension"):
                agent_ext = str(agent["extension"])
                agent_id = agent.get("id", "")
                agi_verbose(f"[FIND_AGENT] Found agent {agent_id} ext {agent_ext}")

                # Notificar al backend que asignamos este agente
                try:
                    assign_url = f"{BACKEND_URL}/agents/status/"
                    assign_data = json.dumps({
                        "status": "ON_CALL",
                        "agent_id": int(agent_id)
                    }).encode()
                    assign_req = urllib.request.Request(assign_url, data=assign_data, method="POST")
                    assign_req.add_header("Content-Type", "application/json")
                    urllib.request.urlopen(assign_req, timeout=3)
                except Exception as e:
                    agi_verbose(f"[FIND_AGENT] Error setting agent status: {e}")

                # Asignar agent_id al call_attempt para que no se marque como ABANDONED
                try:
                    attempt_url = f"{BACKEND_URL}/dialer/attempts/{call_attempt_id}"
                    attempt_data = json.dumps({
                        "agent_id": int(agent_id)
                    }).encode()
                    attempt_req = urllib.request.Request(attempt_url, data=attempt_data, method="PUT")
                    attempt_req.add_header("Content-Type", "application/json")
                    urllib.request.urlopen(attempt_req, timeout=3)
                    agi_verbose(f"[FIND_AGENT] Assigned agent {agent_id} to attempt {call_attempt_id}")
                except Exception as e:
                    agi_verbose(f"[FIND_AGENT] Error assigning agent to attempt: {e}")

                break

        if not agent_ext:
            agi_verbose("[FIND_AGENT] No available agent found")

        agi_set_variable("AGENT_EXTENSION", agent_ext)

    except Exception as e:
        agi_verbose(f"[FIND_AGENT] Error: {str(e)}")
        agi_set_variable("AGENT_EXTENSION", "")

if __name__ == "__main__":
    main()
