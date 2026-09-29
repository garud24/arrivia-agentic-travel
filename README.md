# Agentic Travel Recommendations API

Proof of concept for arrivia's **AI Concierge**: a multi-tenant travel
recommendation service that AI agents can discover and invoke over **MCP
(Model Context Protocol)**. The service personalizes recommendations
from member travel history and loyalty tier while enforcing
**partner-specific rules deterministically on the server**.

-   **Backend:** Python, FastAPI, Pydantic, official MCP Python SDK
-   **Interfaces:** MCP tools, REST API, and a small CLI demo
-   **Upstreams:** mocked member data service and read-only partner
    configuration service
-   **Core safety property:** partner exclusions and recommendation caps
    are enforced in the shared service layer, not delegated to an LLM or
    client

## Quick Start

### Prerequisites

-   Python 3.12+
-   Node.js 18+ only if using MCP Inspector

### Install and test

``` bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements-lock.txt

pytest -q
```

The repository currently contains 20 tests covering recommendation
behavior, configuration failures, REST behavior, and MCP tool exposure.

## Run the Demo

### 1. CLI

``` bash
python cli.py member_001
python cli.py member_002
python cli.py member_003
```

Expected behavior:

-   `member_001` is Gold and belongs to `partner_bank_a`.
    Recommendations are capped at 3 and cruises are excluded.
-   `member_002` is Platinum and belongs to `partner_bank_b`. There is
    no recommendation cap and no category exclusion.
-   `member_003` belongs to a partner with no configuration. The request
    fails closed instead of returning unfiltered recommendations.

The CLI also works interactively:

``` bash
python cli.py
```

### 2. REST API

``` bash
uvicorn app.main:app --reload
```

Open Swagger UI at `http://127.0.0.1:8000/docs`.

Available endpoints:

  ----------------------------------------------------------------------------
  Endpoint                                 Purpose
  ---------------------------------------- -----------------------------------
  `GET /health`                            Health check

  `GET /api/members/{member_id}`           Retrieve mocked member profile

  `GET /api/recommendations/{member_id}`   Generate personalized,
                                           partner-compliant recommendations
  ----------------------------------------------------------------------------

Error behavior:

  Case                                         Status
  ------------------------------------------ --------
  Success                                       `200`
  Unknown member                                `404`
  Missing or invalid partner configuration      `503`

A missing or invalid partner configuration intentionally returns `503`:
without the partner's rules, the service cannot safely determine what is
allowed.

### 3. MCP Server

The MCP server runs over stdio. `mcp_config.json` launches it using the
project's virtual environment:

``` json
{
  "mcpServers": {
    "arrivia-travel": {
      "command": ".venv/bin/python",
      "args": ["-m", "app.mcp_server"]
    }
  }
}
```

Run MCP Inspector with the checked-in configuration:

``` bash
npx @modelcontextprotocol/inspector --config mcp_config.json --server arrivia-travel
```

Headless tool discovery:

``` bash
npx @modelcontextprotocol/inspector --cli \
  --config mcp_config.json \
  --server arrivia-travel \
  --method tools/list
```

Invoke the recommendation tool:

``` bash
npx @modelcontextprotocol/inspector --cli \
  --config mcp_config.json \
  --server arrivia-travel \
  --method tools/call \
  --tool-name get_travel_recommendations \
  --tool-arg member_id=member_001
```

The MCP server exposes:

  -----------------------------------------------------------------------------
  MCP tool                                  Purpose
  ----------------------------------------- -----------------------------------
  `get_member_profile(member_id)`           Returns loyalty tier, partner ID,
                                            and recent travel history

  `get_travel_recommendations(member_id)`   Returns personalized
                                            recommendations after partner rules
                                            are enforced, including an
                                            `applied_rules` summary
  -----------------------------------------------------------------------------

Both MCP tools call the same application services used by the REST API
and CLI. The MCP layer translates expected domain failures into
`ToolError` so an agent receives a useful error rather than a raw
implementation exception.

## Project Layout

``` text
app/
  main.py                      FastAPI application and /health
  api/
    routes.py                  REST endpoints and HTTP error mapping
  mcp_server.py                MCP tools and ToolError mapping
  services/
    recommendation_service.py  personalization and partner-rule enforcement
    member_service.py          mocked member-data client
    partner_service.py         read-only partner-config client and validation
    errors.py                  typed domain errors
  models/
    schemas.py                 Pydantic contracts
  mocks/
    data.py                    mocked members and partner configurations

cli.py                         command-line demo
tests/
  test_recommendations.py      service/rule/personalization tests
  test_interfaces.py           REST and MCP interface tests
mcp_config.json                MCP Inspector configuration
requirements.txt               dependency ranges
requirements-lock.txt          tested dependency versions
```

------------------------------------------------------------------------

# Section A: Architecture & Trade-offs

## Architecture Overview

``` text
                         AI Agent / AI Concierge
                                  |
                                  | MCP (stdio for PoC)
                                  v
                           app/mcp_server.py
                                  |
                                  |
Partner Portal / Ops ---> app/api/routes.py
        CLI -----------+
                       |
                       v
             RecommendationService
                       |
          +------------+-------------+
          |                          |
          v                          v
   MemberService              PartnerConfigService
   mocked upstream            mocked, read-only
          |                          |
          +------------+-------------+
                       |
                       v
             1. Load member
             2. Load + validate partner config
             3. Personalize candidate catalog
                - loyalty-tier eligibility
                - skip visited destinations
                - rank previously booked categories first
             4. Enforce partner exclusions
             5. Enforce partner cap
             6. Return recommendations + applied_rules
```

The MCP server, REST API, and CLI are thin interfaces over one
recommendation service. Business rules therefore have one enforcement
path: an AI agent cannot bypass an exclusion simply because it used MCP
instead of REST.

Personalization is deterministic in this PoC. Candidates can require a
minimum loyalty tier, destinations already present in the member's
travel history are skipped, and categories the member previously booked
are ranked first. Partner policy is applied **after personalization**.
This ordering ensures that a future ranking implementation cannot
reintroduce a category the partner forbids.

Every recommendation response includes `applied_rules`, showing the
configured cap, excluded categories, and counts removed by exclusion and
by cap. The same information is written to application logs for
production diagnosis.

## Design Trade-offs

### 1. Enforce partner rules in code, not in the AI agent

An alternative would be to give the partner configuration to an LLM and
instruct it to obey the rules. That would make the agent more flexible,
but contractual restrictions should not depend on probabilistic model
behavior. The service therefore filters recommendations
deterministically before returning them.

The trade-off is reduced agent flexibility. That is intentional: the
partner configuration is the source of truth.

### 2. Fail closed when partner configuration is unavailable or invalid

If a partner configuration is missing or fails Pydantic validation, the
service raises a typed domain error. REST translates that condition to
`503`; MCP translates it to `ToolError`.

This sacrifices some availability during a configuration outage, but
avoids returning recommendations without knowing the partner's
restrictions.

### 3. Apply exclusions before the recommendation cap

Partner exclusions are applied before the cap. For example, if a partner
allows three recommendations but excludes cruises, an excluded cruise
does not consume one of those three slots.

This produces the requested number of **allowed** recommendations
whenever enough candidates are available.

### 4. Read partner configuration on every request

The PoC intentionally has no configuration cache. A changed cap or
exclusion therefore takes effect on the next request, and there is no
stale-policy cache to diagnose.

The trade-off is an additional upstream read per request once the mock
becomes a real service. If caching is introduced later, its TTL and
invalidation strategy must explicitly define the maximum
policy-propagation delay.

## Handling Partner Configuration Changes

No code change is required when an existing partner changes its
recommendation cap or excluded categories. The configuration is loaded
on each request. Category comparisons normalize case and surrounding
whitespace, and malformed configuration fails closed rather than being
silently ignored.

A code change is required only when the partner configuration introduces
a **new kind of policy**, such as destination exclusions or per-tier
caps. That would require extending the typed `PartnerConfig` contract,
adding deterministic enforcement to the rule phase, and adding
regression tests.

------------------------------------------------------------------------

# Four-Week Delivery Plan

  ---------------------------------------------------------------------------
  Week                    Deliverable                 Status
  ----------------------- --------------------------- -----------------------
  **1**                   Shared service layer,       Implemented in PoC
                          deterministic               
                          personalization, partner    
                          rule enforcement, typed     
                          errors, fail-closed         
                          configuration handling,     
                          REST API, MCP tools over    
                          stdio, CLI, and automated   
                          tests                       

  **2**                   Replace mocks with HTTP     Next
                          clients for member and      
                          partner-config services;    
                          add explicit timeouts, safe 
                          retries for reads,          
                          schema/contract tests, and  
                          deploy a container to       
                          arrivia's existing platform 

  **3**                   Move MCP to Streamable HTTP Next
                          behind the existing         
                          gateway; add                
                          service-to-service          
                          authentication, partner     
                          authorization/scoping,      
                          structured metrics/alerts,  
                          and evaluate a short-TTL    
                          configuration cache         

  **4**                   Load testing, failure       Next
                          testing, runbook review,    
                          on-call handoff, and a      
                          limited partner pilot       
                          behind an existing feature  
                          flag                        

  **Later**               Real travel inventory,      Later
                          stronger ranking/ML         
                          personalization, shared     
                          category taxonomy,          
                          feedback/experimentation,   
                          and session-aware           
                          recommendation limits if    
                          required                    
  ---------------------------------------------------------------------------

A session-wide recommendation cap is deliberately outside this PoC. The
supplied configuration is modeled as a cap per response; enforcing a cap
across a session would require shared session state and introduces a new
dependency.

------------------------------------------------------------------------

# Section B: Production Readiness & Incident Response

## Incident Runbook: "AI Concierge shows cruises, but my partner excludes cruises"

**Severity:** High. A partner-specific policy may be violated in a
member-visible experience.

### 1. Triage

Collect:

-   member ID
-   partner ID
-   timestamp
-   request/session identifier if available
-   screenshot or conversation transcript

Determine whether the issue affects one member or multiple members for
the same partner.

### 2. Reproduce

Call either:

``` text
GET /api/recommendations/<member_id>
```

or:

``` text
get_travel_recommendations(member_id)
```

through MCP.

Inspect the returned `applied_rules`. It records the configuration the
recommendation service actually enforced.

### 3. Diagnose

  -----------------------------------------------------------------------
  Observation             Likely cause            Next step
  ----------------------- ----------------------- -----------------------
  `excluded_categories`   Wrong/stale upstream    Compare the member's
  does not contain        config or incorrect     `partner_id` with the
  `cruise`                member-to-partner       read-only
                          mapping                 partner-config service

  Config uses a different Taxonomy mismatch       Compare configuration
  category such as                                values with canonical
  `cruises` or                                    inventory categories
  `Cruise Line`                                   

  `applied_rules`         The AI layer added an   Compare MCP tool-call
  contains `cruise` and   item not returned by    output with the final
  the tool response       the tool                agent response
  contains no cruise, but                         
  the member saw one                              

  Item is effectively a   Inventory/catalog       Correct the source
  cruise but is           tagging problem         taxonomy and add a
  categorized as another                          regression test
  type                                            

  A recent deployment     Rule-enforcement        Roll back or hotfix and
  returns a cruise        regression              add a regression test
  despite a matching                              
  exclusion                                       
  -----------------------------------------------------------------------

### 4. Mitigate and Resolve

**Recommendation-service regression:** roll back or hotfix the service
and add a test reproducing the incident.

**Partner configuration is incorrect:** this service must not edit the
read-only partner configuration. Escalate to the owning configuration
team with the member ID, partner ID, raw configuration evidence, and
`applied_rules`. Until policy correctness is restored, fail closed for
the affected partner or disable the recommendation experience using an
existing platform feature flag if one is available.

**Agent added unsupported recommendations:** preserve the server-side
recommendation service as the policy boundary. Tighten the
concierge/tool contract so the user-facing agent only presents
recommendation items returned by `get_travel_recommendations`.

**Taxonomy mismatch:** correct the canonical category mapping at the
appropriate source and add a regression test for the exact category
variant.

### 5. Follow-up

Perform a post-incident review. Add monitoring that can detect
unexpected changes in exclusion behavior, such as a sudden drop in
`removed_by_exclusion` for a partner whose configuration still contains
exclusions.

## Part B2: Required Reasoning Question --- Candidate Must Complete Without AI

> **Do not submit this placeholder.**
>
> The challenge explicitly requires this section to be answered without
> AI assistance. Write your own response here before submission.

------------------------------------------------------------------------

# Section C: AI Usage Log

I used AI assistance during architecture review, implementation,
debugging, and documentation. I treated generated suggestions as
hypotheses to verify against the running code and challenge requirements
rather than accepting them automatically.

## Interaction 1: MCP SDK and Inspector compatibility

**Asked:** Help expose the recommendation service through MCP and verify
tool discovery/invocation.

**Received:** The initial implementation used the MCP v1 `FastMCP` API.
After the local environment installed MCP v2, the import failed because
the API had changed. Pinning v1 allowed the server to start, but the
current Inspector then behaved unreliably during tool discovery.

**Kept / changed:** I did not keep the version workaround as the final
design. Because the MCP adapter was small, I migrated it to MCP v2 using
`MCPServer` and pinned the tested v2 dependency in
`requirements-lock.txt`. The recommendation domain logic did not need to
change.

## Interaction 2: Diagnosing MCP launch and Inspector failures

**Asked:** Diagnose why Inspector could initialize but tool requests
timed out, and later why `mcp dev` failed.

**Received:** The debugging separated transport/tooling problems from
application logic. `mcp dev` attempted to launch through `uv`, and
file-based execution also created import-path problems for `from app...`
imports.

**Kept / changed:** Instead of restructuring working application imports
around a development helper, I kept the package layout and added
`mcp_config.json` to launch the MCP server as a module with the project
virtual environment:

``` text
.venv/bin/python -m app.mcp_server
```

I documented Inspector CLI commands as the repeatable
discovery/invocation path.

## Interaction 3: Challenge-oriented code review

**Asked:** Review the implementation against the challenge rather than
only checking whether it ran.

**Received:** The review identified gaps in the early PoC:
recommendations were not meaningfully personalized, error handling was
too string-dependent, malformed partner configuration needed explicit
fail-closed handling, and the rule tests needed stronger cases.

**Kept / changed:** I added typed domain errors, Pydantic validation for
partner configuration, deterministic personalization based on loyalty
tier and travel history, `applied_rules` for diagnosis, and additional
tests. I also strengthened the exclusion tests after noticing that a
recommendation cap could accidentally mask a broken exclusion rule.

------------------------------------------------------------------------

# Testing Strategy

The test suite covers behavior at the service and interface boundaries.

Key cases include:

-   partner recommendation cap is enforced
-   excluded cruise categories never reach the response
-   another partner can receive cruises when its configuration allows
    them
-   exclusions are applied before the cap
-   missing partner configuration fails closed
-   unknown member raises a typed not-found error
-   malformed partner configuration fails closed
-   zero recommendation cap is supported
-   category matching ignores case and surrounding whitespace
-   configuration changes take effect on the next request
-   `applied_rules` reports enforced policy
-   previously visited destinations are skipped
-   Platinum-only offers are hidden from lower tiers
-   previously booked travel categories rank first
-   exclusions still hold when personalization strongly prefers the
    excluded category
-   REST maps domain errors to appropriate HTTP status codes
-   MCP exposes both tools
-   MCP surfaces expected domain failures to the agent as tool errors

Run:

``` bash
pytest -q
```

------------------------------------------------------------------------

# Known Limitations

-   Member and partner-config services are in-process mocks rather than
    real network dependencies.
-   There are no upstream network timeouts, retries, or circuit-breaking
    behavior yet because there are no network calls in the PoC.
-   Candidate inventory is static.
-   Personalization is a deterministic heuristic rather than an ML/LLM
    ranking model.
-   MCP currently uses stdio and has no authentication.
-   The PoC does not implement partner-scoped authorization, so it must
    not be exposed directly to external partners in its current form.
-   Recommendation caps are per response rather than per session.
-   There is no partner-config cache; this favors immediate policy
    consistency over upstream-read efficiency for the PoC.

# Design Principle

The AI agent is a **consumer of recommendations, not the policy
enforcement boundary**.

Partner policy remains deterministic, centralized, testable, and shared
across REST, MCP, and CLI.
