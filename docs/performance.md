# Performance

What I've actually measured vs. what I've guessed. Numbers are from
`make load-smoke` on my laptop (i7-12700, NVMe, no GPU, 32GB RAM, single
worker) unless otherwise noted. Don't take these as SLOs.

## Hot paths

| Conversion | Latency (p50) | Latency (p99) | Notes |
|---|---|---|---|
| PDF → DOCX (10MB) | 1.8s | 4.2s | pdf2docx (no LO) |
| DOCX → PDF (10MB) | 2.4s | 6.1s | LibreOffice headless |
| DOCX → HTML | 0.6s | 1.4s | Pandoc |
| PNG → WebP (2MB) | 40ms | 110ms | Pillow |
| CSV → XLSX (100k rows) | 120ms | 380ms | openpyxl |
| XLSX → CSV | 200ms | 700ms | openpyxl |
| HEIC → JPG | 350ms | 900ms | pillow-heif |

Numbers degrade sharply past 100MB inputs. The worker process dies if
you give it a 1GB PDF (LibreOffice OOMs at ~3GB RSS). Need to add a
memory cap and either reject or stream the conversion.

## API

- `GET /v1/formats`: 12ms cold, 0.8ms warm (Redis cache).
- `POST /v1/convert` (create task only): 35ms p50, 110ms p99.
- `POST /v1/files/uploads` (10MB): 480ms p50, 1.2s p99. The bottleneck
  is the magic-byte scan, not the network.
- `GET /v1/tasks/{id}`: 4ms p50, 18ms p99.
- `WS /v1/ws/tasks/{id}`: 2-3 events per conversion on average, mostly
  on state transitions. Connection setup is ~40ms.

## Where the time goes (DOCX → PDF, 10MB)

```
pandoc parse    0.18s
LO spawn        0.40s   <- this is the floor; we can't really reduce
LO convert      1.50s
result upload   0.20s
result row      0.05s
                  -----
                  2.33s
```

The LO spawn dominates. We tried persistent LO instances via UNO
(looping `--accept` and connecting) but the OOM/handle-leak issues
weren't worth the 400ms gain. We re-evaluate if it ever matters.

## Database

Postgres 16, single instance, 4 vCPU, 8GB RAM. The slow query in the
slow log is consistently:

```sql
SELECT * FROM tasks
WHERE owner_id = $1 AND state IN ('queued', 'running')
ORDER BY priority DESC, queued_at ASC
LIMIT 50;
```

The `(owner_id, state, priority DESC, queued_at)` index covers it
and it's < 5ms even with a million rows.

## Worker concurrency

Each Celery worker is configured with `-c 4` (4 concurrent slots).
Higher than that and LibreOffice processes start contending for temp
dirs. The bottleneck is the conversion tool, not the worker loop.

## Bottlenecks I have NOT measured

- The 0.3s cold-start on the WS endpoint after a worker pod restart.
  Suspect it's a JWT verification in the WS middleware, not the WS
  handshake itself, but never confirmed.
- Memory usage per worker under sustained 100% load. We see ~600MB
  resident per worker, which seems high but I haven't profiled it.
- Redis pubsub throughput when there are 10k concurrent WS subscribers.
  We have never had that many.

## Things I would change if I had time

1. Switch file storage to multipart uploads with presigned URLs,
   instead of proxying through the API. Would cut the p99 of large
   uploads roughly in half.
2. Move the magic-byte scan off the request path. It's CPU-bound and
   blocks the event loop. A separate process that pulls from a queue
   would let uploads return 202 immediately.
3. Add a warm pool of LibreOffice instances. UNO is annoying but
   400ms per conversion adds up.

I keep a list of "what would I do with two weeks" ideas in
`docs/operations.md` under "Tech debt roadmap".
