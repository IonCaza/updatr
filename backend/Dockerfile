FROM python:3.12-slim

ARG APP_PORT=8000
ARG NODE_ENV=development
ENV APP_PORT=${APP_PORT}
ENV NODE_ENV=${NODE_ENV}

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    openssh-client \
    sshpass \
    nmap \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN ansible-galaxy collection install ansible.windows --force

RUN mkdir -p /tmp/updatr_keys && chmod 700 /tmp/updatr_keys

COPY . .

EXPOSE ${APP_PORT}

CMD if [ "$NODE_ENV" = "production" ]; then \
      uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT} --workers 2; \
    else \
      uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT} --reload; \
    fi
