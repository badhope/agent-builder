# Multi-stage build for the React + Vite frontend.

FROM node:20-alpine AS build
WORKDIR /app

RUN npm install -g pnpm

COPY package.json pnpm-lock.yaml .npmrc* ./
RUN pnpm install --frozen-lockfile

COPY tsconfig.json vite.config.ts tailwind.config.ts postcss.config.cjs \
     index.html .eslintrc.cjs .prettierrc.json ./
COPY src ./src
COPY public ./public

ENV NODE_ENV=production
RUN pnpm build

# ---- runtime ----
FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s \
  CMD wget -q -O- http://127.0.0.1/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
