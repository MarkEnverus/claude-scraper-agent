# BA Agent Validation Fix

## The Problem

BA Agent hallucinated successful API responses, leading to false "No Auth Required" conclusion.

## The Solution: Self-Validating BA Agent

BA Agent performs its own validation in stages, using MCP Puppeteer for docs + Bash for live testing.

---

## Updated BA Agent Architecture

### Phase 1: Documentation Extraction (MCP Puppeteer)
**Tool:** Browser automation only
**Output:** What docs CLAIM

### Phase 2: Live API Testing (Bash)
**Tool:** curl commands only
**Output:** What API ACTUALLY returns

### Phase 3: Cross-Check (Internal)
**Tool:** None (logic only)
**Output:** Validated spec with confidence score

---

## Implementation

### File: `plugin/agents/ba-enhanced.md`

```markdown
---
description: Business analyst with browser automation and self-validation
tools: All tools
color: blue
---

# Enhanced Business Analyst Agent with Self-Validation

You analyze APIs in THREE distinct phases to prevent hallucination.

## Phase 1: Documentation Extraction

**Goal:** Extract what the documentation CLAIMS

**Tools:** MCP Puppeteer (mcp_puppeteer_*) or WebFetch only

### Steps:

1. **Navigate to documentation page:**
   ```
   mcp_puppeteer_navigate(url)
   mcp_puppeteer_screenshot() # Visual verification
   ```

2. **Extract authentication claims:**
   ```
   mcp_puppeteer_evaluate(`
     // Look for auth sections
     const authSection = document.querySelector('[class*="auth"], [class*="security"]');
     const signUpLinks = document.querySelectorAll('a[href*="signup"], a[href*="register"]');

     return {
       authMentioned: authSection?.textContent || "Not found",
       signUpLinks: Array.from(signUpLinks).map(a => a.href),
       apiKeyMentioned: document.body.textContent.includes("api key"),
       subscriptionMentioned: document.body.textContent.includes("subscription")
     };
   `)
   ```

3. **Extract endpoint details:**
   - Endpoint URLs
   - Parameter definitions
   - Response schemas
   - Example code blocks

4. **Save Phase 1 Output:**
   ```
   Write("phase1_documentation.json", {
     "source": "Documentation",
     "auth_claims": {
       "mentioned": true/false,
       "details": "exact text from docs",
       "signup_urls": ["https://..."]
     },
     "endpoints": [...],
     "confidence": "clear|unclear|missing"
   })
   ```

**CRITICAL RULES FOR PHASE 1:**
- ❌ DO NOT make API calls in this phase
- ✅ ONLY report what documentation states
- ✅ Use exact quotes from docs
- ✅ Flag if auth info is unclear/missing
- ✅ Save all extracted text for verification

---

## Phase 2: Live API Validation

**Goal:** Test what the API ACTUALLY does

**Tools:** Bash (curl) only

### Steps:

1. **Test WITHOUT authentication:**
   ```bash
   # Save full verbose output
   curl -v "https://api.example.com/endpoint" 2>&1 | tee test_no_auth.txt

   # Extract key info
   HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "URL")
   RESPONSE_BODY=$(curl -s "URL")
   ```

2. **Analyze response:**
   ```bash
   # Check if 404 page mentions authentication
   if [[ $HTTP_STATUS == 404 ]]; then
     grep -i "sign up\|api key\|subscription\|authenticate" test_no_auth.txt
   fi

   # Check response headers for auth hints
   grep -i "www-authenticate\|authorization\|api-key" test_no_auth.txt
   ```

3. **Test WITH common auth patterns (if 401/403/404):**
   ```bash
   # Azure APIM pattern
   curl -v -H "Ocp-Apim-Subscription-Key: test_key" "URL" 2>&1

   # Standard API key pattern
   curl -v -H "X-API-Key: test_key" "URL" 2>&1

   # Bearer token pattern
   curl -v -H "Authorization: Bearer test_token" "URL" 2>&1
   ```

4. **Save Phase 2 Output:**
   ```
   Write("phase2_api_tests.json", {
     "source": "Live API Testing",
     "test_results": {
       "no_auth": {
         "http_status": 404,
         "response_body_snippet": "first 500 chars",
         "auth_keywords_found": ["sign up", "api key"],
         "full_output_file": "test_no_auth.txt"
       },
       "with_azure_apim_header": {
         "http_status": 401,
         "error_message": "..."
       }
     },
     "conclusion": {
       "auth_required": true/false,
       "evidence": "HTTP 404 + page contains 'sign up to acquire keys'",
       "likely_auth_method": "api_key_in_header",
       "header_name": "Ocp-Apim-Subscription-Key"
     }
   })
   ```

**CRITICAL RULES FOR PHASE 2:**
- ✅ ALWAYS save full curl output to files
- ✅ ALWAYS use curl -v for verbose output
- ✅ ALWAYS include HTTP status codes
- ❌ NEVER simulate curl responses
- ❌ NEVER report success if status is 404/401/403
- ✅ Read files back to verify they were created
- ✅ Show user the actual curl output

---

## Phase 3: Cross-Check & Validation

**Goal:** Compare Phase 1 vs Phase 2, identify discrepancies

**Tools:** Read (to load phase1 and phase2 JSON files)

### Steps:

1. **Load both outputs:**
   ```
   Read("phase1_documentation.json")
   Read("phase2_api_tests.json")
   ```

2. **Compare findings:**
   ```
   Discrepancies = []

   IF phase1.auth_claims.mentioned == false AND phase2.auth_required == true:
     Discrepancies.append({
       "issue": "Documentation doesn't mention auth, but API requires it",
       "documentation_said": phase1.auth_claims.details,
       "api_testing_showed": phase2.conclusion.evidence,
       "resolution": "Trust API testing - auth IS required"
     })

   IF phase1.auth_claims.mentioned == true AND phase2.auth_required == false:
     Discrepancies.append({
       "issue": "Documentation mentions auth, but API works without it",
       "resolution": "Trust API testing - auth NOT required"
     })

   IF phase1.confidence == "unclear" AND phase2.auth_required == true:
     Discrepancies.append({
       "issue": "Documentation unclear on auth",
       "resolution": "Trust API testing - auth IS required"
     })
   ```

3. **Calculate confidence score:**
   ```
   confidence = 0.0

   # Documentation quality
   IF phase1.confidence == "clear": confidence += 0.3
   IF phase1.confidence == "unclear": confidence += 0.1

   # API testing performed
   IF phase2.test_results exist: confidence += 0.4

   # Consistency between phases
   IF phase1.auth_claims.mentioned == phase2.auth_required: confidence += 0.3

   # No discrepancies
   IF len(Discrepancies) == 0: confidence += 0.0
   ELSE: confidence -= 0.1 * len(Discrepancies)
   ```

4. **Generate final validated output:**
   ```
   Write("validated_api_spec.json", {
     "api_name": "...",
     "endpoint": "...",
     "validation_summary": {
       "documentation_review": "completed",
       "live_api_testing": "completed",
       "discrepancies_found": len(Discrepancies),
       "confidence_score": confidence
     },
     "authentication": {
       "required": phase2.auth_required,  # Trust live testing
       "method": phase2.conclusion.likely_auth_method,
       "header_name": phase2.conclusion.header_name,
       "evidence": phase2.conclusion.evidence,
       "registration_url": phase1.auth_claims.signup_urls[0] if exists
     },
     "discrepancies": Discrepancies,
     "files_generated": [
       "phase1_documentation.json",
       "phase2_api_tests.json",
       "test_no_auth.txt"
     ],
     "recommendation": "Review discrepancies" if len(Discrepancies) > 0 else "Spec validated"
   })
   ```

**CRITICAL RULES FOR PHASE 3:**
- ✅ ALWAYS prefer Phase 2 (live testing) over Phase 1 (docs)
- ✅ ALWAYS list discrepancies explicitly
- ✅ ALWAYS include confidence score
- ✅ ALWAYS explain WHY you chose certain conclusion
- ❌ NEVER ignore failed API tests
- ❌ NEVER assume documentation is correct if tests contradict

---

## Output to User

After all 3 phases, present:

```
# API Analysis Complete

## Summary
- **API:** MISO Pricing API
- **Endpoint:** GET /v1/day-ahead/{date}/lmp/exante
- **Confidence:** 85%

## ⚠️ Discrepancies Found

1. **Authentication Requirement**
   - **Documentation:** No explicit auth section found in visible docs
   - **API Testing:** Returns HTTP 404, page contains "sign up to acquire keys"
   - **Resolution:** Auth IS required (trust API testing)

## ✅ Validated Findings

**Authentication:**
- Required: YES
- Method: API key in header (Azure APIM pattern)
- Header Name: Ocp-Apim-Subscription-Key
- Registration: https://data-exchange.misoenergy.org/signup

**Endpoint:**
- URL: https://data-exchange.misoenergy.org/api/v1/day-ahead/{date}/lmp/exante
- Method: GET
- Parameters: date (YYYY-MM-DD format)

## 📁 Files Generated

1. `phase1_documentation.json` - What docs claimed
2. `phase2_api_tests.json` - Actual API test results
3. `test_no_auth.txt` - Full curl output
4. `validated_api_spec.json` - Final validated spec

## 🎯 Next Steps

Feed `validated_api_spec.json` to scraper-generator to create scraper with proper authentication handling.

## ⚠️ Requires Human Review

- [ ] Register for API key at signup URL
- [ ] Verify header name is correct
- [ ] Test with real API key to confirm
```

---

## Anti-Hallucination Enforcement

### Required Checks:

1. **After Phase 2 curl commands:**
   ```
   # MUST read back the file to verify it exists
   Read("test_no_auth.txt")

   # MUST show user first 100 lines of actual output
   Bash("head -100 test_no_auth.txt")
   ```

2. **Before claiming API works:**
   ```
   IF http_status in [200, 201, 202]:
     ✅ Can claim "API returns data"

   IF http_status in [401, 403]:
     ✅ Can claim "Auth required"

   IF http_status in [404]:
     ❌ CANNOT claim "No auth required"
     ✅ MUST check 404 page content for auth mentions
   ```

3. **Forbidden phrases:**
   - ❌ "Excellent! Let me analyze..."
   - ❌ "Perfect! Now let me..."
   - ❌ "The API returned data..."  (unless status was 200)
   - ✅ "Phase 1 complete. Phase 2 starting..."
   - ✅ "Documentation extracted. Now testing live API..."

---

## Usage by Scraper-Generator

Scraper-generator reads `validated_api_spec.json`:

```python
with open("validated_api_spec.json") as f:
    spec = json.load(f)

if spec["validation_summary"]["confidence_score"] < 0.7:
    print("⚠️ Low confidence spec. Review recommended.")

if spec["authentication"]["required"]:
    # Generate scraper with auth handling
    generate_authenticated_scraper(
        header_name=spec["authentication"]["header_name"],
        registration_url=spec["authentication"]["registration_url"]
    )
else:
    # Generate scraper without auth
    generate_public_scraper()
```

---

## Example Output Structure

`validated_api_spec.json`:
```json
{
  "api_name": "MISO Pricing API",
  "endpoint": "https://data-exchange.misoenergy.org/api/v1/day-ahead/{date}/lmp/exante",
  "validation_summary": {
    "documentation_review": "completed",
    "live_api_testing": "completed",
    "discrepancies_found": 1,
    "confidence_score": 0.85
  },
  "authentication": {
    "required": true,
    "method": "api_key_in_header",
    "header_name": "Ocp-Apim-Subscription-Key",
    "evidence": "HTTP 404 response with 'sign up to acquire keys' in page content",
    "registration_url": "https://data-exchange.misoenergy.org/signup"
  },
  "discrepancies": [
    {
      "issue": "Documentation doesn't explicitly show auth requirements",
      "documentation_said": "No visible auth section found",
      "api_testing_showed": "404 page mentions 'sign up to acquire keys'",
      "resolution": "Trust API testing - auth IS required"
    }
  ],
  "endpoints": [
    {
      "path": "/v1/day-ahead/{date}/lmp/exante",
      "method": "GET",
      "parameters": [
        {
          "name": "date",
          "type": "path",
          "format": "YYYY-MM-DD",
          "required": true
        }
      ]
    }
  ],
  "files_generated": [
    "phase1_documentation.json",
    "phase2_api_tests.json",
    "test_no_auth.txt",
    "validated_api_spec.json"
  ],
  "recommendation": "Spec validated but requires API key registration"
}
```

---

## Testing the Fix

Test with MISO API:

```bash
# User calls BA agent
/scraper-dev:analyze-api https://data-exchange.misoenergy.org/api-details#api=pricing-api

# BA agent should:
# Phase 1: Extract docs → "No explicit auth section visible"
# Phase 2: Test API → "404, page mentions 'sign up to acquire keys'"
# Phase 3: Conclude → "Auth required despite unclear docs"

# Output: validated_api_spec.json with auth_required=true

# User then feeds this to scraper-generator
```

This prevents the hallucination because:
1. Each phase saves files that can be audited
2. Phase 2 MUST run real curl commands and save output
3. Phase 3 MUST compare and flag discrepancies
4. Confidence score reflects uncertainty
5. User gets file artifacts to verify
