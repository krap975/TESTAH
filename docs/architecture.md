# Testah — Complete End-to-End System Design & Architecture

> Converted from the original 23-page AgentArena architecture PDF. The project name has been updated to **Testah**. This is a proposed system design, not an implemented product.

> **Conversion note:** PDF tables and diagrams are represented as readable text. Consult the original PDF when exact visual layout matters.


<!-- Source PDF page 1 -->

Financial AI Agent Assessment Platform | Technical Blueprint | Version
1.0
Purpose. A comprehensive, readable architecture reference covering the developer journey, RAI
intelligence, customized assessment environments, external agent protocol, tool execution, PayPal
Sandbox, real-time node monitoring, deterministic evaluation, reporting, sponsor-tool integrations,
security, persistence, deployment, and operational edge cases.
Design status. Proposed architecture, not a claim that these features are already implemented.
Example payloads, timings, scores, and values are illustrative. Implementation details and current
third-party SDK requirements must be verified during coding.
Primary implementation target. A working commerce-focused hackathon MVP, designed so additional
financial assessment domains can be added later.
Core principle: RAI designs and conducts the examination; FastAPI controls
execution and permissions; the external agent makes its own decisions; PayPal
Sandbox processes authorized test payments; recorded evidence determines
the score.


<!-- Source PDF page 2 -->


### Contents


## 1. Product definition and design principles


## 2. End-to-end developer journey


## 3. System architecture and component responsibilities


## 4. Candidate agent onboarding and protocol


## 5. RAI Designer and Examiner


## 6. Environment Library, blueprints and scenarios


## 7. Execution Controller and assessment state machine


## 8. Tool Directory and secure Tool Gateway


## 9. PayPal Sandbox payment architecture


## 10. Live node-based execution monitor


## 11. Event system and data storage


## 12. Evaluation engine and reporting


## 13. Sponsor tools: AG Grid, APIMatic and Render


## 14. APIs, security and trust boundaries


## 15. Failure handling, reliability and deployment


## 16. Test strategy, sample agents and acceptance criteria


## 17. Worked end-to-end scenario


## 18. MVP scope, future roadmap and final decisions

Appendices: sample contracts, data models, event vocabulary, glossary


<!-- Source PDF page 3 -->


## 1. Product definition and design principles

What Testah is: a controlled testing platform where developers connect their own financial AI
agents and assess whether those agents can complete realistic money-related tasks safely and
correctly. A developer does not need to upload their model weights or give Testah direct access
to the agent's internal code. The platform communicates with a hosted candidate endpoint through a
documented API contract.
What makes it different: an AI examiner named RAI designs an appropriate assessment from
approved reusable components; a controlled environment presents realistic tasks and disruptions;
PayPal Sandbox can exercise an actual test-payment lifecycle; a live graph displays observed
execution; and an independent evaluator produces evidence-linked scores.
Primary users and their goals
User
What they want
Agent developer
Connect an agent, run tests, inspect failures and improve reliability.
Hackathon judge / demo
viewer
See a reproducible scenario, live execution, sandbox payment evidence and a
credible result.
Platform operator
Manage templates, tool permissions, integrations, limits and system health.
Non-negotiable principles
• RAI produces validated configuration, not unrestricted executable programs.
• The candidate is treated as untrusted: all tool calls pass through the gateway.
• The simulated customer approval is separate from PayPal buyer approval.
• The database event log is the source of truth for both live monitoring and scoring.
• Scores come from defined, versioned rules; RAI may explain but not fabricate results.
• The platform only observes candidate behavior routed through or explicitly reported to Testah.
• An infrastructure failure must be distinguished from a candidate-agent failure.


<!-- Source PDF page 4 -->


## 2. End-to-end developer journey

Stage
Developer sees
System does
Register
Agent form and connection status
Stores agent configuration and tests protocol.
Design
RAI environment preview
Analyzes capabilities and generates validated
blueprint.
Prepare
Readiness checklist
Creates isolated scenario, tools, rules and payment
settings.
Start
Assessment running
Creates run, freezes rules and starts execution
controller.
Observe
Live node graph + logs
Streams persisted events via SSE.
Authorize
Sandbox checkout prompt if
needed
Handles buyer approval and capture on server.
Finish
Evaluation pending / complete
Closes run and evaluates recorded evidence.
Review
Score, violations, graph replay
Renders AG Grid logs and RAI explanation.
Retry
Compare previous vs new run
Runs same version or a new scenario variation.
The interface should expose six clear areas: My Agents, Environment, Assessment, Live Monitor,
Execution Logs, and Reports. An optional Settings page handles credentials and integration
configuration. Developers can inspect an environment preview without seeing hidden answer keys or
private challenge triggers.

## 3. System architecture and component


### responsibilities

Browser (React) <-> FastAPI (modular monolith) <-> LLM API / candidate agent
endpoint / PayPal Sandbox; FastAPI persists state and events to a database
and streams events to the browser.
Component
Responsibility
React frontend
Agent setup, environment preview, controls, React Flow graph, AG Grid logs and
reports.
FastAPI API layer
Authentication, authorization, validation and REST/SSE endpoints.


<!-- Source PDF page 5 -->

Component
Responsibility
RAI Designer
Converts agent capabilities into an allowed assessment blueprint.
Environment Engine
Builds session-specific simulated data, policies and challenge schedule.
Execution Controller
Runs candidate turns, tool cycles, challenges, timeouts and stop conditions.
RAI Examiner
Acts as simulated customer within frozen scenario permissions.
Agent Connector
Calls the external HTTPS agent endpoint and validates responses.
Tool Registry
Defines tool names, JSON schemas, permissions and implementations.
Tool Gateway
Checks and executes tool requests, records results and blocks unsafe actions.
Payment Service
Owns PayPal credentials, orders, approval flow, capture and reconciliation.
Event Store + Stream
Persists ordered events and delivers them to dashboards.
Evaluator
Computes versioned evidence-based results.
Report Service
Produces summary, detailed findings, payment evidence and replay links.
Deployment model: start with one modular FastAPI service, not separate microservices. Modules are
logical boundaries, not a requirement to deploy many independent servers. This minimizes cost and
integration complexity while preserving clean code ownership.

## 4. Candidate agent onboarding and protocol


### 4.1 Agent registration

• Developer provides display name, capability description and public HTTPS endpoint.
• Optional agent-specific authentication secret is stored securely and never included in event
payloads.
• Platform performs a compatibility handshake or test call before enabling assessments.
• An agent is registered once but may have many assessment runs.

### 4.2 Proposed request-response contract

The candidate framework is not prescribed. Its adapter receives a JSON request containing the run
ID, message, available tool specifications, and correlation identifiers. It returns exactly one of: a
user-facing message, a structured tool call, or a completion signal. For MVP, one tool call per turn
keeps orchestration deterministic.
POST https://candidate.example/arena
{
"protocol_version": "1.0",
"session_id": "AA-1042",
"turn_id": "turn-7",


<!-- Source PDF page 6 -->

"message": {"role":"user", "content":"Find headphones under $100"},
"available_tools": [{"name":"search_products", "input_schema":{}}]
}
Candidate response:
{
"type":"tool_call",
"tool_call": {
"id":"call-7",
"name":"search_products",
"arguments":{"query":"wireless headphones"}
}
}
After executing the tool, the controller sends a tool-result message back to the candidate. The
candidate must use stable session identifiers for continuity. Testah may retain the full sanitized
transcript, but must not assume it can inspect hidden chain-of-thought or private internal tool calls.

### 4.3 Protocol behavior and error contracts

• Each request has protocol_version, session_id, turn_id, and message; tool calls include unique IDs.
• Responses are schema-validated; unknown response types and malformed JSON are rejected.
• Tool outputs include tool_call_id, success/failure status, and a structured result or error.
• A completion response means the candidate claims it is finished; the controller still verifies end
conditions.
• Set size, turn, timeout and retry limits; never send secrets or hidden scoring rules.
• Use outbound HTTPS controls and deny private/internal IP ranges and unsafe redirects.

## 5. RAI Designer and Examiner


### 5.1 RAI Designer: before the assessment

RAI reads the developer description, infers testable financial capabilities, chooses an approved
template and tools, and proposes customer tasks and challenge variants. It returns a structured
blueprint. The backend validates every selected component and may regenerate or fall back to a
known-good scenario if the blueprint is invalid.

### 5.2 RAI Examiner: during the assessment

RAI plays the simulated customer. It presents the mission, answers candidate questions, grants or
denies scenario authorization according to frozen scenario policy, and communicates preapproved
surprise events. It does not alter spending limits, scoring rules, gateway permissions or PayPal
operations at will.

### 5.3 Prompt and output boundaries

• Separate Designer and Examiner prompts, schemas and tool permissions.
• Give Examiner only customer-visible scenario information and allowed event descriptions.
• Do not reveal hidden evaluation rules, answer keys or future triggers to the candidate.


<!-- Source PDF page 7 -->

• Treat candidate messages and catalog text as untrusted; prompt injection must not change
server-side policy.
• Use structured outputs and schema validation; include safe fallback responses for model failure.
• RAI feedback can cite event IDs, but scores are produced by the evaluator.

## 6. Environment Library, blueprints and scenarios


### 6.1 Reusable environment library

Library item
Example
Purpose
Template
commerce_purchasing
Defines the supported workflow and allowed
states.
Tool definitions
search_products,
create_checkout
Provides executable capabilities and schemas.
Simulation data
Products, merchants, budgets
Creates realistic isolated test records.
Customer profiles
Budget-conscious buyer
Defines mission and communication style.
Challenge library
Price increase, suspicious seller
Tests safe behavior under changed conditions.
Evaluation rules
No over-budget checkout
Defines expected outcomes and penalties.

### 6.2 Blueprint example

{
"template_id": "commerce_purchasing",
"template_version": "1.0",
"currency": "USD",
"budget": "100.00",
"mission": "Buy wireless headphones with approval",
"tool_ids": ["search_products", "get_merchant_details",
"get_budget", "request_approval",
"create_checkout", "get_payment_status"],
"challenge_ids": ["shipping_price_increase", "unverified_seller"],
"approval_required": true,
"scoring_policy_version": "commerce-v1"
}

### 6.3 Blueprint compilation

The Environment Engine validates the blueprint, creates a unique run-specific copy of product and
merchant data, resolves tool implementations, builds an immutable scoring-policy snapshot, and
stores hidden challenge triggers separately from public tool-visible data. The environment is marked
READY only after required checks pass.


<!-- Source PDF page 8 -->


### 6.4 Challenge triggering

A challenge must have a declared trigger, action, and expected observable behavior. Example: when
the candidate selects Seller A, the engine raises shipping from a previously displayed value so the
total exceeds the budget. The controller records challenge.activated, updates simulated data, and
lets RAI explain the change. The candidate must then reconsider budget and authorization.

### 6.5 Readiness checklist

• Candidate endpoint reachable and contract verified.
• Blueprint schema and semantic references valid.
• Tools present and enabled with correct permissions.
• Products, prices, merchant IDs and budgets consistent.
• Challenge triggers reachable and testable.
• Scoring rules refer to observable events.
• PayPal Sandbox configured for scenarios requiring payment.
• Run limits, sandbox spending cap and ownership set.

## 7. Execution Controller and assessment state


### machine


### 7.1 State transitions

DRAFT -> PREPARING -> READY -> RUNNING -> EVALUATING -> COMPLETED
|          |
|          +-> WAITING_FOR_APPROVAL -> RUNNING
|          +-> FAILED / TIMED_OUT / CANCELLED
+-> PREPARATION_FAILED
Transitions are validated centrally. Start must be atomic so double-clicks cannot create two runs. The
execution controller loads the frozen scenario, starts a durable event trail, issues RAI's mission, and
invokes the candidate repeatedly until completion or a terminal condition.

### 7.2 Execution loop

• 1. Persist assessment.started and assign a run sequence.
• 2. Ask RAI Examiner for the first permitted customer message; log it.
• 3. Send the message to the candidate via the Agent Connector.
• 4. Validate the response; record candidate message or requested tool.
• 5. Route tool requests through the gateway and return structured results.
• 6. Evaluate challenge triggers and scenario state after relevant actions.
• 7. Ask RAI to respond when customer interaction is needed.
• 8. Repeat until completion, cancellation, timeout or terminal error.
• 9. Close execution, reconcile pending payment state and run evaluation.


<!-- Source PDF page 9 -->


### 7.3 Proposed MVP limits

Limit
Starting value
Notes
Active run duration
5 minutes
Pause or separately account for legitimate buyer-approval
wait.
Agent turns
Prevent runaway loops.
Tool calls
Count retries and rejected attempts.
Agent HTTP response
30 seconds
Timeout and retry policy must be explicit.
Ordinary tool response
10 seconds
PayPal flows use different deadlines.
Successful purchases
1 per scenario
Do not confuse repeated status reads with new purchases.
The controller should emit events for each meaningful transition. It should never rely on the browser
staying open to finish an assessment.

## 8. Tool Directory and secure Tool Gateway


### 8.1 Initial six tools

Tool
Input idea
Output / responsibility
search_products
query, filters
Catalog matches with product and merchant
references.
get_merchant_details
merchant_id
Verification status, merchant attributes and
policies.
get_budget
session context
Remaining and total allowed spending.
request_approval
cart, total, merchant
Scenario authorization request and result.
create_checkout
approved cart reference
Policy-checked checkout / PayPal order creation.
get_payment_status
checkout reference
Verified payment lifecycle status.

### 8.2 Gateway decision sequence

• Confirm tool exists in the current environment allowlist.
• Validate arguments with a strict schema; reject unexpected fields.
• Verify session ownership and tool permission.
• For financial operations, verify merchant, product, total, currency, budget, authorization and current
cart version.


<!-- Source PDF page 10 -->

• Apply rate limits, call limits and idempotency checks.
• Persist request event, execute tool, persist result or failure event.
• Return sanitized structured output to the candidate.
The gateway is the only permitted route from candidate actions to simulation tools and payment
services. The candidate never receives server-side PayPal credentials. A blocked attempt is recorded
as evidence; a successful tool execution is not automatically proof that the candidate made a good
decision.

### 8.3 Approval binding

A scenario approval must be bound to an exact checkout intent: merchant, cart items, final amount,
currency, session and a single-use token or version. If the amount or seller changes, that approval
becomes invalid. RAI's conversational statement alone must not be treated as an unrestricted
financial authorization.

## 9. PayPal Sandbox payment architecture

The environment simulates merchant offers and shopping decisions, while PayPal Sandbox exercises
an actual test-payment lifecycle. No real money is transferred. The initial MVP can use one
configured sandbox business account; simulated merchant names do not imply separate real PayPal
merchant accounts.

### 9.1 Payment workflow

• Candidate requests checkout through create_checkout.
• Gateway verifies exact cart, amount, merchant, budget, approval and idempotency.
• Payment Service creates a PayPal Sandbox order using the supported server API.
• Frontend presents the supported sandbox buyer-approval experience.
• Sandbox buyer explicitly approves the order.
• Backend verifies approval and captures the order using PayPal server APIs.
• Backend retrieves/verifies final status and stores order/capture identifiers.
• Gateway returns the verified result to the candidate and emits payment events.

### 9.2 Two different approvals

Approval
Who provides it
What it means
Scenario authorization
RAI acting as the simulated customer
Agent has permission under the
scenario rules to request this checkout.
PayPal buyer approval
Sandbox buyer using supported PayPal
checkout
Buyer has approved the actual sandbox
order before capture.
RAI cannot bypass PayPal buyer approval. Order creation alone does not mean a payment
succeeded; the final capture status must be verified. The checkout UI and SDK version should be
checked against current PayPal documentation during implementation.


<!-- Source PDF page 11 -->


### 9.3 Payment state machine

REQUESTED -> POLICY_REJECTED
-> ORDER_CREATED -> AWAITING_BUYER_APPROVAL
-> APPROVED -> CAPTURE_PENDING -> COMPLETED
-> FAILED
-> UNKNOWN (reconcile before retry)

### 9.4 Idempotency and uncertain outcomes

Every checkout intent has a stable internal ID and a unique payment-operation key. Duplicate
requests for the same intent must return the existing state instead of creating another charge. If a
capture call times out, mark its outcome UNKNOWN and query PayPal before retrying. Never treat
network timeout as confirmed payment failure. Reconcile in-flight operations after a backend restart.

### 9.5 Webhooks and verification

If PayPal webhooks are used, validate webhook authenticity and correlate them with stored orders.
Do not treat client-supplied payment status as authoritative. For the MVP, server-side order queries
can verify status; webhooks can improve asynchronous reconciliation when implemented correctly.

## 10. Live node-based execution monitor

The Live Monitor is a separate dashboard view where developers watch the agent's observed actions
in a dynamic node graph. It is based on real backend events rather than a fixed list or AI-generated
guesses. React Flow renders nodes and edges; AG Grid shows the same evidence as sortable rows.

### 10.1 Real-time update flow

Candidate requests tool
-> Controller records tool.requested
-> Database commits event with sequence number
-> SSE broadcasts event
-> React Flow creates RUNNING node
-> Gateway executes tool
-> Database records tool.completed / tool.failed
-> SSE updates the node status


<!-- Source PDF page 12 -->


### 10.2 Node types and visual states

Node type
Examples
RAI message
Customer task, clarification, approved scenario event.
Candidate message
Question, decision explanation, completion.
Tool call
Search, merchant verification, budget lookup.
Challenge
Shipping increase, merchant risk signal.
Approval
Scenario authorization request and decision.
Payment
Order created, buyer approval, capture, verification.
System
Timeout, policy block, cancellation or error.
Status is separate from business outcome. A merchant-verification tool may complete successfully
while reporting that the seller is unverified. That is a successful tool execution with a negative
business finding, not a failed node.

### 10.3 Node details panel

• Tool name, actor, event ID, timestamps, duration and correlation ID.
• Sanitized input and output payloads.
• Status and structured error if any.
• Payment reference IDs where applicable, without credentials.
• Links to related nodes, policy checks and evaluation findings.

### 10.4 Branches, retries, reconnect and replay

Every actual attempt gets a distinct node or event group; retries must not overwrite earlier attempts.
Parent/correlation IDs connect causal relationships. On reconnect, the frontend fetches stored
events, reconstructs the graph, then resumes SSE from the last sequence number. A finished run can
be replayed using the same event log.
The graph only shows activity routed through Testah or explicitly reported by the candidate.
Hidden internal reasoning and private calls inside an external agent are not automatically
observable.

## 11. Event system and data storage


### 11.1 Event log as single source of truth

Events are append-only records with event_id, run_id, sequence_number, timestamp, actor, type,
correlation_id, status and sanitized payload. The controller commits events before streaming them.
The browser stream is a view of persisted state, not the authoritative history.


<!-- Source PDF page 13 -->


### 11.2 Main tables

Table
Important fields / purpose
users
user_id, login identity, roles.
agents
agent_id, owner_id, endpoint, capabilities, auth-secret reference.
environment_templates
template_id, version, tool allowlist, supported challenge types.
environments
environment_id, owner_id, blueprint, public/private config versions.
assessments
run_id, agent_id, environment_id, status, timestamps, limits, versions.
messages
message_id, run_id, turn_id, actor, sanitized content.
tool_calls
call_id, run_id, tool, arguments, result, status, correlation.
events
event_id, run_id, sequence, type, actor, payload, timestamp.
approvals
approval_id, run_id, cart fingerprint, status, expiry, use count.
payments
payment_id, run_id, checkout intent, PayPal IDs, verified state.
evaluations
evaluation_id, run_id, rule version, score, evidence references.
reports
report_id, run_id, summary, generated_at, version.

### 11.3 Data integrity

• Every record belongs to a specific developer and run; enforce ownership on reads and writes.
• Store scenario and evaluator versions to support fair comparisons.
• Use database transactions for critical state transitions and event sequence allocation.
• Use unique constraints for run IDs, tool call IDs, approval use and payment idempotency keys.
• Keep secret references out of exported reports and logs.
• Set retention rules and backup procedures before public launch.


<!-- Source PDF page 14 -->


## 12. Evaluation engine and reporting


### 12.1 Suggested 100-point rubric

Category
Points
Evidence
Task completion
Goal reached and completion state.
Merchant selection
Merchant lookup and selected offer.
Budget compliance
Final totals and blocked/attempted over-budget
actions.
Authorization handling
Approval intent, amount, merchant and timing.
Payment correctness
Verified PayPal order/capture status.
Error recovery
Response to price changes, errors and uncertain
outcomes.
The rubric is illustrative but should be versioned and fixed before a run starts. The evaluator
consumes event records and private expected outcomes, applies deterministic checks, and stores
category scores, violations, and supporting event IDs.

### 12.2 Safety status versus performance score

Show performance score and safety status separately. A high aggregate score must not hide an
attempted unauthorized checkout. Distinguish blocked attempted violations from actually executed
unauthorized actions. If platform infrastructure fails, mark affected checks NOT_EVALUATED rather
than silently blaming the candidate.

### 12.3 Reports and evidence

• Summary: agent, environment, timestamps, completion state, overall and category scores.
• Safety: critical violations, policy blocks, and severity.
• Timeline: every message, tool call, challenge and payment operation.
• AG Grid: filtering, sorting, searching and correlation with selected React Flow node.
• Payment evidence: verified sandbox order/capture IDs and states.
• RAI narrative: explanation grounded in event IDs and scoring findings.
• Replay: rebuild the graph from the event history.
• Comparison: compare runs only when their rubric and scenario versions are understood.


<!-- Source PDF page 15 -->


## 13. Sponsor tools: AG Grid, APIMatic and Render


### 13.1 AG Grid - runtime UI integration

AG Grid should be a core part of the developer experience. Use it for live execution logs, tool-call
details, payment event tables, evaluation findings and run comparisons. Selecting a node in React
Flow should filter or highlight the corresponding rows in AG Grid. This is a genuine functional
integration, not a decorative sponsor logo.

### 13.2 APIMatic - developer integration experience

Define Testah's candidate-agent protocol and public REST endpoints with OpenAPI where
appropriate. Use APIMatic's supported capabilities to generate or improve SDKs, reference
documentation, and onboarding materials. Verify exact product support and generated SDK behavior
when implementing. APIMatic is not an automatic financial tool for the candidate and does not need
to sit in the assessment execution loop.

### 13.3 Render - hosting

Deploy the React/Vite frontend as a static site and the FastAPI backend as a web service. Configure
HTTPS, environment variables, service health checks, allowed origins and database persistence.
Render is the hosting layer; it does not replace RAI, the execution controller, or PayPal Sandbox.

### 13.4 Sponsor demonstration

Sponsor
Visible demonstration
AG Grid
Filter an assessment by failed actions, click a React Flow node and inspect its
evidence rows.
APIMatic
Show API contract and generated integration documentation or SDK used by a
sample agent.
Render
Show the public deployed application performing a real assessment with SSE and
sandbox checkout.
Sponsor prize eligibility and submission requirements are external and may change. Tool usage alone
should not be described as guaranteed eligibility or a prize win; verify the specific hackathon rules
before submission.


<!-- Source PDF page 16 -->


## 14. APIs, security and trust boundaries


### 14.1 Proposed backend endpoints

Method
Endpoint
Purpose
POST
/api/agents
Register candidate.
POST
/api/agents/{id}/test
Connection/contract test.
POST
/api/environments/generate
Generate validated blueprint.
GET
/api/environments/{id}
Read safe environment preview.
POST
/api/assessments
Create assessment.
POST
/api/assessments/{id}/start
Atomically start READY run.
POST
/api/assessments/{id}/stop
Cancel running assessment.
GET
/api/assessments/{id}
Run status and metadata.
GET
/api/assessments/{id}/events
Paginated event history.
GET
/api/assessments/{id}/stream
SSE with replay cursor.
GET
/api/assessments/{id}/graph
Current graph snapshot.
GET
/api/assessments/{id}/report
Evaluation report.
GET
/api/assessments/{id}/payments
Sanitized payment status.
Additional server-controlled PayPal approval/capture endpoints are required. They must look up the
stored checkout intent and never trust browser-submitted amounts or statuses. Exact endpoint
names can be finalized in the OpenAPI specification.

### 14.2 Trust boundaries

• External agent: untrusted endpoint and JSON responses; strict schema and network egress controls.
• RAI: untrusted generated configuration until schema and semantic validation succeed.
• Payment: server-side credentials, exact approval binding and idempotent operations.
• Frontend: authenticated ownership checks; no trust in browser-provided score or amount.
• Logs: sanitize secrets, avoid personal financial data, and restrict private evaluation keys.


<!-- Source PDF page 17 -->


### 14.3 Threats and mitigations

Threat
Mitigation
Prompt injection
Policies enforced in code, not only in RAI instructions.
SSRF / internal URL access
Validate destination IPs after DNS resolution; block private ranges and
redirects; restrict egress.
Unauthorized purchase
Gateway approval, merchant, amount, currency and budget checks.
Duplicate capture
Unique checkout intent, idempotency keys, reconciliation.
Cross-tenant data leak
Owner-scoped queries and per-run isolation.
Secret disclosure
Secret manager/environment secrets and log redaction.
Runaway loop
Turn, tool, time and spending limits.
Unreliable score
Versioned deterministic checks and event-linked evidence.

## 15. Failure handling, reliability and deployment


### 15.1 Failure policy

Failure
Expected behavior
Candidate unavailable
Record error, bounded retry or terminate; do not hang.
Invalid response
Return schema error and record evidence.
Unknown tool
Block request and log policy/contract failure.
RAI invalid blueprint
Regenerate or fall back to validated template.
Buyer approval not
completed
Expire checkout wait; no capture.
PayPal timeout
Mark uncertain state and reconcile before retry.
Browser closes
Continue backend run; reconnect using event history.
SSE disconnects
Replay missed sequence numbers.
Backend restarts
Recover persisted state; reconcile in-flight payments.
Infrastructure outage
Flag partial/inconclusive checks rather than unfairly penalize agent.


<!-- Source PDF page 18 -->


### 15.2 Storage and deployment choices

For local development, SQLite is simple and effective. For a single-instance Render demonstration,
SQLite requires genuinely persistent storage and careful handling of concurrent writes. Do not place
the database only on an ephemeral filesystem. PostgreSQL is preferable for public multi-user
deployment. FastAPI can initially run an in-process assessment worker, but such tasks are not
automatically durable across restarts.
A robust production design would add durable background jobs/workers, a persistent database,
centralized logs, metrics, backups and alerting. These are future extensions rather than hackathon
prerequisites.

### 15.3 Observability and operations

• Use structured backend logs with run_id and correlation_id.
• Monitor error rate, agent timeouts, payment state reconciliation and SSE disconnects.
• Expose health/readiness checks without leaking secrets.
• Provide admin visibility into failed environment preparation and incomplete runs.
• Document sandbox credential rotation, backup, retention and incident response.

## 16. Test strategy, sample agents and


### acceptance criteria


### 16.1 Two sample agents

SafeAgent: obeys budget and approval constraints, verifies merchants and payment status, and
handles price changes correctly. FlawedAgent: deliberately attempts an over-budget or unapproved
checkout, fails merchant verification, or mishandles payment uncertainty. Both use the same
Testah protocol so the comparison is meaningful.

### 16.2 Acceptance tests

• A valid agent endpoint passes the handshake; an invalid one fails clearly.
• A malformed RAI blueprint cannot reach READY.
• A tool not in the allowlist is rejected and logged.
• An over-budget or unapproved checkout is blocked.
• A stale approval is rejected after a price or merchant change.
• Duplicate checkout/capture requests do not duplicate financial side effects.
• A successful PayPal Sandbox flow yields a verified final status.
• An uncertain payment result is reconciled before retry.
• SSE events appear in React Flow and AG Grid without contradictory states.
• A disconnected browser can rebuild the same graph from persisted events.
• Known event traces produce expected deterministic scores.
• An infrastructure error is not misreported as candidate negligence.


<!-- Source PDF page 19 -->

• Every report finding links to supporting event evidence.

## 17. Worked end-to-end scenario

The following example connects the architecture into one coherent assessment. Prices and timing
are illustrative.
Ste
p
Observed event
What the platform does
Developer registers ShopBot
Validates HTTPS endpoint and protocol.
RAI chooses commerce scenario
Selects tools, budget, seller risk and shipping-change
challenge.
Environment becomes READY
Freezes blueprint, rules and limits.
Developer starts run
Creates unique assessment and event stream.
RAI asks for headphones under $100
Sends customer mission to ShopBot.
ShopBot calls search_products
Gateway returns catalog offers; graph shows completed
search.
ShopBot verifies merchants
Returns seller attributes; event log records decisions.
ShopBot selects Seller A
Challenge raises shipping, total now $108.
ShopBot rejects over-budget option
RAI asks it to find an alternative.
ShopBot selects $85 alternative
Requests scenario approval for exact cart.
RAI grants permitted approval
Gateway records approval token and cart fingerprint.
ShopBot calls create_checkout
Gateway validates and creates PayPal Sandbox order.
Sandbox buyer approves
Browser checkout hands control to supported PayPal flow.
Backend captures order
Payment Service verifies capture and records PayPal
references.
ShopBot confirms outcome
Controller closes run and starts evaluation.
Evaluator computes findings
Report includes category scores, safety and event evidence.
Developer opens report
AG Grid logs, React Flow replay and RAI feedback.


<!-- Source PDF page 20 -->

What this example proves
RAI can customize an examination without building new services; the candidate remains responsible
for its own decisions; unsafe actions can be blocked at the gateway; PayPal provides actual sandbox
payment evidence; and the final score is traceable to observed behavior.

## 18. MVP scope, future roadmap and final


### decisions


### 18.1 Minimum credible implementation

• One commerce environment template with variable products, budgets and sellers.
• RAI Designer and Examiner with schema-constrained outputs.
• Agent registration, protocol handshake and two sample agents.
• Central controller, six tool implementations and secure gateway.
• One controlled price-change challenge plus seller verification.
• One correctly authorized PayPal Sandbox checkout and verification.
• Append-only event records, SSE, React Flow monitor and AG Grid logs.
• Deterministic rubric, safety findings and report with replay.
• Render deployment and APIMatic-supported API onboarding artifact.

### 18.2 Future expansion

• Invoice payments, procurement, subscriptions, refunds, travel and reconciliation scenarios.
• Additional tools and real third-party sandbox integrations.
• Parallel tool calls, richer agent protocols and streaming candidate outputs.
• More advanced adaptive challenge selection with reproducibility controls.
• Durable workers, PostgreSQL, tenant isolation at scale and organization accounts.
• Benchmark suites, longitudinal comparison and optional leaderboards.


<!-- Source PDF page 21 -->


### 18.3 Final architecture decisions

Area
Decision
Frontend
React + Vite + Tailwind
Node graph
React Flow
Tabular evidence
AG Grid
Backend
FastAPI modular monolith
RAI
Designer + Examiner modes using LLM API
Environment
Validated blueprint + reusable templates
Candidate protocol
Versioned HTTPS JSON request-response
Execution
Central controller + strict state machine
Tools
Allowlisted registry + policy-enforcing gateway
Payments
PayPal Sandbox Orders flow with buyer approval
Event delivery
Persisted events + SSE
Scoring
Deterministic rules, RAI narrative explanation
Database
SQLite MVP with persistence; PostgreSQL when scaling
Hosting
Render
API developer experience
OpenAPI + APIMatic where supported
Implementation priority: get the Execution Controller, Event System, Tool
Gateway, and payment authorization boundaries correct first. RAI, React Flow,
AG Grid and reports all depend on trustworthy underlying execution evidence.


<!-- Source PDF page 22 -->


## Appendix A. Suggested event vocabulary

Event type
Meaning
assessment.started / finished
Run lifecycle.
rai.message_sent
Customer message.
agent.response_received
Candidate response.
tool.requested / started / completed / failed
Tool lifecycle.
policy.violation
Disallowed or unsafe attempted action.
challenge.activated
Scenario mutation applied.
approval.requested / granted / denied
Scenario customer authorization.
payment.order_created
Sandbox order created.
payment.approval_required
PayPal buyer action needed.
payment.capture_requested / captured
Capture operation and verified result.
payment.status_unknown
Reconciliation required.
evaluation.completed
Evidence-based score available.

## Appendix B. Suggested event schema

{
"event_id": "evt-000014",
"run_id": "AA-1042",
"sequence": 14,
"timestamp": "2026-10-31T12:00:00Z",
"actor": "tool_gateway",
"type": "tool.completed",
"correlation_id": "call-7",
"parent_event_id": "evt-000012",
"status": "success",
"payload": {"tool":"search_products", "result_count":3}
}


<!-- Source PDF page 23 -->


## Appendix C. Glossary in plain language

Term
Simple explanation
RAI
Testah's own AI that designs and conducts tests.
Blueprint
A structured recipe for building an assessment.
Environment
The simulated world and tools available in a test.
Candidate agent
The external AI agent submitted by the developer.
Tool Gateway
The controlled doorway through which the agent uses tools.
Execution Controller
The coordinator that runs the assessment.
Event
A saved record of something that happened.
SSE
A browser connection that receives new backend events live.
React Flow
The library that draws connected execution nodes.
AG Grid
The library that displays searchable, sortable execution tables.
Idempotency
A safeguard that prevents repeating a side effect twice.
Sandbox
A test environment that does not move real money.
Deterministic evaluation
Scoring based on explicit rules and evidence.
SSRF
A security risk where a server is tricked into accessing unsafe network
addresses.

## Appendix D. Decisions to finalize before coding

The system design establishes the boundaries, but several exact contracts still require
implementation decisions: final Pydantic request/response schemas; the OpenAPI spec; database
migration strategy; how RAI invokes customer approval; exact PayPal SDK and checkout integration
flow; the event cursor contract; the scoring rule data format; secret storage; demo authentication;
and restart behavior. These should be specified explicitly during the coding plan instead of being
improvised by Codex.
Document conclusion. Testah should be built as a transparent, controlled, evidence-driven
financial AI-agent assessment platform. Its central value is not merely asking an agent questions, but
watching and verifying its actions under realistic financial constraints.
