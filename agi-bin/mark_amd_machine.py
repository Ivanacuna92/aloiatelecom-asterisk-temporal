#!/usr/bin/env python3
"""
AGI Script: mark_amd_machine.py
Registra deteccion de contestadora (AMD MACHINE) en la DB.
Actualiza call_attempts con status failed + info AMD, y marca lead.is_voicemail.
"""

import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configuracion de base de datos (mismos defaults que mark_abandoned.py)
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

    def verbose(self, message, level=1):
        """Log verbose en Asterisk"""
        sys.stdout.write(f'VERBOSE "{message}" {level}\n')
        sys.stdout.flush()
        sys.stdin.readline()


def mark_amd_machine(call_attempt_id, amd_status, amd_cause):
    """
    Marca un intento de llamada como contestadora detectada por AMD.

    Args:
        call_attempt_id: ID del intento de llamada
        amd_status: MACHINE, NOTSURE, etc.
        amd_cause: Razon detallada (TOOLONG, MAXWORDS, etc.)

    Returns:
        bool: True si se marco correctamente
    """
    engine = None
    session = None
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Actualizar call_attempt con info AMD
        update_query = text("""
            UPDATE call_attempts
            SET status = 'failed',
                disposition = 'AMD_MACHINE',
                amd_status = :amd_status,
                amd_cause = :amd_cause,
                is_answering_machine = true,
                ended_at = NOW()
            WHERE id = :call_attempt_id
        """)
        session.execute(update_query, {
            "call_attempt_id": call_attempt_id,
            "amd_status": amd_status,
            "amd_cause": amd_cause
        })

        # Obtener lead_id para marcar voicemail
        info_query = text("""
            SELECT lead_id FROM call_attempts WHERE id = :call_attempt_id
        """)
        result = session.execute(info_query, {"call_attempt_id": call_attempt_id}).fetchone()

        if result and result[0]:
            lead_id = result[0]
            session.execute(
                text("UPDATE leads SET is_voicemail = true WHERE id = :lead_id"),
                {"lead_id": lead_id}
            )

        session.commit()
        return True

    except Exception as e:
        sys.stderr.write(f"Error en mark_amd_machine: {str(e)}\n")
        if session:
            try:
                session.rollback()
            except Exception:
                pass
        return False
    finally:
        if session:
            try:
                session.close()
            except Exception:
                pass
        if engine:
            try:
                engine.dispose()
            except Exception:
                pass


def main():
    """Funcion principal del AGI script"""
    agi = AGI()

    # Obtener variables de canal
    call_attempt_id = agi.get_variable('CALL_ATTEMPT_ID')
    amd_status = agi.get_variable('AMDSTATUS')
    amd_cause = agi.get_variable('AMDCAUSE')

    if not call_attempt_id:
        agi.verbose("ERROR: CALL_ATTEMPT_ID no proporcionado", 1)
        return

    agi.verbose(f"AMD MACHINE detectada - call_attempt={call_attempt_id} status={amd_status} cause={amd_cause}", 2)

    success = mark_amd_machine(call_attempt_id, amd_status or "MACHINE", amd_cause or "UNKNOWN")

    if success:
        agi.verbose(f"Llamada {call_attempt_id} marcada como AMD_MACHINE", 2)
    else:
        agi.verbose(f"ERROR: No se pudo marcar llamada {call_attempt_id} como AMD_MACHINE", 1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        sys.stderr.write(f"Error fatal en AGI mark_amd_machine: {str(e)}\n")
        sys.exit(1)
