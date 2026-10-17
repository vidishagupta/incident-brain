# Incident Brain — Video Demo Script & Scene Breakdown

**Target Runtime**: 1:30 (Max 2:00)  
**Resolution**: 1920x1080 (1080p, 30 FPS)  
**Audio**: AI Voiceover (`en-US-ChristopherNeural` via edge-tts) with burned-in subtitles  
**Tracks Entered**: Track 1 (Connected Data), Track 2 (Agent Memory), Track 3 (Company Brain)

---

### Scene 1: Hook & The Outage Crisis (0:00 - 0:14)
- **Visual**: Sleek dark Title Card with glowing FalkorDB branding, track badges, and hackathon banner.
- **Voiceover**: 
  > *"When critical microservices crash, engineers waste hours guessing the blast radius and digging through outdated wikis. Meet Incident Brain: an autonomous incident response copilot powered by FalkorDB graph database."*
- **Callout**: *Zero Guesswork. Graph-Driven Incident Triage.*

---

### Scene 2: Living Graph Architecture (0:14 - 0:28)
- **Visual**: Architecture Diagram illustrating flow: Alert -> Autonomous Agent -> Graph Tools -> FalkorDB (`company_graph` & `memory_<team>`) -> Blast Radius, Owners & Postmortem.
- **Voiceover**: 
  > *"Incident Brain models services, dependencies, historical outages, and architectural decisions as a living graph. The agent uses parameterized Cypher and matrix GraphBLAS algorithms to drive every answer."*
- **Callout**: *100% Graph-Grounding. No Hallucinations.*

---

### Scene 3: Live Multi-Hop Investigation (0:28 - 0:50)
- **Visual**: Playwright recording of the interactive dashboard. User selects `auth-service` (HikariCP pool leak). Force-graph lights up node-by-node across 3 hops. Blast radius panel lists affected services.
- **Voiceover**: 
  > *"Watch the live investigation. When Auth Service suffers connection pool exhaustion, the agent executes multi-hop graph traversal. The force graph lights up hop-by-hop, revealing six affected downstream services and calculating PageRank risk."*
- **Callout**: *Multi-Hop Blast Traversal (`DEPENDS_ON*1..4`)*

---

### Scene 4: Proof & Verification Trace (0:50 - 1:06)
- **Visual**: Switch to "Cypher & Trace" tab. Shows each step of the autonomous agent reasoning loop, tool execution summaries, and exact parameterized Cypher queries with syntax highlighting.
- **Voiceover**: 
  > *"No hallucinations. Every recommendation links directly to graph facts: primary owner Alice Chen, historical incident INC-101, and the exact Cypher query used in the step-by-step reasoning trace."*
- **Callout**: *Cypher Proof & Auditable Agent Trace*

---

### Scene 5: Agent Memory Across Sessions (1:06 - 1:22)
- **Visual**: Switch to "Team Memory" tab. Demonstrates logging the verified remediation into `memory_core_platform`. The new incident node appears instantly in the graph and is queried by subsequent triage sessions.
- **Voiceover**: 
  > *"Track Two: Persistent memory. When the engineer logs the remediation, it is committed to FalkorDB team memory. The next time an outage occurs, the agent immediately finds the verified fix across sessions."*
- **Callout**: *Persistent Team Graph Memory (`memory_<team>`)*

---

### Scene 6: Conclusion & Three Tracks (1:22 - 1:35)
- **Visual**: Closing Card displaying the GitHub repo URL, FalkorDB credit, and the 3 track badges.
- **Voiceover**: 
  > *"Incident Brain enters all three Graph Hacks tracks: agents on connected data, agent memory, and company brain. Built with FalkorDB, FastAPI, and Playwright. The future of autonomous reliability is here."*
- **Callout**: *Open Source on GitHub | Built for Graph Hacks 2026*
