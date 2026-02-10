# HW2: PageRank Analysis on Google Cloud Storage

## Project Information
- **Project ID**: constant-idiom-485622-f3
- **Bucket Name**: bu-cs528-mahicm13
- **Region**: us-central1
- **Files**: 20,000 HTML files
- **Max Links**: 375

## How to Run
```bash
pip install google-cloud-storage
gcloud auth application-default login
python3 pagerank_analysis.py bu-cs528-mahicm13 --workers 20
```

## Parameters
- `bucket_name`: GCS bucket name
- `--workers`: parallel download workers (default: 20)

## Results (Cloud Shell)
### Link Statistics
- Outgoing: Avg=188.39, Median=189, Min=1, Max=374
- Incoming: Avg=188.39, Median=188, Min=135, Max=241

### PageRank
- Converged: 3 iterations
- Sum: 1.0000000000 VERIFIED

### Top 5 Pages
1. Page 2243: PR=0.0001173095 (In:200, Out:224)
2. Page 10296: PR=0.0001090302 (In:221, Out:262)
3. Page 3293: PR=0.0001081576 (In:162, Out:258)
4. Page 18886: PR=0.0001031583 (In:176, Out:192)
5. Page 487: PR=0.0001026857 (In:192, Out:30)

### Timing
- Total: 674.07 seconds

## Bug Fix
Changed `random.randrange(0, max_refs)` to `random.randrange(1, max_refs)`

## Algorithm
PR(A) = (1-d)/N + d * sum(PR(Ti)/C(Ti))
- d=0.85, N=20000, threshold=0.5%

## Bucket Access
```bash
gsutil ls gs://bu-cs528-mahicm13/html_files/ | head -10
```
