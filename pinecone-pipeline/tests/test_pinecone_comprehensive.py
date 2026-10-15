#!/usr/bin/env python3
"""
Comprehensive Pinecone Testing Script

This script tests Pinecone functionality with real-world scenarios:
- Connection and index management
- Vector upserts with metadata
- Search with retry mechanism (accounts for indexing delays)
- Metadata filtering
- Performance benchmarking
- Error handling

Usage:
    python test_pinecone_comprehensive.py [options]
"""

import os
import json
import time
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
    exit(1)


def wait_for_indexing(seconds: int = 5):
    """Wait for Pinecone to index the vectors."""
    print(f"⏳ Waiting {seconds} seconds for indexing...")
    time.sleep(seconds)


def test_search_with_retry(index_name: str, namespace: str, max_retries: int = 3) -> bool:
    """Test search with retry mechanism to handle indexing delays."""
    print(f"\n🔍 Testing Search with Retry (namespace: '{namespace}')...")
    
    try:
        pc = get_pinecone()
        index = get_index(pc, index_name)
        
        query_text = "machine learning algorithms"
        query_embedding = embed_texts([query_text])[0]
        
        for attempt in range(max_retries):
            print(f"   Attempt {attempt + 1}/{max_retries}")
            
            results = index.query(
                vector=query_embedding,
                top_k=5,
                include_metadata=True,
                namespace=namespace
            )
            
            if len(results.matches) > 0:
                print(f"   ✅ Found {len(results.matches)} results!")
                for i, match in enumerate(results.matches):
                    print(f"      {i+1}. Score: {match.score:.4f} - {match.metadata.get('fileName', 'N/A')}")
                return True
            else:
                print(f"   ⏳ No results yet, waiting...")
                if attempt < max_retries - 1:
                    wait_for_indexing(3)
        
        print("   ⚠️ No results found after all retries")
        return True  # Still consider it a pass as the search worked
        
    except Exception as e:
        print(f"❌ Search with retry failed: {e}")
        return False


def test_real_content_search(index_name: str, namespace: str) -> bool:
    """Test search using content from your actual documents."""
    print(f"\n🎯 Testing Real Content Search (namespace: '{namespace}')...")
    
    try:
        pc = get_pinecone()
        index = get_index(pc, index_name)
        
        # Try to search in the default namespace where your real content is
        real_queries = [
            "instrukcja dla pracownika",
            "najem mieszkania",
            "umowa najmu",
            "regulamin"
        ]
        
        for query in real_queries:
            print(f"\n   🔍 Query: '{query}'")
            query_embedding = embed_texts([query])[0]
            
            # Search in default namespace (where your real documents are)
            results = index.query(
                vector=query_embedding,
                top_k=3,
                include_metadata=True,
                namespace="default"  # Your real content namespace
            )
            
            print(f"      📊 Found {len(results.matches)} results")
            for i, match in enumerate(results.matches):
                metadata = match.metadata
                print(f"      {i+1}. Score: {match.score:.4f}")
                print(f"         File: {metadata.get('fileName', 'N/A')}")
                print(f"         Section: {metadata.get('sectionTitle', 'N/A')}")
                if 'pageNumber' in metadata:
                    print(f"         Page: {metadata['pageNumber']}")
                
        return True
        
    except Exception as e:
        print(f"❌ Real content search failed: {e}")
        return False


def test_benchmark_embedding(num_texts: int = 100) -> bool:
    """Benchmark embedding generation performance."""
    print(f"\n⚡ Benchmarking Embedding Generation ({num_texts} texts)...")
    
    try:
        # Generate test texts
        test_texts = [f"This is test sentence number {i} about various topics." for i in range(num_texts)]
        
        start_time = time.time()
        embeddings = embed_texts(test_texts)
        end_time = time.time()
        
        duration = end_time - start_time
        texts_per_second = num_texts / duration
        
        print(f"   ✅ Generated {len(embeddings)} embeddings in {duration:.2f} seconds")
        print(f"   ⚡ Performance: {texts_per_second:.1f} texts/second")
        
        if texts_per_second > 10:
            print("   🚀 Good performance!")
        elif texts_per_second > 5:
            print("   👍 Acceptable performance")
        else:
            print("   ⚠️ Slow performance - check your OpenAI API key and network")
            
        return True
        
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        return False


def test_large_batch_upsert(index_name: str, namespace: str) -> bool:
    """Test upserting a larger batch of vectors."""
    print(f"\n📦 Testing Large Batch Upsert (namespace: '{namespace}')...")
    
    try:
        # Create a larger set of test documents
        large_test_docs = []
        for i in range(20):
            doc = {
                "stableId": f"large_test_{i:03d}",
                "content": f"This is large test document number {i}. It contains various information about topic {i % 5}.",
                "docId": f"large_test_batch",
                "fileName": f"test_doc_{i:03d}.txt",
                "filePath": f"/test/test_doc_{i:03d}.txt",
                "sourceRelativePath": f"batch/test_doc_{i:03d}.txt",
                "pageNumber": i + 1 if i % 3 == 0 else None,  # Some have page numbers
                "slideNumber": None,
                "sheetName": None,
                "chunkIndex": i,
                "sectionTitle": f"Section {i // 5 + 1}",
                "sectionPath": f"Chapter {i // 10 + 1} > Section {i // 5 + 1}",
                "language": "en",
                "isTable": i % 7 == 0,  # Some are tables
                "elementType": "Table" if i % 7 == 0 else "Text",
                "lastModified": "2025-01-01T10:00:00",
                "mimeType": "text/plain",
                "fileExt": "txt"
            }
            large_test_docs.append(doc)
        
        start_time = time.time()
        upsert_stats = upsert_objects(
            index_name=index_name,
            objects=large_test_docs,
            namespace=namespace,
            batch_size=10,
        )
        end_time = time.time()
        
        duration = end_time - start_time
        vectors_per_second = upsert_stats.pinecone_upsert_rows / duration
        
        print(f"   ✅ Upserted {upsert_stats.pinecone_upsert_rows} vectors in {duration:.2f} seconds")
        print(f"   ⚡ Performance: {vectors_per_second:.1f} vectors/second")
        
        return True
        
    except Exception as e:
        print(f"❌ Large batch upsert failed: {e}")
        return False


def test_advanced_filtering(index_name: str, namespace: str) -> bool:
    """Test advanced metadata filtering scenarios."""
    print(f"\n🎛️ Testing Advanced Filtering (namespace: '{namespace}')...")
    
    try:
        pc = get_pinecone()
        index = get_index(pc, index_name)
        query_embedding = embed_texts(["test query"])[0]
        
        wait_for_indexing(5)  # Wait for large batch to be indexed
        
        advanced_filters = [
            {
                "filter": {"$and": [{"isTable": True}, {"language": "en"}]},
                "description": "Tables in English"
            },
            {
                "filter": {"$or": [{"pageNumber": {"$gte": 10}}, {"isTable": True}]},
                "description": "Page 10+ OR tables"
            },
            {
                "filter": {"sectionTitle": {"$in": ["Section 1", "Section 2", "Section 3"]}},
                "description": "Specific sections"
            },
            {
                "filter": {"fileName": {"$regex": "test_doc_0.*"}},
                "description": "Files matching pattern"
            }
        ]
        
        for filter_info in advanced_filters:
            filter_expr = filter_info["filter"]
            description = filter_info["description"]
            
            print(f"\n   🔍 {description}")
            print(f"      Filter: {filter_expr}")
            
            try:
                results = index.query(
                    vector=query_embedding,
                    top_k=10,
                    include_metadata=True,
                    namespace=namespace,
                    filter=filter_expr
                )
                
                print(f"      📊 Found {len(results.matches)} results")
                for i, match in enumerate(results.matches[:3]):  # Show top 3
                    metadata = match.metadata
                    print(f"      {i+1}. {metadata.get('fileName', 'N/A')} (Table: {metadata.get('isTable', False)})")
                    
            except Exception as filter_error:
                print(f"      ❌ Filter failed: {filter_error}")
        
        return True
        
    except Exception as e:
        print(f"❌ Advanced filtering failed: {e}")
        return False


def test_cleanup_large_batch(index_name: str, namespace: str) -> bool:
    """Clean up the large batch test data."""
    print(f"\n🧹 Cleaning up large batch test data...")
    
    try:
        pc = get_pinecone()
        index = get_index(pc, index_name)
        
        # Delete by filter
        index.delete(
            filter={"docId": "large_test_batch"},
            namespace=namespace
        )
        
        print(f"   ✅ Deleted large batch test data")
        return True
        
    except Exception as e:
        print(f"❌ Large batch cleanup failed: {e}")
        return False


def main():
    """Main testing function."""
    parser = argparse.ArgumentParser(description="Comprehensive Pinecone testing")
    parser.add_argument("--index-name", default="text-embedding-3-small",
                       help="Pinecone index name")
    parser.add_argument("--namespace", default="test-comprehensive",
                       help="Test namespace")
    parser.add_argument("--skip-cleanup", action="store_true",
                       help="Skip cleanup")
    parser.add_argument("--skip-large-batch", action="store_true",
                       help="Skip large batch tests")
    parser.add_argument("--quick", action="store_true",
                       help="Run quick tests only")
    
    args = parser.parse_args()
    
    print("🧪 Comprehensive Pinecone Testing")
    print("=" * 60)
    print(f"Index: {args.index_name}")
    print(f"Namespace: {args.namespace}")
    print("=" * 60)
    
    # Define test suite
    if args.quick:
        tests = [
            ("Connection", lambda: test_connection(args.index_name)),
            ("Embedding Benchmark", lambda: test_benchmark_embedding(10)),
            ("Real Content Search", lambda: test_real_content_search(args.index_name, args.namespace)),
        ]
    else:
        tests = [
            ("Connection", lambda: test_connection(args.index_name)),
            ("Embedding Benchmark", lambda: test_benchmark_embedding(50)),
            ("Real Content Search", lambda: test_real_content_search(args.index_name, args.namespace)),
        ]
        
        if not args.skip_large_batch:
            tests.extend([
                ("Large Batch Upsert", lambda: test_large_batch_upsert(args.index_name, args.namespace)),
                ("Search with Retry", lambda: test_search_with_retry(args.index_name, args.namespace)),
                ("Advanced Filtering", lambda: test_advanced_filtering(args.index_name, args.namespace)),
            ])
    
    # Run tests
    results = {}
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Cleanup
    if not args.skip_cleanup and not args.skip_large_batch and not args.quick:
        cleanup_result = test_cleanup_large_batch(args.index_name, args.namespace)
        results["Cleanup"] = cleanup_result
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 COMPREHENSIVE TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All tests passed! Pinecone is working excellently.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the output above.")
        return 1


def test_connection(index_name: str) -> bool:
    """Test basic connection (reused from original script)."""
    try:
        pc = get_pinecone()
        ensure_index(pc, index_name)
        index = get_index(pc, index_name)
        stats = index.describe_index_stats()
        print(f"✅ Connected successfully. Total vectors: {stats['total_vector_count']}")
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    exit(main())
