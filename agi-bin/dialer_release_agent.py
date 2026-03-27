#!/usr/bin/env python3
"""
AGI Script: dialer_release_agent.py
====================================
Libera un agente al finalizar una llamada predictiva/progresiva.
Se ejecuta desde el handler 'h' (hangup) del dialplan.

Funcionalidad:
- Lee CALL_ATTEMPT_ID y AGENT_EXTENSION de las variables de canal
- Marca Agent.status = AVAILABLE
- Marca AgentSession.status = 'available' y decrementa active_calls
- Actualiza CallAttempt con ended_at y status
- Incrementa total_calls_handled para round-robin

Uso desde Asterisk:
  exten => h,1,AGI(dialer_release_agent.py)
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


def release_agent(call_attempt_id, agent_extension, dialstatus):
    """
    Libera al agente asignado a la llamada.

    1. Busca el call_attempt por ID
    2. Marca Agent.status = AVAILABLE
    3. Decrementa AgentSession.active_calls y pone status = 'available' si active_calls llega a 0
    4. Actualiza call_attempt con ended_at y status final
    5. Incrementa total_calls_handled para round-robin
    """
    engine = None
    session = None
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        Session = sessionmaker(bind=engine)
        session = Session()

        agent_id = None

        # Estrategia 1: Buscar por call_attempt_id
        if call_attempt_id:
            result = session.execute(
                text("SELECT agent_id FROM call_attempts WHERE id = :id"),
                {"id": call_attempt_id}
            ).fetchone()
            if result and result[0]:
                agent_id = result[0]

        # Estrategia 2: Buscar por agent_extension
        if not agent_id and agent_extension:
            result = session.execute(
                text("SELECT id FROM agents WHERE extension = :ext AND is_active = true"),
                {"ext": agent_extension}
            ).fetchone()
            if result:
                agent_id = result[0]

        if not agent_id:
            sys.stderr.write(f"[RELEASE] No agent found for attempt={call_attempt_id} ext={agent_extension}\n")
            return False

        # 1. Marcar Agent como DISPO (debe hacer disposicion antes de volver a AVAILABLE)
        # Previene que el predictivo/progresivo le asigne otra llamada inmediatamente
        session.execute(
            text("UPDATE agents SET status = 'DISPO'::agentstatus WHERE id = :agent_id AND status = 'BUSY'::agentstatus"),
            {"agent_id": agent_id}
        )

        # 2. Actualizar AgentSession: decrementar active_calls y poner after_call_work
        session.execute(
            text("""
                UPDATE agent_sessions
                SET active_calls = GREATEST(0, COALESCE(active_calls, 1) - 1),
                    status = CASE
                        WHEN GREATEST(0, COALESCE(active_calls, 1) - 1) = 0 THEN 'after_call_work'
                        ELSE status
                    END,
                    total_calls_handled = COALESCE(total_calls_handled, 0) + 1
                WHERE agent_id = :agent_id
                  AND logged_out_at IS NULL
            """),
            {"agent_id": agent_id}
        )

        # 3. Actualizar CallAttempt con ended_at, status, y answered_at
        if call_attempt_id:
            final_status = 'completed' if dialstatus == 'ANSWER' else 'failed'
            session.execute(
                text("""
                    UPDATE call_attempts
                    SET ended_at = NOW(),
                        status = :status,
                        answered_at = CASE
                            WHEN :dialstatus = 'ANSWER' AND answered_at IS NULL THEN NOW()
                            ELSE answered_at
                        END
                    WHERE id = :id AND ended_at IS NULL
                """),
                {"id": call_attempt_id, "status": final_status, "dialstatus": dialstatus}
            )

            # 4. Actualizar unified_status del Lead según resultado
            lead_result = session.execute(
                text("SELECT lead_id FROM call_attempts WHERE id = :id"),
                {"id": call_attempt_id}
            ).fetchone()

            if lead_result and lead_result[0]:
                lead_id = lead_result[0]
                if dialstatus == 'ANSWER':
                    # Llamada exitosa - marcar como contactado
                    session.execute(
                        text("""
                            UPDATE leads
                            SET unified_status = 'contactado'
                            WHERE id = :lead_id
                        """),
                        {"lead_id": lead_id}
                    )
                else:
                    # Llamada no exitosa - verificar si tiene más reintentos disponibles
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
                        # Sin más reintentos - marcar como no contactado
                        session.execute(
                            text("""
                                UPDATE leads
                                SET unified_status = 'no_contactado'
                                WHERE id = :lead_id
                            """),
                            {"lead_id": lead_id}
                        )

        session.commit()
        sys.stderr.write(f"[RELEASE] Agent {agent_id} (ext {agent_extension}) released OK\n")
        return True

    except Exception as e:
        sys.stderr.write(f"[RELEASE] Error: {str(e)}\n")
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

    # Obtener variables de canal
    call_attempt_id = agi.get_variable('CALL_ATTEMPT_ID')
    agent_extension = agi.get_variable('AGENT_EXTENSION')
    dialstatus = agi.get_variable('DIALSTATUS')

    agi.verbose(
        f"[RELEASE] attempt={call_attempt_id} agent={agent_extension} dialstatus={dialstatus}",
        1
    )

    if not call_attempt_id and not agent_extension:
        agi.verbose("[RELEASE] No call_attempt_id or agent_extension - nothing to release", 1)
        return

    success = release_agent(call_attempt_id, agent_extension, dialstatus)

    if success:
        agi.verbose(f"[RELEASE] Agent {agent_extension} released successfully", 1)
    else:
        agi.verbose(f"[RELEASE] Failed to release agent {agent_extension}", 1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        sys.stderr.write(f"[RELEASE] Fatal error: {str(e)}\n")
        sys.exit(1)
