# Build the SPA, then serve the static output from nginx.
#
# Two stages so the shipped image contains no node_modules and no build
# toolchain — a few MB of static files instead of several hundred.

FROM node:22-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
# Vite inlines env vars at build time, so the API URL has to be known here
# rather than at container start.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
