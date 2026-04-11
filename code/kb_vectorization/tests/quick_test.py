#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/didi/Downloads/panth/kb_vectorization')

from core.config import Config
from core.vectorizer import Vectorizer, MarkdownParser

print("=" * 50)
print("Vectorization Quick Test")
print("=" * 50)

config = Config()
print(f"min_chunk_size: {config.min_chunk_size}")
print(f"chunk_size: {config.chunk_size}")
print()

parser = MarkdownParser(config)
test_content = """# Merchant Profile Data

## 1. Data Sources

Merchant profile data comes from several sources:

1. Transaction data - from merchant settlement system
2. Behavior data - from merchant APP and backend
3. Qualification data - from merchant review system

## 2. Coverage Calculation

Merchant coverage = merchants with profiles / total merchants * 100%

Current coverage about 65%, target is 90%+.
"""

print(f"Test content length: {len(test_content)}")

processed = parser._preprocess(test_content)
print(f"Processed length: {len(processed)}")

vectorizer = Vectorizer(config)

import tempfile
test_file = tempfile.mktemp(suffix='.md')
with open(test_file, 'w', encoding='utf-8') as f:
    f.write(test_content)

try:
    vec_chunks = vectorizer.vectorize_file(test_file)
    print(f"Vectorization: {len(vec_chunks)} chunks")
    if vec_chunks:
        print(f"Vector dim: {len(vec_chunks[0].vector)}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

os.unlink(test_file)
print("Test Completed")
