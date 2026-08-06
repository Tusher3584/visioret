# CPU-only by default (matches requirements.txt's plain torch install) --
# portable to any machine, including one with no GPU. model/ is mounted as a
# volume at runtime (see docker-compose.yml), not copied in here, so
# retraining the checkpoint never requires an image rebuild.

FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

EXPOSE 8000

CMD ["sh", "-c", "cd backend && alembic upgrade head && cd .. && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
