---
id: aidlc-program-overview
description: "AWS AI-DLC program overview covering phases and deliverables"
inclusion: always
priority: 85
---

# AWS AI-DLC â€” Program Overview

This rule renders into the engagement only when the `aws-aidlc` program is in the active set. It tells the agent what AI-DLC is, what artifacts it produces, and how those artifacts integrate with the rest of AINE.

## What AI-DLC is

[AWS Labs' AI-DLC](https://github.com/awslabs/aidlc-workflows) is an open-source workflow methodology â€” not a tool â€” that structures software development around AI-assisted engineering. It declares three phases:

| Phase | Purpose | What it produces |
|---|---|---|
| Inception | Determine WHAT to build and WHY | Requirements, user stories, application design, units of work |
| Construction | Determine HOW to build it | Functional design, NFR design, infrastructure design, code |
| Operations | Deploy and run | (placeholder in AWS Labs' release; **completed by AINE programs in this engagement** â€” see the bridge) |

AI-DLC enforces explicit user-confirmation gates between every stage. Verbatim user input is captured in `aidlc-docs/audit.md`. Decisions are not advanced without typed acknowledgement.

## How this program integrates with AINE

AINE owns the **engagement** layer (multi-program orchestration across an organisation: AIM + RAI + Resilience + AI Ops). AI-DLC owns the **workload** layer (one application from intent through code to operate).

When the `aws-aidlc` program is active in an engagement:

1. **Discovery surface.** AI-DLC's Inception phase replaces AINE's local nine-question discovery skill. The bridge steering routes `/discovery` to `/aidlc-inception`.
2. **Spec / build surface.** AI-DLC's Construction phase replaces the bespoke Kiro three-file spec produced by `aws-app-builder`. The aws-app-builder program continues to provide the AINE 15-layer mapping and reference material; the requirements and design artifacts live under `aidlc-docs/`.
3. **Operations surface.** AI-DLC's Operations phase is currently a placeholder in AWS Labs' release. AINE *completes* it by routing the engagement's resilience review, AI BOM, deployment, observability, and production-readiness work into `aidlc-docs/operations/`. See `aidlc-aine-bridge.md` for the routing table.

## Skills exposed by this program

| Skill | Trigger | When to use |
|---|---|---|
| Install AI-DLC | `/aidlc-install` | Before anything else, once per engagement. Walks the platform-specific install. |
| Start Inception | `/aidlc-inception` | Discovery surface. Captures verbatim business and product requirements. |
| Advance Construction | `/aidlc-construction` | After Inception is signed off. Produces design and code. |
| Complete Operations | `/aidlc-operations` | After Construction is signed off. Routes AINE operations programs into AI-DLC's Operations phase. |
| Sync to AINE intake | `/aidlc-sync` | After Inception. Mirrors AI-DLC requirements to AINE `state.intake.*` so AIM, RAI, and other AINE programs can read intake without parsing AI-DLC documents. |

## Conventions this program follows

- **Two artifact trees, no duplication.** AI-DLC writes under `aidlc-docs/`. AINE writes under `artifacts/`. The bridge ensures one is the source of truth for any given artifact; the other contains a pointer.
- **AI-DLC's audit log is authoritative for verbatim user input.** AINE's `state/history.jsonl` records AINE-program-level decisions and references the AI-DLC audit log timestamp for the evidence.
- **Mandatory user confirmation.** AI-DLC's "DO NOT PROCEED until user confirms" rule is upheld at every AI-DLC gate. AINE programs invoked from the Operations phase respect their own confirmation gates as well.
- **Sticky discovery surface.** Once an engagement starts with AI-DLC, it stays with AI-DLC. Once it starts without AI-DLC, it stays without. Mid-engagement switches are not supported â€” installing AI-DLC after AINE's local discovery has run does not retroactively re-route.

## What this program does NOT do

- **Does not bundle AI-DLC.** Installation is the FDE's responsibility (the install skill walks them through it but does not include the rules). This keeps AINE and AI-DLC independently versionable.
- **Does not modify AI-DLC's rules.** The `.kiro/steering/aws-aidlc-rules/` directory and `.aidlc-rule-details/` directory installed by AI-DLC are read-only from AINE's perspective.
- **Does not duplicate AI-DLC's audit log.** AINE's `state/history.jsonl` references AI-DLC's `aidlc-docs/audit.md` rather than copying entries.
- **Does not block AINE programs that have nothing to do with workload lifecycle.** AIM (org-level assessment), the multicloud programs, and AIDLC (Q Developer adoption â€” note the name collision) all run independently of `aws-aidlc`.

## Why priority 85

The `discovery-first-gate.md` (priority 99) blocks artifact production globally. The `aidlc-aine-bridge.md` (priority 87) routes between surfaces. This file is descriptive â€” priority 85 places it just below the routing rule so the agent reads it as program-context after deciding which surface is in use.
