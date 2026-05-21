# AI Engineer — screening question bank (demo)

Each `json` block is **one chunk** = one row after ingest.  
`role` must be exactly: `AI Engineer`.

```json
{
  "role": "AI Engineer",
  "topic": "Transformers",
  "question": "At a high level, how does attention help a transformer model relate tokens to each other?",
  "why_this_is_asked": "Checks foundational understanding beyond buzzwords — what attention computes and why depth helps.",
  "good_signals": [
    "Explains weighted combination of values based on query-key compatibility",
    "Mentions self-attention vs cross-attention when relevant",
    "Connects to long-range dependencies vs recurrence",
    "Notes complexity tradeoffs (sequence length) at a conceptual level"
  ],
  "bad_signals": [
    "Says attention 'finds important words' with no mechanism",
    "Confuses attention with embedding lookup",
    "Cannot relate attention to the rest of the block (FFN, residuals)"
  ],
  "follow_ups": [
    "Why multi-head attention instead of one big head?",
    "What problem did positional encoding solve?",
    "When would encoder-only vs decoder-only architectures be preferred?"
  ]
}
```

```json
{
  "role": "AI Engineer",
  "topic": "Fine-tuning vs prompting",
  "question": "When would you choose supervised fine-tuning over prompt engineering for a business use case?",
  "why_this_is_asked": "Surfaces cost, latency, data availability, risk, and maintainability tradeoffs.",
  "good_signals": [
    "Discusses data volume/quality and evaluation harness",
    "Mentions latency/cost of long prompts vs smaller model + SFT",
    "Talks safety, drift, and rollback for model updates",
    "Gives an example where SFT wins (style/domain) vs prompting wins (rapid iteration)"
  ],
  "bad_signals": [
    "Always prefers 'fine-tuning' with no criteria",
    "Ignores evaluation and offline vs online metrics",
    "No mention of catastrophic forgetting or maintenance"
  ],
  "follow_ups": [
    "How would you detect regressions after an update?",
    "What is your approach to labeling and QA for training data?",
    "How do you handle PII in fine-tuning datasets?"
  ]
}
```

```json
{
  "role": "AI Engineer",
  "topic": "RAG",
  "question": "Describe a minimal RAG pipeline for internal docs search. What are the main failure modes?",
  "why_this_is_asked": "Validates practical retrieval design: chunking, embeddings, reranking, grounding, and evaluation.",
  "good_signals": [
    "Mentions chunking strategy and metadata filters",
    "Describes embedding + vector search + optional reranker",
    "Lists failure modes: hallucination, stale docs, wrong chunk, injection",
    "Mentions citations / grounding responses to retrieved text"
  ],
  "bad_signals": [
    "Equates RAG with 'put everything in the prompt'",
    "No evaluation or offline replay story",
    "Omits authZ for document access"
  ],
  "follow_ups": [
    "How would you measure retrieval quality before changing the LLM?",
    "When would you add hybrid search (keyword + vector)?",
    "How do you mitigate prompt injection from retrieved pages?"
  ]
}
```

```json
{
  "role": "AI Engineer",
  "topic": "Evaluation",
  "question": "How would you evaluate an LLM feature before and after launch?",
  "why_this_is_asked": "Separates offline benchmarks from online guardrails and human-in-the-loop quality.",
  "good_signals": [
    "Offline: golden sets, pairwise human eval, task-specific metrics",
    "Online: shadow traffic, canary, error budgets, user outcome metrics",
    "Talks guardrails for safety/toxicity and regression suites",
    "Mentions data leakage concerns between train/eval"
  ],
  "bad_signals": [
    "Only 'vibes' or demo prompts",
    "No distinction between offline and production signals",
    "Cannot define a single success metric for the feature"
  ],
  "follow_ups": [
    "What would you put in a launch checklist for an LLM endpoint?",
    "How do you sample production conversations for review ethically?",
    "What is an acceptable latency budget for your use case?"
  ]
}
```

```json
{
  "role": "AI Engineer",
  "topic": "Serving & performance",
  "question": "What techniques reduce latency and cost for serving an LLM in production?",
  "why_this_is_asked": "Touches caching, batching, quantization, routing, and capacity — typical AI engineer production work.",
  "good_signals": [
    "KV cache / streaming for UX",
    "Caching repeated prefixes or retrieval results",
    "Smaller models for routing or distilled heads",
    "Batching, dynamic batching, autoscaling, and cold start awareness",
    "Quantization / spec decode only if they can explain tradeoffs"
  ],
  "bad_signals": [
    "Only 'use a bigger GPU'",
    "No mention of caching or prompt reuse",
    "Confuses throughput with tail latency"
  ],
  "follow_ups": [
    "How would you debug a p95 latency regression?",
    "When is speculative decoding worth the complexity?",
    "How do you protect against traffic spikes?"
  ]
}
```
