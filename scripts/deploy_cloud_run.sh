#!/usr/bin/env bash
set -euo pipefail

service_name="strength-atlas"
migration_job_name="strength-atlas-migrate"
repository_name="strength-atlas"
runtime_service_account_name="strength-atlas-runtime"
default_region="us-central1"
default_env_file="var/atlas/cloud-run.env.yaml"

usage() {
  echo "Usage: scripts/deploy_cloud_run.sh PROJECT_ID [REGION] [ENV_FILE]" >&2
  echo "Optional: set ATLAS_PRODUCTION_ORIGIN=https://your-domain.example" >&2
}

fail() {
  echo "cloud-run-deploy: $*" >&2
  exit 1
}

[[ $# -ge 1 && $# -le 3 ]] || {
  usage
  exit 2
}

project_id="$1"
region="${2:-$default_region}"
env_file="${3:-$default_env_file}"
runtime_identity="${runtime_service_account_name}@${project_id}.iam.gserviceaccount.com"

command -v gcloud >/dev/null 2>&1 || fail "gcloud is not installed"
command -v git >/dev/null 2>&1 || fail "git is not installed"
[[ -f "$env_file" ]] || fail "missing environment file: $env_file"

if ! git diff --quiet || ! git diff --cached --quiet; then
  fail "refusing to deploy an uncommitted worktree"
fi

if rg -n "REPLACE_" "$env_file" >/dev/null; then
  fail "replace every REPLACE_* value in $env_file"
fi

gcloud iam service-accounts describe "$runtime_identity" \
  --project "$project_id" >/dev/null \
  || fail "missing runtime service account: $runtime_identity"

for secret_name in atlas-database-url atlas-supabase-service-key atlas-browser-use-api-key; do
  gcloud secrets describe "$secret_name" --project "$project_id" >/dev/null \
    || fail "missing Secret Manager secret: $secret_name"
done

revision="$(git rev-parse --short=12 HEAD)"
image_uri="${region}-docker.pkg.dev/${project_id}/${repository_name}/app:${revision}"
service_secrets="ATLAS_DATABASE_URL=atlas-database-url:latest,ATLAS_SUPABASE_SERVICE_KEY=atlas-supabase-service-key:latest,ATLAS_BROWSER_USE_API_KEY=atlas-browser-use-api-key:latest"

gcloud services enable \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  --project "$project_id"

if ! gcloud artifacts repositories describe "$repository_name" \
  --location "$region" \
  --project "$project_id" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$repository_name" \
    --repository-format docker \
    --location "$region" \
    --description "Strength Atlas release images" \
    --project "$project_id"
fi

gcloud builds submit . \
  --tag "$image_uri" \
  --region "$region" \
  --project "$project_id"

gcloud run jobs deploy "$migration_job_name" \
  --image "$image_uri" \
  --region "$region" \
  --project "$project_id" \
  --service-account "$runtime_identity" \
  --command alembic \
  --args=-c,alembic.ini,upgrade,head \
  --set-secrets ATLAS_DATABASE_URL=atlas-database-url:latest \
  --tasks 1 \
  --max-retries 0 \
  --task-timeout 10m \
  --cpu 1 \
  --memory 512Mi \
  --quiet

gcloud run jobs execute "$migration_job_name" \
  --region "$region" \
  --project "$project_id" \
  --wait

# The first revision remains private and uses a deliberately invalid host.
# This lets us discover Google's generated URL without exposing a permissive
# TrustedHost configuration.
gcloud run deploy "$service_name" \
  --image "$image_uri" \
  --region "$region" \
  --project "$project_id" \
  --service-account "$runtime_identity" \
  --cpu 1 \
  --memory 1Gi \
  --min 0 \
  --max 1 \
  --concurrency 1 \
  --timeout 60s \
  --port 8080 \
  --execution-environment gen2 \
  --cpu-throttling \
  --no-cpu-boost \
  --env-vars-file "$env_file" \
  --set-secrets "$service_secrets" \
  --no-allow-unauthenticated \
  --quiet

service_url="$(gcloud run services describe "$service_name" \
  --region "$region" \
  --project "$project_id" \
  --format 'value(status.url)')"
[[ "$service_url" == https://* ]] || fail "Cloud Run did not return an HTTPS service URL"

production_origin="${ATLAS_PRODUCTION_ORIGIN:-$service_url}"
[[ "$production_origin" == https://* ]] || fail "ATLAS_PRODUCTION_ORIGIN must start with https://"
production_host="${production_origin#https://}"
[[ "$production_host" != */* ]] || fail "ATLAS_PRODUCTION_ORIGIN must not contain a path"

gcloud run services update "$service_name" \
  --region "$region" \
  --project "$project_id" \
  --cpu 1 \
  --memory 1Gi \
  --min 0 \
  --max 1 \
  --concurrency 1 \
  --timeout 60s \
  --cpu-throttling \
  --no-cpu-boost \
  --update-env-vars "ATLAS_CORS_ALLOWED_ORIGINS=${production_origin},ATLAS_TRUSTED_HOSTS=${production_host}" \
  --quiet

gcloud run services add-iam-policy-binding "$service_name" \
  --region "$region" \
  --project "$project_id" \
  --member allUsers \
  --role roles/run.invoker \
  --quiet

echo "Cloud Run deployment complete: $service_url"
echo "Configured production origin: $production_origin"
