# Deploying AI CarryON to Firebase / Cloud Run

Run all of this **on your MacBook**, inside this folder, logged into the
Google account that owns your Firebase (Blaze) project. Replace
`YOUR_PROJECT_ID` everywhere with your actual Firebase project ID.

## 0. One-time setup

```bash
# Install/update the gcloud CLI if you don't have it:
#   https://cloud.google.com/sdk/docs/install
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable the APIs this needs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com

# If Firestore isn't already provisioned for this project (native mode):
gcloud firestore databases create --location=us-central1

# Deploy the composite indexes Firestore needs (do this before first run)
firebase deploy --only firestore:indexes --project YOUR_PROJECT_ID
```

## 1. Move your secrets into Secret Manager

For every env var currently set on Railway (see README's Environment
Variables table — `GROQ_API_KEY`, `GEMINI_API_KEY`, `PEXELS_API_KEY`,
`YOUTUBE_API_KEY`, `YOUTUBE_TOKEN_B64`, `YOUTUBE_CLIENT_SECRETS_B64`,
`YOUTUBE_ANALYTICS_TOKEN_B64`, `YOUTUBE_TOKEN_JSON`/`HINDI_TOKEN_JSON`,
`SARVAM_API_KEY`, `APP_PASSWORD`, `INSTAGRAM_USERNAME`,
`INSTAGRAM_PASSWORD` — you can drop `GITHUB_TOKEN`/`GITHUB_REPO`, they
were only for the now-retired GitHub data-backup):

```bash
echo -n "your-actual-value" | gcloud secrets create GROQ_API_KEY --data-file=-
echo -n "your-actual-value" | gcloud secrets create GEMINI_API_KEY --data-file=-
# ...repeat for each one
```

## 2. Backfill your existing SQLite data into Firestore (run once, locally)

```bash
# Point at your real aicarryon.db (pull it off Railway first if needed —
# e.g. via `railway run cat output/aicarryon.db > aicarryon.db` or similar)
gcloud auth application-default login   # lets the script write to Firestore
python3 -c "
from agents.database import db
db.migrate_from_sqlite('path/to/your/aicarryon.db')
"
```

## 2b. Backfill Cricket's existing Supabase data into Firestore (run once, locally)

```bash
# Requires psycopg2-binary locally for this one call only:
pip install psycopg2-binary

gcloud auth application-default login   # if you haven't already from step 2
python3 -c "
from agents_cricket.database import db
db.migrate_from_supabase('postgresql://your-current-supabase-connection-string')
"
```

Do this **before** pointing `scheduler_cricket.py` at Cloud Run — otherwise
`get_all_posted_match_ids()` comes back empty and matches you've already
covered can get reposted.

## 3. Build and deploy the dashboard (Cloud Run service)

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ai-carryon

gcloud run deploy ai-carryon-dashboard \
  --image gcr.io/YOUR_PROJECT_ID/ai-carryon \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 1 \
  --memory 1Gi \
  --set-secrets "GROQ_API_KEY=GROQ_API_KEY:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,APP_PASSWORD=APP_PASSWORD:latest"
  # add the rest of your secrets the same way, comma-separated
```

This gives you a public URL immediately — visit it to confirm the
dashboard loads and `db.get_public_stats()` reads from Firestore.

## 4. Deploy the English + Hindi workers as Cloud Run Jobs

```bash
# English
gcloud run jobs create ai-carryon-worker-english \
  --image gcr.io/YOUR_PROJECT_ID/ai-carryon \
  --region us-central1 \
  --command python \
  --args scheduler.py \
  --memory 2Gi \
  --task-timeout 3600 \
  --max-retries 0 \
  --set-secrets "GROQ_API_KEY=GROQ_API_KEY:latest,YOUTUBE_TOKEN_B64=YOUTUBE_TOKEN_B64:latest"
  # ...plus every other secret this channel needs

# Hindi
gcloud run jobs create ai-carryon-worker-hindi \
  --image gcr.io/YOUR_PROJECT_ID/ai-carryon \
  --region us-central1 \
  --command python \
  --args scheduler_hindi.py \
  --memory 2Gi \
  --task-timeout 3600 \
  --max-retries 0 \
  --set-secrets "GROQ_API_KEY=GROQ_API_KEY:latest,SARVAM_API_KEY=SARVAM_API_KEY:latest,HINDI_TOKEN_JSON=HINDI_TOKEN_JSON:latest"
  # ...plus every other secret this channel needs

# Cricket — build with requirements_cricket.txt instead of requirements.txt,
# so make sure your Cloud Build step (or a separate Dockerfile) installs
# google-cloud-firestore instead of the old psycopg2-binary. DATABASE_URL
# is no longer needed — cricket now authenticates to Firestore the same
# way English/Hindi do (the Job's service account, via ADC).
gcloud run jobs create ai-carryon-worker-cricket \
  --image gcr.io/YOUR_PROJECT_ID/ai-carryon \
  --region us-central1 \
  --command python \
  --args scheduler_cricket.py \
  --memory 2Gi \
  --task-timeout 3600 \
  --max-retries 0 \
  --set-secrets "GROQ_API_KEY=GROQ_API_KEY:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest"
  # ...plus every other secret this channel needs (CRICAPI key, cricket YouTube tokens, etc.)
```

`--task-timeout 3600` gives each run up to an hour — raise it if a full
video-render pipeline sometimes takes longer.

## 5. Wire up Cloud Scheduler (replaces the old always-on polling loop)

```bash
# English — every hour, on the hour
gcloud scheduler jobs create http ai-carryon-english-hourly \
  --schedule "0 * * * *" \
  --uri "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT_ID/jobs/ai-carryon-worker-english:run" \
  --http-method POST \
  --oauth-service-account-email YOUR_PROJECT_ID@appspot.gserviceaccount.com

# Hindi — every hour, on the hour
gcloud scheduler jobs create http ai-carryon-hindi-hourly \
  --schedule "0 * * * *" \
  --uri "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT_ID/jobs/ai-carryon-worker-hindi:run" \
  --http-method POST \
  --oauth-service-account-email YOUR_PROJECT_ID@appspot.gserviceaccount.com

# Cricket — every hour, on the hour (scheduler_cricket.py's own throttling
# logic, via cricket_db.get_meta, decides whether that hour actually does
# anything — same pattern as before, just reading from Firestore now)
gcloud scheduler jobs create http ai-carryon-cricket-hourly \
  --schedule "0 * * * *" \
  --uri "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT_ID/jobs/ai-carryon-worker-cricket:run" \
  --http-method POST \
  --oauth-service-account-email YOUR_PROJECT_ID@appspot.gserviceaccount.com
```

The invoking service account needs the **Cloud Run Invoker** role on
each job:

```bash
gcloud run jobs add-iam-policy-binding ai-carryon-worker-english \
  --region us-central1 \
  --member "serviceAccount:YOUR_PROJECT_ID@appspot.gserviceaccount.com" \
  --role "roles/run.invoker"
# repeat for ai-carryon-worker-hindi and ai-carryon-worker-cricket
```

## 6. One manual test run before trusting the schedule

```bash
gcloud run jobs execute ai-carryon-worker-english --region us-central1 --update-env-vars FORCE_GENERATE=true
```

Watch it in the Cloud Run console (Jobs → ai-carryon-worker-english →
Logs) — this bypasses the top-hour gate and daily cap so you get an
immediate end-to-end run: research → script → SEO → thumbnail → images
→ voice → captions → video → YouTube upload.

## 7. Once you've confirmed a few successful automated runs

- Point your domain / share the new Cloud Run dashboard URL instead of
  the Railway one (`ai-carryon-production.up.railway.app`)
- Delete the two Railway projects (`strong-simplicity`, `giving-beauty`)
- `agents_cricket/` is now on Firestore too (its own `cricket_`-prefixed
  collections in the same project) — once you've confirmed cricket runs
  cleanly against Firestore, decommission its old Supabase project and
  drop `DATABASE_URL` from wherever it was hosted (it's no longer read
  anywhere in the codebase)

## Troubleshooting

- **Firestore "failed precondition: index required" error** — the error
  message includes a direct link to create the missing index; click it,
  or make sure step 0's `firebase deploy --only firestore:indexes` ran
  successfully first.
- **Cloud Run Job says "permission denied" calling Firestore** — the Job's
  service account needs the `roles/datastore.user` role:
  `gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member serviceAccount:YOUR_PROJECT_ID@appspot.gserviceaccount.com --role roles/datastore.user`
