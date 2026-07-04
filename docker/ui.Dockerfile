# ============================================================================
# Structured Data Extraction — UI image
#
# Multi-stage build: stage 1 (node) runs the Vite production build, stage 2
# (nginx) serves the resulting static bundle and proxies /api to the api
# container. Nothing from node_modules survives into the runtime image.
# ============================================================================

# ---------- Stage 1: build the Vite bundle -----------------------------------
FROM node:20-alpine AS builder

WORKDIR /ui

# Copy package manifests first — this lets Docker cache the npm install
# layer across code-only changes.
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copy the rest of the ui source and build.
COPY ui/ ./
RUN npm run build

# ---------- Stage 2: serve with nginx ----------------------------------------
FROM nginx:1.27-alpine AS runtime

# Custom nginx config — proxies /api to the api container.
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
# Remove the stock nginx config that listens on :80 — we listen on :5173 only.
RUN rm -f /etc/nginx/conf.d/default.conf.bak && \
    sed -i '/listen       80;/d' /etc/nginx/nginx.conf 2>/dev/null || true

# Copy the built bundle.
COPY --from=builder /ui/dist /usr/share/nginx/html

EXPOSE 5173

# nginx:alpine runs as root by default — nginx workers drop to `nginx` user
# themselves once bound to the port, so we leave the entrypoint alone.
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:5173/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
