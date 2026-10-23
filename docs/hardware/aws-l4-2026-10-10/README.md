# Apertus 1.5 8B on one NVIDIA L4 (AWS, 10 October 2026)

The `local-llm` compose profile (vLLM from the official Apertus image, the official bf16
weights) ran for the first time on a GPU host: an AWS g6.xlarge in Zurich with one
NVIDIA L4 24 GB. The repository was a clean clone of `main` at 6936d05. `make run`
started the app unchanged next to the vLLM service, and two jobs on the example letter
went through the app's own API. This folder holds what the hardware statements in the
README and in docs/architecture.md rest on.

## Setup

| | |
|---|---|
| Machine | AWS g6.xlarge, eu-central-2 (Zurich), zone eu-central-2b, on demand: 4 vCPUs, 16 GiB RAM, 100 GB gp3 disk (125 MB/s) |
| GPU | 1 x NVIDIA L4: 23,034 MiB, of which PyTorch sees 22.04 GiB; power limit 72 W |
| System | Ubuntu 24.04.4, kernel 7.0.0-1014-aws, NVIDIA driver 595.91.07 (server, open kernel modules, CUDA 13.2), Docker 29.9.0, Compose 5.6.0, NVIDIA Container Toolkit 1.20.1 |
| vLLM | `ghcr.io/swiss-ai/vllm_apertus_1.5_release:latest-amd64`, digest `sha256:d85533f251c8272218ae2e519510836376e5a335b44f2204f193018e37753bc6`, vLLM 0.23.1rc1.dev1029+ga601a9d99 |
| Model | `swiss-ai/Apertus-v1.5-8B`, revision `a411d838600baf0e3635a3daf66fb7c55fc97bb6`: bf16 with the image encoder, 17.2 GiB on disk (18.4 GB) |
| Server flags | docker-compose.yml of 6936d05 plus `--kv-cache-dtype=fp8` and `--max-num-seqs=16` (`docker-compose.override.yml` here); both are defaults in docker-compose.yml since this run |
| App | Profile B of `.env.example`: `LLM_BASE_URL=http://vllm:8000/v1`, the 8B writes and judges, `LLM_THINKING_MODE=chat-template`, `LLM_CACHE=0` |

The machine started as plain Ubuntu. The driver came from `ubuntu-drivers install
--gpgpu nvidia:595-server-open` with `nvidia-utils-595-server`, Docker from Docker's apt
repository, the container toolkit from NVIDIA's (`nvidia-ctk runtime configure
--runtime=docker`).

## Starting the profile

As it stood in the repository, the profile did not start on a 24 GB card:

| Start | Flags | Result |
|---|---|---|
| 1 | As in docker-compose.yml (`--max-model-len=32768`, `--gpu-memory-utilization=0.9`) | Refused: one 32k request needs 4.0 GiB of KV cache, 2.13 GiB were left after the weights; at most 17,440 tokens would fit |
| 2 | Plus `--kv-cache-dtype=fp8` | The KV cache fits (34,896 tokens), then the warm-up runs out of memory: the CUDA graphs for 256 parallel sequences took 0.84 GiB, and the sampler's warm-up needed 262 MiB more than was free |
| 3 | Plus `--max-num-seqs=16` | Starts. KV cache 2.37 GiB, 38,752 tokens: 1.18 requests of 32k tokens at once |

A shorter context is no way out: the stages ask for up to 16,000 output tokens on top of
the prompt (Write with thinking; Understand, Judge and Repair ask for 12,000,
`pipeline/stages.py`), and vLLM rejects a request whose prompt and `max_tokens` exceed
the context.

GPU memory at start 3, by vLLM's own accounting (`vllm.log`):

| | GiB |
|---|---|
| Weights | 17.23 |
| KV cache (FP8) | 2.37 |
| CUDA graphs | 0.16 |
| Peak activation and non-torch memory | 0.24 |

During the jobs nvidia-smi showed at most 21,350 of 23,034 MiB in use. With the weights
already on disk, the start took about 7 minutes from the container's start to
"Application startup complete": about 80 s to set up the server and the engine, 146 s to
load the weights (the disk reads 125 MB/s) and 187 s for profiling, compilation and
warm-up. The first start downloads the weights first (about 140 s here).

## The two jobs

Both ran the team's example letter `data/examples/sources/praemienverbilligung-brief.txt`
(232 words, German) as P2 at level A2, posted to `/api/jobs` of the app that `make run`
had started. One job at a time, nothing else on the GPU.

| | Job 1: thinking in Understand and Judge | Job 2: thinking only in Understand |
|---|---|---|
| Setting | Profile B as in `.env.example` | Plus `LLM_THINKING_STAGES=understand` |
| Job id | `36c565d96a6a` | `a516c6801eb6` |
| From submission to review | 3,794 s (63.2 min) | 1,323 s (22.1 min) |
| Model calls | 15, together 3,790 s | 12, together 1,320 s |
| Tokens in / out | 48,834 / 61,133 | 45,868 / 21,295 |
| Understand | 2 calls, 808 s: the reasoning hit the 12,000-token cap (744 s), the answer came from the fallback without thinking | The same: 2 calls, 808 s, cap hit |
| Write | 1 call, 60 s | 1 call, 65 s |
| Judge | 7 calls, 2,869 s: 6 with thinking (5,135 to 12,000 output tokens; one hit the cap) and that one's fallback | 5 calls, 323 s (51 to 87 s each) |
| Repair and Recover | 4 and 1 calls, 54 s | 4 calls, 123 s |
| Result | Version 5 of 6 kept, 2 blocking findings; stopped because a facts round brought no progress | Version 4 of 5 kept, 4 blocking findings; stopped after 3 repair rounds |
| Review | By the owner: 24 decisions (19 approved, 4 edited, 1 rejected), complete | Not reviewed |
| GPU | 99 % load, 71.7 W on average: about 76 Wh | 98 % load, 71.5 W on average: about 26 Wh |

The blocking findings of the two jobs are not comparable: the judge reads the drafts with
thinking in one job and without in the other.

## What the run shows

- With the two flags the profile runs on one 24 GB GPU, the smallest common data-centre
  card. By the same arithmetic a card with 32 GB or more needs neither flag (not tested).
- One request generates 16.2 tokens per second (median of 518 vLLM samples, at most
  16.6). That is close to what the L4's memory bandwidth allows: each token reads the
  language model's weights (about 16 GB; the image encoder is not used for text) at
  300 GB/s, at most about 18 tokens per second. Larger cards are faster in proportion to
  their bandwidth (not measured).
- The GPU was the limit throughout: 98 to 99 % load at its 72 W power limit, and model
  calls took more than 99 % of each job.
- The 8B's reasoning ran away: Understand hit the 12,000-token cap in both jobs and the
  judge once in job 1, and on this card each capped call costs 12.4 minutes. Without
  thinking in the judge a letter took 22 minutes; the capped Understand call took 744 s
  of them, all other calls together 576 s (9.6 minutes).
- What the FP8 KV cache does to quality is not measured: a comparison with a bf16 KV
  cache needs a larger card.

## Files

| File | Content |
|---|---|
| `job1-default/job-audit.json` | Job 1's audit bundle (the app's JSON export): source, fact sheet, all drafts, judge reports, repairs, rule findings, summary and the owner's review |
| `job1-default/job.md` | Job 1's final text with the review applied (the Markdown export) |
| `job1-default/job-usage.json` | Job 1's settings and every model call with its tokens and time |
| `job2-thinking-understand/` | The same three files for job 2, without a review |
| `vllm.log` | vLLM's start-up lines (start 3) and its speed lines during both jobs, every 10 s |
| `gpu.csv` | nvidia-smi every 10 s from job 1's start to job 2's end: time, load, memory in use, power |
| `docker-compose.override.yml` | The vLLM command of the run |

## Running it again

On a host with one NVIDIA GPU of 24 GB or more and Docker with the NVIDIA Container
Toolkit: copy `.env.example` to `.env`, switch to profile B and set `HF_TOKEN` (the
weights are gated: accept their terms on Hugging Face once). Then:

```
docker compose --profile local-llm up -d vllm   # ready at "Application startup complete"
make run OPEN_BROWSER=0
# in a second terminal
curl -F file=@data/examples/sources/praemienverbilligung-brief.txt -F level=A2 \
  -F condition=P2 http://localhost:8000/api/jobs
```

`GET /api/jobs/<id>` shows the stage and every model call so far, and
`GET /api/jobs/<id>/export?format=json` returns the audit bundle.
