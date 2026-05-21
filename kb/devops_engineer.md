# DevOps Engineer — screening question bank (demo)

Each `json` block is **one chunk** = one row after ingest.  
`role` must be exactly: `DevOps Engineer`.

```json
{
  "role": "DevOps Engineer",
  "topic": "Kubernetes",
  "question": "Can you explain how Kubernetes handles pod scaling and self-healing?",
  "why_this_is_asked": "Evaluates core orchestration concepts: controllers, ReplicaSets, probes, and recovery when nodes or pods fail.",
  "good_signals": [
    "Mentions ReplicaSets / Deployments and desired state reconciliation",
    "Explains Horizontal Pod Autoscaler with a metric example",
    "Contrasts readiness vs liveness probes with a concrete use case",
    "Describes what happens when a node disappears (rescheduling)"
  ],
  "bad_signals": [
    "Only defines Kubernetes as 'Docker manager' with no controllers",
    "Cannot describe what happens on node loss",
    "Confuses probes with load balancer health checks only"
  ],
  "follow_ups": [
    "What happens to pods on a node that becomes NotReady?",
    "How would you debug CrashLoopBackOff for a Deployment?",
    "When would you choose StatefulSet over Deployment?"
  ]
}
```

```json
{
  "role": "DevOps Engineer",
  "topic": "CI/CD",
  "question": "Walk me through how you would design a CI/CD pipeline for a microservice from commit to production.",
  "why_this_is_asked": "Tests practical delivery engineering: stages, gates, environments, secrets, rollbacks, and ownership.",
  "good_signals": [
    "Separates build, test, security scan, staging deploy, prod promote",
    "Mentions artifact immutability and versioned releases",
    "Talks about rollback strategy and feature flags or canary",
    "Calls out secrets management and least privilege"
  ],
  "bad_signals": [
    "Only lists tools with no stages or quality gates",
    "No mention of testing or promotion criteria",
    "Manual SSH deploys described as 'the pipeline'"
  ],
  "follow_ups": [
    "Where would you run integration tests vs unit tests?",
    "How do you prevent a bad migration from taking down prod?",
    "How do you handle database schema changes safely?"
  ]
}
```

```json
{
  "role": "DevOps Engineer",
  "topic": "Linux & production troubleshooting",
  "question": "A service is intermittently slow on a Linux VM. How do you narrow down whether it is CPU, memory, disk, or network?",
  "why_this_is_asked": "Screens for structured troubleshooting and familiarity with common OS signals under pressure.",
  "good_signals": [
    "Starts with symptoms → metrics → narrowing hypotheses",
    "Mentions CPU load vs utilization, iowait, swap thrash",
    "Uses network latency/packet loss vs app timeouts deliberately",
    "Suggests tracing request path (LB → app → DB) after OS checks"
  ],
  "bad_signals": [
    "Randomly restarts services without evidence",
    "Only suggests 'scale up' with no diagnosis",
    "Cannot name a single command or metric"
  ],
  "follow_ups": [
    "What does high iowait usually indicate?",
    "How would you confirm a memory leak vs traffic spike?",
    "What logs would you check first for a 502 from an upstream?"
  ]
}
```

```json
{
  "role": "DevOps Engineer",
  "topic": "Observability",
  "question": "Explain the difference between metrics, logs, and traces — and give an example of when each is the fastest path to root cause.",
  "why_this_is_asked": "Validates SRE-style thinking for incident response and capacity planning.",
  "good_signals": [
    "Clear definitions with an on-call scenario for each signal",
    "Mentions exemplars or correlation IDs linking logs to traces",
    "Talks SLIs/SLOs and alerting noise vs symptom-based alerts",
    "Gives a concrete example (e.g., latency regression) and tool-agnostic approach"
  ],
  "bad_signals": [
    "Uses 'logs' to mean everything",
    "Cannot give a scenario where traces beat logs",
    "No mention of cardinality or alert fatigue"
  ],
  "follow_ups": [
    "What makes a good SLO for an API dependency?",
    "How do you avoid high-cardinality metrics blowing up cost?",
    "When would you add a synthetic check?"
  ]
}
```

```json
{
  "role": "DevOps Engineer",
  "topic": "Infrastructure as Code",
  "question": "How do you structure Terraform (or similar IaC) so changes are safe, reviewable, and repeatable across environments?",
  "why_this_is_asked": "Checks module boundaries, state management, drift, and promotion patterns common in real teams.",
  "good_signals": [
    "Modules by domain; environment separation via workspaces or dirs with clear promotion",
    "Remote state locking; plan in CI; apply with approvals",
    "Mentions drift detection and import workflows when reality diverges",
    "Secrets not committed; IAM least privilege patterns"
  ],
  "bad_signals": [
    "One giant repo with copy-paste env files",
    "No plan/apply separation or peer review",
    "Stores secrets in plain tfvars in git"
  ],
  "follow_ups": [
    "How do you handle breaking changes to modules consumers rely on?",
    "What is your policy on manual console changes?",
    "How would you roll back a bad Terraform apply?"
  ]
}
```
