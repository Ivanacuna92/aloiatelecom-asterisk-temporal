#!/usr/bin/env python3
"""
AGI Script: mark_abandoned.py
Marca una llamada como abandonada cuando no hay agentes disponibles
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

    def verbose(self, message, level=1):
        """Log verbose en Asterisk"""
        sys.stdout.write(f'VERBOSE "{message}" {level}\n')
        sys.stdout.flush()
        sys.stdin.readline()


def mark_call_abandoned(call_attempt_id):
    """
    Marca un intento de llamada como abandonado

    Args:
        call_attempt_id: ID del intento de llamada

    Returns:
        bool: True si se marcó correctamente
    """
    engine = None
    session = None
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Actualizar call_attempt (usar NOW() de PostgreSQL, no datetime de Python)
        update_query = text("""
            UPDATE call_attempts
            SET status = 'abandoned',
                was_abandoned = true,
                abandon_reason = 'No agents available',
                ended_at = NOW()
            WHERE id = :call_attempt_id
        """)

        session.execute(update_query, {
            "call_attempt_id": call_attempt_id
        })

        # Obtener campaign_id y lead_id
        info_query = text("""
            SELECT campaign_id, lead_id FROM call_attempts WHERE id = :call_attempt_id
        """)
        result = session.execute(info_query, {"call_attempt_id": call_attempt_id}).fetchone()

        if result:
            campaign_id = result[0]
            lead_id = result[1]

            # Incrementar contador de abandonadas en dialer_settings
            stats_query = text("""
                UPDATE dialer_settings
                SET total_calls_abandoned = COALESCE(total_calls_abandoned, 0) + 1,
                    current_abandon_rate = CASE
                        WHEN COALESCE(total_calls_made, 0) > 0
                        THEN CAST((COALESCE(total_calls_abandoned, 0) + 1) * 100.0 / total_calls_made AS INTEGER)
                        ELSE 0
                    END
                WHERE campaign_id = :campaign_id
            """)
            session.execute(stats_query, {"campaign_id": campaign_id})

            # Actualizar unified_status del lead (abandonada = no contactado... por ahora)
            if lead_id:
                # Verificar si tiene más reintentos
                retry_check = session.execute(
                    text("""
                        SELECT l.attempts, ds.max_attempts_per_lead
                        FROM leads l
                        JOIN lead_lists ll ON l.list_id = ll.id
                        JOIN dialer_settings ds ON ds.campaign_id = ll.campaign_id
                        WHERE l.id = :lead_id
                    """),
                    {"lead_id": lead_id}
                ).fetchone()

                if retry_check and retry_check[0] >= retry_check[1]:
                    session.execute(
                        text("UPDATE leads SET unified_status = 'no_contactado' WHERE id = :lead_id"),
                        {"lead_id": lead_id}
                    )

        session.commit()
        return True

    except Exception as e:
        sys.stderr.write(f"Error en mark_abandoned: {str(e)}\n")
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
    """Función principal del AGI script"""
    agi = AGI()

    # Obtener CALL_ATTEMPT_ID
    call_attempt_id = agi.get_variable('CALL_ATTEMPT_ID')

    if not call_attempt_id:
        agi.verbose("ERROR: CALL_ATTEMPT_ID no proporcionado", 1)
        return

    agi.verbose(f"Marcando llamada {call_attempt_id} como abandonada", 2)

    # Marcar como abandonada
    success = mark_call_abandoned(call_attempt_id)

    if success:
        agi.verbose(f"Llamada {call_attempt_id} marcada como ABANDONADA", 2)
    else:
        agi.verbose(f"ERROR: No se pudo marcar llamada {call_attempt_id} como abandonada", 1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        sys.stderr.write(f"Error fatal en AGI: {str(e)}\n")
        sys.exit(1)
