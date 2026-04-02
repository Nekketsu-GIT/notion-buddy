FROM python:3.11-slim

WORKDIR /app

# System deps for sentence-transformers / onnxruntime
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY notion_agent/ ./notion_agent/

# ChromaDB persist dir inside container — mount a volume to keep it across runs
ENV CHROMA_PERSIST_DIR=/data/chroma
VOLUME ["/data/chroma"]

ENTRYPOINT ["python", "-m", "notion_agent"]
CMD ["--help"]
