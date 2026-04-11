#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import existing vectors from JSON file to ChromaDB

This script loads the pre-generated vectors from the JSON file
and imports them into the ChromaDB database for integration with
the existing LocalRAG system.
"""

import json
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
import hashlib

def import_vectors(source_json_path: str, target_db_path: str, batch_size: int = 32) -> dict:
    """
    Import vectors from JSON file to ChromaDB
    
    Args:
        source_json_path: Path to source vectors JSON file
        target_db_path: Path to ChromaDB database
        batch_size: Number of documents per batch
        
    Returns:
        dict: Import statistics
    """
    
    print("=" * 80)
    print("🚀 Importing Vectors to ChromaDB")
    print("=" * 80)
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. Verify source file exists
    source_path = Path(source_json_path)
    if not source_path.exists():
        print(f"❌ Source file not found: {source_json_path}")
        return {"success": False, "error": "Source file not found"}
    
    print(f"📂 Source: {source_json_path}")
    print(f"   Size: {source_path.stat().st_size / (1024*1024):.2f} MB")
    
    # 2. Load vectors from JSON
    print("\n📥 Loading vectors from JSON...")
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        vectors = data.get('vectors', [])
        metadata = data.get('metadata', {})
        
        print(f"✅ Loaded {len(vectors)} vectors")
        print(f"   Vector dimension: {metadata.get('vector_dimension', 'unknown')}")
        print(f"   Generation time: {metadata.get('timestamp', 'unknown')}")
        
    except Exception as e:
        print(f"❌ Failed to load JSON: {str(e)}")
        return {"success": False, "error": f"Failed to load JSON: {str(e)}"}
    
    # 3. Initialize ChromaDB
    print("\n🗄️  Initializing ChromaDB...")
    try:
        import chromadb
        
        # Create DB directory if needed
        os.makedirs(target_db_path, exist_ok=True)
        
        # Initialize client
        client = chromadb.PersistentClient(path=target_db_path)
        
        # Get or create collection
        # IMPORTANT: Allow custom vector dimension (256 for our character-frequency vectors)
        collection = client.get_or_create_collection(
            name="documents",
            metadata={
                "hnsw:space": "cosine",
                "hnsw:construction_ef": 200,
                "hnsw:search_ef": 200
            }
        )
        
        print(f"✅ ChromaDB initialized")
        print(f"   Location: {target_db_path}")
        print(f"   Collection: documents")
        
    except Exception as e:
        print(f"❌ Failed to initialize ChromaDB: {str(e)}")
        return {"success": False, "error": f"ChromaDB initialization failed: {str(e)}"}
    
    # 4. Import vectors in batches
    print("\n🔄 Importing vectors...")
    successful = 0
    failed = 0
    
    try:
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i+batch_size]
            
            ids = []
            embeddings = []
            documents = []
            metadatas = []
            
            for vec_data in batch:
                try:
                    # Extract vector data
                    vec_id = vec_data.get('id')
                    embedding = vec_data.get('vector', [])
                    doc_name = vec_data.get('name', 'unknown')
                    doc_path = vec_data.get('path', '')
                    text_preview = vec_data.get('text_preview', '')
                    doc_size = vec_data.get('size', 0)
                    
                    # Validate vector dimension
                    if len(embedding) != 256:
                        print(f"⚠️  Warning: Vector {vec_id} has dimension {len(embedding)}, expected 256")
                        # Pad or truncate to 256
                        if len(embedding) < 256:
                            embedding = embedding + [0.0] * (256 - len(embedding))
                        else:
                            embedding = embedding[:256]
                    
                    ids.append(vec_id)
                    embeddings.append(embedding)
                    documents.append(text_preview[:5000])  # Store preview
                    metadatas.append({
                        "source": doc_path,
                        "size": doc_size,
                        "type": Path(doc_path).suffix if doc_path else "unknown"
                    })
                    
                    successful += 1
                    
                except Exception as e:
                    print(f"⚠️  Failed to process vector {vec_data.get('id', 'unknown')}: {str(e)}")
                    failed += 1
                    continue
            
            # Batch add to collection
            if ids:
                try:
                    collection.add(
                        ids=ids,
                        embeddings=embeddings,
                        documents=documents,
                        metadatas=metadatas
                    )
                    print(f"  ✅ Batch {i//batch_size + 1}: {len(ids)} documents added")
                except Exception as e:
                    print(f"  ❌ Failed to add batch: {str(e)}")
                    failed += len(ids)
                    successful -= len(ids)
        
        print(f"\n✅ Import complete!")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")
        
        # 5. Verify collection
        collection_count = collection.count()
        print(f"\n📊 Collection stats:")
        print(f"   Total documents: {collection_count}")
        
        return {
            "success": True,
            "total_imported": successful,
            "failed": failed,
            "collection_count": collection_count,
            "db_path": target_db_path
        }
        
    except Exception as e:
        print(f"❌ Import failed: {str(e)}")
        return {"success": False, "error": f"Import failed: {str(e)}"}


def main():
    parser = argparse.ArgumentParser(
        description="Import vectors from JSON to ChromaDB"
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Path to source vectors JSON file"
    )
    parser.add_argument(
        "--target",
        default="/Users/didi/Downloads/panth/data/chroma",
        help="Path to ChromaDB database (default: /Users/didi/Downloads/panth/data/chroma)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for import (default: 32)"
    )
    
    args = parser.parse_args()
    
    # Run import
    result = import_vectors(args.source, args.target, args.batch_size)
    
    # Print result
    print("\n" + "=" * 80)
    if result.get("success"):
        print("✅ Import succeeded!")
        print(f"   Imported: {result.get('total_imported')} documents")
        print(f"   Failed: {result.get('failed')} documents")
        print(f"   Collection: {result.get('collection_count')} total documents")
        sys.exit(0)
    else:
        print("❌ Import failed!")
        print(f"   Error: {result.get('error')}")
        sys.exit(1)


if __name__ == '__main__':
    main()
