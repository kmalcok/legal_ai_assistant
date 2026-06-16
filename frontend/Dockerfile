### Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Install deps first (better layer caching)
COPY package.json package-lock.json ./
# Ensure devDependencies are installed in the build stage (vite is a devDependency).
# Some CI/build environments set NODE_ENV=production or npm config that omits dev deps,
# which would make `npm run build` fail with "vite: not found".
ENV NODE_ENV=development
RUN npm ci --include=dev

# Build-time API base URL (Vite env vars are baked into the bundle)
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Build
COPY . .
RUN npm run build


### Runtime stage (static hosting)
FROM nginx:1.27-alpine

# Nginx will envsubst templates in /etc/nginx/templates into /etc/nginx/conf.d at startup.
# API_UPSTREAM is used to proxy /v1/* to your backend (same-origin, no CORS).
ENV API_UPSTREAM=http://backend:8000

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/99-runtime-config.sh /docker-entrypoint.d/99-runtime-config.sh
RUN chmod +x /docker-entrypoint.d/99-runtime-config.sh

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]


