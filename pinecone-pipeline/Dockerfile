# Pinecone indexing pipeline: parse, chunk, embed (OpenAI), upsert.
# CPU image; GPU/local embeddings are a separate future track (see infrastructure/docs/GDPR-MIGRATION-PLAN.md).
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-pol \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Layer 1: dependency lock only — cache hits unless pyproject.toml / uv.lock change.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Layer 2: install local package (fast; invalidates on pipeline Python changes, not scripts).
COPY cli.py pinecone_io.py retrieval_helper.py summary_spans.py corpus_metadata.py ./
COPY document_parser ./document_parser
RUN uv sync --frozen --no-dev

# Layer 3: operational scripts (not part of the wheel); changes here do not re-download deps.
COPY scripts ./scripts

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["uv", "run", "ragstone-index"]
