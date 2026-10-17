# How I Built Incident Brain: An Autonomous Incident Copilot Powered by FalkorDB

*By Vidisha Gupta — Built for Graph Hacks 2026 (WeMakeDevs x FalkorDB)*

![Incident Brain Cover Image](/video/output/thumbnail.jpg)

It was 2:14 AM on a Saturday when our primary authentication service first started dropping requests. Within seconds, alarms flooded Slack. But the hardest part of that incident wasn’t fixing the bug; it was answering the frantic questions that followed: *What else broke? Who owns this service? Has anyone seen this exact connection leak before?*

Traditional incident management tools are static databases of tickets and text alerts. They have no concept of dependency topology or organizational memory. As an on-call engineer, you’re forced to mentally reconstruct a massive dependency graph in the middle of a high-stress outage.

That’s why I built **Incident Brain**: a fully autonomous incident copilot powered by **FalkorDB** that calculates blast radius, identifies experts, surfaces past remediations, and remembers solutions across sessions.

---

### The Power of Graph: Why Relational Databases Fail Here

Microservice architectures are directed graphs. When Service A depends on Service B, and Service B depends on Service C, a failure cascades downstream in non-linear ways. Calculating the blast radius in a relational database requires expensive, recursive SQL joins that buckle under load.

With **FalkorDB**, multi-hop traversal is native, fast, and expressive. Using parameterized Cypher, Incident Brain discovers all affected downstream services up to four hops away with a single query:

```cypher
MATCH path = (s:Service {name: $service_name})<-[:DEPENDS_ON*1..4]-(downstream:Service)
RETURN downstream.name, downstream.tier, length(path) AS hop
ORDER BY hop ASC
```

FalkorDB computes this matrix-based traversal in milliseconds thanks to GraphBLAS. In addition to depth traversal, Incident Brain runs FalkorDB’s native **PageRank algorithm** (`CALL algo.PageRank`) to calculate topological centrality, instantly highlighting which downstream services bear the highest systemic risk during an incident.

![Incident Brain Live Graph Visualizer](/video/temp/scene_2_arch.png)

---

### Dual-Agent Architecture: Triage & Scribe

Incident Brain uses a two-agent cooperative handoff:
1. **The Triage Agent** queries FalkorDB using specialized tools (`blast_radius`, `risk_rank`, `who_knows`, `similar_incidents`, `explain_path`, and `get_docs`). It verifies facts against the graph—never hallucinating—and writes an `Investigation` node into the database.
2. **The Scribe Agent** reads the investigation subgraph and immediately drafts a structured incident postmortem, complete with executive impact summaries, key responder Slack contacts, and runbook links.

Every step taken by the agent is visible in a collapsible "How I Figured This Out" trace panel, showing the exact Cypher executed.

---

### Persistent Memory Across Sessions (Track 2)

Most AI agents suffer from amnesia: once the chat window closes, their context disappears. Incident Brain solves this by treating FalkorDB as long-term episodic memory.

Using FalkorDB's multi-graph capabilities, each engineering squad gets an isolated memory graph (e.g., `memory_core_platform`, `memory_payments_squad`), while sharing global organizational topology in `company_graph`. When an engineer logs a remediation, it is committed to their team’s graph memory. The next time an outage with similar symptoms strikes, the agent immediately surfaces the exact fix that resolved it in the past.

![Incident Brain Graph Reasoning Trace](/video/temp/scene_1_title.png)

---

### What I Learned & What’s Next

Building Incident Brain for Graph Hacks showed me that graphs are the natural mental model for autonomous agents. Large language models provide the reasoning interface, but FalkorDB provides the ground truth, structural constraint, and persistent memory that mission-critical systems demand.

Check out the project on GitHub, clone the repo, and run `docker compose up` to see Incident Brain in action. Never guess your blast radius again!
