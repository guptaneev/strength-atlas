#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "answer-model-deploy: $*" >&2
  exit 1
}

[[ $# -eq 6 ]] || {
  echo "Usage: $0 PROJECT_ID REGION ADAPTER_BUCKET ADAPTER_PREFIX MODEL_VERSION ARTIFACT_SHA256" >&2
  exit 2
}

project_id="$1"
region="$2"
adapter_bucket="$3"
adapter_prefix="${4#/}"
model_version="$5"
artifact_sha256="$6"
service_name="strength-atlas-answer-staging"
repository_name="strength-atlas"
runtime_identity="strength-atlas-runtime@${project_id}.iam.gserviceaccount.com"
api_key_secret="atlas-answer-model-api-key"

command -v gcloud >/dev/null 2>&1 || fail "gcloud is not installed"
command -v git >/dev/null 2>&1 || fail "git is not installed"
[[ "$artifact_sha256" =~ ^[0-9a-f]{64}$ ]] || fail "artifact checksum must be 64 lowercase hex characters"
[[ -n "$(gcloud auth list --filter=status:ACTIVE --format='value(account)')" ]] \
  || fail "no active gcloud account; run gcloud auth login"
git diff --quiet && git diff --cached --quiet || fail "refusing to deploy an uncommitted worktree"

gcloud storage buckets describe "gs://${adapter_bucket}" --project "$project_id" >/dev/null \
  || fail "adapter bucket is unavailable: gs://${adapter_bucket}"
gcloud secrets describe "$api_key_secret" --project "$project_id" >/dev/null \
  || fail "missing Secret Manager secret: $api_key_secret"

revision="$(git rev-parse --short=12 HEAD)"
image_uri="${region}-docker.pkg.dev/${project_id}/${repository_name}/answer-model:${revision}"

gcloud services enable artifactregistry.googleapis.com cloudbuild.googleapis.com run.googleapis.com \
  secretmanager.googleapis.com storage.googleapis.com --project "$project_id"

if ! gcloud artifacts repositories describe "$repository_name" \
  --location "$region" --project "$project_id" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$repository_name" --repository-format docker \
    --location "$region" --project "$project_id"
fi

gcloud builds submit . --config=- --project "$project_id" --region "$region" <<EOF
steps:
- name: gcr.io/cloud-builders/docker
  args: [build, -f, Dockerfile.answer-model, -t, ${image_uri}, .]
images: [${image_uri}]
EOF

gcloud run deploy "$service_name" \
  --image "$image_uri" \
  --project "$project_id" \
  --region "$region" \
  --service-account "$runtime_identity" \
  --execution-environment gen2 \
  --gpu 1 \
  --gpu-type nvidia-l4 \
  --no-gpu-zonal-redundancy \
  --cpu 4 \
  --memory 16Gi \
  --concurrency 1 \
  --min 0 \
  --max 1 \
  --timeout 300s \
  --port 8080 \
  --add-volume "name=answer-model,type=cloud-storage,bucket=${adapter_bucket},readonly=true" \
  --add-volume-mount "volume=answer-model,mount-path=/models" \
  --set-env-vars "ATLAS_ANSWER_SERVER_MODEL_ID=Qwen/Qwen2.5-3B-Instruct,ATLAS_ANSWER_SERVER_ADAPTER_PATH=/models/${adapter_prefix},ATLAS_ANSWER_SERVER_MODEL_VERSION=${model_version},ATLAS_ANSWER_SERVER_ARTIFACT_SHA256=${artifact_sha256}" \
  --set-secrets "ATLAS_ANSWER_SERVER_API_KEY=${api_key_secret}:latest" \
  --no-allow-unauthenticated \
  --quiet

service_url="$(gcloud run services describe "$service_name" --project "$project_id" \
  --region "$region" --format='value(status.url)')"
echo "Answer-model staging deployment complete: ${service_url}/v1/generate"
