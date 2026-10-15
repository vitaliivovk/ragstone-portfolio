#!/usr/bin/env python3
"""
Pinecone Testing Script

This script tests Pinecone functionality including:
- Connection and index management
- Vector upserts with metadata
- Various search scenarios
- Metadata filtering
- Null value handling

Usage:
    python test_pinecone.py [--index-name INDEX_NAME] [--namespace NAMESPACE]
"""

import os
import json
import argparse
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.getcwd(), ".env.local"))
load_dotenv()

try:
    from pinecone_io import (
        get_pinecone, 
        ensure_index, 
        get_index, 
        embed_texts,
        build_vectors_from_objects,
        upsert_objects
    )
except ImportError as e:
    print(f"Error importing pinecone_io: {e}")
    print("Make sure pinecone_io.py is in the same directory")
    exit(1)


def create_test_documents() -> List[Dict[str, Any]]:
    """Create test documents with various metadata patterns for testing."""
    return [
        {
            "stableId": "test_doc_1:0001",
            "content": "This is a test document about artificial intelligence and machine learning.",
            "docId": "test_doc_1",
            "fileName": "ai_overview.pdf",
            "filePath": "/test/ai_overview.pdf",
            "sourceRelativePath": "folder/ai_overview.pdf",
            "pageNumber": 1,  # Non-null page number
            "slideNumber": None,  # Null slide number
            "sheetName": None,  # Null sheet name
            "chunkIndex": 1,
            "sectionTitle": "Introduction to AI",
            "sectionPath": "Chapter 1 > Introduction to AI",
            "language": "en",
            "isTable": False,
            "elementType": "Text",
            "lastModified": "2025-01-01T10:00:00",
            "mimeType": "application/pdf",
            "fileExt": "pdf"
        },
        {
            "stableId": "test_doc_2:0001",
            "content": "Machine learning algorithms include supervised and unsupervised learning methods.",
            "docId": "test_doc_2",
            "fileName": "ml_presentation.pptx",
            "filePath": "/test/ml_presentation.pptx",
            "sourceRelativePath": "ml_presentation.pptx",
            "pageNumber": None,  # Null page number
            "slideNumber": 5,  # Non-null slide number
            "sheetName": None,  # Null sheet name
            "chunkIndex": 1,
            "sectionTitle": "ML Algorithms",
            "sectionPath": "Part 2 > ML Algorithms",
            "language": "en",
            "isTable": False,
            "elementType": "Text",
            "lastModified": "2025-01-01T11:00:00",
            "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "fileExt": "pptx"
        },
        {
            "stableId": "test_doc_3:0001",
            "content": "Neural networks are composed of layers of interconnected nodes called neurons.",
            "docId": "test_doc_3",
            "fileName": "neural_networks.xlsx",
            "filePath": "/test/neural_networks.xlsx",
            "sourceRelativePath": "data/neural_networks.xlsx",
            "pageNumber": None,  # Null page number
            "slideNumber": None,  # Null slide number
            "sheetName": "Network Architecture",  # Non-null sheet name
            "chunkIndex": 1,
            "sectionTitle": None,  # Null section title
            "sectionPath": None,  # Null section path
            "language": "en",
            "isTable": True,  # This is table data
            "elementType": "Table",
            "lastModified": "2025-01-01T12:00:00",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "fileExt": "xlsx"
        },
        {
            "stableId": "test_doc_4:0001",
            "content": "Deep learning uses multiple layers to progressively extract higher-level features.",
            "docId": "test_doc_4",
            "fileName": "deep_learning.pdf",
            "filePath": "/test/deep_learning.pdf",
            "sourceRelativePath": "deep_learning.pdf",
            "pageNumber": 15,  # Non-null page number
            "slideNumber": None,  # Null slide number
            "sheetName": None,  # Null sheet name
            "chunkIndex": 1,
            "sectionTitle": "Deep Learning Fundamentals",
            "sectionPath": "Chapter 3 > Deep Learning Fundamentals",
            "language": "en",
            "isTable": False,
            "elementType": "Text",
            "lastModified": "2025-01-01T13:00:00",
            "mimeType": "application/pdf",
            "fileExt": "pdf"
        }
    ]


def test_connection(index_name: str) -> bool:
    """Test Pinecone connection and index setup."""
    print("🔗 Testing Pinecone Connection...")
    try:
        pc = get_pinecone()
        print(f"✅ Connected to Pinecone successfully")
        
        # List existing indexes
        indexes = pc.list_indexes()
        print(f"📋 Existing indexes: {[idx.name for idx in indexes]}")
        
        # Ensure test index exists
        ensure_index(pc, index_name)
        print(f"✅ Index '{index_name}' is ready")
        
        # Get index stats
        index = get_index(pc, index_name)
        stats = index.describe_index_stats()
        print(f"📊 Index stats: {stats}")
        
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def test_embedding_generation() -> bool:
    """Test embedding generation."""
    print("\n🧠 Testing Embedding Generation...")
    try:
        test_texts = [
            "This is a test sentence.",
            "Another test sentence about machine learning.",
            "Final test sentence."
        ]
        
        embeddings = embed_texts(test_texts)
        print(f"✅ Generated {len(embeddings)} embeddings")
        print(f"📐 Embedding dimension: {len(embeddings[0])}")
        
        # Verify all embeddings have same dimension
        dims = [len(emb) for emb in embeddings]
        if len(set(dims)) == 1:
            print(f"✅ All embeddings have consistent dimension: {dims[0]}")
        else:
            print(f"❌ Inconsistent embedding dimensions: {dims}")
            return False
            
        return True
    except Exception as e:
        print(f"❌ Embedding generation failed: {e}")
        return False


def test_vector_building() -> bool:
    """Test vector building with metadata filtering."""
    print("\n🏗️  Testing Vector Building...")
    try:
        test_docs = create_test_documents()
        vectors = build_vectors_from_objects(test_docs)
        
        print(f"✅ Built {len(vectors)} vectors from {len(test_docs)} documents")
        
        # Analyze metadata filtering
        for i, (doc, vector) in enumerate(zip(test_docs, vectors)):
            print(f"\n📄 Document {i+1}: {doc['fileName']}")
            print(f"   Original metadata fields: {len([k for k, v in doc.items() if v is not None])}")
            print(f"   Pinecone metadata fields: {len(vector['metadata'])}")
            
            # Show which fields were filtered out
            original_keys = set(doc.keys())
            pinecone_keys = set(vector['metadata'].keys())
            filtered_out = original_keys - pinecone_keys
            if filtered_out:
                print(f"   🚫 Filtered out (null): {sorted(filtered_out)}")
            
            # Show preserved fields
            preserved = pinecone_keys & original_keys
            print(f"   ✅ Preserved: {sorted(preserved)}")
        
        return True
    except Exception as e:
        print(f"❌ Vector building failed: {e}")
        return False


def test_upsert(index_name: str, namespace: str) -> bool:
    """Test upserting vectors to Pinecone."""
    print(f"\n⬆️  Testing Vector Upsert to namespace '{namespace}'...")
    try:
        test_docs = create_test_documents()
        
        # Upsert test documents
        upsert_stats = upsert_objects(
            index_name=index_name,
            objects=test_docs,
            namespace=namespace,
            batch_size=2,  # Small batch for testing
        )

        print(f"✅ Upserted {upsert_stats.pinecone_upsert_rows} vectors successfully")
        
        # Verify upsert by checking index stats
        pc = get_pinecone()
        index = get_index(pc, index_name)
        stats = index.describe_index_stats()
        
        namespace_stats = stats.namespaces.get(namespace, {})
        vector_count = namespace_stats.get('vector_count', 0)
        print(f"📊 Vectors in namespace '{namespace}': {vector_count}")
        
        return True
    except Exception as e:
        print(f"❌ Upsert failed: {e}")
        return False


def test_search(index_name: str, namespace: str) -> bool:
    """Test various search scenarios."""
    print(f"\n🔍 Testing Search in namespace '{namespace}'...")
    try:
        pc = get_pinecone()
        index = get_index(pc, index_name)
        
        # Test queries
        test_queries = [
            {
                "query": "machine learning algorithms",
                "description": "General ML query"
            },
            {
                "query": "neural networks and deep learning",
                "description": "Neural networks query"
            },
            {
                "query": "artificial intelligence introduction",
                "description": "AI introduction query"
            }
        ]
        
        for query_info in test_queries:
            query_text = query_info["query"]
            description = query_info["description"]
            
            print(f"\n🎯 {description}: '{query_text}'")
            
            # Generate query embedding
            query_embedding = embed_texts([query_text])[0]
            
            # Search without filters
            results = index.query(
                vector=query_embedding,
                top_k=3,
                include_metadata=True,
                namespace=namespace
            )
            
            print(f"   📊 Found {len(results.matches)} results")
            for i, match in enumerate(results.matches):
                print(f"   {i+1}. Score: {match.score:.4f}")
                print(f"      ID: {match.id}")
                print(f"      File: {match.metadata.get('fileName', 'N/A')}")
                print(f"      Type: {match.metadata.get('elementType', 'N/A')}")
                if 'pageNumber' in match.metadata:
                    print(f"      Page: {match.metadata['pageNumber']}")
                if 'slideNumber' in match.metadata:
                    print(f"      Slide: {match.metadata['slideNumber']}")
                if 'sheetName' in match.metadata:
                    print(f"      Sheet: {match.metadata['sheetName']}")
        
        return True
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return False


def test_metadata_filtering(index_name: str, namespace: str) -> bool:
    """Test search with metadata filtering."""
    print(f"\n🎛️  Testing Metadata Filtering in namespace '{namespace}'...")
    try:
        pc = get_pinecone()
        index = get_index(pc, index_name)
        
        # Generate a general query embedding
        query_embedding = embed_texts(["machine learning"])[0]
        
        # Test various filters
        filters = [
            {
                "filter": {"isTable": True},
                "description": "Only table content"
            },
            {
                "filter": {"fileExt": "pdf"},
                "description": "Only PDF documents"
            },
            {
                "filter": {"pageNumber": {"$exists": True}},
                "description": "Documents with page numbers"
            },
            {
                "filter": {"slideNumber": {"$exists": True}},
                "description": "Documents with slide numbers"
            }
        ]
        
        for filter_info in filters:
            filter_expr = filter_info["filter"]
            description = filter_info["description"]
            
            print(f"\n🔍 Filter: {description}")
            print(f"   Expression: {filter_expr}")
            
            results = index.query(
                vector=query_embedding,
                top_k=5,
                include_metadata=True,
                namespace=namespace,
                filter=filter_expr
            )
            
            print(f"   📊 Found {len(results.matches)} results")
            for i, match in enumerate(results.matches):
                metadata = match.metadata
                print(f"   {i+1}. {metadata.get('fileName', 'N/A')} - {metadata.get('elementType', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"❌ Metadata filtering failed: {e}")
        return False


def test_cleanup(index_name: str, namespace: str) -> bool:
    """Clean up test data."""
    print(f"\n🧹 Cleaning up test data from namespace '{namespace}'...")
    try:
        pc = get_pinecone()
        index = get_index(pc, index_name)
        
        # Delete test vectors by ID
        test_ids = [
            "test_doc_1:0001",
            "test_doc_2:0001", 
            "test_doc_3:0001",
            "test_doc_4:0001"
        ]
        
        index.delete(ids=test_ids, namespace=namespace)
        print(f"✅ Deleted {len(test_ids)} test vectors")
        
        return True
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return False


def main():
    """Main testing function."""
    parser = argparse.ArgumentParser(description="Test Pinecone functionality")
    parser.add_argument("--index-name", default="text-embedding-3-small",
                       help="Pinecone index name (default: text-embedding-3-small)")
    parser.add_argument("--namespace", default="test", 
                       help="Pinecone namespace for testing (default: test)")
    parser.add_argument("--skip-cleanup", action="store_true",
                       help="Skip cleanup step (leave test data in Pinecone)")
    
    args = parser.parse_args()
    
    print("🧪 Pinecone Testing Script")
    print("=" * 50)
    print(f"Index: {args.index_name}")
    print(f"Namespace: {args.namespace}")
    print("=" * 50)
    
    # Run tests
    tests = [
        ("Connection", lambda: test_connection(args.index_name)),
        ("Embedding Generation", test_embedding_generation),
        ("Vector Building", test_vector_building),
        ("Vector Upsert", lambda: test_upsert(args.index_name, args.namespace)),
        ("Search", lambda: test_search(args.index_name, args.namespace)),
        ("Metadata Filtering", lambda: test_metadata_filtering(args.index_name, args.namespace)),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Cleanup (optional)
    if not args.skip_cleanup:
        cleanup_result = test_cleanup(args.index_name, args.namespace)
        results["Cleanup"] = cleanup_result
    
    # Print summary
    print("\n" + "=" * 50)
    print("🏁 TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} {test_name}")
        if passed_test:
            passed += 1
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Pinecone is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    exit(main())
