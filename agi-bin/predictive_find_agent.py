#!/usr/bin/env python3
"""
AGI Script: predictive_find_agent.py
Busca agente disponible para marcador predictivo (más rápido)
"""

import sys
import os
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configuración de base de datos
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_USER = os.getenv('DB_USER', 'aloia_user')
DB_PASS = os.getenv('DB_PASS', 'aloia2025secure')
DB_NAME = os.getenv('DB_NAME', 'aloia_telecom')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


class AGI:
    """Clase simple para manejar protocolo AGI"""

    def __init__(self):
        self.env = {}
        self._read_environment()

    def _read_environment(self):
        """Lee variables de entorno de Asterisk"""
        while True:
            line = sys.stdin.readline().strip()
            if not line:
                break
            key, value = line.split(':', 1)
            self.env[key.strip()] = value.strip()

    def get_variable(self, name):
        """Obtiene una variable de canal"""
        sys.stdout.write(f'GET VARIABLE {name}\n')
        sys.stdout.flush()
        result = sys.stdin.readline().strip()
        if '200 result=1' in result:
            value = result.split('(')[1].split(')')[0]
            return value
        return ""

    def set_variable(self, name, value):
        """Establece una variable de canal"""
        sys.stdout.write(f'SET VARIABLE {name} "{value}"\n')
        sys.stdout.flush()
        sys.stdin.readline()

    def verbose(self, message, level=1):
        """Log verbose en Asterisk"""
        sys.stdout.write(f'VERBOSE "{message}" {level}\n')
        sys.stdout.flush()
        sys.stdin.readline()


def predictive_find_agent(campaign_id, call_attempt_id):
    """
    Busca agente disponible para marcador predictivo

    Args:
        campaign_id: ID de la campaña
        call_attempt_id: ID del intento de llamada

    Returns:
        tuple: (extension, agent_id) o ("", None)
    """
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Buscar agente disponible (query optimizada para velocidad)
        query = text("""
            SELECT a.extension, a.id
            FROM agents a
            JOIN campaigns c ON c.group_id = a.group_id
            WHERE c.id = :campaign_id
              AND a.is_active = true
              AND a.status IN ('available', 'ready', 'AVAILABLE', 'READY')
              AND a.id NOT IN (
                  SELECT DISTINCT agent_id
                  FROM active_calls
                  WHERE agent_id IS NOT NULL
                    AND ended_at IS NULL
              )
            ORDER BY a.last_call_time ASC NULLS FIRST
            LIMIT 1
        """)

        result = session.execute(query, {"campaign_id": campaign_id}).fetchone()

        if result:
            agent_extension = str(result[0])
            agent_id = result[1]

            # Actualizar call_attempt con el agente asignado
            if call_attempt_id:
                update_query = text("""
                    UPDATE call_attempts
                    SET agent_id = :agent_id,
                        status = 'dialing',
                        started_at = :now
                    WHERE id = :call_attempt_id
                """)
                session.execute(update_query, {
                    "agent_id": agent_id,
                    "call_attempt_id": call_attempt_id,
                    "now": datetime.utcnow()
                })
                session.commit()

            session.close()
            return (agent_extension, agent_id)

        session.close()
        return ("", None)

    except Exception as e:
        sys.stderr.write(f"Error en predictive_find_agent: {str(e)}\n")
        return ("", None)


def main():
    """Función principal del AGI script"""
    agi = AGI()

    # Obtener variables
    campaign_id = agi.get_variable('CAMPAIGN_ID')
    call_attempt_id = agi.get_variable('CALL_ATTEMPT_ID')

    if not campaign_id:
        agi.verbose("ERROR: CAMPAIGN_ID no proporcionado", 1)
        agi.set_variable('AGENT_EXTENSION', '')
        return

    agi.verbose(f"Predictive: Buscando agente para campaña {campaign_id}", 2)

    # Buscar agente
    agent_extension, agent_id = predictive_find_agent(campaign_id, call_attempt_id)

    if agent_extension:
        agi.verbose(f"Predictive: Agente {agent_extension} asignado", 2)
        agi.set_variable('AGENT_EXTENSION', agent_extension)
        if agent_id:
            agi.set_variable('AGENT_ID', str(agent_id))
    else:
        agi.verbose("Predictive: Sin agentes disponibles - llamada será abandonada", 2)
        agi.set_variable('AGENT_EXTENSION', '')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        sys.stderr.write(f"Error fatal en AGI: {str(e)}\n")
        sys.exit(1)
