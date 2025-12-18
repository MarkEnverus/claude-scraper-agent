# Bedrock Agent Core Strategy for Autonomous Scraper Platform

## Executive Summary

**Decision: Use Agent Core for AI agents, K8s for scrapers**

Agent Core is purpose-built for hosting autonomous AI agents that monitor, fix, and maintain code. Our scrapers run in K8s; our AI maintenance agents run in Agent Core.

---

## Architecture Overview

### Data Collection Layer (K8s)
- **Scrapers**: Docker containers running Python scraper code
- **Orchestration**: K8s CronJobs/Jobs for scheduling
- **Storage**: S3 (data), Redis (hash registry), Kafka (notifications)
- **Execution**: On-demand or scheduled collection runs

### AI Agent Layer (Agent Core)
- **scraper-generator**: Creates new scrapers from API specs
- **scraper-fixer**: Diagnoses and repairs broken scrapers
- **scraper-updater**: Migrates scrapers to new infrastructure versions
- **code-quality-checker**: Validates mypy, ruff, pytest compliance
- **ba-enhanced**: Analyzes API documentation with browser automation

---

## Why Agent Core for AI Agents

| Feature | Our Need | How Agent Core Helps |
|---------|----------|---------------------|
| **Runtime** | Run AI agents on-demand when issues detected | Serverless, no idle costs, fast cold start |
| **Memory** | Track recurring scraper issues, fix history | Persistent memory across agent sessions |
| **Observability** | Audit what fixes agents applied and why | Full trace of agent reasoning + CloudWatch metrics |
| **Gateway** | Agents need K8s API, GitHub API, S3 access | Converts APIs to agent-compatible tools |
| **Policy** | Prevent agents from deploying without review | Define boundaries (e.g., require PR approval) |
| **Multi-agent** | BA agent → generator → quality checker pipeline | Coordinate multiple agents in workflows |
| **Identity** | Secure access to GitHub, K8s, AWS resources | IAM integration, session isolation |

---

## Autonomous Workflow Example

### Scenario: Scraper Fails in K8s

1. **Detection & Alerting**
   - Scraper pod fails in K8s
   - CloudWatch alarm triggers
   - EventBridge rule invokes Agent Core

2. **Diagnosis** (scraper-fixer agent)
   - Agent reads K8s pod logs via Gateway
   - Agent checks Redis hash registry for duplicate issues
   - Agent uses Memory to recall similar past failures
   - Agent identifies root cause (e.g., API schema change)

3. **Fix Generation**
   - Agent generates code fix
   - Agent validates fix locally (dry run)
   - Agent commits fix to branch

4. **Quality Validation** (code-quality-checker agent)
   - Multi-agent handoff via Agent Core
   - Runs mypy type checking
   - Runs ruff style validation
   - Runs pytest unit tests
   - Reports validation results

5. **Deployment Decision**
   - **High confidence (>95%)**: Auto-deploy to K8s
   - **Medium confidence (70-95%)**: Create GitHub PR for review
   - **Low confidence (<70%)**: Alert human engineer

6. **Learning & Memory**
   - Agent stores fix pattern in Memory
   - Future similar issues resolved faster
   - Pattern recognition improves over time

---

## Integration Architecture

```
┌─────────────────────────────────────────────────┐
│ K8s Cluster (Data Collection)                   │
│  - Scraper pods (Docker containers)             │
│  - CronJobs for scheduling                      │
│  - ConfigMaps for scraper configs               │
└─────────────────┬───────────────────────────────┘
                  │ (failures, metrics)
                  ↓
┌─────────────────────────────────────────────────┐
│ AWS CloudWatch                                   │
│  - Pod failure alarms                           │
│  - Data freshness metrics                       │
│  - Error rate thresholds                        │
└─────────────────┬───────────────────────────────┘
                  │ (alarm triggers)
                  ↓
┌─────────────────────────────────────────────────┐
│ AWS EventBridge                                  │
│  - Route alarms to correct agents               │
│  - Filter by scraper type, error class          │
└─────────────────┬───────────────────────────────┘
                  │ (invoke agent)
                  ↓
┌─────────────────────────────────────────────────┐
│ Bedrock Agent Core Runtime                      │
│                                                  │
│  ┌──────────────────────────────────────┐      │
│  │ AI Agents (Serverless)               │      │
│  │  - scraper-fixer                     │      │
│  │  - scraper-generator                 │      │
│  │  - code-quality-checker              │      │
│  │  - scraper-updater                   │      │
│  │  - ba-enhanced                       │      │
│  └───────────────┬──────────────────────┘      │
│                  │ (uses tools via Gateway)     │
│  ┌───────────────┴──────────────────────┐      │
│  │ Gateway (Tool Integration)           │      │
│  │  - K8s API (logs, restart, deploy)   │      │
│  │  - GitHub API (PRs, commits)         │      │
│  │  - S3 (read/write scraper code)      │      │
│  │  - Redis (hash registry queries)     │      │
│  │  - Kafka (send notifications)        │      │
│  └──────────────────────────────────────┘      │
│                                                  │
│  ┌──────────────────────────────────────┐      │
│  │ Memory (Cross-Agent Learning)        │      │
│  │  - Fix patterns by error type        │      │
│  │  - Success rate per fix strategy     │      │
│  │  - API schema evolution history      │      │
│  └──────────────────────────────────────┘      │
│                                                  │
│  ┌──────────────────────────────────────┐      │
│  │ Policy (Safety Boundaries)           │      │
│  │  - Require PR for prod deployments   │      │
│  │  - Auto-deploy only if confidence>95%│      │
│  │  - Never delete data without approval│      │
│  └──────────────────────────────────────┘      │
│                                                  │
│  ┌──────────────────────────────────────┐      │
│  │ Observability (CloudWatch)           │      │
│  │  - Agent invocation traces           │      │
│  │  - Fix success/failure rates         │      │
│  │  - Token usage and costs             │      │
│  └──────────────────────────────────────┘      │
└─────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Manual + Agent Core (Weeks 1-4)
**Goal:** Deploy agents to Agent Core, validate functionality

**Tasks:**
1. Migrate existing agents to Agent Core Runtime
   - Package agents as Agent Core compatible format
   - Test agent invocation and response
2. Configure Gateway for tool access
   - K8s API (read logs, get pod status)
   - GitHub API (read repos, create branches)
   - S3 (read/write scraper code)
   - Redis (query hash registry)
3. Manual agent triggering
   - Create CLI tool to invoke agents
   - Test on real scraper failures
4. Build confidence
   - Review agent decisions
   - Validate fix quality
   - Measure success rate

**Success Criteria:**
- All 5 agents deployed to Agent Core ✓
- Gateway configured for all required APIs ✓
- 10+ manual agent invocations successful ✓
- Agent fix success rate >80% ✓

### Phase 2: Semi-Autonomous (Weeks 5-8)
**Goal:** Automatic triggering, human approval for deployments

**Tasks:**
1. EventBridge integration
   - Configure CloudWatch alarms for scraper failures
   - Create EventBridge rules to invoke agents
   - Test automatic agent triggering
2. PR-based deployment flow
   - Agents create GitHub PRs for fixes
   - Human reviews and approves
   - Merge triggers K8s deployment
3. Memory implementation
   - Store fix patterns by error type
   - Track which fixes work consistently
   - Use historical data for faster diagnosis
4. Observability dashboard
   - CloudWatch dashboard for agent metrics
   - Alert on agent failures
   - Track cost per fix

**Success Criteria:**
- Agents auto-triggered by failures ✓
- 100% of fixes go through PR review ✓
- Fix patterns stored in Memory ✓
- Observability dashboard operational ✓

### Phase 3: Full Autonomy (Weeks 9-12)
**Goal:** High-confidence fixes auto-deploy, minimal human intervention

**Tasks:**
1. Policy-based auto-deployment
   - Define confidence threshold (>95%)
   - Auto-deploy high-confidence fixes
   - Create PR for medium confidence (70-95%)
   - Alert human for low confidence (<70%)
2. Multi-agent coordination
   - BA agent → generator → quality checker pipeline
   - Automatic new scraper generation from API changes
   - End-to-end autonomous workflow
3. Self-improvement loop
   - Track fix success rate by confidence level
   - Adjust confidence thresholds based on outcomes
   - Agents learn from past mistakes via Memory
4. Scale testing
   - Test with 100+ scrapers
   - Validate cost model at scale
   - Optimize agent performance

**Success Criteria:**
- >50% of fixes auto-deployed without review ✓
- Agent fix success rate >90% ✓
- Multi-agent pipelines working end-to-end ✓
- System handles 100+ scrapers autonomously ✓

---

## Key Agent Core Features We'll Use

### 1. Runtime
- **Serverless execution**: No idle compute costs
- **Fast cold starts**: Agents respond to failures quickly
- **Multi-agent coordination**: Chain agents together
- **Framework agnostic**: Use Claude, GPT, or custom models

### 2. Memory
- **Short-term memory**: Context within single agent session
- **Long-term memory**: Cross-session pattern storage
- **Shared memory**: Multiple agents access same knowledge
- **Use cases**:
  - Remember which API endpoints frequently break
  - Recall successful fix patterns by error type
  - Track scraper reliability over time

### 3. Gateway
- **API-to-tool conversion**: Make any API agent-accessible
- **Authentication**: Secure credential management
- **Rate limiting**: Prevent API abuse
- **Use cases**:
  - K8s API: Get logs, restart pods, deploy containers
  - GitHub API: Create PRs, commit code, merge branches
  - S3: Read scraper code, write fixes
  - Redis: Check hash registry for duplicates

### 4. Observability
- **Execution traces**: See every step agent takes
- **CloudWatch metrics**: Track invocations, latency, errors
- **Custom metrics**: Log fix success rate, confidence scores
- **Use cases**:
  - Audit what fixes agents applied
  - Debug agent reasoning errors
  - Measure ROI (cost per fix vs manual time)

### 5. Policy
- **Action boundaries**: Prevent destructive operations
- **Approval workflows**: Require human review for sensitive changes
- **Compliance**: Ensure agents follow company rules
- **Use cases**:
  - Never deploy to prod without review
  - Auto-deploy only if confidence >95%
  - Require approval for scraper deletion

### 6. Identity
- **IAM integration**: Use AWS roles for permissions
- **Session isolation**: Separate agent executions
- **Credential management**: Secure GitHub tokens, API keys
- **Use cases**:
  - Agents assume IAM role with K8s access
  - GitHub tokens stored securely
  - Audit trail of which agent did what

---

## Cost Analysis

### Agent Core Costs (Estimated)

**Assumptions:**
- 100 scrapers in production
- 10% failure rate per month
- Average 3 agent invocations per failure (fixer → quality checker → updater)

**Monthly Costs:**
- Agent invocations: 100 scrapers × 10% failure × 3 agents = 30 invocations/month
- Runtime cost: 30 × $0.30/invocation = **$9/month**
- Gateway API calls: 30 × 20 calls × $0.01 = **$6/month**
- Memory storage: 1 GB × $0.10 = **$0.10/month**
- CloudWatch observability: ~**$5/month**

**Total: ~$20/month** at 100 scrapers, 10% failure rate

**ROI Calculation:**
- Manual fix time: 30 min/failure × 10 failures = 5 hours/month
- Engineer cost: 5 hours × $100/hour = $500/month
- Agent Core cost: $20/month
- **Savings: $480/month** (96% cost reduction)

### Scaling Projections

| Scrapers | Monthly Failures (10%) | Agent Invocations | Est. Cost |
|----------|----------------------|-------------------|-----------|
| 100 | 10 | 30 | $20 |
| 500 | 50 | 150 | $60 |
| 1,000 | 100 | 300 | $110 |
| 5,000 | 500 | 1,500 | $500 |
| 10,000 | 1,000 | 3,000 | $950 |

**Cost remains <$1,000/month even at 10,000 scrapers**

---

## Technical Requirements

### Agent Core Setup

1. **AWS Account Configuration**
   - Enable Bedrock Agent Core in target region
   - Configure IAM roles for agent execution
   - Set up VPC connectivity if needed

2. **Agent Migration**
   - Convert existing agent markdown files to Agent Core format
   - Test agents in Agent Core sandbox
   - Validate tool calling works correctly

3. **Gateway Configuration**
   - Register K8s API endpoint
   - Register GitHub API endpoint
   - Register S3 access
   - Register Redis access
   - Configure authentication for each

4. **Memory Setup**
   - Define memory schemas (fix patterns, error types)
   - Configure memory retention policies
   - Test memory persistence across sessions

5. **Policy Definition**
   - Define auto-deploy confidence threshold
   - Create approval workflow for medium confidence
   - Set boundaries (no data deletion, no force push)

6. **Observability Configuration**
   - Create CloudWatch dashboard for agent metrics
   - Set up alarms for agent failures
   - Configure custom metrics (fix success rate)

### K8s Integration

1. **EventBridge Rules**
   - CloudWatch alarm → EventBridge → Agent Core
   - Filter by scraper type, error class
   - Pass relevant context to agent

2. **Agent Access to K8s**
   - IAM role with K8s API permissions
   - ServiceAccount for pod operations
   - RBAC rules for agent actions (read logs, restart pods, deploy)

3. **Deployment Pipeline**
   - Agent creates branch with fix
   - Agent runs tests locally
   - Agent creates PR or auto-merges
   - GitHub Actions deploys to K8s

---

## Success Metrics

### Agent Performance
- **Fix success rate**: % of agent-generated fixes that work
  - Target: >90% after Phase 3
- **Mean time to resolution (MTTR)**: Time from failure to fix deployed
  - Target: <15 minutes for high-confidence fixes
- **False positive rate**: % of fixes that break things further
  - Target: <5%

### Operational Efficiency
- **Human intervention rate**: % of failures requiring manual fix
  - Target: <10% after Phase 3
- **Cost per fix**: Agent Core cost / number of fixes
  - Target: <$5/fix
- **Engineering time saved**: Hours/month not spent on manual fixes
  - Target: 20+ hours/month at 100 scrapers

### Platform Reliability
- **Scraper uptime**: % of scrapers running without failures
  - Target: >95% after automated fixes
- **Data freshness**: % of scrapers collecting data on schedule
  - Target: >98%
- **Self-healing rate**: % of failures fixed autonomously
  - Target: >80%

---

## Risk Mitigation

### Risk 1: Agent Makes Bad Fix
**Mitigation:**
- Policy requires PR review for confidence <95%
- Quality checker agent validates all fixes
- Rollback mechanism if deployed fix fails
- Memory learns from bad fixes

### Risk 2: Agent Cost Exceeds Budget
**Mitigation:**
- Set AWS budget alerts
- Policy limits agent invocations per hour
- Optimize agent prompts to reduce token usage
- Monitor cost/fix metric weekly

### Risk 3: Agent Breaches Security
**Mitigation:**
- IAM roles with least-privilege access
- Policy prevents destructive operations
- Session isolation prevents cross-contamination
- Audit logs for all agent actions

### Risk 4: Agent Becomes Unavailable
**Mitigation:**
- Fallback to manual fixes if agent timeout
- Alert humans if agent fails 3+ times
- Redundant agent deployment across regions
- Keep manual fix procedures documented

---

## Next Steps

### Immediate (Week 1)
1. Enable Bedrock Agent Core in AWS account
2. Review Agent Core pricing and quotas
3. Design agent migration plan
4. Set up dev/test environment

### Short-term (Weeks 2-4)
1. Migrate first agent (scraper-fixer) to Agent Core
2. Configure Gateway for K8s API access
3. Test manual agent invocation
4. Validate fix quality on real failures

### Medium-term (Weeks 5-8)
1. Deploy all 5 agents to Agent Core
2. Configure EventBridge auto-triggering
3. Implement Memory for fix patterns
4. Create CloudWatch observability dashboard

### Long-term (Weeks 9-12)
1. Enable auto-deployment for high-confidence fixes
2. Implement multi-agent coordination
3. Scale to 100+ scrapers
4. Optimize based on production metrics

---

## Conclusion

**Bedrock Agent Core is the right platform for our autonomous scraper maintenance system.**

**Why:**
- Purpose-built for AI agent operations (not data collection)
- Serverless cost model aligns with usage patterns
- Memory enables learning and improvement
- Observability provides audit trail and debugging
- Policy ensures safety and compliance
- Gateway simplifies tool integration

**Architecture Decision:**
- **K8s**: Run scrapers (data collection workers)
- **Agent Core**: Run AI agents (code maintenance automation)
- **Clean separation of concerns**: Right tool for each job

**Expected Outcome:**
- 90%+ of scraper failures fixed autonomously
- 96% cost reduction vs manual fixes
- <15 minute mean time to resolution
- Platform scales to 10,000+ scrapers

**This is the future of autonomous data platforms.**
