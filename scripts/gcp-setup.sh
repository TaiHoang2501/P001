#!/bin/sh
# One-time Google Cloud setup for deploying the API to Cloud Run from GitHub Actions
# (.github/workflows/deploy-cloudrun.yml). Safe to re-run: existing resources are kept.
#
#   PROJECT_ID=my-gcp-project GITHUB_REPO=nngocnd/bookingbot-mvp sh scripts/gcp-setup.sh
#
# Needs: gcloud CLI logged in (`gcloud auth login`) as a project Owner, and billing enabled on the project.
# Afterwards it prints the GitHub repository variables to add (Settings -> Secrets and variables -> Actions).
# GitHub authenticates through Workload Identity Federation, so no service-account key is ever created.
set -e

: "${PROJECT_ID:?set PROJECT_ID}"
: "${GITHUB_REPO:?set GITHUB_REPO (owner/name)}"
REGION="${REGION:-asia-southeast1}"
REPOSITORY="${REPOSITORY:-bookingbot}"
DEPLOYER="github-deployer"
RUNTIME="bookingbot-api"
SERVICE="bookingbot-api" # Cloud Run service name in deploy-cloudrun.yml
POOL="github"
PROVIDER="github-oidc"

gcloud config set project "$PROJECT_ID"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

echo "==> Enabling APIs"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com iamcredentials.googleapis.com sts.googleapis.com cloudscheduler.googleapis.com

echo "==> Artifact Registry repository for the images"
gcloud artifacts repositories describe "$REPOSITORY" --location "$REGION" >/dev/null 2>&1 ||
  gcloud artifacts repositories create "$REPOSITORY" --repository-format docker --location "$REGION"

echo "==> Secrets (you are asked for the values the first time)"
create_secret() {
  if gcloud secrets describe "$1" >/dev/null 2>&1; then
    echo "    $1 exists, kept (add a version to change it)"
  else
    printf '    %s: ' "$1"
    stty -echo 2>/dev/null || true
    read -r value
    stty echo 2>/dev/null || true
    echo
    printf '%s' "$value" | gcloud secrets create "$1" --data-file=- --replication-policy automatic
  fi
}
create_secret DATABASE_URL # the same Neon connection string Render uses
create_secret GOOGLE_API_KEY
if ! gcloud secrets describe JWT_SECRET >/dev/null 2>&1; then
  # Production refuses secrets shorter than 32 characters (src/config.py)
  openssl rand -base64 48 | tr -d '\n' |
    gcloud secrets create JWT_SECRET --data-file=- --replication-policy automatic
fi

echo "==> Service accounts"
for sa in "$DEPLOYER" "$RUNTIME"; do
  gcloud iam service-accounts describe "$sa@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null 2>&1 ||
    gcloud iam service-accounts create "$sa"
done
DEPLOYER_EMAIL="$DEPLOYER@$PROJECT_ID.iam.gserviceaccount.com"
RUNTIME_EMAIL="$RUNTIME@$PROJECT_ID.iam.gserviceaccount.com"

# The running service only reads its secrets
for secret in DATABASE_URL GOOGLE_API_KEY JWT_SECRET; do
  gcloud secrets add-iam-policy-binding "$secret" --quiet \
    --member "serviceAccount:$RUNTIME_EMAIL" --role roles/secretmanager.secretAccessor >/dev/null
done

# The deployer pushes images, deploys the service and runs it as the runtime account
for role in roles/run.admin roles/artifactregistry.writer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --quiet \
    --member "serviceAccount:$DEPLOYER_EMAIL" --role "$role" --condition None >/dev/null
done
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_EMAIL" --quiet \
  --member "serviceAccount:$DEPLOYER_EMAIL" --role roles/iam.serviceAccountUser >/dev/null

echo "==> Workload Identity Federation for $GITHUB_REPO"
gcloud iam workload-identity-pools describe "$POOL" --location global >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools create "$POOL" --location global --display-name "GitHub Actions"
gcloud iam workload-identity-pools providers describe "$PROVIDER" --location global \
  --workload-identity-pool "$POOL" >/dev/null 2>&1 ||
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --location global \
    --workload-identity-pool "$POOL" --issuer-uri https://token.actions.githubusercontent.com \
    --attribute-mapping 'google.subject=assertion.sub,attribute.repository=assertion.repository' \
    --attribute-condition "assertion.repository == '$GITHUB_REPO'"
# Only workflows from this repository may act as the deployer
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_EMAIL" --quiet \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/attribute.repository/$GITHUB_REPO" >/dev/null

echo "==> Keep-warm ping (Cloud Scheduler calls /health every 5 minutes so users never wait for a cold start)"
SERVICE_URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)' 2>/dev/null || true)
if [ -z "$SERVICE_URL" ]; then
  echo "    service not deployed yet: re-run this script after the first deploy"
elif gcloud scheduler jobs describe bookingbot-api-warmup --location "$REGION" >/dev/null 2>&1; then
  echo "    bookingbot-api-warmup exists, kept"
else
  gcloud scheduler jobs create http bookingbot-api-warmup --location "$REGION" \
    --schedule '*/5 * * * *' --uri "$SERVICE_URL/health" --http-method GET --attempt-deadline 60s \
    --description 'Keep the Cloud Run API warm'
fi

cat <<EOF

Done. Add these GitHub repository variables (not secrets; none of them is sensitive):
  GCP_PROJECT_ID      = $PROJECT_ID
  GCP_REGION          = $REGION
  GCP_WIF_PROVIDER    = projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/providers/$PROVIDER
  GCP_DEPLOYER_SA     = $DEPLOYER_EMAIL
  GCP_RUNTIME_SA      = $RUNTIME_EMAIL
  CLOUD_RUN_CORS_ORIGINS = https://bookingbot-mvp.vercel.app
Then run the "Deploy to Cloud Run" workflow from the Actions tab.
EOF
