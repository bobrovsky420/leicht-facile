# Recorded model answers

Real answers of Apertus v1.5 8B on the team's sample letter
(`track_2b/data/examples/sources/praemienverbilligung-brief.txt`), recorded on 6 October 2026
before the CSCS key was available. They come from the community 4-bit text-only
conversion `Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF`, served by llama.cpp on a laptop
GPU, not from the official model on the CSCS endpoint. They test the parsing and
checking code against real model behaviour; they are not evaluation results.

| File | Content |
|------|---------|
| `letter_source.json` | The letter after ingest (`SourceDocument`) |
| `letter_understand.txt` | Answer of the understand prompt (thinking on; the reasoning is stripped) |
| `letter_write.txt` | Answer of the write prompt (thinking off) |
| `letter_meta.json` | Settings, tokens, latency and the prompt versions used |

Re-record them with the endpoint in `.env` when the prompts change.
