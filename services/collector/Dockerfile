# Collector image (AD-6): one-shot container, root context, runs as host user proxima-jobs (1010).
# Secrets never enter the image - they arrive as /run/secrets files via compose `secrets:`.

FROM node:22-bookworm-slim AS deps
WORKDIR /repo
COPY package.json package-lock.json ./
COPY services/collector/package.json services/collector/package.json
# Транзитивный puppeteer (mermaid-cli из корня) иначе тянет Chromium при npm ci.
ENV PUPPETEER_SKIP_DOWNLOAD=1
RUN npm ci --workspace @proxima/collector --include-workspace-root

FROM node:22-bookworm-slim AS builder
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY contracts contracts
COPY services/collector services/collector
WORKDIR /repo/services/collector
RUN npm run build

FROM node:22-bookworm-slim AS runner
ENV NODE_ENV=production
WORKDIR /app
RUN groupadd --system --gid 1010 proxima-jobs && useradd --system --uid 1010 --gid proxima-jobs --home-dir /nonexistent --shell /usr/sbin/nologin proxima-jobs \
    && mkdir -p /app && chown -R 1010:1010 /app
COPY --from=builder --chown=1010:1010 /repo/node_modules ./node_modules
COPY --from=builder --chown=1010:1010 /repo/services/collector ./services/collector
USER 1010
# AD-6 one-shot job container: the command arrives from
# `docker compose run collector npm run stockout-signal -- …`.
WORKDIR /app/services/collector
