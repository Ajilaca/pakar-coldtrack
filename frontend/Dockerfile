FROM node:20-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED 1

# PENTING — variabel NEXT_PUBLIC_* HARUS tersedia saat `npm run build`.
#
# Next.js menanam nilainya langsung ke dalam bundel JavaScript pada saat
# build, bukan membacanya saat kontainer berjalan. Menaruhnya di blok
# `environment:` docker-compose tidak berpengaruh sama sekali: bundelnya
# sudah terlanjur dicetak dengan nilai bawaan.
#
# Gejalanya halus dan berbahaya — frontend tetap hidup, tapi diam-diam
# kembali ke data tiruan dan tidak pernah memanggil backend. Di mesin
# pengembang tidak ketahuan karena ada .env.local, sementara berkas itu
# masuk .gitignore DAN .dockerignore, jadi hanya muncul pada klon segar.
#
# Nilainya di-set lewat `build.args` di docker-compose.yml.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_USE_MOCK=false
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_USE_MOCK=$NEXT_PUBLIC_USE_MOCK

RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]
