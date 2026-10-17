// Incident Brain Interactive Frontend Logic
let graphInstance = null;
let graphData = { nodes: [], links: [] };
let highlightedNodes = new Set();
let highlightedLinks = new Set();
let rootFailingNode = null;

// Initialize when DOM is ready
document.addEventListener("DOMContentLoaded", async () => {
  initTabs();
  initForceGraph();
  await loadGraphData();
  await checkHealth();
  setupEventListeners();
  loadTeamMemory();
});

// Setup Panel Tabs
function initTabs() {
  const tabs = [
    { btn: "tabTriage", content: "contentTriage" },
    { btn: "tabTrace", content: "contentTrace" },
    { btn: "tabMemory", content: "contentMemory" }
  ];

  tabs.forEach(t => {
    const btn = document.getElementById(t.btn);
    btn.addEventListener("click", () => {
      tabs.forEach(other => {
        document.getElementById(other.btn).classList.remove("active-tab");
        document.getElementById(other.btn).classList.add("text-slate-400");
        document.getElementById(other.content).classList.add("hidden");
      });
      btn.classList.add("active-tab");
      btn.classList.remove("text-slate-400");
      document.getElementById(t.content).classList.remove("hidden");
    });
  });
}

// Check Health & Engine status
async function checkHealth() {
  try {
    const res = await fetch("/health");
    const data = await res.json();
    const modeBadge = document.getElementById("modeBadge");
    const modeText = document.getElementById("modeText");
    if (data.falkordb_connected) {
      modeText.innerText = "FalkorDB Native (Active)";
      modeBadge.className = "flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-pink-500/10 border border-pink-500/30 text-pink-400 text-xs font-mono";
    } else {
      modeText.innerText = "FalkorDB Engine (GraphBLAS)";
      modeBadge.className = "flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono";
    }
  } catch (err) {
    console.error("Health check error:", err);
  }
}

// Initialize 2D Force-Graph
function initForceGraph() {
  const container = document.getElementById("graphCanvas");
  
  graphInstance = ForceGraph()(container)
    .backgroundColor("#090d16")
    .nodeId("id")
    .nodeLabel(node => `${node.label}: ${node.id}`)
    .nodeVal(node => getNodeSize(node))
    .nodeColor(node => getNodeColor(node))
    .nodeCanvasObject((node, ctx, globalScale) => {
      const size = getNodeSize(node);
      const color = getNodeColor(node);
      const isFailing = (node.id === rootFailingNode);
      const isHighlighted = highlightedNodes.has(node.id);

      // Pulse ring around failing root
      if (isFailing) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, size + 6, 0, 2 * Math.PI, false);
        ctx.fillStyle = "rgba(239, 68, 68, 0.25)";
        ctx.fill();
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = "#ef4444";
        ctx.stroke();
      } else if (isHighlighted) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, size + 3, 0, 2 * Math.PI, false);
        ctx.fillStyle = "rgba(245, 158, 11, 0.2)";
        ctx.fill();
      }

      // Draw main circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 1.2;
      ctx.strokeStyle = isFailing ? "#ffffff" : "rgba(255, 255, 255, 0.3)";
      ctx.stroke();

      // Node label
      const label = node.id;
      const fontSize = Math.max(10 / globalScale, 3.5);
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.fillStyle = isFailing ? "#f87171" : (isHighlighted ? "#fbbf24" : "#94a3b8");
      ctx.fillText(label, node.x, node.y + size + 2);
    })
    .linkColor(link => {
      if (highlightedLinks.has(link)) return "#f59e0b";
      return "rgba(148, 163, 184, 0.15)";
    })
    .linkWidth(link => highlightedLinks.has(link) ? 2.5 : 1)
    .linkDirectionalParticles(link => highlightedLinks.has(link) ? 4 : 0)
    .linkDirectionalParticleSpeed(0.01)
    .linkDirectionalParticleWidth(2.5)
    .linkDirectionalParticleColor(() => "#f59e0b")
    .onNodeClick(node => showNodeDetails(node));

  // Resize canvas responsively
  window.addEventListener("resize", () => {
    graphInstance.width(container.clientWidth);
    graphInstance.height(container.clientHeight);
  });
}

function getNodeColor(node) {
  if (node.id === rootFailingNode) return "#ef4444"; // Red for root failure
  if (highlightedNodes.has(node.id)) return "#f59e0b"; // Amber for blast radius
  
  switch (node.label) {
    case "Service": return "#38bdf8"; // Light Blue
    case "Person": return "#3b82f6"; // Blue
    case "Team": return "#06b6d4"; // Cyan
    case "Incident": return "#a855f7"; // Purple
    case "Doc": return "#94a3b8"; // Slate
    case "Decision": return "#cbd5e1"; // Grey
    default: return "#64748b";
  }
}

function getNodeSize(node) {
  if (node.id === rootFailingNode) return 9;
  if (node.label === "Service") return 6;
  if (node.label === "Person") return 5;
  if (node.label === "Incident") return 5.5;
  return 4.5;
}

// Load Graph Data from Server
async function loadGraphData() {
  try {
    const res = await fetch("/api/graph");
    graphData = await res.json();
    graphInstance.graphData(graphData);

    document.getElementById("metricNodes").innerText = graphData.nodes.length;
    document.getElementById("metricEdges").innerText = graphData.links.length;
  } catch (err) {
    console.error("Error loading graph:", err);
  }
}

// Event Listeners for UI buttons
function setupEventListeners() {
  // Zoom Controls
  document.getElementById("btnZoomIn").addEventListener("click", () => {
    graphInstance.zoom(graphInstance.zoom() * 1.3, 400);
  });
  document.getElementById("btnZoomOut").addEventListener("click", () => {
    graphInstance.zoom(graphInstance.zoom() / 1.3, 400);
  });
  document.getElementById("btnCenterGraph").addEventListener("click", () => {
    graphInstance.zoomToFit(400);
  });

  // Sample Selector Change
  document.getElementById("sampleSelector").addEventListener("change", (e) => {
    const svc = e.target.value;
    document.getElementById("inputService").value = svc;
    if (svc === "auth-service") {
      document.getElementById("inputSymptoms").value = "504 Gateway Timeout and connection leaks";
    } else if (svc === "payment-service") {
      document.getElementById("inputSymptoms").value = "Checkout webhook latency > 45s";
    } else if (svc === "inventory-service") {
      document.getElementById("inputSymptoms").value = "Cluster split-brain and ghost reservations";
    }
  });

  // Run Investigation Button
  document.getElementById("btnInvestigate").addEventListener("click", () => {
    const svc = document.getElementById("inputService").value.trim();
    const symptoms = document.getElementById("inputSymptoms").value.trim();
    const team = document.getElementById("teamSelector").value;
    runInvestigation(svc, symptoms, team);
  });

  // Reset Demo Button
  document.getElementById("btnResetDemo").addEventListener("click", async () => {
    if (confirm("Reset and re-seed FalkorDB graph data?")) {
      const res = await fetch("/api/reset-demo", { method: "POST" });
      const data = await res.json();
      rootFailingNode = null;
      highlightedNodes.clear();
      highlightedLinks.clear();
      await loadGraphData();
      alert("FalkorDB graph reset to clean seed state.");
    }
  });

  // Auto Demo Mode Button
  document.getElementById("btnAutoDemo").addEventListener("click", () => {
    runAutoDemoFlow();
  });

  // Close Detail Card
  document.getElementById("btnCloseCard").addEventListener("click", () => {
    document.getElementById("nodeDetailCard").classList.add("hidden");
  });

  // Copy Postmortem
  document.getElementById("btnCopyPostmortem").addEventListener("click", () => {
    const text = document.getElementById("postmortemText").innerText;
    navigator.clipboard.writeText(text);
    alert("Postmortem markdown copied to clipboard!");
  });

  // Form Log Incident
  document.getElementById("formLogIncident").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      title: document.getElementById("logTitle").value,
      service: document.getElementById("logService").value,
      severity: document.getElementById("logSeverity").value,
      root_cause: document.getElementById("logRootCause").value,
      fix: document.getElementById("logFix").value,
      team: document.getElementById("teamSelector").value
    };

    const res = await fetch("/api/incidents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    alert(`Incident ${data.result.incident_id} successfully persisted into FalkorDB memory_${payload.team}!`);
    await loadGraphData();
    await loadTeamMemory();
  });

  // Team Selector Change
  document.getElementById("teamSelector").addEventListener("change", () => {
    loadTeamMemory();
  });
}

// Show Node Details Drawer
function showNodeDetails(node) {
  const card = document.getElementById("nodeDetailCard");
  document.getElementById("cardLabel").innerText = node.label;
  document.getElementById("cardTitle").innerText = node.id;
  
  let html = "";
  if (node.properties) {
    for (const [k, v] of Object.entries(node.properties)) {
      html += `<div><span class="text-slate-400 font-mono">${k}:</span> <span class="text-white">${v}</span></div>`;
    }
  }
  document.getElementById("cardContent").innerHTML = html;
  card.classList.remove("hidden");
}

// Run Investigation Flow
async function runInvestigation(service, symptoms, team) {
  const btn = document.getElementById("btnInvestigate");
  const spinner = document.getElementById("btnInvestigateSpinner");
  const btnText = document.getElementById("btnInvestigateText");

  btn.disabled = true;
  spinner.classList.remove("hidden");
  btnText.innerText = "Analyzing FalkorDB Graph...";

  try {
    const res = await fetch("/api/investigate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ service, symptoms, team })
    });
    const data = await res.json();
    renderInvestigationResults(data);
    animateGraphInvestigation(data);
  } catch (err) {
    console.error("Investigation failed:", err);
    alert("Investigation failed: " + err);
  } finally {
    btn.disabled = false;
    spinner.classList.add("hidden");
    btnText.innerText = "Run Multi-Hop Graph Investigation";
  }
}

// Render Investigation Data into Right Panels
function renderInvestigationResults(data) {
  rootFailingNode = data.service;

  // 1. Blast Radius
  const blastList = document.getElementById("blastList");
  const blastCount = document.getElementById("blastCount");
  blastCount.innerText = data.blast_radius.length;
  document.getElementById("metricBlast").innerText = data.blast_radius.length;

  if (data.blast_radius.length === 0) {
    blastList.innerHTML = `<div class="text-slate-400 py-2">No downstream dependencies affected (isolated service).</div>`;
  } else {
    blastList.innerHTML = data.blast_radius.map(b => `
      <div class="flex items-center justify-between p-2 rounded-lg bg-dark-900 border border-slate-800 hover:border-amber-500/40 transition">
        <div class="flex items-center space-x-2">
          <span class="w-1.5 h-1.5 rounded-full ${b.risk_level === 'CRITICAL' ? 'bg-rose-500' : 'bg-amber-400'}"></span>
          <span class="font-mono text-white font-medium">${b.service}</span>
          <span class="text-[10px] text-slate-400">(${b.tier})</span>
        </div>
        <div class="flex items-center space-x-2">
          <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">Hop ${b.hop}</span>
          <span class="text-[10px] px-1.5 py-0.5 rounded font-bold ${b.risk_level === 'CRITICAL' ? 'bg-rose-500/20 text-rose-400' : 'bg-amber-500/20 text-amber-400'}">${b.risk_level}</span>
        </div>
      </div>
    `).join("");
  }

  // 2. Who to Ask
  const whoList = document.getElementById("whoList");
  if (data.who_knows.length === 0) {
    whoList.innerHTML = `<div class="text-slate-400 py-2">No explicit owner identified. Contact #incident-response.</div>`;
  } else {
    whoList.innerHTML = data.who_knows.map(p => `
      <div class="p-2 rounded-lg bg-dark-900 border border-slate-800 flex items-center justify-between">
        <div>
          <div class="font-medium text-white">${p.name} <span class="text-slate-400 font-normal">(${p.role})</span></div>
          <div class="text-[11px] text-slate-400">${p.reason}</div>
        </div>
        <a href="slack://user?team=T123&id=${p.slack}" class="px-2 py-1 rounded bg-blue-500/10 text-blue-400 border border-blue-500/30 font-mono text-[11px] hover:bg-blue-500/20 transition">
          ${p.slack}
        </a>
      </div>
    `).join("");
  }

  // 3. Similar Incidents
  const similarList = document.getElementById("similarList");
  if (data.similar_incidents.length === 0) {
    similarList.innerHTML = `<div class="text-slate-400 py-2">No past similar incidents found.</div>`;
  } else {
    similarList.innerHTML = data.similar_incidents.map(inc => `
      <div class="p-3 rounded-lg bg-dark-900 border border-purple-500/30 space-y-1.5">
        <div class="flex items-center justify-between">
          <span class="font-semibold text-purple-300 text-xs">${inc.title}</span>
          <span class="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 font-bold">${inc.severity}</span>
        </div>
        <div class="text-slate-300 text-[11px]"><strong class="text-slate-400">Root Cause:</strong> ${inc.root_cause}</div>
        <div class="text-emerald-400 text-[11px]"><strong class="text-slate-400">Fix:</strong> ${inc.fix}</div>
      </div>
    `).join("");
  }

  // 4. Postmortem
  document.getElementById("postmortemText").innerText = data.postmortem;

  // 5. Trace & Cypher
  const traceContainer = document.getElementById("traceSteps");
  traceContainer.innerHTML = data.trace.map(t => `
    <div class="p-3 rounded-xl bg-dark-900 border border-slate-800 space-y-2">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <span class="w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center font-mono font-bold text-[10px]">${t.step}</span>
          <span class="font-semibold text-white">${t.tool}</span>
        </div>
        <span class="text-[10px] text-slate-400 font-mono">${t.agent}</span>
      </div>
      <p class="text-slate-300 text-[11px]">${t.explanation}</p>
      <div class="p-2 rounded bg-black/40 border border-slate-800 text-[11px] font-mono text-pink-400 overflow-x-auto">
        <code>${t.cypher}</code>
      </div>
    </div>
  `).join("");
}

// Animate visual graph elements hop by hop
function animateGraphInvestigation(data) {
  highlightedNodes.clear();
  highlightedLinks.clear();

  rootFailingNode = data.service;
  highlightedNodes.add(rootFailingNode);

  // Zoom into root failing service
  const rootNode = graphData.nodes.find(n => n.id === rootFailingNode);
  if (rootNode) {
    graphInstance.centerAt(rootNode.x, rootNode.y, 800);
    graphInstance.zoom(2.2, 800);
  }

  // Sequentially highlight downstream blast radius nodes
  const blast = data.blast_radius || [];
  blast.forEach((b, idx) => {
    setTimeout(() => {
      highlightedNodes.add(b.service);
      
      // Highlight matching edge
      graphData.links.forEach(l => {
        const srcId = typeof l.source === 'object' ? l.source.id : l.source;
        const dstId = typeof l.target === 'object' ? l.target.id : l.target;
        if (srcId === b.service || dstId === b.service) {
          highlightedLinks.add(l);
        }
      });
      graphInstance.graphData(graphData);
    }, 250 * (idx + 1));
  });

  // Also highlight assigned responders
  (data.who_knows || []).forEach(p => highlightedNodes.add(p.name));
}

// Load Isolated Team Memory
async function loadTeamMemory() {
  const team = document.getElementById("teamSelector").value;
  const list = document.getElementById("memoryList");
  try {
    const res = await fetch(`/api/memory?team=${team}`);
    const data = await res.json();
    const nodes = data.snapshot.nodes || [];

    if (nodes.length === 0) {
      list.innerHTML = `<div class="text-slate-400 py-3 text-center">No team-specific memory recorded yet.</div>`;
    } else {
      list.innerHTML = nodes.map(n => `
        <div class="p-2 rounded bg-dark-900 border border-slate-800 flex items-center justify-between">
          <div>
            <span class="font-mono text-indigo-400 font-semibold">${n.id}</span>
            <span class="text-slate-400 text-[11px]">(${n.label})</span>
          </div>
          <span class="text-[10px] text-slate-500 font-mono">${data.graph_name}</span>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Error loading team memory:", err);
  }
}

// Automated Demo Walkthrough for Playwright / Judges
async function runAutoDemoFlow() {
  // 1. Focus input on auth-service
  document.getElementById("inputService").value = "auth-service";
  document.getElementById("inputSymptoms").value = "HikariCP connection pool exhausted (504 timeout)";
  
  // 2. Trigger investigation
  await runInvestigation("auth-service", "HikariCP connection pool exhausted (504 timeout)", "core_platform");

  // 3. Switch to Cypher & Trace tab after 3 seconds
  setTimeout(() => {
    document.getElementById("tabTrace").click();
  }, 3500);

  // 4. Switch to Memory tab after 6 seconds and pre-fill new incident
  setTimeout(() => {
    document.getElementById("tabMemory").click();
    document.getElementById("logTitle").value = "Auth Service HikariCP Leak in Token Validation";
    document.getElementById("logService").value = "auth-service";
    document.getElementById("logRootCause").value = "Unclosed session handle in JWT validator during surge";
    document.getElementById("logFix").value = "Added try-finally block and scaled max pool size to 60";
  }, 6500);
}
