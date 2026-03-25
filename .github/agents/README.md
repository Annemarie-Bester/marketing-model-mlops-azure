# `.github/agents/` — AI Agent Definitions

This folder contains custom GitHub Copilot agent definitions for this project.
Agents are specialised AI assistants that take direction from the developer,
operating within locked tool sets and scoped instructions to assist with
research, code implementation, and documentation tasks.

All agents work under the following principles:

- **User-directed** — agents respond to explicit developer instructions and do not act autonomously
- **Developer accountable** — all AI-generated output must be manually reviewed and tested by the developer before being committed or deployed
- **Scoped by design** — each agent has a defined role it cannot exceed, enforced through tool restrictions and subagent delegation rules

---

## `engineer.agent.md` — Senior Azure MLOps Engineer

### What it is

A custom Copilot agent that behaves as a **pragmatic Senior Azure MLOps Engineer**.
It is scoped exclusively to this assessment's requirements and architecture, and
actively enforces engineering discipline throughout AI-assisted development.

Activate it in VS Code Copilot Chat by selecting **engineer** from the agent picker,
or by typing `@engineer` in the chat input.

### What it does

| Capability | Behaviour |
|---|---|
| Architecture guidance | Enforces the locked stack (GitHub → Azure DevOps → Docker → ACR → AKS → FastAPI → App Insights). Will not suggest alternatives. |
| Code generation | Writes production-style Python — modular, config-driven, no hardcoding |
| Pipeline thinking | Always reasons about the full pipeline: data → features → train → evaluate → artifact → serve |
| Overengineering prevention | Intervenes when complexity exceeds what the problem requires |
| Time management | Prioritises high-impact, fast-to-deliver work given the ~60 hour constraint |
| Decision justification | Explains every significant choice using simplicity, time, and alignment with requirements |

### Tools it uses

```
read     — reads existing files before modifying them
edit     — creates and modifies source files
search   — searches the codebase for context
execute  — runs terminal commands to verify outputs
web      — fetches external documentation when required to support implementation
todo     — tracks task progress across multi-step work
```

---

## Why a Custom Agent? — AI-Driven Development with Controlled Drift

### The problem with unconstrained AI assistance

Using a general-purpose AI assistant on a production ML project introduces several
risks:

- **Model drift via AI suggestion**: A generic assistant may suggest popular but
  inappropriate tools (MLflow, Feast, Ray, etc.) that are overkill for the task,
  creating complexity that diverges from the original design intent. Each accepted
  suggestion compounds this drift.
- **Inconsistent patterns**: Without enforced standards, AI-generated code across
  different sessions can have conflicting styles, abstraction levels, and
  assumptions, making the codebase harder to reason about.
- **Scope creep**: AI tends to anticipate hypothetical future requirements and
  add flexibility that is never used — pure complexity cost.
- **Unreproducible decisions**: When AI is used ad hoc, the rationale behind
  design choices is lost, making the system harder to maintain or defend.

### How this agent addresses that

The agent definition acts as a **persistent specification** for AI behaviour on
this project. It enforces:

1. **Locked architecture** — the agent cannot suggest alternatives to the
   defined stack, keeping all generated code aligned with the infrastructure
   decisions already made.

2. **Config-driven code generation** — all generated code reads from `config.yaml`.
   No values are hardcoded into AI-generated code, so the system remains
   reproducible and consistent across sessions.

3. **Single responsibility per module** — the agent enforces the `src/data.py`,
   `src/features.py`, `src/train.py`, `src/evaluate.py`, `src/api/` structure.
   This prevents AI from generating "helpful" utility modules that fragment the
   codebase.

4. **Explicit intervention triggers** — the agent is instructed to actively
   correct over-modelling, unnecessary abstraction, or CI/CD neglect. It does
   not passively accept direction that diverges from requirements.

5. **Documented decisions** — the agent always justifies choices in terms of
   simplicity, time constraints, and alignment with the case study. This creates
   an audit trail for design decisions made with AI assistance.

### The outcome

AI-assisted development with this agent is **faster** than unconstrained
assistance because the agent's constraints eliminate the review burden of
evaluating off-spec suggestions. Every generated code block is already
aligned with the architecture, the module structure, and the assessment goals —
the developer's focus stays on evaluation and iteration, not on filtering
AI output.

---

## `docs.agent.md` — ML Documentation & Research Specialist

### What it is

A custom Copilot agent that behaves as a **Machine Learning Documentation & Research Specialist**.
It is responsible for researching official sources, writing and improving `.md` files, and
curating references. It never modifies code logic.

Activate it in VS Code Copilot Chat by selecting **docs** from the agent picker,
or by typing `@docs` in the chat input.

### What it does

| Capability | Behaviour |
|---|---|
| Documentation writing | Creates and improves `.md` files with clear heading hierarchy, professional tone, and logical flow |
| Source research | Fetches and validates official documentation (Microsoft, Kubernetes, GitHub, scikit-learn) before writing |
| Reference curation | Keeps references minimal, grouped by category, and sourced from official documentation first |
| Architecture documentation | Explains design decisions, tradeoffs, and architecture — not just what, but why |
| Scope enforcement | Will not modify code logic, refactor functions, or change pipelines |

### Tools it uses

```
read     — reads existing files before writing or modifying them
edit     — creates and modifies .md documentation files only
search   — searches the codebase for context before writing
web      — fetches and validates official documentation sources
```

### Scope boundaries

**Allowed:**
- Create and edit `.md` files
- Add minimal explanatory comments to code files (design decisions only)
- Research and validate documentation sources via web

**Not allowed:**
- Modify code logic, refactor functions, or change pipelines
- Add excessive inline comments explaining basic operations
- Act autonomously on research direction without user alignment
- Invoke `@engineer` as a subagent — docs cannot proxy code changes through engineer

---

## Agent Relationships & Delegation Model

The two agents have an intentionally one-directional subagent relationship,
enforced through the `agents:` frontmatter field in each agent definition.

### Allowed delegation

```
User → @docs    (research and documentation tasks)
User → @engineer    (implementation and code tasks)
@engineer → @docs   (engineer may delegate documentation tasks to docs)
```

### Blocked delegation

```
@docs → @engineer   (explicitly blocked — agents: [] in docs.agent.md)
```

### Why this matters

**Separation of concerns is enforced at the framework level, not just in the prompt.**
`docs` is restricted to `[read, search, edit, web]` — it has no `execute` or code-modifying
capability. However, if `docs` could invoke `engineer` as a subagent, it could proxy code
changes through engineer, making its own tool restriction meaningless.

Setting `agents: []` on `docs` closes that gap: docs is incapable of triggering any
code changes, directly or indirectly.

**Circular handoffs are prevented.** Allowing both agents to invoke each other
creates the structural condition for a delegation loop (`docs → engineer → docs → ...`).
The one-directional constraint eliminates this.

### The natural workflow

The delegation model reflects how these agents are actually used in practice:

```
1. User → @docs      Research a topic, validate sources, draft documentation
2. User reviews      Developer reads docs output, decides what to implement
3. User → @engineer  Implement based on documented decisions
4. User tests        Developer runs, tests, and validates all generated code
5. User commits      Developer is responsible for everything committed to the repo
```

Feedback from engineer back to docs (e.g. "document this implementation decision")
is a legitimate delegation — it flows in the same direction as the workflow, not
against it.

---

## AI Tool Disclosure

This project was developed with significant AI assistance throughout. This section
documents the tools used, how they were applied, and how AI output was validated —
in accordance with ACM's authorship policy on generative AI disclosure and
Microsoft's responsible AI guidelines for auditable AI-assisted decisions.

### Tools used

| Tool | Role | Version / Model |
|---|---|---|
| GitHub Copilot Chat (VS Code) | Code generation, documentation writing, architecture research, MLOps reference research | Extension v0.40+ |
| `@engineer` custom agent | ML pipeline code, FastAPI serving layer, CI/CD pipeline design, AKS deployment configuration | Claude Sonnet 4.6 |
| `@docs` custom agent | Documentation writing, official source research, REFERENCES.md curation, `docs/` content | Claude Opus 4.6 |

Both Claude Sonnet 4.6 and Claude Opus 4.6 (Anthropic, via GitHub Copilot) were used across different
tasks: Sonnet for engineering tasks requiring speed and precision, Opus for documentation and research
tasks requiring deeper synthesis and reasoning.

### How AI output was validated

Agents in this project are assistants — they produce output in response to developer
instructions, and the developer is responsible for everything that reaches the
remote repository. Validation operated at three levels:

1. **No autonomous commits** — agents cannot push, deploy, or commit. Every piece
   of AI-generated output — code, documentation, configuration — was manually
   reviewed and tested by the developer before being staged or committed.

2. **Custom agent constraints** — the `@engineer` agent definition locks the architecture,
   module structure, and coding standards. AI-generated code cannot deviate from these
   constraints without explicit developer override. This prevents the most common failure
   mode of unconstrained AI assistance: architectural drift.

3. **Research grounding** — the `@docs` agent fetched official documentation
   (Microsoft, Kubernetes, GitHub, scikit-learn) before writing any documentation
   section. All references were validated against the source before being added to
   `REFERENCES.md`.

4. **Explicit scope boundaries** — each agent definition includes a list of what it is
   NOT allowed to do, enforced through both prompt instructions and tool restrictions.
   `docs` cannot execute code; `docs` cannot delegate to `engineer`. These are
   framework-level constraints, not just guidelines.

### What AI generated vs what the developer decided

| Decision type | Made by |
|---|---|
| Architecture selection (AKS, ACR, FastAPI, Azure DevOps) | Developer |
| Module structure (`src/data.py`, `src/features.py`, etc.) | Developer |
| Model selection (Logistic Regression over Gradient Boosting) | Developer — based on F1 minority class result |
| Agent constraint definitions (locked architecture, tool restrictions) | Developer |
| Implementation of locked architecture in code | AI (`@engineer`) |
| Documentation drafting for `docs/` and `REFERENCES.md` | AI (`@docs`) with developer review |
| MLOps research synthesis (deployment strategies, maturity levels) | AI (`@docs`) with official source citations |

### References for responsible AI use

- GitHub. [Responsible use of GitHub Copilot Chat in your IDE](https://docs.github.com/en/copilot/responsible-use/chat-in-your-ide). 2025.
- Microsoft. [Responsible AI in Azure workloads](https://learn.microsoft.com/en-us/azure/well-architected/ai/responsible-ai). 2025.
- ACM. [Policy on Authorship — Generative AI Disclosure](https://www.acm.org/publications/policies/frequently-asked-questions). 2024.

---

## Adding New Agents

If the project grows to need specialised agents (e.g. a CI/CD-only agent, or an
API design agent), place their `.agent.md` files in this folder following the
same pattern: locked tools, single role, explicit constraints, keyword-rich
description.
