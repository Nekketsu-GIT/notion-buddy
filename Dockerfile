FROM python:3.11-slim

WORKDIR /app

# System deps for sentence-transformers / onnxruntime
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model so cold starts need no network access
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY notion_agent/ ./notion_agent/

# Persist dirs — mount volumes to keep data across runs
ENV CHROMA_PERSIST_DIR=/data/chroma
ENV AGENT_LOG_DIR=/data/agent_log
ENV HF_HUB_OFFLINE=1
VOLUME ["/data/chroma", "/data/agent_log"]

ENTRYPOINT ["python", "-m", "notion_agent"]
CMD ["--help"]
