#!/bin/bash
# Blaster webhook helper script
# Receives: campaign_id phone call_id channel dtmf_option duration output_file

CAMPAIGN_ID="$1"
PHONE="$2"
CALL_ID="$3"
CHANNEL="$4"
DTMF_OPTION="$5"
DURATION="$6"
OUTPUT_FILE="$7"

# Call webhook and save response to file
curl -s -X POST "http://localhost:8001/api/v1/blaster/ivr-webhook" \
  -H "Content-Type: application/json" \
  -d "{\"campaign_id\":\"${CAMPAIGN_ID}\",\"phone\":\"${PHONE}\",\"call_id\":\"${CALL_ID}\",\"channel\":\"${CHANNEL}\",\"dtmf_option\":\"${DTMF_OPTION}\",\"call_status\":\"answered\",\"duration\":${DURATION}}" \
  > "$OUTPUT_FILE" 2>/dev/null

# Output the file path for confirmation
echo "$OUTPUT_FILE"
