#!/usr/bin/env python3
"""
AGI Script: find_available_agent.py
Busca un agente disponible para marcador predictivo/progresivo
"""

import sys
import os
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


def find_available_agent(campaign_id, call_attempt_id=None):
    """
    Busca un agente disponible para la campaña y lo asigna al call_attempt
    """
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Query simple para buscar agente disponible
        query = text("""
            SELECT a.id, a.extension
            FROM agents a
            JOIN campaigns c ON c.group_id = a.group_id
            WHERE c.id = :campaign_id
              AND a.is_active = true
              AND a.status = 'AVAILABLE'::agentstatus
            ORDER BY a.id
            LIMIT 1
        """)

        result = session.execute(query, {"campaign_id": campaign_id}).fetchone()

        if result:
            agent_id = result[0]
            agent_extension = str(result[1])
            
            # Marcar agente como BUSY
            update_agent = text("""
                UPDATE agents SET status = 'BUSY'::agentstatus 
                WHERE id = :agent_id
            """)
            session.execute(update_agent, {"agent_id": agent_id})
            
            # Asignar agente al call_attempt si se proporciona
            if call_attempt_id:
                update_attempt = text("""
                    UPDATE call_attempts 
                    SET agent_id = :agent_id, answered_at = NOW()
                    WHERE id = :call_attempt_id
                """)
                session.execute(update_attempt, {
                    "agent_id": agent_id,
                    "call_attempt_id": call_attempt_id
                })
            
            session.commit()
            session.close()
            return agent_extension
        
        session.close()
        return ""

    except Exception as e:
        sys.stderr.write(f"Error en find_available_agent: {str(e)}\n")
        return ""


def main():
    """Función principal del AGI script"""
    agi = AGI()

    # Obtener variables de canal
    campaign_id = agi.get_variable('CAMPAIGN_ID')
    call_attempt_id = agi.get_variable('CALL_ATTEMPT_ID')

    if not campaign_id:
        agi.verbose("ERROR: CAMPAIGN_ID no proporcionado", 1)
        agi.set_variable('AGENT_EXTENSION', '')
        return

    agi.verbose(f"Buscando agente para campaña {campaign_id}, attempt {call_attempt_id}", 2)

    # Buscar agente disponible
    agent_extension = find_available_agent(campaign_id, call_attempt_id)

    if agent_extension:
        agi.verbose(f"Agente encontrado: {agent_extension}", 2)
        agi.set_variable('AGENT_EXTENSION', agent_extension)
    else:
        agi.verbose("No hay agentes disponibles", 2)
        agi.set_variable('AGENT_EXTENSION', '')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        sys.stderr.write(f"Error fatal en AGI: {str(e)}\n")
        sys.exit(1)
