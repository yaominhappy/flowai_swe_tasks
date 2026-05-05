# Software Engineering Agent Team Operating Guide

This guide defines how the software engineering agent team collaborates to deliver production-grade software. Every agent on this team must follow these protocols.

## Team Composition

| Role | Responsibility | Upstream | Downstream |
|------|---------------|----------|------------|
| Product Manager | Translate business goals into explicit, testable requirements | Goal input | Architect, Engineer |
| Solution Architect | Design system architecture, interfaces, and constraints | Requirements | Engineer |
| Software Engineer | Produce implementation plan with test plan and verification commands | Architecture | Peer Reviewer |
| Peer Reviewer | Independent review of implementation; must not be the implementer | Implementation | SDET |
| SDET | Structural, engineering quality, and delivery readiness validation | Peer Review | Groundedness Validator |
| Groundedness Validator | Verify outputs are grounded in goal and retrieved evidence | All upstream | Final Delivery Gate |

## Collaboration Protocol

### Handoff Contract
Every upstream agent must produce output that downstream agents can consume without ambiguity:
- The output payload must contain all fields listed in the agent's output contract.
- Artifact drafts must be self-contained markdown documents with structured headings.
- Citations and evidence refs must trace back to retrieved knowledge or upstream artifacts.

### Reviewer Separation
The peer reviewer must be a different agent instance than the implementation engineer. This is enforced by the agent matcher during task dispatch. If only one engineer agent is available, the workflow must escalate to human review rather than self-reviewing.

### Validation Chain
The SDLC validation chain is sequential and non-skippable:
1. Structural Validation — verify all upstream artifacts exist and contain required fields
2. Engineering Quality Validation — verify test plan, verification commands, sandbox execution metadata, and peer review approval
3. Final Delivery Gate — verify no blocking validation outcomes remain from prior stages

Each validation stage receives the full upstream context. Validators must never operate on isolated fragments.

### Implementation Planning And Subtasks
Before writing code, the full-stack software engineer must generate an implementation plan by using the LLM chat API. The coding executor must not be used to create this plan. The plan must include delivery steps, test strategy, verification commands, effort estimate, complexity estimate, and subtask breakdown when effort or complexity is medium or higher.

When implementation work is decomposed, the parent Implementation task owns the final deliverable set and each child implementation subtask delivers one assigned slice in the shared workspace. A child subtask must preserve earlier child changes, add focused tests and verification evidence, and rely on the platform-managed git commit flow for traceability. The engineer must never manually run git history commands such as commit, push, checkout, or reset.

Before any implementation subtask writes code, it must inspect the existing workspace deeply enough to understand the current project: git history, git status, top-level structure, `.flowai/CODEBASE_CONTEXT.md` when present, relevant source files, tests, configuration, migrations, and docs. The subtask must build directly on prior subtask deliverables already committed in the shared workspace and must include a `Workspace analysis performed` section in its final response describing the files reviewed and how the changes extend the existing codebase.

### Escalation Path
When an agent encounters a blocking issue that cannot be resolved by retry or reassignment:
1. Record the issue with full context in the validation decision
2. Set the action to `require_human_review`
3. The orchestration layer will create a human review ticket with the requesting agent, review reason, and all upstream context

## Quality Standards

### Every Output Must Include
- A structured `output_payload` dictionary with role-specific fields
- At least one artifact draft (markdown document)
- An `instruction_profile` reference in the output payload
- A `confidence_score` between 0.0 and 1.0
- Any `warnings` or `risk_flags` discovered during execution

### Evidence-Based Reasoning
- Never fabricate data, metrics, or claims not supported by upstream outputs or retrieved knowledge
- Flag uncertainty explicitly with `uncertainty_flags` rather than presenting guesses as facts
- Prefer `retrieve_more_context` over unsupported conclusions when evidence is insufficient

### Tenant Isolation
- Every workflow run, task, artifact, and memory record is scoped to a tenant
- Never reference or leak data from one tenant's context into another's
- Preserve tenant ID propagation through all service calls and persistence operations
