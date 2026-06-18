FROM node:20-alpine AS base
RUN npm install -g pnpm

FROM base AS deps
WORKDIR /app
# Copy monorepo root files
COPY pnpm-workspace.yaml ./
COPY package.json ./
COPY pnpm-lock.yaml ./
COPY tsconfig.base.json ./
# Copy all app packages
COPY apps ./apps
COPY packages ./packages
# Install dependencies
RUN pnpm install --frozen-lockfile

FROM base AS builder
WORKDIR /app
COPY --from=deps /app ./
RUN pnpm --filter admin-app build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3001
COPY --from=builder /app/apps/admin-app/.next/standalone ./apps/admin-app
COPY --from=builder /app/apps/admin-app/.next/static ./apps/admin-app/.next/static
EXPOSE 3001
CMD ["node", "apps/admin-app/server.js"]
