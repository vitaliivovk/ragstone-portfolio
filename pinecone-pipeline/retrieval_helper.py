import json
import os
from typing import Dict, List, Optional, Any

from pinecone_io import get_pinecone, get_index

_pipeline_dir = os.path.dirname(os.path.abspath(__file__))
_default_chunk_output_dir = os.path.join(_pipeline_dir, "chunk_output")


def get_full_text_from_cache(doc_id: str, chunk_index: int, chunk_output_dir: str = None) -> Optional[str]:
    if chunk_output_dir is None:
        chunk_output_dir = _default_chunk_output_dir
    """
    Retrieve full text content from cached JSONL files using docId and chunkIndex.
    
    Args:
        doc_id: Document ID from Pinecone metadata
        chunk_index: Chunk index from Pinecone metadata  
        chunk_output_dir: Directory containing JSONL cache files
    
    Returns:
        Full text content if found, None otherwise
    """
    # Find the JSONL file that contains this docId
    if not os.path.exists(chunk_output_dir):
        return None
        
    for filename in os.listdir(chunk_output_dir):
        if not filename.endswith('.jsonl'):
            continue
            
        file_path = os.path.join(chunk_output_dir, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    
                    # Check if this is the chunk we're looking for
                    if (obj.get('docId') == doc_id and 
                        obj.get('chunkIndex') == chunk_index):
                        return obj.get('content', '')
        except Exception as exc:
            print(f"Error reading {file_path}: {exc}")
            continue
    
    return None


def search_and_get_full_chunks(query: str, index_name: str, namespace: str = "v3", 
                              top_k: int = 5, chunk_output_dir: str = None) -> List[Dict[str, Any]]:
    if chunk_output_dir is None:
        chunk_output_dir = _default_chunk_output_dir
    """
    Search Pinecone and retrieve full text content for each result.
    
    Args:
        query: Search query string
        index_name: Pinecone index name
        namespace: Pinecone namespace
        top_k: Number of results to return
        chunk_output_dir: Directory containing JSONL cache files
    
    Returns:
        List of dictionaries containing search results with full text content
    """
    from pinecone_io import embed_texts
    
    # Get embedding for query
    query_embedding = embed_texts([query])[0]
    
    # Search Pinecone
    pc = get_pinecone()
    index = get_index(pc, index_name)
    
    search_results = index.query(
        vector=query_embedding,
        top_k=top_k,
        namespace=namespace,
        include_metadata=True
    )
    
    # Enhance results with full text content
    enhanced_results = []
    for match in search_results.matches:
        result = {
            'id': match.id,
            'score': match.score,
            'metadata': match.metadata,
            'textSnippet': match.metadata.get('textSnippet', ''),
            'fullText': None
        }
        
        # Try to get full text from cache
        doc_id = match.metadata.get('docId')
        chunk_index = match.metadata.get('chunkIndex')
        
        if doc_id is not None and chunk_index is not None:
            full_text = get_full_text_from_cache(doc_id, chunk_index, chunk_output_dir)
            result['fullText'] = full_text
        
        enhanced_results.append(result)
    
    return enhanced_results


def get_chunk_by_stable_id(stable_id: str, chunk_output_dir: str = None) -> Optional[Dict[str, Any]]:
    if chunk_output_dir is None:
        chunk_output_dir = _default_chunk_output_dir
    """
    Retrieve a specific chunk by its stableId from cache.
    
    Args:
        stable_id: The stableId of the chunk (format: docId:chunkIndex)
        chunk_output_dir: Directory containing JSONL cache files
    
    Returns:
        Full chunk object if found, None otherwise
    """
    if ':' in stable_id:
        doc_id, chunk_str = stable_id.split(':', 1)
        try:
            chunk_index = int(chunk_str)
        except ValueError:
            return None
    else:
        return None
    
    # Find the JSONL file that contains this docId
    if not os.path.exists(chunk_output_dir):
        return None
        
    for filename in os.listdir(chunk_output_dir):
        if not filename.endswith('.jsonl'):
            continue
            
        file_path = os.path.join(chunk_output_dir, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    
                    # Check if this is the chunk we're looking for
                    if obj.get('stableId') == stable_id:
                        return obj
        except Exception as exc:
            print(f"Error reading {file_path}: {exc}")
            continue
    
    return None


# Example usage function
def search_with_full_context(query: str, index_name: str = "text-embedding-3-small", 
                           namespace: str = "default", top_k: int = 3) -> None:
    """
    Example function showing how to search and get full text results.
    """
    print(f"Searching for: {query}")
    print("-" * 50)
    
    results = search_and_get_full_chunks(query, index_name, namespace, top_k)
    
    for idx, result in enumerate(results, 1):
        print(f"\n{idx}. Score: {result['score']:.4f}")
        print(f"   File: {result['metadata'].get('fileName', 'Unknown')}")
        print(f"   Section: {result['metadata'].get('sectionTitle', 'N/A')}")
        print(f"   Snippet: {result['textSnippet'][:100]}...")
        
        if result['fullText']:
            print(f"   Full text ({len(result['fullText'])} chars): {result['fullText'][:200]}...")
        else:
            print("   Full text: Not found in cache")
        print("-" * 30)


if __name__ == "__main__":
    # Example usage
    search_with_full_context("najem mieszkania procedura", top_k=3)
