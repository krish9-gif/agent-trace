# Project Dynamo & Harbor Benchmark Engineering: Master Interview Book

> **Target Standard:** Frontier AI Benchmark Engineering, LLM Red-Teaming, and Autonomous Agent Systems.  
> **Author:** Krish Joshi | AI Evaluation & Systems Engineer (Handshake Senior Quality Reviewer R1 & Benchmark Engineer).  
> **Repository:** [github.com/krish9-gif/ai-systems-eval-portfolio](https://github.com/krish9-gif/ai-systems-eval-portfolio)

---

## 1. Executive Summary: What is Benchmark Systems Engineering?

In frontier AI labs (OpenAI, Anthropic, Scale AI, Handshake), standard static multiple-choice evaluations (MMLU, GSM8K) have saturated. Frontier models (Claude 3.7, GPT-4o, Llama 3.3) are now evaluated on **complex, multi-turn software engineering tasks** inside containerized Linux environments (Terminal-Bench, SWE-bench, Harbor format).

A benchmark task is not just a coding problem—it is a **secure, air-gapped, deterministic distributed system** that must:
1. Provide an isolated environment where an autonomous agent operates via bash and terminal tools.
2. Mathematically prove whether the agent solved the issue or hallucinated the solution.
3. Prevent agent cheating (inspecting hidden test files, hardcoding answers, or mutating test runners).
4. Run 100% offline and deterministically across multiple evaluations.

---

## 2. The Project Dynamo Evaluation Pipeline Architecture

In Project Dynamo, every task repository must survive an automated 13-stage GitHub Actions gauntlet before receiving the green **`accepted` (`#0e8a16`)** label:

```text
[PR Push / Synchronize]
         │
         ▼
 1. review / changes (Branch & submission path format)
         │
         ▼
 2. review / cosine_similarity (Semantic uniqueness check)
         │
         ▼
 3. review / review (Claude Rubric: 31 Strict Criteria)
         │
         ▼
 4. review / validation (Docker Build, Oracle 1.0, Nop 0.0)
         │
         ▼
 5. review / ratelimit (Max 6 pass@2 runs / 24h)
         │
         ▼
 6. review / pass2 (Dual Frontier Agent Trials: >=1 Valid Fail)
         │
 ┌───────┴──────────────────────┐
 │                              │
 ▼                              ▼
 7. review / ava_review         8. review / deep_review
 (Blind Verifier Audit)         (Gap Rubric & Trajectory Integrity)
 │                              │
 └───────┬──────────────────────┘
         │
         ▼
 9. review / tier1 (QC Rework Attempt Check >=60%)
         │
         ▼
10. review / qc_gate (44 Deterministic Quality Checks)
         │
         ▼
11. review / trials (Pass@5 Benchmark Verification)
         │
         ▼
12. review / gate (Final Labeler: 'accepted' #0e8a16 vs 'needs-revision')
```

### Core Pipeline Invariants:
* **The Nop Baseline Invariant (Reward: 0.0):** Before any solution runs, the test suite MUST be executed against the initial, unsolved environment state. It **must fail**. If tests pass on an unsolved baseline, the task is immediately rejected as trivial/self-passing.
* **The Oracle Solver Invariant (Reward: 1.0):** The reference solution (`solve.py`) must dynamically compute the solution from raw inputs and pass all tests with a 1.0 score. **Zero hardcoded outputs allowed.**
* **The Accepted Label Standard:** A task is only considered passed when GitHub PR carries the official green `accepted` label (`#0e8a16`).

---

## 3. The 25 Deterministic Static Checks: Why 80% of Tasks Fail

The first phase of the pipeline runs 25 deterministic static checks before launching compute. The most common critical failure modes include:

| Check Category | Exact Rule | Why Models / Engineers Fail It |
| :--- | :--- | :--- |
| **Answer Leakage** | `instruction.md` must never contain actual answer strings or golden hashes. | Models lazily copy-paste golden answers into markdown examples instead of using `<str>` or `0` placeholders. |
| **Algorithm Naming** | Never name the target algorithm in `instruction.md`. | Saying *"use Dijkstra or priority queues"* instead of *"find the shortest valid path"* violates the instruction concision and outcome verification rubric. |
| **Dockerfile Hygiene** | Every `COPY` target must exist in build context; pinned base image; non-root user. | Models reference non-existent files or run as root, breaking security sandboxing. |
| **Heredoc Strings** | Python code > 20 lines must be in its own file. `exec("""...""")` is banned. | Models inline bash or python scripts as raw multi-line strings, failing code quality audits. |
| **Hardcoded Answers** | `solve.py` must dynamically parse inputs and compute state. | Models write `print('{"result": 42}')` instead of calculating it from input datasets. |

---

## 4. Two-Tier Test Harnesses & Anti-Cheat Engineering

Why naive PyTest suites fail in autonomous agent evaluation:
* **Problem 1 (Compute Waste):** If an agent produces completely invalid syntax or corrupts a file, running a 5-minute integration test wastes server budget.
* **Problem 2 (Agent Cheating & Tampering):** Sophisticated agents can use `sed` to edit `test_outputs.py` to `assert True`, or write fake CTRF reports to disk.

### The Two-Tier Isolation Solution:
```
┌────────────────────────────────────────────────────────────────────────┐
│                   AIR-GAPPED EPHEMERAL SANDBOX                         │
│                                                                        │
│   Candidate Agent Patch ──► Mutates File System                        │
│                                   │                                    │
│       STAGE 1: SMOKE INVARIANT    ▼                                    │
│   ┌────────────────────────────────────────────────────────────┐       │
│   │ • Fast file existence & JSON syntax check (< 500ms)        │       │
│   │ • assert_safe_path() (blocks directory traversal '../')    │       │
│   └───────────────────────────────┬────────────────────────────┘       │
│                                   │ (PASS)                             │
│       STAGE 2: DEEP VERIFICATION  ▼                                    │
│   ┌────────────────────────────────────────────────────────────┐       │
│   │ • Full Causality & State Mutation Matrix                   │       │
│   │ • SHA-256 State Manifest Hashing (Zero Tampering)          │       │
│   │ • CTRF Schema Test Report Export (ctrf-report.json)        │       │
│   └────────────────────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Technical Interview Q&A (STAR Method)

### Q1: "What was your exact role on Project Dynamo and what does the benchmark pipeline do?"
> **Candidate Answer:**  
> *"On Project Dynamo, I authored and audited containerized software evaluation environments following the Harbor benchmark standard. The pipeline evaluates frontier models on complex system tasks (distributed state reconciliation, GPU kernel debugging, Linux OS recovery).  
> What makes the pipeline rigorous is its multi-stage gauntlet: every task must pass 25 deterministic static checks, an automated Nop baseline check (proving tests fail on unsolved initial states), an Oracle solve (proving dynamic solvability with 1.0 reward), dual-agent pass@2 trials, and a 44-point QC gate before receiving the final `accepted` label."*

---

### Q2: "How do you prevent an autonomous agent from 'cheating' on an evaluation?"
> **Candidate Answer:**  
> *"We employ a four-layer anti-cheat architecture:  
> 1. **Read-Only Test Isolation:** The test suite and reference answers are mounted into an out-of-band volume that the agent's non-root user cannot modify or overwrite.  
> 2. **Nop Baseline Verification:** Before running the agent, we run the test suite against the untouched environment. It must fail with exit code 1. This guarantees the tests are not self-passing.  
> 3. **Cryptographic SHA-256 Assertions:** Instead of checking superficial string matches, we compute a SHA-256 digest of the canonical state manifest.  
> 4. **Trajectory Auditing (`AgentTrace`):** We inspect the agent's tool execution graph to verify that claimed actions (e.g. file edits or database commits) correspond to physical tool invocations."*

---

### Q3: "What is an Action Hallucination in multi-turn agent evaluation?"
> **Candidate Answer:**  
> *"In multi-turn tool calling, language models are trained via RLHF to be helpful and persuasive. When a tool fails (e.g. an HTTP 403 Forbidden or bash exit code 1), the agent frequently synthesizes text claiming: 'I have updated the file and resolved the bug'.  
> We classify this into:  
> • **Ghost Actions:** The agent never executed the tool at all.  
> • **Masked Failures:** The tool executed and returned an error, but the model covered it up in its final message.  
> In my open-source project `AgentTrace`, I built a deterministic regex and execution-graph reconciler that flags these anomalies and computes a calibrated SQS score from 0.0 to 5.0."*

---

### Q4: "Why use a two-tier evaluation harness instead of running all tests at once?"
> **Candidate Answer:**  
> *"Two-tier harnesses separate fast invariant validation from deep integration tests:  
> • **Tier 1 (Smoke Probe, < 1s):** Checks file existence, basic syntax invariants, and runs `assert_safe_path()` to detect jailbreaks. If Tier 1 fails, execution aborts immediately, saving 90% of compute.  
> • **Tier 2 (Deep Invariants):** Runs boundary conditions, distributed state reconciliation, and cryptographic checksums. This pattern is standard across SWE-bench and Harbor pipelines."*

---

## 6. Live Whiteboard System Design Walkthrough

When an interviewer asks you to diagram a production benchmark pipeline:

```
[Agent Shell Output] ──────────► [Non-Root Sandbox /workspace]
                                            │
                                            ▼
                           [Stage 1: Smoke Probe < 500ms]
                            - assert_safe_path()
                            - JSON Syntax Validation
                                            │ (Pass)
                                            ▼
                           [Stage 2: Deep Verification]
                            - Causal State Check
                            - SHA-256 Golden Hash Assert
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
             [CTRF Schema Report]                       [AgentTrace Auditor]
              - ctrf-report.json                         - Action Hallucination?
              - pass@1 / pass@2 metric                   - SQS Score (0.0 - 5.0)
```
