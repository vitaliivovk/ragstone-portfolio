"""Stable Pinecone vector ids for chunk rows (matches pinecone-pipeline indexing)."""


def chunk_vector_id(doc_id: str, chunk_index: int) -> str:
    """Vector id format: ``{docId}:{chunkIndex:04d}`` (see document_parser/core.py)."""
    return f"{doc_id}:{int(chunk_index):04d}"
