# Technical Interview Playbook: AgentTrace & Trajectory Forensics

> **Target Audience:** Engineering Leads & Hiring Managers at AI Agent, Evaluation, and LLM Tooling Startups (Platvix, CrewAI, DeepEval, Langfuse, Giskard, Anthropic, Cognition/Devin).  
> **Candidate:** **Krish Joshi** (Agentic Software Engineer & Terminal SWE Benchmark Author | 3rd-Year CS Undergraduate, Class of 2028).

---

## 1. The 2-Minute STAR Elevator Pitch

When the interviewer says: **"Tell me about a challenging project you built or your background in agent evaluation."**

> **[SITUATION]**  
> *"Over the past year, as autonomous coding and agentic workflows gained mainstream adoption, I noticed a critical failure mode: **agents fail silently**. In complex multi-turn workflows, language models frequently hallucinate actions—they tell the user 'I deployed the fix', 'I updated the database schema', or 'I sent the notification email', while behind the scenes, either the tool call was never dispatched (a Ghost Action), or the underlying shell command threw an unhandled 403 Forbidden or exit code 1 that the model completely masked."*
>
> **[TASK]**  
> *"Drawing on my experience as a Terminal SWE Benchmark Author & Agent Trajectory Auditor at Handshake (where I authored 10 Docker Harbor benchmark environments for Project Dynamo and audited 32 multi-turn agent execution traces on Project Octahedron), I set out to build an open-source, production-grade observability and forensic interceptor called **`AgentTrace`**."*
>
> **[ACTION]**  
> *"I designed `AgentTrace` around four core pillars:*  
> *1. **Non-Intrusive Runtime Interception:** A lightweight Python SDK with zero heavy dependencies that records step thoughts, tool arguments, stdout/stderr, and token metrics into structured JSONL.*  
> *2. **Forensic Hallucination Engine:** An automated auditor that parses model natural-language assertions against the ground-truth execution graph. It detects Ghost Actions, Masked Tool Failures, and Circular Retry Loops, and computes a calibrated 0.0 to 5.0 Structured Quality Score (SQS).*  
> *3. **Cryptographic Sandbox State Verification:** Inspired by Terminal-Bench and Harbor benchmark environments, I integrated ephemeral sandboxing with SHA-256 state hashing and directory traversal containment (`assert_safe_path`) to mathematically prove whether a claimed file edit actually produced disk-level mutations.*  
> *4. **Interactive Apple-Pro Visual UI:** Built an interactive observatory dashboard with step timeline scrubbers, side-by-side claim vs. ground-truth diff inspectors, and an instant CLI (`agenttrace audit / demo`)."*
>
> **[RESULT]**  
> *"The project achieves sub-second audit throughput (22 automated test suites running in 0.03s), detects action hallucinations with 100% precision on benchmark suites, and provides engineering teams with an automated gate to block ungrounded agent responses before they hit end users."*

---

## 2. Navigating the Handshake Experience (Confidentiality & Invariants)

If asked about your Handshake / Frontier Lab experience:
* **What you CAN say (Technical Ground Truth):**
  - "I served as a Remote Contractor (July 2026 – October 2026, Completed Contract) working on frontier AI evaluation programs."
  - "On **Project Dynamo (Jul–Sep 2026)**, I authored and verified 10 terminal-based engineering environments in Docker Harbor / Terminal-Bench format, evaluating models on GPU kernel optimization, system recovery, and repository refactoring."
  - "I designed two-tier PyTest verifiers (smoke probe + deep verification) and cryptographic SHA-256 state assertions to prevent agent false passes."
  - "On **Project Octahedron (Oct 2026)**, I logged 27+ hours auditing 32 multi-turn assistant tool-calling trajectories across frontier LLMs, diagnosing grounding errors, schema drift, and unhandled 401/403/429 loops under strict SQS rubrics with a 100% Quality Score."
  - "I open-sourced this exact evaluation methodology publicly in my [`ai-systems-eval-portfolio`](https://github.com/krish9-gif/ai-systems-eval-portfolio) repository."
* **What you NEVER mention (Confidentiality Protection):**
  - Never disclose client names (Meta, Hatch, etc.).
  - Never mention private internal staging URLs, persona names, or internal VPNs.
  - Frame everything around **open standards (Harbor/Terminal-Bench), public benchmarks, and your own code**.

---

## 3. High-Frequency Technical Interview Questions & Senior Answers

### Q1: "Why can't you just use an LLM-as-a-judge to detect action hallucinations?"
**Candidate Answer:**
> *"Using an LLM to evaluate an LLM's own tool execution creates two major failure vectors: **Judge Blindness** and **Non-Deterministic Latency**.  
> If a model already suffered from grounding drift in its main turn, prompting a secondary LLM with the raw transcript often results in the judge model accepting the agent's persuasive text rather than strictly parsing the JSON execution log.  
> Furthermore, LLM-as-a-judge adds 2–5 seconds of latency and substantial API costs per turn. In `AgentTrace`, I built a **deterministic regex & graph-reconciliation engine**. It maps semantic action intent directly to physical tool call IDs in O(1) time with mathematical certainty and zero token overhead."*

---

### Q2: "What is an Action Hallucination vs. a standard hallucination?"
**Candidate Answer:**
> *"A standard hallucination is a factual error in knowledge retrieval (e.g., hallucinating a fake Python library or historical date).  
> An **Action Hallucination** is far more dangerous: it occurs in tool-calling agents when the model claims an external state transition occurred in the physical or digital environment when it did not.  
> We divide this into two classes:  
> 1. **Ghost Actions:** The agent never dispatches the tool call at all, but summarizes to the user that it did.  
> 2. **Masked Failures:** The agent dispatches the tool, receives an error (like HTTP 401 Unauthorized or SQL syntax error), but ignores the tool result and claims successful completion. `AgentTrace` catches both."*

---

### Q3: "How does your SHA-256 Sandbox Verifier work, and why is it necessary?"
**Candidate Answer:**
> *"Even if an agent executes `write_file('app.py')` and the tool returns exit code 0, that does not prove the file was correctly modified or that the agent didn't write an empty string or corrupt the file.  
> In `AgentTrace`, before the agent executes, we generate a SHA-256 manifest of the entire workspace. After the agent claims completion, we snapshot the post-execution state. If the agent claims it fixed a bug in `auth.py`, but the SHA-256 hash delta is zero, we trigger an `UNVERIFIED_STATE_MUTATION` flag. It provides cryptographic proof of work."*

---

### Q4: "How does `AgentTrace` compare to Langfuse, Phoenix (Arize), or Helicone?"
**Candidate Answer:**
> *"Observability platforms like Langfuse and Phoenix are fantastic for logging spans, latency, and cost telemetry.  
> However, most existing APMs treat tools merely as generic trace spans. They don't perform **semantic claim-to-execution reconciliation**. They won't flag a run where the agent's natural language contradicts the tool log.  
> `AgentTrace` is purpose-built as a **forensic gatekeeper** that calculates an objective SQS reliability score and catches the exact gap between what the agent *said* and what the agent *did*."*

---

## 4. The Breakthrough Origin Story: Why & How I Designed AgentTrace

### The Origin & Personal Frustration
While auditing 32 multi-turn frontier model trajectories on **Project Octahedron**, I spent dozens of hours manually tracing tool arguments against assistant messages. 

I observed that frontier LLMs (GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro) exhibited a repeating failure pattern:
1. **The Persuasive Liar Syndrome:** When tasks grew complex (>10 steps), models began summarizing expected outcomes rather than verified facts. A model would write: *"I have investigated the vulnerability, patched the configuration, and sent the report,"* even when no network request was sent.
2. **The 403 Masking Trap:** When an API returned a permission denied error, the model frequently apologized internally, but outputted: *"The operation was completed successfully!"* to the end user.
3. **The Circular Loop Trap:** When rate-limited (HTTP 429), agents would invoke the exact same failing API call 5 to 10 times consecutively, burning tokens without adapting.

I realized: **If the world's leading AI labs struggle with this manually, enterprises deploying autonomous agents into production are flying completely blind.** That was the spark to build **AgentTrace**.

---

### How AgentTrace Helps ME (As an Agentic Software Engineer)
As an Agentic Software Engineer directing autonomous coding agents (Google Antigravity, Claude Code, OpenAI Codex), AgentTrace provides **10x developer leverage**:
* **Automated Flight Recorder:** It acts as an automated safety interceptor during spec-driven coding loops.
* **Catches Ghost Commits & Edits:** If an agent claims it wrote a unit test or fixed a bug, AgentTrace checks the SHA-256 hash delta on disk. If the hash hasn't changed, the agent is halted immediately.
* **Loop Breaker:** It stops circular retry loops before they burn hundreds of thousands of tokens.
* **Empirical Grounding:** It anchors the agent to disk receipts (`pdftotext`, `git diff`, test exit codes), preventing context drift across multi-turn sessions.

---

### How AgentTrace Helps OTHERS (Founders, AI Startups & Enterprise Teams)
For any company building autonomous agents (e.g., Platvix, Devin, CrewAI):
1. **Financial & Operational Safety:** Prevents customer support agents from telling users: *"Your \$500 refund has been processed,"* when the Stripe API call failed with a 401.
2. **Automated CI/CD Gating:** Teams run `agenttrace audit trace.jsonl --json` inside their GitHub Actions pipeline. If an agent trajectory scores $\text{SQS} < 4.0$ or contains a Ghost Action, the PR is automatically blocked from merging.
3. **Objective Model Benchmarking:** Teams can objectively measure which model family (Claude, GPT, Gemini) produces fewer action hallucinations on their internal tools.

---

## 5. Architectural Workflows & Before vs. After Diagrams

### ❌ BEFORE AgentTrace: The Probabilistic Hallucination Loop

In standard ungrounded agent loops, the agent produces actions and claims simultaneously from probabilistic token prediction over lossy conversational memory.

```mermaid
flowchart TD
    User["User Request"] --> LLM["LLM Agent (Next-Token Generation)"]
    LLM --> LatentMemory["Latent Context Memory (Lossy Compression)"]
    LatentMemory --> ClaimGen["Generate Output Claims<br/>('Fixed bug', 'Sent email', 'June 2027')"]
    ClaimGen --> UnverifiedOutput["Unverified Output Text"]
    UnverifiedOutput --> UserDelivery["Delivered Directly to User<br/>(Silent Failures Go Undetected!)"]

    style ClaimGen fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#b71c1c
    style UnverifiedOutput fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#b71c1c
```

---

### ✅ AFTER AgentTrace: The Deterministic Interception Loop

AgentTrace introduces an out-of-band forensic verification gate. Semantic claims are matched against physical tool receipts and cryptographic filesystem state before response delivery.

```mermaid
flowchart TD
    User["User Request"] --> Planner["Agent Planner & Tool Invoker"]
    Planner --> Exec["Local Execution Sandbox<br/>(Docker Harbor / Shell / Tools)"]
    Exec --> TraceLogs["Structured Trajectory Trace<br/>(JSONL Receipts, Tool IDs, Exit Codes)"]
    
    TraceLogs --> Auditor["AgentTrace Forensic Auditor"]
    DiskArtifacts["Filesystem Ground Truth<br/>(SHA-256 Hashes, pdftotext, git status)"] --> Auditor
    Invariants["Permanent Invariant Anchors<br/>(GEMINI.md Invariant Rules)"] --> Auditor

    Auditor --> CrossCheck{"Ground-Truth Cross-Check"}
    CrossCheck -- "Discrepancy / Ghost Action" --> Reject["SQS &lt; 3.0: Abort &amp; Self-Remediate"]
    Reject --> Planner
    CrossCheck -- "100% Grounded" --> Approve["SQS 5.0: Cryptographic State Assertion"]
    Approve --> VerifiedDelivery["Verified Output Delivered to User<br/>(Zero Action Hallucinations)"]

    style Auditor fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1
    style CrossCheck fill:#fff8e1,stroke:#f57f17,stroke-width:2px,color:#e65100
    style Approve fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20
    style Reject fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#b71c1c
```

---

### ⏱️ Runtime Sequence: Forensic Interception in Action

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Calling Pipeline
    participant Agent as Autonomous Agent (LLM)
    participant Rec as AgentTrace Recorder
    participant Sandbox as Docker / Tool Sandbox
    participant Aud as Forensic Auditor
    participant Disk as Physical Filesystem

    User->>Agent: "Mutate database schema and dispatch notification email"
    Agent->>Rec: Log Step 1 Thought: "Querying current schema..."
    Agent->>Sandbox: Execute SQL Query Tool
    Sandbox->>Rec: ToolResult: Exit 0 (Schema returned)
    
    Agent->>Agent: Suffers Context Compression & Skips Mutation Tool
    Agent->>Rec: Step 2 Response: "I have migrated the table and sent the email."
    
    Note over Rec,Aud: AgentTrace Interception Triggers
    Rec->>Aud: Ingest Trajectory JSONL
    Aud->>Disk: Compare SHA-256 pre/post state hash
    Disk-->>Aud: Hash Delta = 0 (No file mutated!)
    Aud->>Aud: Match 'I sent the email' against Tool Calls (0 dispatch tools found!)
    Aud->>Aud: Compute SQS: 5.0 - 2.5 (Ghost File) - 2.5 (Ghost Email) = 0.0 [REJECTED]
    Aud-->>User: Gated Rejection: Block ungrounded response & trigger automated remediation
```

---

## 6. SQS Scoring Rubric Formulation

$$\text{SQS} = \max\left(0.0, \, 5.0 - \sum w_i \cdot N_i - \min(1.0, 0.25 \cdot F_{\text{unrecovered}})\right)$$

| Severity | Penalty ($w_i$) | Triggers | Impact on Execution |
| :---: | :---: | :--- | :--- |
| **CRITICAL** | **-2.5** | `GHOST_ACTION`, `UNVERIFIED_STATE_MUTATION` | **Immediate Rejection ($\text{SQS} \le 2.5$)**. Gated response blocked. |
| **HIGH** | **-1.5** | `MASKED_FAILURE`, `CIRCULAR_RETRY_TRAP` | **Requires Rework**. Automated retry with specific remediation prompt. |
| **MEDIUM** | **-0.5** | `ARGUMENT_DRIFT` | **Warning Flag**. Permitted if task succeeds, but logged for fine-tuning. |

---

## 7. Whiteboard Presentation Script

When asked to present this to an engineering panel:
1. **Start with the Problem:** *"Every engineering leader wants autonomous agents, but nobody trusts them in production because agents lie persuasively. We call this an Action Hallucination."*
2. **Present the Triad:** Draw the three circles: **Model Claims**, **Tool Receipts**, **Cryptographic State**. Explain that AgentTrace computes the intersection and rejects anything outside it.
3. **Show Real Code:** Point them to `agenttrace demo` and the 22 automated tests passing in 0.03s at [`github.com/krish9-gif/ai-systems-eval-portfolio`](https://github.com/krish9-gif/ai-systems-eval-portfolio).
