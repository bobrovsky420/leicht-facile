# Public AI routing checks of 6, 13 and 28 October 2026

A record, not a description of the current version: three checks of which compute
partner the Public AI gateway sent each Apertus model name to, read from the gateway's
response headers while the evaluation ran. They settled the `publicai` provider's
profile in [architecture.md §6](../architecture.md#6-the-llm-client): every stage on
the 70B, no thinking, the gateway's response cache bypassed per request, the results
labelled Public AI and never Swiss-hosted. The gateway changes its routing without
notice; §6 says what holds now, and a new check belongs in a new record. Moved here
from the design document's §6 in November 2026.

## 6 October 2026

The 8B went to Juelich's Blablador (vLLM) and thought through the chat template, but
only in about two of three identical calls, so comparisons of thinking against no
thinking were left to the CSCS endpoint. The 70B went to Infomaniak
(`Apertus-v1.5-70B`) and ignored the thinking switch. The `-thinking` names were not
usable: `apertus-v1.5-8b-thinking` served the older Apertus 1 8B through Featherless.
The gateway's response cache ignored the thinking switch, which is why the profile turns
the cache off per request (`extra_body = { cache = { no-cache = true } }`).

## 13 October 2026

One small call per name: the 8B still went to Juelich (Germany, 4 of 4 calls); the 70B
was split between Infomaniak (Switzerland) and Featherless (a US company), 8 of 11
calls to Featherless; both `-thinking` names answered with an error. So the gateway was
not Swiss-hosted throughout, whatever its own pages said.

## 28 October 2026

The gateway still listed all four names, but chat completions with both 8B names and
both `-thinking` names answered 400 ("invalid model name" for the key); the 70B
answered from a new partner (`maas.phoeniqs.com`) and the Apertus 1 8B from
Featherless. From this check on, the preset runs every stage on the 70B, without
thinking.
