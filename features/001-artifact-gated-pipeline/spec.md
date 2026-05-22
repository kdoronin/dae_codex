# Spec

Feature: Artifact-gated DAE runtime enforcement

Scenario: Prompt with policy terms receives context
  Given DAE runtime state is missing required artifacts
  When a user prompt mentions implementation, bypass, hooks, CRAP, ATDD, quality, or tests
  Then the prompt hook reports the current checkpoint and missing artifacts
  And the prompt hook does not return a hard block decision

Scenario: Planning artifacts remain possible before approval
  Given the current checkpoint is before plan approval
  When the agent writes charter, acceptance criteria, Gherkin spec, plan, progress, handoff, evidence, or policy override artifacts
  Then the write is allowed

Scenario: Implementation writes require prior gates
  Given charter, acceptance criteria, Gherkin spec, plan, or approval is missing
  When the agent attempts an implementation, scaffold, config, or test write
  Then the write is denied with the missing artifacts named

Scenario: Quality evidence gates completion
  Given an implementation-affecting edit has occurred
  When completion or release is attempted before fresh required quality evidence exists
  Then completion or release is denied with the missing evidence named

Scenario: Audited override controls relaxation
  Given strict quality defaults are configured
  When a required gate is relaxed without audit fields
  Then configuration validation fails
  But when scope, justification, approver, approval time, and expiry or no-expiry reason are present
  Then configuration validation accepts the override for that scope
