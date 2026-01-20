#!/usr/bin/env python3
"""Benchmark RAM preload vs disk access for PDF extraction."""
import time
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.spec_parser.parsers.pymupdf_extractor import PyMuPDFExtractor

def main():
    pdf_path = Path('data/specs/poct1a_specs/02_Roche_cobas_Liat_Host_Interface_Manual_POCT1-A.pdf')
    
    print('=== RAM PRELOAD BENCHMARK (20 pages) ===')
    print()
    
    # Test 1: RAM preload
    print('Test 1: WITH RAM preload...')
    start = time.time()
    with PyMuPDFExtractor(pdf_path, preload_to_ram=True) as extractor:
        bundles, failed = extractor._extract_pages_parallel([i for i in range(1, 21)], max_workers=4)
    ram_time = time.time() - start
    print(f'  Time: {ram_time:.2f}s ({len(bundles)} pages)')
    
    # Test 2: Disk access
    print('Test 2: WITHOUT RAM preload...')
    start = time.time()
    with PyMuPDFExtractor(pdf_path, preload_to_ram=False) as extractor:
        bundles, failed = extractor._extract_pages_parallel([i for i in range(1, 21)], max_workers=4)
    disk_time = time.time() - start
    print(f'  Time: {disk_time:.2f}s ({len(bundles)} pages)')
    
    print()
    print('=== RESULTS ===')
    print(f'RAM preload:  {ram_time:.2f}s')
    print(f'Disk access:  {disk_time:.2f}s')
    diff = disk_time - ram_time
    if diff > 0:
        print(f'Speedup:      {diff:.2f}s faster ({(disk_time/ram_time):.2f}x)')
    else:
        print(f'Difference:   {abs(diff):.2f}s slower')
    print()
    print('Projected for 236 pages:')
    print(f'  RAM:  {(ram_time/20)*236:.1f}s')
    print(f'  Disk: {(disk_time/20)*236:.1f}s')

if __name__ == '__main__':
    main()
