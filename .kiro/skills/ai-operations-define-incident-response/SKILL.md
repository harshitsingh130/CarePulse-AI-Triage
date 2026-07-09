---
id: define-incident-response
name: "Define Incident Response (aine-ai-operations)"
description: "Per-system incident-response runbook covering severity classes, on-call rotation, and post-incident review process."
trigger: command
phrase: "/define-incident"
---

## Objective

Define an AI-specific incident response framework that covers detection, triage, response, resolution, and post-incident review for every production AI system. AI incidents differ from traditional software incidents because model behaviour is probabilistic, failures can be silent, and impact may not be immediate.

## Procedure

1. **Identify AI-specific failure modes.** For each system in the AI BOM, document:
   - Silent regression (model output quality degrades without errors)
   - Hallucination spike (factually wrong outputs increase)
   - Prompt injection (adversarial input bypasses guardrails)
   - Data drift (input distribution shifts from training data)
   - Cost runaway (token usage spikes unexpectedly)
   - Availability failure (model endpoint unreachable)
   - Guardrail bypass (safety filters fail to catch harmful output)

2. **Define severity levels for AI incidents:**
   - **Sev 1 - Harmful output:** System produced output that caused harm (financial, reputational, safety). Immediate page. All hands until resolved.
   - **Sev 2 - Wrong autonomous decision:** System made an incorrect decision without human check. Page within 15 minutes.
   - **Sev 3 - Degraded quality:** System output quality measurably below baseline but no harm. Investigate within 1 hour.
   - **Sev 4 - Anomaly detected:** Monitoring flagged something unusual. Investigate within 1 business day.

3. **Define the on-call rotation:**
   - Primary responder (AI/ML engineer or AI SRE)
   - Secondary responder (platform engineer)
   - Escalation path (engineering manager -> director -> VP)
   - Communication plan (who notifies the business, customers, regulators?)

4. **Define detection mechanisms per failure mode:**
   - Golden-set evaluation (daily regression check against known-good outputs)
   - Guardrail hit-rate monitoring (sudden spike = potential bypass)
   - Cost anomaly alerts (> 2x daily average triggers investigation)
   - Latency monitoring (p99 latency breach)
   - User feedback signals (thumbs-down rate, escalation rate)

5. **Define the post-incident review (PIR) process:**
   - Timeline reconstruction (what happened, when, who noticed)
   - Root cause (model, data, prompt, infrastructure, guardrail, or human error?)
   - Impact assessment (users affected, decisions influenced, financial cost)
   - Remediation (what was done to fix it)
   - Prevention (what changes prevent recurrence)
   - Lessons learned (what do we now know that we didn't before?)

6. **Produce the artifact** with one section per system, one runbook per Sev 1/2 failure mode.

## Done when

- Incident response artifact exists for every Sev 1 and Sev 2 failure mode.
- On-call rotation is defined with named roles (not people - roles survive rotation).
- Detection mechanisms are documented and at least one (golden-set or cost anomaly) is implemented.
- PIR process is documented and has been reviewed by the engineering manager.
- A tabletop exercise date is scheduled (within 30 days of artifact completion).

## Anti-patterns

- Copy-pasting traditional SRE runbooks without AI-specific failure modes.
- Defining detection without implementing at least one mechanism.
- Skipping the tabletop exercise - the runbook is untested until exercised.
