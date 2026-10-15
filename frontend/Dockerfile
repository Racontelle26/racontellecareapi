# Version web de Racontelle Care (service Railway distinct de l'API).
# Étape 1 : export statique Expo. Étape 2 : Caddy sert les fichiers.

FROM node:22-slim AS build

WORKDIR /app

# Adresse de l'API intégrée au bundle au moment de la compilation.
ARG EXPO_PUBLIC_BACKEND_URL=https://racontellecareapi-production.up.railway.app
ENV EXPO_PUBLIC_BACKEND_URL=$EXPO_PUBLIC_BACKEND_URL \
    CI=1

COPY package.json yarn.lock ./
COPY scripts ./scripts
RUN yarn install --frozen-lockfile --network-timeout 600000

COPY . .
RUN npx expo export --platform web --output-dir dist

FROM caddy:2.10-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv

# Railway injecte PORT à l'exécution ; Caddy l'écoute via {$PORT}.
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
