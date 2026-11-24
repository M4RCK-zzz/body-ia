# Frontend BODYVISION AI: build con Vite y servido por Nginx (Fase 9).
#
# Un solo lockfile: `package-lock.json` (npm). El `pnpm-lock.yaml` se eliminó en
# la Fase 9 (decisión D12) para que el build sea reproducible.
FROM node:22-alpine AS build

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# La URL de la API es relativa en producción (mismo origen, ver D9).
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# --- servidor ---------------------------------------------------------------
FROM nginx:1.27-alpine

RUN rm -rf /usr/share/nginx/html/*
COPY --from=build /app/dist /usr/share/nginx/html
# Plantillas: el entrypoint oficial de Nginx aplica `envsubst` sobre
# /etc/nginx/templates/*.template y escribe el resultado en conf.d/.
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf
COPY docker/nginx/templates/ /etc/nginx/templates/
COPY docker/nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY docker/nginx/proxy-headers.conf /etc/nginx/snippets/proxy-headers.conf
COPY docker/nginx/docker-entrypoint.d/ /docker-entrypoint.d/

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
