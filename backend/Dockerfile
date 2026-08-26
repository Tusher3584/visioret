# CPU-only by design -- portable to any machine, including one with no GPU.
# model/ is mounted as a volume at runtime (see docker-compose.yml), not
# copied in here, so retraining the checkpoint never requires an image
# rebuild.

FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install torch/torchvision from PyTorch's CPU index FIRST, then everything
# else from PyPI.
#
# This is not an optimization, it is a correctness fix. On Linux x86-64,
# `pip install torch` from PyPI resolves to the CUDA-enabled wheel and drags
# in ~2.5 GB of nvidia-cu12-* libraries -- inside a container that has no GPU
# access and never will. It made this image 10.7 GB. The versions here must
# stay identical to the pins in requirements.txt; because they are already
# satisfied, the second pip run leaves them alone instead of pulling the
# CUDA build back in.
RUN pip install --no-cache-dir \
        torch==2.6.0 torchvision==0.21.0 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

EXPOSE 8000

CMD ["sh", "-c", "cd backend && alembic upgrade head && cd .. && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
