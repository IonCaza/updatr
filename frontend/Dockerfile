FROM node:20-slim

ARG APP_PORT=3000
ARG NODE_ENV=development
ARG NEXT_PUBLIC_API_URL

ENV PORT=${APP_PORT}
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

WORKDIR /app

COPY package.json package-lock.json ./
RUN NODE_ENV=development npm ci

COPY . .

RUN if [ "$NODE_ENV" = "production" ]; then npm run build; fi

ENV NODE_ENV=${NODE_ENV}

EXPOSE ${APP_PORT}

CMD if [ "$NODE_ENV" = "production" ]; then npm run start; else npm run dev; fi
