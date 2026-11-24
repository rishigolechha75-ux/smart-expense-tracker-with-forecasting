# Single image for the hosted demo: builds the React app, then serves it with the API.
# (backend/Dockerfile + docker-compose.yml is the API-only setup with PostgreSQL.)

FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY --from=web /web/dist frontend/dist

WORKDIR /app/backend
# train the forecasting model at build time so the container starts quickly
RUN python -c "from app.forecasting import load_or_train; load_or_train()"

ENV PORT=8000
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
