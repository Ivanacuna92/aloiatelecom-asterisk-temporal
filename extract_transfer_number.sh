#!/bin/bash
# Script para extraer transfer_number de la respuesta JSON del webhook
# Uso: ./extract_transfer_number.sh 'JSON_STRING'

JSON_INPUT="$1"

# Usar grep y sed para extraer el valor de transfer_number
# Buscar el patrón "transfer_number":"NUMERO" o "transfer_number": "NUMERO"
TRANSFER_NUM=$(echo "$JSON_INPUT" | grep -oP '"transfer_number"\s*:\s*"\K[^"]+' 2>/dev/null)

# Si no encontró con grep -P (Perl regex), intentar con sed
if [ -z "$TRANSFER_NUM" ]; then
    TRANSFER_NUM=$(echo "$JSON_INPUT" | sed -n 's/.*"transfer_number"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' 2>/dev/null)
fi

# Retornar el número (sin espacios ni saltos de línea)
echo -n "$TRANSFER_NUM" | tr -d '\n\r '
