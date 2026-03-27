#!/usr/bin/env python3
"""
AGI Script: process_amd_result.py
==================================
Script AGI para procesar resultados de AMD (Answering Machine Detection).

Funcionalidad (FASE 2.1):
- Captura AMDSTATUS y AMDCAUSE de Asterisk
- Actualiza CallAttempt con resultados AMD
- Marca is_answering_machine = True si se detectó máquina
- Calcula duración del análisis AMD

Uso desde Asterisk:
  AGI(process_amd_result.py,${CALL_ATTEMPT_ID},${AMDSTATUS},${AMDCAUSE})

Parámetros:
  - call_attempt_id: ID del CallAttempt
  - amd_status: HUMAN, MACHINE, NOTSURE, HANGUP
  - amd_cause: TOOLONG, TOOLSHORT, INITIALSILENCE, HUMAN, MAXWORDS, etc.
"""

import sys
import os
import logging
from datetime import datetime

# Agregar el directorio padre al path para poder importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session

from app.config.database import SessionLocal
from app.models.models import CallAttempt

# Configurar logging
def setup_logging():
    """Configurar logging de forma segura para tests y producción"""
    handlers = []

    # Intentar agregar FileHandler si el directorio existe
    try:
        handlers.append(logging.FileHandler('/var/log/asterisk/agi_process_amd.log'))
    except (FileNotFoundError, PermissionError):
        # Si no existe el directorio o no hay permisos, solo usar stderr
        pass

    # Siempre agregar stderr
    handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=logging.INFO,
        format='[AGI-PROCESS-AMD] %(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

setup_logging()
logger = logging.getLogger(__name__)


class AGI:
    """Clase helper para comunicación AGI con Asterisk"""

    def __init__(self):
        self.env = {}
        self._read_environment()

    def _read_environment(self):
        """Leer variables de entorno de Asterisk"""
        while True:
            line = sys.stdin.readline().strip()
            if not line:
                break
            key, value = line.split(':', 1)
            self.env[key.strip()] = value.strip()

    def verbose(self, message, level=1):
        """Enviar mensaje verbose a Asterisk"""
        sys.stdout.write(f'VERBOSE "{message}" {level}\n')
        sys.stdout.flush()
        sys.stdin.readline()

    def get_variable(self, var_name):
        """Obtener variable de Asterisk"""
        sys.stdout.write(f'GET VARIABLE {var_name}\n')
        sys.stdout.flush()
        result = sys.stdin.readline().strip()
        # Formato: 200 result=1 (valor)
        if '(' in result and ')' in result:
            value = result.split('(')[1].split(')')[0]
            return value
        return None


def process_amd_result(db: Session, call_attempt_id: int, amd_status: str, amd_cause: str = None) -> bool:
    """
    Procesar resultado de AMD y actualizar CallAttempt

    Args:
        db: Sesión de base de datos
        call_attempt_id: ID del call attempt
        amd_status: Status de AMD (HUMAN, MACHINE, NOTSURE, HANGUP)
        amd_cause: Causa del resultado (TOOLONG, TOOLSHORT, etc.)

    Returns:
        bool: True si se procesó correctamente
    """
    try:
        # Buscar el call_attempt
        call_attempt = db.query(CallAttempt).filter(CallAttempt.id == call_attempt_id).first()

        if not call_attempt:
            logger.error(f"CallAttempt {call_attempt_id} not found")
            return False

        campaign_id = call_attempt.campaign_id

        logger.info(f"Processing AMD result for CallAttempt {call_attempt_id} (Campaign: {campaign_id})")
        logger.info(f"AMD Status: {amd_status}, AMD Cause: {amd_cause}")

        # Guardar resultados AMD
        call_attempt.amd_status = amd_status
        call_attempt.amd_cause = amd_cause or "UNKNOWN"

        # Calcular duración de AMD
        # Si tenemos answered_at, calculamos cuánto tiempo tomó el análisis
        if call_attempt.answered_at:
            amd_duration = int((datetime.now() - call_attempt.answered_at).total_seconds() * 1000)
            call_attempt.amd_duration = amd_duration
            logger.info(f"AMD analysis took {amd_duration}ms")
        else:
            call_attempt.amd_duration = 0

        # Determinar si es contestadora automática
        if amd_status == "MACHINE":
            call_attempt.is_answering_machine = True
            logger.info(f"Answering machine detected (Cause: {amd_cause})")
        else:
            call_attempt.is_answering_machine = False
            if amd_status == "HUMAN":
                logger.info("Human detected - call will continue")
            elif amd_status == "NOTSURE":
                logger.info("AMD uncertain - treating as human")
            elif amd_status == "HANGUP":
                logger.info("Client hung up during AMD analysis")

        db.commit()

        logger.info(f"SUCCESS: AMD result processed for CallAttempt {call_attempt_id}")

        return True

    except Exception as e:
        logger.error(f"Error processing AMD result: {e}", exc_info=True)
        db.rollback()
        return False


def main():
    """Función principal del script AGI"""
    agi = AGI()
    db = SessionLocal()

    try:
        # Obtener argumentos desde Asterisk
        # Argumentos: call_attempt_id amd_status [amd_cause]
        args = sys.argv[1:]

        if len(args) < 2:
            logger.error("Missing arguments. Usage: process_amd_result.py <call_attempt_id> <amd_status> [amd_cause]")
            agi.verbose("Error: Missing required arguments")
            return

        call_attempt_id = int(args[0])
        amd_status = args[1].upper()

        # AMD cause es opcional
        amd_cause = None
        if len(args) >= 3:
            amd_cause = args[2].upper()
        else:
            # Intentar obtener de variables de Asterisk si no se pasó como argumento
            amd_cause = agi.get_variable('AMDCAUSE')

        logger.info(f"=== AGI PROCESS AMD STARTED === CallAttempt: {call_attempt_id}, Status: {amd_status}, Cause: {amd_cause}")

        agi.verbose(f"Processing AMD result: {amd_status} ({amd_cause})")

        # Procesar resultado AMD
        if process_amd_result(db, call_attempt_id, amd_status, amd_cause):
            agi.verbose(f"AMD result saved successfully")
            logger.info("SUCCESS: AMD result processed and saved")
        else:
            agi.verbose("Error processing AMD result")
            logger.error("Failed to process AMD result")

        logger.info("=== AGI PROCESS AMD FINISHED ===")

    except Exception as e:
        logger.error(f"Critical error in AGI script: {e}", exc_info=True)
        agi.verbose(f"AGI Error: {str(e)}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
