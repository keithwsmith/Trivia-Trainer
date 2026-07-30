FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite file lives here by default (see .env.example); mount a volume at
# /app/data in production so it survives container restarts/upgrades.
ENV SQLITE_DB_PATH=/app/data/jeopardy.db
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
