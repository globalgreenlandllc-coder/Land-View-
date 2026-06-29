# ---- build the React/Vite SPA ----
FROM node:20-alpine AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- python runtime serving API + built SPA via gunicorn ----
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=web /web/dist ./web/dist
ENV PORT=8000 HOST=0.0.0.0
EXPOSE 8000
# 2 workers; long timeout because a live image render can take 30-60s.
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} -w 2 -t 180 server:app"]
