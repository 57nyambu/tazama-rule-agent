#!/bin/bash
set -e

# ─────────────────────────────────────────────────────────────────
# Tazama Rule Installer
# - Extracts version + config data directly from Docker image
# - Registers rule in all DB tables (rule, network_map, typology)
# - Restarts typology-processor automatically
# Usage: sudo bash install-rule.sh
# ─────────────────────────────────────────────────────────────────

NAMESPACE="tazama"
CONFIGMAP="tazama-rule-common-config"
TYPOLOGY_ID="typology-processor@1.0.0"
PG_DEPLOY="postgres"
PG_DB="configuration"
PG_USER="postgres"
TENANT_ID="DEFAULT"

# How long to keep polling logs for stream names (seconds)
LOG_POLL_TIMEOUT=60
LOG_POLL_INTERVAL=3

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()   { echo -e "${GREEN}[INFO]${NC}  $1"; }
prompt() { echo -e "${CYAN}[INPUT]${NC} $1"; }
warn()   { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
pg()     { kubectl exec -i deployment/${PG_DEPLOY} -n ${NAMESPACE} -- psql -U ${PG_USER} -d ${PG_DB} -c "$1"; }
pg_val() { kubectl exec -i deployment/${PG_DEPLOY} -n ${NAMESPACE} -- psql -U ${PG_USER} -d ${PG_DB} -t -A -c "$1"; }

echo ""
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo -e "${GREEN}   Tazama Rule Installer               ${NC}"
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo ""

# ── Step 1: Basic inputs ──────────────────────────────────────────
prompt "Rule number (e.g. 006, 007, 028):"
read -p "  > " RULE_NUM

prompt "Docker image tag (e.g. 3.0.0):"
read -p "  > " IMAGE_TAG

RULE_NAME="rule-${RULE_NUM}"
IMAGE="tazamaorg/${RULE_NAME}:${IMAGE_TAG}"
DEPLOY_FILE="${RULE_NAME}-deploy.yaml"

# ── Step 2: Extract data from image via docker cp ─────────────────
# Uses 'docker create' (no container started) + 'docker cp' to read files.
# Works even when the image has no shell or node in PATH.
info "Pulling image ${IMAGE}..."
docker pull ${IMAGE} || error "Failed to pull image ${IMAGE}"

info "Inspecting image contents (no container started)..."
TMP_CONTAINER=$(docker create ${IMAGE} 2>/dev/null)

extract_file() {
  docker cp ${TMP_CONTAINER}:"$1" - 2>/dev/null | tar -xO 2>/dev/null || true
}

PKG_JSON=$(extract_file /home/app/package.json)
BUNDLED_RULE_VER=""
if [ -n "$PKG_JSON" ]; then
  # The bundled rule library is listed under "dependencies" as "rule": "npm:@tazama-lf/rule-NNN@X.Y.Z"
  # We need that version, NOT the top-level app "version" field.
  # Pattern: "rule": "npm:@tazama-lf/rule-030@2.1.0"  →  extract 2.1.0
  BUNDLED_RULE_VER=$(echo "$PKG_JSON" \
    | grep -o '"rule"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+' \
    | head -1)
  if [ -n "$BUNDLED_RULE_VER" ]; then
    info "Found bundled rule lib version in package.json: ${BUNDLED_RULE_VER}"
  else
    warn "Could not extract rule lib version from package.json — will rely on pod logs."
  fi
fi

# Try common locations for a bundled rule config
BUNDLED_CONFIG=""
for CONFIG_PATH in \
  /home/app/src/config.json \
  /home/app/config/rule-config.json \
  /home/app/build/config.json \
  /home/app/node_modules/@tazama-lf/rule-${RULE_NUM}/config.json; do
  RESULT=$(extract_file "$CONFIG_PATH")
  if [ -n "$RESULT" ]; then
    BUNDLED_CONFIG="$RESULT"
    info "Found bundled config at ${CONFIG_PATH}"
    break
  fi
done

docker rm ${TMP_CONTAINER} >/dev/null 2>&1
info "Image inspection done."
echo ""

# ── Step 3: Deploy pod ────────────────────────────────────────────
info "Writing deployment yaml..."
cat > ${DEPLOY_FILE} <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${RULE_NAME}
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${RULE_NAME}
  template:
    metadata:
      labels:
        app: ${RULE_NAME}
    spec:
      containers:
      - name: ${RULE_NAME}
        image: ${IMAGE}
        envFrom:
        - configMapRef:
            name: ${CONFIGMAP}
        env:
        - name: FUNCTION_NAME
          value: "${RULE_NAME}@${IMAGE_TAG}"
EOF

if kubectl get deployment ${RULE_NAME} -n ${NAMESPACE} >/dev/null 2>&1; then
  warn "Deployment ${RULE_NAME} already exists — updating..."
  kubectl apply -f ${DEPLOY_FILE}
  kubectl rollout restart deployment/${RULE_NAME} -n ${NAMESPACE}
else
  info "Creating deployment ${RULE_NAME}..."
  kubectl apply -f ${DEPLOY_FILE}
fi

info "Waiting for pod to be ready (up to 120s)..."
kubectl rollout status deployment/${RULE_NAME} -n ${NAMESPACE} --timeout=120s

# ── Step 4: Poll logs until stream names appear ───────────────────
info "Polling pod logs for NATS stream names (timeout: ${LOG_POLL_TIMEOUT}s)..."
CONSUMER_STREAM=""
PRODUCER_STREAM=""
ELAPSED=0

while [ $ELAPSED -lt $LOG_POLL_TIMEOUT ]; do
  LOGS=$(kubectl logs -n ${NAMESPACE} deployment/${RULE_NAME} --tail=30 2>/dev/null || true)
  CONSUMER_STREAM=$(echo "$LOGS" | grep -o '"consumerStreamName":"[^"]*"' | cut -d'"' -f4 || true)
  PRODUCER_STREAM=$(echo "$LOGS" | grep -o '"producerStreamName":"[^"]*"' | cut -d'"' -f4 || true)

  if [ -n "$CONSUMER_STREAM" ]; then
    info "Stream names detected after ${ELAPSED}s."
    break
  fi

  echo "  ...waiting (${ELAPSED}s elapsed)"
  sleep ${LOG_POLL_INTERVAL}
  ELAPSED=$((ELAPSED + LOG_POLL_INTERVAL))
done

if [ -z "$CONSUMER_STREAM" ]; then
  # Last resort: try to build from package.json version if we got it
  if [ -n "$BUNDLED_RULE_VER" ]; then
    warn "Logs did not return stream names in time. Using package.json version: ${BUNDLED_RULE_VER}"
    CONSUMER_STREAM="sub-${RULE_NAME}@${BUNDLED_RULE_VER}"
    PRODUCER_STREAM="pub-${RULE_NAME}@${BUNDLED_RULE_VER}"
  else
    error "Could not detect stream names from logs or package.json.\nCheck manually: kubectl logs -n ${NAMESPACE} deployment/${RULE_NAME}"
  fi
fi

# Ground truth version always from the stream name
INTERNAL_VER=$(echo "$CONSUMER_STREAM" | grep -o '@[^@]*$' | tr -d '@')

if [ -n "$BUNDLED_RULE_VER" ] && [ "$BUNDLED_RULE_VER" != "$INTERNAL_VER" ]; then
  warn "package.json rule lib version (${BUNDLED_RULE_VER}) differs from stream version (${INTERNAL_VER}). Using stream version."
fi

RULE_ID="${RULE_NUM}@${INTERNAL_VER}"
VER_CLEAN=$(echo ${INTERNAL_VER} | tr -d '.')
TERM_ID="v${RULE_NUM}at${VER_CLEAN}at${VER_CLEAN}"

echo ""
echo -e "${CYAN}  Detected:${NC}"
echo "    Rule ID        : ${RULE_ID}"
echo "    Consumer stream: ${CONSUMER_STREAM}"
echo "    Producer stream: ${PRODUCER_STREAM}"
echo "    Term ID        : ${TERM_ID}"
echo ""

# ── Step 5: Check existing DB state ──────────────────────────────
RULE_EXISTS=$(pg_val "SELECT COUNT(*) FROM rule WHERE ruleid = '${RULE_ID}';")
NM_RAW=$(pg_val "SELECT configuration->'messages'->0->'typologies'->0->'rules' FROM network_map WHERE configuration->>'active' = 'true';")
NM_EXISTS=$(echo "$NM_RAW" | grep -c "${RULE_ID}" || true)
TY_RAW=$(pg_val "SELECT configuration->'rules' FROM typology WHERE typologyid = '${TYPOLOGY_ID}';")
TY_EXISTS=$(echo "$TY_RAW" | grep -c "${RULE_ID}" || true)

# ── Step 6: Rule description ──────────────────────────────────────
prompt "Rule description (enter to use: 'Rule ${RULE_NUM} Configuration'):"
read -p "  > " RULE_DESC
[ -z "$RULE_DESC" ] && RULE_DESC="Rule ${RULE_NUM} Configuration"

# ── Step 7: Bands ─────────────────────────────────────────────────
echo ""
echo -e "${CYAN}── Band Configuration ───────────────────${NC}"
if [ -n "$BUNDLED_CONFIG" ]; then
  echo -e "${YELLOW}  Bundled config found in image:${NC}"
  echo "$BUNDLED_CONFIG" | python3 -m json.tool 2>/dev/null || echo "$BUNDLED_CONFIG"
  echo ""
fi

prompt "Number of bands:"
read -p "  > " BAND_COUNT

BANDS_JSON=""
PREV_UPPER=""
for ((i=1; i<=BAND_COUNT; i++)); do
  echo "  Band $i of ${BAND_COUNT}:"
  read -p "    subRuleRef (e.g. .0${i}): " BAND_REF
  read -p "    reason: " BAND_REASON
  BAND_ENTRY="{\"reason\": \"${BAND_REASON}\", \"subRuleRef\": \"${BAND_REF}\""
  if [ $i -lt $BAND_COUNT ]; then
    read -p "    upperLimit: " BAND_UPPER
    [ -n "$PREV_UPPER" ] && BAND_ENTRY="${BAND_ENTRY}, \"lowerLimit\": ${PREV_UPPER}"
    BAND_ENTRY="${BAND_ENTRY}, \"upperLimit\": ${BAND_UPPER}"
    PREV_UPPER=$BAND_UPPER
  else
    [ -n "$PREV_UPPER" ] && BAND_ENTRY="${BAND_ENTRY}, \"lowerLimit\": ${PREV_UPPER}"
  fi
  BAND_ENTRY="${BAND_ENTRY}}"
  [ -z "$BANDS_JSON" ] && BANDS_JSON="$BAND_ENTRY" || BANDS_JSON="${BANDS_JSON}, $BAND_ENTRY"
done

# ── Step 8: Exit conditions ───────────────────────────────────────
echo ""
echo -e "${CYAN}── Exit Conditions ──────────────────────${NC}"
prompt "Number of exit conditions (0 for none):"
read -p "  > " EXIT_COUNT
EXIT_JSON=""
for ((i=1; i<=EXIT_COUNT; i++)); do
  echo "  Exit $i of ${EXIT_COUNT}:"
  read -p "    subRuleRef (e.g. .x00): " EXIT_REF
  read -p "    reason: " EXIT_REASON
  ENTRY="{\"reason\": \"${EXIT_REASON}\", \"subRuleRef\": \"${EXIT_REF}\"}"
  [ -z "$EXIT_JSON" ] && EXIT_JSON="$ENTRY" || EXIT_JSON="${EXIT_JSON}, $ENTRY"
done

# ── Step 9: Typology weights ──────────────────────────────────────
echo ""
echo -e "${CYAN}── Typology Weights ─────────────────────${NC}"
echo "  Include every ref the rule can return: band refs, exit refs, .err"
prompt "Number of weight entries:"
read -p "  > " WGHT_COUNT
WGHTS_JSON=""
for ((i=1; i<=WGHT_COUNT; i++)); do
  read -p "  [$i] ref (e.g. .01, .err, .x00): " W_REF
  read -p "  [$i] weight (e.g. 0, 200, 400):   " W_VAL
  ENTRY="{\"ref\": \"${W_REF}\", \"wght\": \"${W_VAL}\"}"
  [ -z "$WGHTS_JSON" ] && WGHTS_JSON="$ENTRY" || WGHTS_JSON="${WGHTS_JSON}, $ENTRY"
done

# ── Step 10: Confirm ──────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo -e "${GREEN}   Summary                             ${NC}"
echo -e "${GREEN}══════════════════════════════════════${NC}"
echo "  Rule ID        : ${RULE_ID}"
echo "  Description    : ${RULE_DESC}"
echo "  Term ID        : ${TERM_ID}"
echo "  Bands          : [${BANDS_JSON}]"
echo "  Exit conds     : [${EXIT_JSON}]"
echo "  Weights        : [${WGHTS_JSON}]"
echo ""
echo "  DB state:"
[ "$RULE_EXISTS" -gt "0" ] \
  && echo "    rule table   : already exists (will skip insert)" \
  || echo "    rule table   : will insert"
[ "$NM_EXISTS" -gt "0" ] \
  && echo "    network_map  : already exists (will skip)" \
  || echo "    network_map  : will add"
[ "$TY_EXISTS" -gt "0" ] \
  && echo "    typology     : already exists (will skip)" \
  || echo "    typology     : will add"
echo ""
prompt "Proceed? (y/n):"
read -p "  > " CONFIRM
[ "$CONFIRM" != "y" ] && error "Aborted."

# ── Step 11: DB writes ────────────────────────────────────────────
info "Writing to database..."

if [ "$RULE_EXISTS" -eq "0" ]; then
  pg "
  INSERT INTO rule (configuration)
  VALUES ('{
      \"id\": \"${RULE_ID}\",
      \"cfg\": \"${INTERNAL_VER}\",
      \"desc\": \"${RULE_DESC}\",
      \"config\": {
          \"bands\": [${BANDS_JSON}],
          \"parameters\": {\"maxQueryRange\": 86400000},
          \"exitConditions\": [${EXIT_JSON}]
      },
      \"tenantId\": \"${TENANT_ID}\"
  }'::jsonb);
  "
  info "Rule inserted into rule table."
else
  warn "Skipped rule table insert (already exists)."
fi

if [ "$NM_EXISTS" -eq "0" ]; then
  pg "
  UPDATE network_map
  SET configuration = jsonb_set(
      configuration,
      '{messages,0,typologies,0,rules}',
      (configuration->'messages'->0->'typologies'->0->'rules')::jsonb
      || '[{\"id\": \"${RULE_ID}\", \"cfg\": \"${INTERNAL_VER}\"}]'::jsonb
  )
  WHERE configuration->>'active' = 'true';
  "
  info "Rule added to network_map."
else
  warn "Skipped network_map (already exists)."
fi

if [ "$TY_EXISTS" -eq "0" ]; then
  pg "
  UPDATE typology
  SET configuration = jsonb_set(
      configuration,
      '{rules}',
      (configuration->'rules')::jsonb
      || '[{
          \"id\": \"${RULE_ID}\",
          \"cfg\": \"${INTERNAL_VER}\",
          \"wghts\": [${WGHTS_JSON}],
          \"termId\": \"${TERM_ID}\"
      }]'::jsonb
  )
  WHERE typologyid = '${TYPOLOGY_ID}';
  "

  # Append termId to expression array
  CURRENT_EXPR=$(pg_val "SELECT configuration->'expression' FROM typology WHERE typologyid = '${TYPOLOGY_ID}';")
  NEW_EXPR=$(echo "$CURRENT_EXPR" | sed "s/]$/, \"${TERM_ID}\"]/")
  pg "
  UPDATE typology
  SET configuration = jsonb_set(
      configuration,
      '{expression}',
      '${NEW_EXPR}'::jsonb
  )
  WHERE typologyid = '${TYPOLOGY_ID}';
  "
  info "Typology weights and expression updated."
else
  warn "Skipped typology (already exists)."
fi

# ── Step 12: Verify ───────────────────────────────────────────────
echo ""
info "Verification:"
echo ""
echo -e "${CYAN}--- rule table ---${NC}"
pg "SELECT ruleid, rulecfg, tenantid FROM rule ORDER BY ruleid;"
echo ""
echo -e "${CYAN}--- network_map rules ---${NC}"
pg "SELECT configuration->'messages'->0->'typologies'->0->'rules' FROM network_map;"
echo ""
echo -e "${CYAN}--- typology rules ---${NC}"
pg "SELECT jsonb_array_elements(configuration->'rules')->>'id' AS rule_id,
          jsonb_array_elements(configuration->'rules')->>'termId' AS term_id
   FROM typology WHERE typologyid = '${TYPOLOGY_ID}';"
echo ""
echo -e "${CYAN}--- typology expression ---${NC}"
pg "SELECT configuration->'expression' FROM typology WHERE typologyid = '${TYPOLOGY_ID}';"

# ── Step 13: Restart typology-processor ──────────────────────────
info "Restarting typology-processor..."
kubectl rollout restart deployment/typology-processor -n ${NAMESPACE}
kubectl rollout status deployment/typology-processor -n ${NAMESPACE} --timeout=90s

echo ""
echo -e "${GREEN}══════════════════════════════════════${NC}"
info "Done! Rule ${RULE_ID} is installed."
echo "  Monitor: kubectl logs -n ${NAMESPACE} deployment/${RULE_NAME} -f"
echo -e "${GREEN}══════════════════════════════════════${NC}"