#!/bin/bash
set -e
while IFS='=' read -r key val; do
  [[ -z "$key" || "$key" == \#* ]] && continue
  case "$key" in
    GROQ_API_KEY|GEMINI_API_KEY|PEXELS_API_KEY|YOUTUBE_API_KEY|YOUTUBE_TOKEN_B64|YOUTUBE_CLIENT_SECRETS_B64|SARVAM_API_KEY|APP_PASSWORD)
      echo -n "$val" | gcloud secrets versions add "$key" --data-file=-
      echo "Updated $key"
      ;;
  esac
done < .env
