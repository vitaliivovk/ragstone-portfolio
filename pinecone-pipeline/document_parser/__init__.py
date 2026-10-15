"""Document parsing and chunking for the Pinecone indexing pipeline."""

from document_parser.core import (
    CHUNK_OUTPUT_DIR,
    DOCS_DIR,
    build_objects_for_file,
    build_output_path_for_objects,
    compute_doc_id,
    list_supported_files,
    normalize_source_relative_path,
    write_objects_to_jsonl,
)
from document_parser.chunking import (
    count_tokens,
    merge_units_into_chunks,
    normalize_elements_to_units,
)

__all__ = [
    "CHUNK_OUTPUT_DIR",
    "DOCS_DIR",
    "build_objects_for_file",
    "build_output_path_for_objects",
    "compute_doc_id",
    "list_supported_files",
    "normalize_source_relative_path",
    "write_objects_to_jsonl",
    "count_tokens",
    "merge_units_into_chunks",
    "normalize_elements_to_units",
]
