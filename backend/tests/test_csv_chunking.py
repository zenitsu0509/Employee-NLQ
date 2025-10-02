"""Unit test for CSV chunking with bonus data."""
from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from backend.api.services.document_processor import DocumentProcessor


def test_csv_chunking_preserves_header_and_bonus_data():
    """Test that CSV files are chunked with headers and bonus column is preserved."""
    # Create a minimal CSV similar to salaries.csv
    csv_content = """employee_id,month,base_salary,bonus
1,2024-01,85000,2000
2,2024-01,110000,5000
3,2024-01,75000,1500
4,2024-01,90000,2500
5,2024-01,130000,6000
6,2024-01,120000,4000
7,2024-01,78000,1000
8,2024-01,95000,3000
9,2024-01,98000,2500
10,2024-01,115000,3500
11,2024-01,88000,2200
12,2024-01,92000,2800
"""
    
    with NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp:
        tmp.write(csv_content)
        tmp.flush()
        csv_path = Path(tmp.name)
    
    try:
        # Create a mock processor (we only need the chunking methods)
        processor = DocumentProcessor(vector_store=None, model=None, batch_size=32)
        
        # Read and infer document type
        doc_type = processor._infer_document_type(csv_content, csv_path)
        assert doc_type == "table", f"Expected 'table' type, got {doc_type}"
        
        # Chunk the CSV
        chunks = processor.dynamic_chunking(csv_content, doc_type)
        
        # Verify chunks
        assert len(chunks) > 0, "No chunks generated"
        print(f"Generated {len(chunks)} chunks")
        
        # Each chunk should have the header
        for i, chunk in enumerate(chunks):
            lines = chunk.strip().splitlines()
            assert len(lines) > 0, f"Chunk {i} is empty"
            header = lines[0]
            assert "employee_id" in header, f"Chunk {i} missing header"
            assert "bonus" in header, f"Chunk {i} missing bonus column in header"
            print(f"\nChunk {i+1}:")
            print(chunk[:200] + "..." if len(chunk) > 200 else chunk)
        
        # Verify bonus data is present in chunks
        all_chunk_text = "\n".join(chunks)
        assert "bonus" in all_chunk_text, "Bonus column name not found in chunks"
        assert "2000" in all_chunk_text, "Bonus value 2000 not found in chunks"
        assert "5000" in all_chunk_text, "Bonus value 5000 not found in chunks"
        
        print("\n✓ CSV chunking test passed!")
        
    finally:
        csv_path.unlink()


if __name__ == "__main__":
    test_csv_chunking_preserves_header_and_bonus_data()
