# Graph Report - Hackathon  (2026-10-16)

## Corpus Check
- Corpus is ~1,813 words - fits in a single context window. You may not need a graph.

## Summary
- 95 nodes · 110 edges · 16 communities (4 shown, 12 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 13 edges (avg confidence: 0.89)
- Token cost: 63,726 input · 0 output

## Community Hubs (Navigation)
- Scam Analysis Pipeline Concepts
- Frontend Build Config
- React UI Components
- Analyze API & Schemas
- FastAPI App & Tests
- Rules Test Placeholder

## God Nodes (most connected - your core abstractions)
1. `react` - 7 edges
2. `Scam Analyzer` - 7 edges
3. `analyze()` - 6 edges
4. `Backend Python Dependencies` - 6 edges
5. `AnalyzeRequest` - 5 edges
6. `ExternalCheckResult` - 5 edges
7. `AnalyzeResponse` - 5 edges
8. `scripts` - 4 edges
9. `Google Gemini LLM Reasoning` - 4 edges
10. `FastAPI Backend` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Scam Indicators (tone, urgency, impersonation, call-to-action)` --semantically_similar_to--> `Heuristic Rules Engine`  [INFERRED] [semantically similar]
  backend/app/prompts/analyze_prompt.txt → README.md
- `Frontend index.html (root mount)` --references--> `Scam Analyzer`  [EXTRACTED]
  frontend/index.html → README.md
- `tldextract` --implements--> `Domain Intelligence / Analysis`  [INFERRED]
  backend/requirements.txt → README.md
- `httpx` --conceptually_related_to--> `Google Safe Browsing Verification`  [INFERRED]
  backend/requirements.txt → README.md
- `Gemini Scam Analysis System Prompt` --implements--> `Google Gemini LLM Reasoning`  [INFERRED]
  backend/app/prompts/analyze_prompt.txt → README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Multi-stage Scam Analysis Pipeline** — readme_heuristic_rules_engine, readme_link_extraction, readme_domain_intelligence, readme_google_safe_browsing, readme_gemini_llm_reasoning, readme_ensemble_scoring [INFERRED 0.85]
- **Gemini LLM Stage (prompt + SDK + concept)** — backend_app_prompts_analyze_prompt_system_prompt, backend_requirements_google_genai, readme_gemini_llm_reasoning [INFERRED 0.85]

## Communities (16 total, 12 thin omitted)

### Community 0 - "Scam Analysis Pipeline Concepts"
Cohesion: 0.16
Nodes (18): Scam Indicators (tone, urgency, impersonation, call-to-action), Gemini Scam Analysis System Prompt, Backend Python Dependencies, fastapi, google-genai, httpx, pydantic / pydantic-settings, tldextract (+10 more)

### Community 1 - "Frontend Build Config"
Cohesion: 0.12
Nodes (16): dependencies, react, react-dom, devDependencies, vite, @vitejs/plugin-react, name, private (+8 more)

### Community 2 - "React UI Components"
Cohesion: 0.16
Nodes (4): analyzeText(), App(), react, react-dom

### Community 3 - "Analyze API & Schemas"
Cohesion: 0.29
Nodes (5): analyze(), AnalyzeRequest, AnalyzeResponse, ExternalCheckResult, RuleFlag

## Knowledge Gaps
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `react` connect `React UI Components` to `Frontend Build Config`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `analyze()` (e.g. with `AnalyzeRequest` and `AnalyzeResponse`) actually correct?**
  _`analyze()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `Frontend Build Config` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._