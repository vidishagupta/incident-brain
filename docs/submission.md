# Graph Hacks Submission — Incident Brain

**Project Title**: Incident Brain  
**Tagline**: Autonomous incident response copilot leveraging FalkorDB graph topology, PageRank risk scoring, and persistent episodic memory across teams.  
**Author**: Vidisha Gupta (Solo)  
**Hackathon**: Graph Hacks (WeMakeDevs x FalkorDB)  
**GitHub Repository**: https://github.com/vidishagupta/incident-brain  
**Live Application URL**: https://incident-brain-ashen.vercel.app  
**License**: MIT License  

---

### Track Entries (Enters All 3 Tracks)
1. **Track 1: Agents Acting on Connected Data**  
   Incident Brain's autonomous Triage Agent traverses multi-hop dependency chains (`DEPENDS_ON*1..4`), executes FalkorDB GraphBLAS PageRank (`CALL algo.PageRank`), and pinpoints causal paths via `shortestPath`. Every answer is 100% grounded in verified graph facts.
2. **Track 2: Agent Memory Across Sessions**  
   Utilizes FalkorDB multi-graph architecture to isolate episodic incident memory into per-team graphs (`memory_<team>`). When remediations are logged, they persist across sessions, enabling instant retrieval when similar outages strike in the future.
3. **Track 3: Company Brain**  
   Unifies organizational knowledge into a single living graph in `company_graph`: microservices, code tiering, ownership hierarchies (`OWNS`), team memberships (`MEMBER_OF`), runbooks (`DOCUMENTED_IN`), and Architectural Decision Records (`SHAPED`).

---

### FalkorDB Usage Deep-Dive
Incident Brain relies exclusively on FalkorDB as its central graph database:
- **Parameterized Cypher Execution**: 100% of graph interactions utilize parameterized Cypher (`graph.query(cypher, params)`) ensuring plan caching and query safety.
- **Multi-Hop Traversal**: Computes failure blast radius across up to 4 dependency tiers with:
  ```cypher
  MATCH path = (s:Service {name: $service_name})<-[:DEPENDS_ON*1..4]-(downstream:Service)
  RETURN downstream.name, downstream.tier, length(path) AS hop
  ORDER BY hop ASC
  ```
- **Graph Algorithm**: Uses native FalkorDB PageRank algorithm (`CALL algo.PageRank({damping: 0.85, iterations: 20}) YIELD node, score`) to calculate systemic service criticality.
- **Multi-Graph Isolation**: Separates company-wide topology (`company_graph`) from isolated squad memory graphs (`memory_core_platform`, `memory_payments_squad`, `memory_reliability_ops`).
- **Graph Handoff**: Triage Agent writes an `Investigation` node into the graph, which Scribe Agent reads to automatically draft the postmortem markdown.

---

### Key Features
- **Instant Blast Radius**: Visually lights up affected downstream services hop-by-hop on an interactive 2D Force-Graph canvas.
- **Who to Ask**: Traverses service ownership and past incident resolutions to recommend domain experts with direct Slack links.
- **Similar Past Incidents**: Matches historical incidents linked by `:SIMILAR_TO` or symptom patterns, displaying root causes and verified fixes.
- **Proof & Cypher Trace**: Collapsible "How I figured this out" panel auditing every tool step and raw Cypher query.
- **Zero-Key Deterministic Mode**: Runs out of the box with zero paid API keys, while supporting LLM providers (Groq/OpenAI/Gemini) if configured.
- **One-Command Setup**: Clean reproducible deployment with `docker compose up` or local venv.

---

### Verification Checklist
- [x] All code is 100% NEW, written specifically for Graph Hacks.
- [x] Official `falkordb` Python client used exclusively with parameterized Cypher.
- [x] Full test suite (21/21 passing tests in pytest).
- [x] Dockerfile and docker-compose.yml included and verified.
- [x] Demo video with AI voiceover and burned-in subtitles generated.
- [x] Zero committed secrets or credentials (.env gitignored).
