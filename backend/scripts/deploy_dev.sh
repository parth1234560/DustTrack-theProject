#!/usr/bin/env bash
# Deploy the backend zip to the 7 dev Lambdas. See backend/README.md.
# --configure also sets handlers/timeout/memory and merges table env vars.
# WARNING: --configure drifts from Terraform; the owner must apply the same
# settings in infra/terraform or the next apply reverts them.
set -euo pipefail
cd "$(dirname "$0")/.."
REGION="ap-south-1"
PREFIX="dusttrack-dev"
API_FN="${API_FN:-}"
STEPS="validate_input analyse_image fetch_weather update_cadence score_segment publish_work_list"
CONFIGURE=0
[ "${1:-}" = "--configure" ] && CONFIGURE=1
if [ -z "$API_FN" ] || ! aws lambda get-function --function-name "$API_FN" --region "$REGION" >/dev/null 2>&1; then
  echo "API function not found (API_FN='${API_FN:-unset}'). Candidates:"
  aws lambda list-functions --region "$REGION" --query 'Functions[?contains(FunctionName, `dusttrack`) || contains(FunctionName, `api`)].FunctionName' --output text
  echo "Rerun with API_FN=<name> $0 $*"
  exit 1
fi
./scripts/build_zip.sh >/dev/null
for step in $STEPS; do
  fn="$PREFIX-$(echo "$step" | tr '_' '-')"
  aws lambda update-function-code --function-name "$fn" --zip-file fileb://build/dusttrack-backend.zip --region "$REGION" >/dev/null
  aws lambda wait function-updated --function-name "$fn" --region "$REGION"
  echo "code updated: $fn"
  if [ "$CONFIGURE" = "1" ]; then
    aws lambda update-function-configuration --function-name "$fn" --handler "workflow.$step.handler" --timeout 15 --memory-size 256 --region "$REGION" >/dev/null
    ENV_JSON=$(aws lambda get-function-configuration --function-name "$fn" --region "$REGION" --query 'Environment.Variables // `{}`')
    MERGED=$(TABLES_JSON="$ENV_JSON" PREFIX="$PREFIX" python3 -c "import json,os; e=json.loads(os.environ['TABLES_JSON']); e.setdefault('INSPECTIONS_TABLE', f\"{os.environ['PREFIX']}-inspections\"); e.setdefault('SEGMENTS_TABLE', f\"{os.environ['PREFIX']}-segments\"); e.setdefault('CLEANING_EVENTS_TABLE', f\"{os.environ['PREFIX']}-cleaning-events\"); print(json.dumps(e))")
    aws lambda update-function-configuration --function-name "$fn" --environment "Variables=$MERGED" --region "$REGION" >/dev/null
    echo "configured: $fn (handler/timeout/memory/env merged)"
  fi
done
aws lambda update-function-code --function-name "$API_FN" --zip-file fileb://build/dusttrack-backend.zip --region "$REGION" >/dev/null
aws lambda wait function-updated --function-name "$API_FN" --region "$REGION"
echo "code updated: $API_FN"
if [ "$CONFIGURE" = "1" ]; then
  aws lambda update-function-configuration --function-name "$API_FN" --handler "api.handler.lambda_handler" --timeout 15 --memory-size 256 --region "$REGION" >/dev/null
  echo "configured: $API_FN (handler/timeout/memory)"
  echo "WARNING: --configure drifts from Terraform (see header)."
fi
