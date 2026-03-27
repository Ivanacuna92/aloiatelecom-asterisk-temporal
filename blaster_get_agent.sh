#!/bin/bash
# =============================================================
# Script: blaster_get_agent.sh
# Descripción: Llama al webhook IVR y devuelve info de transferencia
# Uso: blaster_get_agent.sh <campaign_name> <phone_number> <call_id> <dtmf_option>
# Output format: AGENT_EXT|TRANSFER_NUMBER|QUEUE_ENTRY_ID
#   - Si transfer_agent: "1001||42"
#   - Si transfer_to_number: "|5512345678|42"
#   - Si ninguna: "||"
# =============================================================

CAMPAIGN_NAME="$1"
PHONE_NUMBER="$2"
CALL_ID="$3"
DTMF_OPTION="$4"

# Log para debug
echo "$(date) - Params: $CAMPAIGN_NAME $PHONE_NUMBER $CALL_ID $DTMF_OPTION" >> /tmp/blaster_agent.log

# Llamar al endpoint ivr-webhook (puerto 8000 = backend uvicorn)
RESPONSE=$(curl -s --connect-timeout 5 --max-time 10 -X POST "http://localhost:8000/api/v1/blaster/ivr-webhook" \
    -H "Content-Type: application/json" \
    -d "{\"campaign_id\":\"${CAMPAIGN_NAME}\",\"phone\":\"${PHONE_NUMBER}\",\"call_id\":\"${CALL_ID}\",\"dtmf_option\":\"${DTMF_OPTION}\",\"call_status\":\"answered\",\"duration\":0}")

# Log respuesta para debug
echo "$(date) - Response: $RESPONSE" >> /tmp/blaster_agent.log

# Extraer campos del JSON
if command -v jq &> /dev/null; then
    AGENT_EXT=$(echo "$RESPONSE" | jq -r '.agent_extension // empty' 2>/dev/null)
    TRANSFER_NUM=$(echo "$RESPONSE" | jq -r '.transfer_number // empty' 2>/dev/null)
    QUEUE_ENTRY_ID=$(echo "$RESPONSE" | jq -r '.queue_entry_id // empty' 2>/dev/null)
else
    AGENT_EXT=$(echo "$RESPONSE" | grep -o '"agent_extension"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')
    TRANSFER_NUM=$(echo "$RESPONSE" | grep -o '"transfer_number"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')
    QUEUE_ENTRY_ID=$(echo "$RESPONSE" | grep -o '"queue_entry_id"[[:space:]]*:[[:space:]]*[0-9]*' | grep -o '[0-9]*$')
fi

# Log resultado
echo "$(date) - Result: AGENT=$AGENT_EXT TRANSFER=$TRANSFER_NUM QUEUE=$QUEUE_ENTRY_ID" >> /tmp/blaster_agent.log

# Devolver formato: AGENT|TRANSFER_NUMBER|QUEUE_ENTRY_ID
echo -n "${AGENT_EXT}|${TRANSFER_NUM}|${QUEUE_ENTRY_ID}"
