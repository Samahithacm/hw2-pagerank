#!/usr/bin/env python3
import argparse
import re
import statistics
from collections import defaultdict
from google.cloud import storage
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def download_file(bucket, blob_name):
    """Download a single file from GCS with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            blob = bucket.blob(blob_name)
            content = blob.download_as_bytes().decode("utf-8")
            return blob_name, content
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Retry {attempt + 1} for {blob_name}: {str(e)[:50]}")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise

def download_files_parallel(bucket_name, max_workers=20):
    """Download all HTML files from GCS bucket in parallel"""
    print(f"Downloading files from gs://{bucket_name}...")
    start_time = time.time()
    
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    
    # List all blobs with pagination and timeout handling
    print("Listing files in bucket...")
    html_blobs = []
    try:
        # Use page iterator with smaller page size to avoid timeout
        for blob in bucket.list_blobs(timeout=300, page_size=1000):
            if blob.name.endswith('.html'):
                html_blobs.append(blob.name)
            if len(html_blobs) % 5000 == 0 and len(html_blobs) > 0:
                print(f"  Found {len(html_blobs)} files so far...")
    except Exception as e:
        print(f"Error listing blobs: {e}")
        print("Trying alternative method...")
        # Fallback: assume files are in html_files/ directory numbered 0-19999
        html_blobs = [f"html_files/{i}.html" for i in range(20000)]
    
    print(f"Found {len(html_blobs)} HTML files")
    
    files_content = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_file, bucket, blob_name): blob_name 
                   for blob_name in html_blobs}
        
        completed = 0
        failed = 0
        for future in as_completed(futures):
            try:
                blob_name, content = future.result()
                files_content[blob_name] = content
                completed += 1
                if completed % 1000 == 0:
                    print(f"Downloaded {completed}/{len(html_blobs)} files...")
            except Exception as e:
                failed += 1
                if failed < 10:  # Only print first 10 errors
                    print(f"Failed to download a file: {str(e)[:100]}")
    
    elapsed = time.time() - start_time
    print(f"Download completed in {elapsed:.2f} seconds")
    print(f"Successfully downloaded: {completed}, Failed: {failed}")
    
    return files_content

def parse_links(html_content):
    """Extract outgoing links from HTML content"""
    # Pattern to match: <a HREF="NUMBER.html">
    pattern = r'<a HREF="(\d+)\.html">'
    links = re.findall(pattern, html_content)
    return [int(link) for link in links]

def build_graph(files_content):
    """Build graph structure from files"""
    print("Building graph structure...")
    
    graph = defaultdict(list)  # outgoing links: graph[page] = [list of pages it links to]
    incoming = defaultdict(list)  # incoming links: incoming[page] = [list of pages linking to it]
    
    # Extract page numbers from filenames
    pages = set()
    for filename in files_content.keys():
        # Extract number from "html_files/NUMBER.html" or "NUMBER.html"
        # Split by '/' and take last part, then remove .html
        page_num = int(filename.split('/')[-1].replace('.html', ''))
        pages.add(page_num)
    
    # Parse all links
    for filename, content in files_content.items():
        # Extract number from "html_files/NUMBER.html" or "NUMBER.html"
        page_num = int(filename.split('/')[-1].replace('.html', ''))
        outgoing_links = parse_links(content)
        graph[page_num] = outgoing_links
        
        # Build incoming links
        for target in outgoing_links:
            incoming[target].append(page_num)
    
    return graph, incoming, pages

def compute_statistics(graph, pages):
    """Compute statistics on incoming and outgoing links"""
    print("\nComputing link statistics...")
    
    outgoing_counts = [len(graph[page]) for page in pages]
    incoming_counts = defaultdict(int)
    
    # Count incoming links
    for page in pages:
        for target in graph[page]:
            incoming_counts[target] += 1
    
    incoming_values = [incoming_counts[page] for page in pages]
    
    # Compute statistics
    stats = {
        'outgoing': {
            'average': statistics.mean(outgoing_counts),
            'median': statistics.median(outgoing_counts),
            'max': max(outgoing_counts),
            'min': min(outgoing_counts),
            'quintiles': statistics.quantiles(outgoing_counts, n=5)
        },
        'incoming': {
            'average': statistics.mean(incoming_values),
            'median': statistics.median(incoming_values),
            'max': max(incoming_values),
            'min': min(incoming_values),
            'quintiles': statistics.quantiles(incoming_values, n=5)
        }
    }
    
    return stats

def compute_pagerank(graph, pages, damping=0.85, tolerance=0.005, max_iterations=100):
    """
    Compute PageRank using iterative algorithm:
    PR(A) = (1-d)/n + d * sum(PR(Ti)/C(Ti))
    
    where:
    - PR(X) is the pagerank of page X
    - d is the damping factor (0.85)
    - n is the total number of pages
    - Ti are all pages pointing to page A
    - C(X) is the number of outgoing links from page X
    """
    print("\nComputing PageRank...")
    
    n = len(pages)
    pagerank = {page: 1.0/n for page in pages}
    
    # Build incoming links map
    incoming = defaultdict(list)
    for page in pages:
        for target in graph[page]:
            incoming[target].append(page)
    
    # Identify dangling nodes (nodes with no outgoing links)
    dangling_nodes = [page for page in pages if len(graph[page]) == 0]
    if len(dangling_nodes) > 0:
        print(f"Warning: Found {len(dangling_nodes)} dangling nodes (pages with no outgoing links)")
    
    iteration = 0
    while iteration < max_iterations:
        new_pagerank = {}
        
        # Calculate dangling contribution (distribute evenly to all pages)
        dangling_sum = sum(pagerank[page] for page in dangling_nodes)
        
        for page in pages:
            # Base probability + dangling contribution
            rank = (1 - damping) / n + damping * (dangling_sum / n)
            
            # Add contributions from incoming links
            for incoming_page in incoming[page]:
                outgoing_count = len(graph[incoming_page])
                if outgoing_count > 0:
                    rank += damping * (pagerank[incoming_page] / outgoing_count)
            
            new_pagerank[page] = rank
        
        # Check convergence
        total_change = sum(abs(new_pagerank[p] - pagerank[p]) for p in pages)
        total_sum = sum(new_pagerank.values())
        change_percentage = (total_change / total_sum) * 100
        
        pagerank = new_pagerank
        iteration += 1
        
        if iteration % 10 == 0:
            print(f"  Iteration {iteration}: change = {change_percentage:.4f}%")
        
        if change_percentage < (tolerance * 100):
            print(f"Converged after {iteration} iterations (change: {change_percentage:.4f}%)")
            break
    
    if iteration == max_iterations:
        print(f"Reached maximum iterations ({max_iterations})")
    
    return pagerank, iteration

def main():
    parser = argparse.ArgumentParser(description='PageRank analysis on GCS bucket')
    parser.add_argument('bucket_name', help='GCS bucket name (e.g., bu-cs528-mahicm13)')
    parser.add_argument('--workers', type=int, default=20, help='Number of parallel workers for download (default: 20)')
    args = parser.parse_args()
    
    print("="*60)
    print("PAGERANK ANALYSIS ON GOOGLE CLOUD STORAGE")
    print("="*60)
    print(f"Bucket: {args.bucket_name}")
    print(f"Workers: {args.workers}")
    print("="*60 + "\n")
    
    overall_start = time.time()
    
    # Download files
    files_content = download_files_parallel(args.bucket_name, args.workers)
    
    # Build graph
    graph, incoming, pages = build_graph(files_content)
    
    # Compute statistics
    stats = compute_statistics(graph, pages)
    
    print("\n" + "="*60)
    print("LINK STATISTICS")
    print("="*60)
    print(f"\nOutgoing Links:")
    print(f"  Average: {stats['outgoing']['average']:.2f}")
    print(f"  Median: {stats['outgoing']['median']:.2f}")
    print(f"  Max: {stats['outgoing']['max']}")
    print(f"  Min: {stats['outgoing']['min']}")
    print(f"  Quintiles:")
    print(f"    0% (Min): {stats['outgoing']['min']}")
    for i, q in enumerate(stats['outgoing']['quintiles'], 1):
        print(f"    {i*20}%: {q:.2f}")
    print(f"    100% (Max): {stats['outgoing']['max']}")
    
    print(f"\nIncoming Links:")
    print(f"  Average: {stats['incoming']['average']:.2f}")
    print(f"  Median: {stats['incoming']['median']:.2f}")
    print(f"  Max: {stats['incoming']['max']}")
    print(f"  Min: {stats['incoming']['min']}")
    print(f"  Quintiles:")
    print(f"    0% (Min): {stats['incoming']['min']}")
    for i, q in enumerate(stats['incoming']['quintiles'], 1):
        print(f"    {i*20}%: {q:.2f}")
    print(f"    100% (Max): {stats['incoming']['max']}")
    
    # Compute PageRank
    pagerank, iterations = compute_pagerank(graph, pages)
    
    # Get top 5 pages
    top_5 = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:5]
    
    print("\n" + "="*60)
    print("PAGERANK RESULTS")
    print("="*60)
    print(f"\nTotal pages: {len(pages)}")
    print(f"Iterations to convergence: {iterations}")
    
    total_pr = sum(pagerank.values())
    print(f"Sum of all PageRanks: {total_pr:.10f}")
    print(f"Expected: 1.0")
    print(f"Difference: {abs(total_pr - 1.0):.10f}")
    
    if abs(total_pr - 1.0) < 0.01:
        print("✓ VERIFICATION PASSED: Sum ≈ 1.0")
    else:
        print("✗ WARNING: Sum differs from 1.0")
    
    print("\nTop 5 Pages by PageRank:")
    for i, (page, rank) in enumerate(top_5, 1):
        incoming_count = len(incoming.get(page, []))
        outgoing_count = len(graph.get(page, []))
        print(f"  {i}. Page {page}: PR = {rank:.10f}")
        print(f"      Incoming links: {incoming_count}, Outgoing links: {outgoing_count}")
    
    total_time = time.time() - overall_start
    print(f"\n" + "="*60)
    print("EXECUTION SUMMARY")
    print("="*60)
    print(f"Total execution time: {total_time:.2f} seconds")
    print("="*60)

if __name__ == "__main__":
    main()
