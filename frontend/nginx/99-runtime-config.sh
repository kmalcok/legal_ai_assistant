#!/usr/bin/env sh
set -eu

# Generate a runtime config file consumed by the SPA.
# This allows changing backend URL via docker-compose environment without rebuilding the image.

TARGET="/usr/share/nginx/html/runtime-config.js"

API_BASE_URL="${API_BASE_URL:-}"
DEMO_VIDEO_URL="${DEMO_VIDEO_URL:-}"

cat > "$TARGET" <<EOF
// generated at container start
window.__APP_CONFIG__ = window.__APP_CONFIG__ || {};
window.__APP_CONFIG__.API_BASE_URL = "${API_BASE_URL}";
window.__APP_CONFIG__.DEMO_VIDEO_URL = "${DEMO_VIDEO_URL}";
EOF

