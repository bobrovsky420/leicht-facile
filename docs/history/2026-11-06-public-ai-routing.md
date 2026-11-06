# Public AI routing check of 6 November 2026

A record, not a description of the current version: which compute partner the Public AI
gateway sent each Apertus 1.5 name to, read from the gateway's response headers
(`x-litellm-model-api-base`), with small calls and the thinking switch on and off. It
follows the checks of [6, 13 and 28 October 2026](2026-10-28-public-ai-routing.md) and
moved the `publicai-apertus` preset back to the 8B writer with the 70B judge
([architecture.md §6](../architecture.md#6-the-llm-client)).

## 6 November 2026

The gateway listed four Apertus names: `apertus-v1.5-8b`, `apertus-v1.5-70b` and the two
Apertus 1 names (`apertus-8b-instruct`, `apertus-70b-instruct`); the `-thinking` names
were gone from the list.

- `swiss-ai/apertus-v1.5-8b` answered again, after being refused for the key since
  28 October: 6 of 6 calls went to Juelich's Blablador (vLLM, `alias-apertus`).
  `chat_template_kwargs.enable_thinking: true` brought no reasoning in the call that was
  read for it (no reasoning field, a 4-token answer).
- `swiss-ai/apertus-v1.5-70b` answered from `maas.phoeniqs.com`, with no reasoning
  whether the switch was on or off (6 output tokens each).
- `swiss-ai/apertus-v1.5-8b-thinking` and `swiss-ai/apertus-v1.5-70b-thinking` answered
  403 (`key_model_access_denied`), with the switch on and off.
- A second check made each prompt unique (a number in front), so that no cached answer
  could come back: 16 calls, both sizes, with `enable_thinking` true, false or not sent,
  and once with `skip_special_tokens: false` to show any hidden reasoning markers. Every
  answer was 5 or 6 tokens, with no reasoning field and no reasoning in the text, and all
  16 were wrong (9:05 or 9.05 instead of 10:05; once 00:65). Neither size thinks on the
  gateway, whatever the request says.

- Juelich's Blablador page names `alias-apertus` as Apertus 1 (`Apertus-8B-Instruct-2509`),
  so a small image (four digits and a red square) went to each name: the 1.5 8B and the
  1.5 70B read it, while `apertus-8b-instruct` (Apertus 1) answered 400 "This model
  accepts text only". The 8B behind the gateway is Apertus 1.5; the page is out of date.
  Both backends report the same vLLM build (`vllm-0.23.1rc1.dev1029+ga601a9d99`).

So both sizes serve again, neither thinks, and the preset lets the 8B write and the 70B
check without thinking at any stage. The setup has no Public AI numbers yet: the tables
of docs/evaluation-publicai.md were measured with the 70B at every stage.
