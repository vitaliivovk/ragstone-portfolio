import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import tiktoken

from corpus_metadata import derive_corpus_metadata
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI


MODEL_NAME = "text-embedding-3-small"
EMBED_DIM = 1536
# OpenAI embedding endpoints reject inputs over 8192 tokens (cl100k-compatible counting).
OPENAI_EMBEDDING_MAX_INPUT_TOKENS = 8192
EMBED_INPUT_TRUNCATE_TOKENS = OPENAI_EMBEDDING_MAX_INPUT_TOKENS - 1

_embed_tokenizer = None


def _embedding_tokenizer():
    global _embed_tokenizer
    if _embed_tokenizer is None:
        _embed_tokenizer = tiktoken.get_encoding("cl100k_base")
    return _embed_tokenizer


def count_embedding_tokens(text: str) -> int:
    return len(_embedding_tokenizer().encode(text))


def truncate_text_for_embedding(text: str, max_tokens: int = EMBED_INPUT_TRUNCATE_TOKENS) -> str:
    enc = _embedding_tokenizer()
    token_ids = enc.encode(text)
    if len(token_ids) <= max_tokens:
        return text
    return enc.decode(token_ids[:max_tokens])


def embedding_sidecar_path(chunk_jsonl_path: str) -> str:
    """Local cache of vectors next to chunk JSONL: ``foo.docid.jsonl`` → ``foo.docid.embeddings.jsonl``."""
    root, _ext = os.path.splitext(chunk_jsonl_path)
    return f"{root}.embeddings.jsonl"


def _stable_vector_id(obj: Dict[str, Any]) -> str:
    return obj.get("stableId") or f"{obj.get('docId')}:{obj.get('chunkIndex')}"


def _embedding_input_for_object(obj: Dict[str, Any]) -> Tuple[str, str]:
    """Exact string sent to OpenAI embeddings and a SHA-256 digest for cache lookup."""
    raw = obj.get("content", "") or ""
    if count_embedding_tokens(raw) > EMBED_INPUT_TRUNCATE_TOKENS:
        text = truncate_text_for_embedding(raw)
    else:
        text = raw
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, digest


def load_embedding_sidecar(path: str) -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(path):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            sid = rec["stableId"]
            out[sid] = rec
    return out


def save_embedding_sidecar(path: str, objects: Sequence[Dict[str, Any]], cache: Dict[str, Dict[str, Any]]) -> None:
    allowed = {_stable_vector_id(obj) for obj in objects}
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        for sid in sorted(allowed):
            rec = cache.get(sid)
            if not rec:
                continue
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp_path, path)


def embed_objects_with_cache(
    objs: Sequence[Dict[str, Any]],
    cache: Dict[str, Dict[str, Any]],
) -> Tuple[List[List[float]], int, int]:
    """Return (embeddings in object order, api_call_count, cache_hit_count). Updates *cache* in place."""
    n = len(objs)
    results: List[Optional[List[float]]] = [None] * n
    miss_indices: List[int] = []
    miss_texts: List[str] = []
    hits = 0

    texts_and_digests: List[Tuple[str, str]] = [_embedding_input_for_object(obj) for obj in objs]

    for i, obj in enumerate(objs):
        text, digest = texts_and_digests[i]
        sid = _stable_vector_id(obj)
        hit = cache.get(sid)
        if (
            hit
            and hit.get("model") == MODEL_NAME
            and hit.get("digest") == digest
            and isinstance(hit.get("embedding"), list)
            and len(hit["embedding"]) == EMBED_DIM
        ):
            results[i] = hit["embedding"]
            hits += 1
        else:
            miss_indices.append(i)
            miss_texts.append(text)

    if miss_texts:
        fresh = embed_texts(miss_texts)
        for batch_idx, emb in enumerate(fresh):
            obj_idx = miss_indices[batch_idx]
            obj = objs[obj_idx]
            _text, digest = texts_and_digests[obj_idx]
            sid = _stable_vector_id(obj)
            cache[sid] = {
                "stableId": sid,
                "model": MODEL_NAME,
                "digest": digest,
                "embedding": emb,
            }
            results[obj_idx] = emb

    ordered: List[List[float]] = []
    for r in results:
        if r is None:
            raise RuntimeError("embed_objects_with_cache: missing embeddings for some objects")
        ordered.append(r)
    return ordered, len(miss_texts), hits


@dataclass(frozen=True)
class UpsertStats:
    pinecone_upsert_rows: int
    openai_embedding_api_calls: int
    embedding_cache_hits: int


def get_pinecone() -> Pinecone:
    api_key = os.environ.get("PINECONE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY must be set in the environment")
    return Pinecone(api_key=api_key)


def ensure_index(pc: Pinecone, index_name: str, metric: str = "cosine", cloud: str = "aws", region: str = "us-east-1") -> None:
    cloud_resolved = os.environ.get("PINECONE_CLOUD", cloud).strip() or cloud
    region_resolved = os.environ.get("PINECONE_REGION", region).strip() or region
    if not pc.has_index(index_name):
        pc.create_index(
            name=index_name,
            dimension=EMBED_DIM,
            metric=metric,
            spec=ServerlessSpec(cloud=cloud_resolved, region=region_resolved),
        )


def get_index(pc: Pinecone, index_name: str):
    return pc.Index(index_name)


def get_openai() -> OpenAI:
    api_key = (os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_APIKEY", "")).strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set for embeddings")
    return OpenAI(api_key=api_key)


def estimate_tokens(text: str) -> int:
    """Token count for batch sizing (same as chunking: cl100k)."""
    return count_embedding_tokens(text)


def embed_texts(
    texts: Sequence[str],
    max_tokens_per_batch: int = 200000,
    max_tokens_per_text: int = EMBED_INPUT_TRUNCATE_TOKENS,
) -> List[List[float]]:
    """
    Embed texts in batches to avoid OpenAI token limits.

    Each string is truncated with tiktoken to at most ``max_tokens_per_text`` (default
    under the API hard cap of 8192 tokens per input).
    """
    client = get_openai()
    all_embeddings = []
    
    if not texts:
        return all_embeddings
    
    # Convert to list for indexing
    text_list = list(texts)
    current_batch = []
    current_tokens = 0
    
    for idx, text in enumerate(text_list):
        text_tokens = count_embedding_tokens(text)

        if text_tokens > max_tokens_per_text:
            print(
                f"Warning: Text {idx} has {text_tokens} tokens, truncating to "
                f"{max_tokens_per_text} for embedding API limit ({OPENAI_EMBEDDING_MAX_INPUT_TOKENS})."
            )
            text = truncate_text_for_embedding(text, max_tokens_per_text)
            text_tokens = count_embedding_tokens(text)

        # If adding this text would exceed the batch limit, process current batch first
        if current_batch and (current_tokens + text_tokens > max_tokens_per_batch):
            # Process current batch
            print(f"Processing batch of {len(current_batch)} texts with ~{current_tokens} tokens")
            res = client.embeddings.create(input=current_batch, model=MODEL_NAME)
            all_embeddings.extend([item.embedding for item in res.data])
            
            # Start new batch
            current_batch = [text]
            current_tokens = text_tokens
        else:
            # Add to current batch
            current_batch.append(text)
            current_tokens += text_tokens
    
    # Process final batch if any texts remain
    if current_batch:
        print(f"Processing final batch of {len(current_batch)} texts with ~{current_tokens} tokens")
        res = client.embeddings.create(input=current_batch, model=MODEL_NAME)
        all_embeddings.extend([item.embedding for item in res.data])
    
    return all_embeddings


def estimate_metadata_size(metadata: Dict[str, Any]) -> int:
    """Estimate the byte size of metadata when serialized to JSON."""
    try:
        return len(json.dumps(metadata, ensure_ascii=False).encode('utf-8'))
    except Exception:
        # Fallback rough estimate
        total = 0
        for key, value in metadata.items():
            total += len(str(key)) + len(str(value)) + 10
        return total


def build_metadata_from_object(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pinecone metadata for a chunk or summary routing object (same rules as upsert): truncation for 40KB limit,
    corpusTopic / path fields from derive_corpus_metadata.

    Chunk rows set ``summaries=false``. Summary routing rows set ``summaries=true`` plus span bounds.
    """
    content = obj.get("content", "")
    is_summary = bool(obj.get("summaries"))

    rel_path = obj.get("sourceRelativePath")
    corpus_meta = derive_corpus_metadata(rel_path if rel_path is not None else "")

    base_metadata: Dict[str, Any] = {
        "docId": obj.get("docId"),
        "fileName": obj.get("fileName"),
        "sourceRelativePath": rel_path,
        "corpusTopic": corpus_meta.get("corpusTopic"),
        "corpusTopFolder": corpus_meta.get("corpusTopFolder"),
        "corpusPathPrefix": corpus_meta.get("corpusPathPrefix"),
        "pageNumber": obj.get("pageNumber"),
        "slideNumber": obj.get("slideNumber"),
        "sheetName": obj.get("sheetName"),
        "chunkIndex": obj.get("chunkIndex"),
        "blockStartIndex": obj.get("blockStartIndex"),
        "blockEndIndex": obj.get("blockEndIndex"),
        "sectionTitle": obj.get("sectionTitle"),
        "sectionPath": obj.get("sectionPath"),
        "language": obj.get("language"),
        "isTable": obj.get("isTable"),
        "elementType": obj.get("elementType"),
        "coordinates": obj.get("coordinates"),
        "lastModified": obj.get("lastModified"),
        "mimeType": obj.get("mimeType"),
        "fileExt": obj.get("fileExt"),
        "tokens": obj.get("tokens"),
        "sharepointUrl": obj.get("sharepointUrl"),
        "highlightPhrase": obj.get("highlightPhrase"),
        "summaries": is_summary,
    }
    if is_summary:
        base_metadata["spanId"] = obj.get("spanId")
        base_metadata["chunkIndexStart"] = obj.get("chunkIndexStart")
        base_metadata["chunkIndexEnd"] = obj.get("chunkIndexEnd")

    base_size = 0
    for key, value in base_metadata.items():
        if value is not None:
            base_size += len(str(key)) + len(str(value)) + 10

    max_text_bytes = 35 * 1024 - base_size

    if content and len(content.encode("utf-8")) <= max_text_bytes:
        text_to_store = content
        is_truncated = False
    elif content:
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > max_text_bytes:
            truncated_bytes = content_bytes[:max_text_bytes]
            try:
                text_to_store = truncated_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text_to_store = truncated_bytes[:-10].decode("utf-8", errors="ignore")
            is_truncated = True
        else:
            text_to_store = content
            is_truncated = False
    else:
        text_to_store = ""
        is_truncated = False

    metadata: Dict[str, Any] = {}
    for key, value in {
        **base_metadata,
        "text": text_to_store,
        "textTruncated": is_truncated,
        "originalTextLength": len(content) if content else 0,
    }.items():
        if value is not None:
            metadata[key] = value

    estimated_size = estimate_metadata_size(metadata)
    if estimated_size > 40 * 1024:
        print(f"Warning: Metadata still too large ({estimated_size} bytes), emergency truncation")
        available_for_text = 30 * 1024 - (estimated_size - len(text_to_store.encode("utf-8")))
        if available_for_text > 100:
            text_bytes = text_to_store.encode("utf-8")[:available_for_text]
            try:
                metadata["text"] = text_bytes.decode("utf-8")
            except UnicodeDecodeError:
                metadata["text"] = text_bytes[:-10].decode("utf-8", errors="ignore")
            metadata["textTruncated"] = True
        else:
            metadata["text"] = content[:200] if content else ""
            metadata["textTruncated"] = True

    return metadata


def build_vectors_from_objects(
    objs: Sequence[Dict[str, Any]],
    precomputed_embeddings: Optional[Sequence[Sequence[float]]] = None,
) -> List[Dict[str, Any]]:
    if precomputed_embeddings is None:
        texts: List[str] = [obj.get("content", "") for obj in objs]
        embeddings: List[List[float]] = embed_texts(texts)
    else:
        embeddings = [list(row) for row in precomputed_embeddings]
        if len(embeddings) != len(objs):
            raise ValueError(
                f"precomputed_embeddings length {len(embeddings)} does not match objects {len(objs)}"
            )
    vectors: List[Dict[str, Any]] = []
    for obj, emb in zip(objs, embeddings):
        vid = _stable_vector_id(obj)
        metadata = build_metadata_from_object(obj)
        vectors.append(
            {
                "id": vid,
                "values": emb,
                "metadata": metadata,
            }
        )
    return vectors


def upsert_vectors(
    index_name: str,
    vectors: Sequence[Dict[str, Any]],
    namespace: str,
    batch_size: int = 100,
) -> int:
    """Upsert pre-built vectors (single namespace)."""
    if not vectors:
        return 0
    pc = get_pinecone()
    ensure_index(pc, index_name)
    index = get_index(pc, index_name)
    total = 0
    for idx in range(0, len(vectors), batch_size):
        batch = list(vectors[idx : idx + batch_size])
        index.upsert(vectors=batch, namespace=namespace)
        total += len(batch)
    return total


def upsert_objects_to_namespaces(
    index_name: str,
    objects: Sequence[Dict[str, Any]],
    namespaces: Sequence[str],
    batch_size: int = 100,
    embedding_cache_path: Optional[str] = None,
) -> UpsertStats:
    """Embed each batch once (with optional disk cache), upsert the same vectors to every namespace."""
    if not objects:
        return UpsertStats(0, 0, 0)
    ns_list = [ns.strip() for ns in namespaces if ns and ns.strip()]
    if not ns_list:
        raise ValueError("At least one non-empty namespace is required")
    pc = get_pinecone()
    ensure_index(pc, index_name)
    index = get_index(pc, index_name)
    total_rows = 0
    api_calls = 0
    cache_hits = 0

    cache: Dict[str, Dict[str, Any]] = {}
    if embedding_cache_path:
        cache = load_embedding_sidecar(embedding_cache_path)

    object_list = list(objects)
    for batch_start in range(0, len(object_list), batch_size):
        batch_objs = object_list[batch_start : batch_start + batch_size]
        embeddings, miss_n, hit_n = embed_objects_with_cache(batch_objs, cache)
        api_calls += miss_n
        cache_hits += hit_n
        vectors = build_vectors_from_objects(batch_objs, precomputed_embeddings=embeddings)
        for namespace in ns_list:
            index.upsert(vectors=vectors, namespace=namespace)
            total_rows += len(vectors)

    if embedding_cache_path:
        save_embedding_sidecar(embedding_cache_path, object_list, cache)

    return UpsertStats(
        pinecone_upsert_rows=total_rows,
        openai_embedding_api_calls=api_calls,
        embedding_cache_hits=cache_hits,
    )


def upsert_objects(
    index_name: str,
    objects: Sequence[Dict[str, Any]],
    namespace: Optional[str] = None,
    batch_size: int = 100,
    embedding_cache_path: Optional[str] = None,
) -> UpsertStats:
    if not objects:
        return UpsertStats(0, 0, 0)
    ns = namespace if namespace is not None and namespace.strip() else "v3"
    return upsert_objects_to_namespaces(
        index_name,
        objects,
        [ns],
        batch_size=batch_size,
        embedding_cache_path=embedding_cache_path,
    )
