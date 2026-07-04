#!/bin/sh
# ============================================================================
# HF Space entrypoint. Runs uvicorn in the background and nginx in the
# foreground so PID 1 is nginx (and stops cleanly on SIGTERM from HF's
# infrastructure).
# ============================================================================
set -eu

# Sanity check: HF's secret injection puts OPENAI_API_KEY on env.
# Log a friendly warning if it's missing — don't hard-fail so the UI still
# loads and can show the /schemas endpoint.
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "[hf-entrypoint] WARN: OPENAI_API_KEY is not set. /extract will 500."
    echo "[hf-entrypoint] Add it under Space Settings → Repository secrets."
fi

# --- background: uvicorn -----------------------------------------------------
# Bind to localhost only — nginx is the only thing that talks to it.
# 1 worker keeps the DocumentExtractor singleton coherent (matches api.Dockerfile).
uvicorn src.api.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 1 \
    --log-level info &
UVICORN_PID=$!
echo "[hf-entrypoint] uvicorn started (pid $UVICORN_PID)"

# Trap so a SIGTERM to nginx also stops uvicorn.
term() {
    echo "[hf-entrypoint] shutting down"
    kill -TERM "$UVICORN_PID" 2>/dev/null || true
    wait "$UVICORN_PID" 2>/dev/null || true
    exit 0
}
trap term TERM INT

# --- wait until uvicorn is ready before starting nginx ----------------------
# HF's infra checks the app port; we don't want nginx serving 502s while
# uvicorn is still importing pdfplumber/pymupdf (which is slow).
for i in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "[hf-entrypoint] api healthy after ${i}s"
        break
    fi
    sleep 1
done

# --- foreground: nginx -------------------------------------------------------
echo "[hf-entrypoint] starting nginx on :7860"
exec nginx -g 'daemon off;'
