# Сборка webapp (PA-49). Standalone-выход Next.js кладём в минимальный рантайм.
# Секреты и домен приходят окружением на VPS - в образ их не печём.

FROM node:22-bookworm-slim AS deps
WORKDIR /repo
COPY package.json package-lock.json ./
COPY services/collector/package.json services/collector/
COPY services/webapp/package.json services/webapp/
RUN npm ci --workspace @proxima/webapp --include-workspace-root

FROM node:22-bookworm-slim AS builder
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/services/webapp/node_modules ./services/webapp/node_modules
COPY package.json package-lock.json ./
COPY services/webapp ./services/webapp
WORKDIR /repo/services/webapp
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
RUN groupadd --system --gid 1001 webapp && useradd --system --uid 1001 --gid webapp webapp
COPY --from=builder --chown=webapp:webapp /repo/services/webapp/.next/standalone ./
COPY --from=builder --chown=webapp:webapp /repo/services/webapp/.next/static ./services/webapp/.next/static
COPY --from=builder --chown=webapp:webapp /repo/services/webapp/public ./services/webapp/public
USER webapp
EXPOSE 3000
CMD ["node", "services/webapp/server.js"]
