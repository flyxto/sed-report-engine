# Deployment & Operations

How the reporting engine (and the design modules that use it) are intended to
run in production. This captures the hosting, networking, cost, and performance
decisions made during design. Numbers marked *(measured)* were profiled on a
developer Mac; a proper on-hardware benchmark is still pending (see
[Open items](#open-items)).

## Deployment model: one box hosts everything

A **single dedicated-core server** hosts the whole stack — the design modules
(rafts, beams, pf, rw), the reporting/printer, a Redis job queue, and a
Cloudflare Tunnel. Reporting is light enough to ride along with the FEA at no
meaningful cost.

```
Client
  │  (HTTPS)
Cloudflare edge  ── DNS / WAF / Access ──┐
  │  Tunnel (cloudflared, outbound only) │
  ▼                                      │
The box (no public ports open):          │
  ┌────────────────────────────────────┐ │
  │ api (FastAPI)   enqueue jobs        │ │
  │ redis           shared queue (local)│ │
  │ worker ×N       analyse (FEA)       │ │
  │                 → render (reporting)│ │
  │                 → upload to R2 ──────┼─┼──►  Cloudflare R2  ──► served via
  └────────────────────────────────────┘ │      (zero egress)      Cloudflare edge
```

### The one rule: a single shared worker pool

FEA is CPU-bound and single-threaded per analysis, so **cores are the shared,
finite resource**. Do **not** run a separate always-on worker pool per module —
that oversubscribes the CPU. Instead:

- **One Redis queue** that every module's jobs go into.
- **One pool of ~N workers** (N ≈ cores − 1–2, leaving headroom for API/Redis/
  tunnel/OS) pulling jobs from any module.

Total analysis capacity across *all* modules combined is what one pool provides.
Size to **combined** demand, not per-module. Adding a second worker node later is
trivial — point more workers at the same queue.

## Why ReportLab, not WeasyPrint

The design modules previously rendered reports with **WeasyPrint**. The new
engine uses **ReportLab**. Measured on the same 162 KB report:

| | WeasyPrint (old) | reporting / ReportLab (new) |
|---|---|---|
| Peak RAM per render | **160 MB** *(measured)* | **~48 MB** *(measured)* |
| System dependencies | Pango, Cairo, GDK (native, via `apt`) | none — pure `pip install` |
| Output | PDF only | HTML **and** PDF from one model |
| Behaviour on weak/throttled CPU | degrades badly | flat, light, predictable |

~3× lighter, dependency-free (simpler/smaller Docker image), and it produces the
on-screen HTML *and* the PDF from one component model. This is what makes it safe
to co-host on the single box and what keeps per-render memory flat under
concurrency.

> Scope note: switching to this engine removes **WeasyPrint's** cost. It does not
> by itself change **plot generation** cost. If Plotly + **kaleido** (a headless
> Chromium) is in the figure path, that's a separate heavyweight — prefer
> **matplotlib SVG** for engineering diagrams. See [Open items](#open-items).

## Hosting decision

FEA needs **strong single-core performance** and **dedicated (non-oversold)
cores** so a noisy neighbour can't steal CPU mid-solve. That ruled some options
in and out:

| Option | Verdict |
|---|---|
| **Netcup RS 4000 G12** — 12 dedicated EPYC "Turin" cores, 32 GB DDR5 ECC, 1 TB NVMe, ~€33.55/mo | ✅ **Chosen.** Dedicated cores, great value |
| Netcup RS 2000 G12 — 8 dedicated cores, 16 GB | ✅ Viable smaller option |
| Hetzner AX bare-metal (Ryzen) — ~€46–50/mo | ✅ Fastest per-analysis; EU-only, bare-metal mgmt |
| SSD Nodes 4X-LARGE — 12 vCPU Xeon Silver, 48 GB, ~$16/mo | ❌ **Rejected** — oversold/shared, weak for sustained FEA; 3-yr lock-in |
| Hetzner CCX (dedicated vCPU cloud) | ❌ Overpriced after 2026 hikes |
| Cloudflare Containers | ⚠️ Fine for the *printer* alone (~$5–10/mo bursty), but always-on ≈ $24/mo and it can't easily run the FEA stack |

Locations: Netcup G12 is Germany / Austria / US (Manassas) — no AU/Sydney region
at time of writing. For an **async** backend (jobs queued, results fetched later)
box location barely matters; report **downloads come from R2 via Cloudflare's
edge** (Auckland/Sydney PoPs), so delivery is fast regardless of where compute sits.

## Networking: Cloudflare Tunnel + R2

- **Cloudflare Tunnel** — `cloudflared` dials outbound to Cloudflare, so **no
  public IP and no open inbound ports** are needed. Firewall all inbound; route
  SSH through the tunnel or keep it key-only. Big security win (nothing to scan).
- **Cloudflare R2** — S3-compatible object storage with **zero egress fees**.
  Render outputs are written to R2 and served from Cloudflare's edge. The
  engine returns bytes, so uploading to R2 is a one-line change:
  ```python
  pdf = reporting.render_report(provider, results, "pdf")   # stamped for the portal
  r2.put_object(Bucket="reports", Key="house3.pdf", Body=pdf)
  ```
- **Redis** — bind to localhost / the internal Docker network only. **Never
  expose it.** The tunnel fronts only the API.

## Cost summary (indicative)

| Item | ~Monthly |
|---|---|
| Netcup RS 4000 G12 (compute) | ~€33.55 (~$36) |
| Cloudflare Tunnel | free |
| Cloudflare R2 (storage) | pennies — thousands of ~50 KB PDFs sit within/near the free tier; egress $0 |
| **Total** | **~$36/mo** for the whole stack |

A separate printing box (earlier considered on SSD Nodes / Cloudflare Containers)
is **not needed** — printing rides on the same box for ~free.

## Performance findings *(measured on a Mac; re-benchmark on target HW)*

| Stage | Wall | Peak RAM |
|---|---|---|
| FEA — all 8 raft systems (serial) | ~2.4 s | 50 MB |
| FEA — single system (compute core) | ~0.3 s | 49 MB |
| WeasyPrint — one 162 KB report → PDF | 0.8 s | 160 MB |
| reporting engine — full render | sub-second | ~48 MB |

**Key insight — the "30 s" question.** A production AWS VM reported ~30 s *for
the analysis*. On a healthy machine the same 8-system analysis is ~2.4 s — a ~12×
gap that points at the **environment**, not the algorithm. Prime suspects:

1. **Throttled instance** — a burstable t2/t3 (micro/small) with drained CPU
   credits runs sustained work at ~10–20 % of a vCPU.
2. **The 8-way `parallel=True` path** — spawns 8 processes each re-importing
   numpy/scipy/matplotlib; on a 1–2 vCPU box that's an import-storm + contention.
   On a 12-core dedicated box it parallelises cleanly instead.

**Per-job memory (once on the new engine)** ≈ analysis 50 MB + reporting 48 MB +
matplotlib figures ~50–100 MB ≈ **~150–250 MB per job** — far below the earlier
1–2 GB caution. On 32 GB, ~10 workers use ~2.5 GB; **cores, not RAM, are the
limit.** So the single Netcup box hosting everything is a confident fit *if the
analysis benchmark confirms the throttling hypothesis*.

## Open items

Resolve these with the on-hardware benchmark before final sizing:

1. **Analysis performance benchmark** on the real/target box — measure **wall vs
   CPU time** (wall ≫ cpu ⇒ throttling/contention, not compute) and
   **`parallel=False` vs `parallel=True`** (serial much faster ⇒ multiprocessing
   spawn is the culprit). Reusable snippet:
   ```python
   import os, time, resource, platform
   os.environ["MPLBACKEND"] = "Agg"
   from raft_pipeline import run_all_systems
   for par in (False, True):
       t, c = time.perf_counter(), time.process_time()
       run_all_systems("inputs/house3_config.json", verbose=False, parallel=par)
       w, cpu = time.perf_counter()-t, time.process_time()-c
       rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
       rss = rss/1024 if platform.system()=="Linux" else rss/1024/1024  # -> MB
       print(f"parallel={par}: wall={w:.1f}s cpu={cpu:.1f}s peakRSS={rss:.0f}MB")
   ```
2. **Per-analysis peak RAM** on a worst-case (House 1-scale) slab — confirms the
   ~250 MB/job assumption and thus worker count on 32 GB.
3. **Figure path** — confirm whether Plotly + kaleido (headless Chromium) is used;
   if so, moving engineering diagrams to matplotlib SVG likely removes a big chunk
   of remaining report time.
4. **Wire rafts-hybrid onto the new engine** — replace the WeasyPrint path with
   `reporting.render_report()` (mostly code *removed*).
