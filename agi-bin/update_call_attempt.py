#!/usr/bin/env python3
"""
AGI Script: update_call_attempt.py
Actualiza el estado final de un intento de llamada
"""

import sys
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configuración de base de datos
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_USER = os.getenv('DB_USER', 'aloia_user')
DB_PASS = os.getenv('DB_PASS', 'aloia2025secure')
DB_NAME = os.getenv('DB_NAME', 'aloia_telecom')

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Mapeo de DIALSTATUS de Asterisk a estados de call_attempt
DIALSTATUS_MAP = {
    'ANSWER': 'answered',
    'BUSY': 'busy',
    'NOANSWER': 'no_answer',
    'CANCEL': 'cancelled',
    'CONGESTION': 'failed',
    'CHANUNAVAIL': 'failed',
    'DONTCALL': 'failed',
    'TORTURE': 'failed',
    'INVALIDARGS': 'failed'
}

# Mapeo de DIALSTATUS a blaster_status para campañas blaster
BLASTER_STATUS_MAP = {
    'ANSWER': 'completed',
    'BUSY': 'busy',
    'NOANSWER': 'no_answer',
    'CANCEL': 'no_answer',
    'CONGESTION': 'failed',
    'CHANUNAVAIL': 'failed',
    'DONTCALL': 'failed',
    'TORTURE': 'failed',
    'INVALIDARGS': 'failed'
}


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


def update_call_attempt(call_attempt_id, dialstatus):
    """
    Actualiza el estado final de un intento de llamada

    Args:
        call_attempt_id: ID del intento de llamada
        dialstatus: Estado de Asterisk (ANSWER, BUSY, NOANSWER, etc.)

    Returns:
        bool: True si se actualizó correctamente
    """
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        now = datetime.utcnow()

        # Mapear DIALSTATUS a nuestro estado
        status = DIALSTATUS_MAP.get(dialstatus, 'failed')

        # Obtener información del call_attempt para calcular duraciones
        info_query = text("""
            SELECT ca.started_at, ca.answered_at, ca.campaign_id, ca.lead_id, c.is_blaster
            FROM call_attempts ca
            LEFT JOIN campaigns c ON c.id = ca.campaign_id
            WHERE ca.id = :call_attempt_id
        """)
        result = session.execute(info_query, {"call_attempt_id": call_attempt_id}).fetchone()

        if not result:
            session.close()
            return False

        started_at = result[0]
        answered_at = result[1]
        campaign_id = result[2]
        lead_id = result[3]
        is_blaster = result[4]

        # Calcular duraciones
        ring_duration = None
        talk_duration = None

        if started_at:
            if answered_at:
                # Tiempo desde inicio hasta respuesta
                ring_duration = int((answered_at - started_at).total_seconds())
                # Tiempo desde respuesta hasta fin
                talk_duration = int((now - answered_at).total_seconds())
            else:
                # Solo timbró, no contestó
                ring_duration = int((now - started_at).total_seconds())

        # Mapear DIALSTATUS a disposition para reportería
        DISPOSITION_MAP = {
            'ANSWER': 'ANSWER',
            'BUSY': 'BUSY',
            'NOANSWER': 'NO_ANSWER',
            'CANCEL': 'CANCEL',
            'CONGESTION': 'CONGESTION',
            'CHANUNAVAIL': 'FAILED',
            'DONTCALL': 'DNC',
            'TORTURE': 'FAILED',
            'INVALIDARGS': 'FAILED'
        }
        disposition = DISPOSITION_MAP.get(dialstatus, 'FAILED')

        # Actualizar call_attempt con disposition
        update_query = text("""
            UPDATE call_attempts
            SET status = :status,
                disposition = :disposition,
                ended_at = :now,
                ring_duration = :ring_duration,
                talk_duration = :talk_duration
            WHERE id = :call_attempt_id
        """)

        session.execute(update_query, {
            "call_attempt_id": call_attempt_id,
            "status": status,
            "disposition": disposition,
            "now": now,
            "ring_duration": ring_duration,
            "talk_duration": talk_duration
        })

        # Actualizar estadísticas de dialer_settings
        if status == 'answered':
            stats_query = text("""
                UPDATE dialer_settings
                SET total_calls_answered = total_calls_answered + 1
                WHERE campaign_id = :campaign_id
            """)
            session.execute(stats_query, {"campaign_id": campaign_id})

            # Actualizar campaign_statistics
            campaign_stats_query = text("""
                UPDATE campaign_statistics
                SET calls_answered_today = calls_answered_today + 1,
                    leads_contacted = leads_contacted + 1,
                    answer_rate = CASE
                        WHEN calls_made_today > 0
                        THEN CAST((calls_answered_today + 1) * 100.0 / calls_made_today AS INTEGER)
                        ELSE 0
                    END
                WHERE campaign_id = :campaign_id
            """)
            session.execute(campaign_stats_query, {"campaign_id": campaign_id})

        elif status in ('busy', 'no_answer', 'failed'):
            # Actualizar contadores de fallos
            campaign_stats_query = text("""
                UPDATE campaign_statistics
                SET calls_failed_today = calls_failed_today + 1
                WHERE campaign_id = :campaign_id
            """)
            session.execute(campaign_stats_query, {"campaign_id": campaign_id})

        # Actualizar blaster_status del lead si es campaña blaster
        sys.stderr.write(f"DEBUG: is_blaster={is_blaster}, lead_id={lead_id}, dialstatus={dialstatus}\n")
        if is_blaster and lead_id:
            blaster_status = BLASTER_STATUS_MAP.get(dialstatus, 'failed')
            sys.stderr.write(f"DEBUG: Updating lead {lead_id} to blaster_status={blaster_status}\n")
            lead_update_query = text("""
                UPDATE leads
                SET blaster_status = :blaster_status
                WHERE id = :lead_id
            """)
            session.execute(lead_update_query, {
                "blaster_status": blaster_status,
                "lead_id": lead_id
            })
            sys.stderr.write(f"DEBUG: Lead update executed\n")

        # Actualizar lead.status para campañas de dialer (predictivo/progresivo)
        if not is_blaster and lead_id:
            # Mapear disposition a lead status enum
            LEAD_STATUS_MAP = {
                'ANSWER': 'CONTACTED',
                'BUSY': 'CALLED',
                'NO_ANSWER': 'CALLED',
                'CANCEL': 'CALLED',
                'CONGESTION': 'CALLED',
                'FAILED': 'CALLED',
                'DNC': 'DO_NOT_CALL',
            }
            new_lead_status = LEAD_STATUS_MAP.get(disposition, 'CALLED')
            sys.stderr.write(f"DEBUG: Updating lead {lead_id} status to {new_lead_status} (disposition={disposition})\n")
            lead_status_query = text("""
                UPDATE leads
                SET status = :new_status::leadstatus
                WHERE id = :lead_id
            """)
            session.execute(lead_status_query, {
                "new_status": new_lead_status,
                "lead_id": lead_id
            })
            sys.stderr.write(f"DEBUG: Lead status updated to {new_lead_status}\n")

        session.commit()
        session.close()
        return True

    except Exception as e:
        sys.stderr.write(f"Error en update_call_attempt: {str(e)}\n")
        return False


def main():
    """Función principal del AGI script"""
    agi = AGI()

    # Obtener variables
    call_attempt_id = agi.get_variable('CALL_ATTEMPT_ID')
    dialstatus = agi.get_variable('DIALSTATUS')

    if not call_attempt_id:
        agi.verbose("ERROR: CALL_ATTEMPT_ID no proporcionado", 1)
        return

    if not dialstatus:
        agi.verbose("ADVERTENCIA: DIALSTATUS no proporcionado, usando FAILED", 1)
        dialstatus = 'FAILED'

    agi.verbose(f"Actualizando llamada {call_attempt_id} con estado {dialstatus}", 2)

    # Actualizar
    success = update_call_attempt(call_attempt_id, dialstatus)

    if success:
        agi.verbose(f"Llamada {call_attempt_id} actualizada correctamente", 2)
    else:
        agi.verbose(f"ERROR: No se pudo actualizar llamada {call_attempt_id}", 1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        sys.stderr.write(f"Error fatal en AGI: {str(e)}\n")
        sys.exit(1)
