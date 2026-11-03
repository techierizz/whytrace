let networkInstance = null;
let temporalNetworkInstance = null;
let currentActiveTab = "investigation";

document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    setupEventListeners();
    await checkHealth();
    runQuery("Why is the connection pool retry limit set to 3?");
}

function setupEventListeners() {
    document.getElementById("tabInvestigation").addEventListener("click", () => switchTab("investigation"));
    document.getElementById("tabCompare").addEventListener("click", () => switchTab("compare"));
    document.getElementById("tabTemporal").addEventListener("click", () => switchTab("temporal"));
    document.getElementById("tabAnalytics").addEventListener("click", () => switchTab("analytics"));

    document.getElementById("queryForm").addEventListener("submit", (e) => {
        e.preventDefault();
        const query = document.getElementById("queryInput").value.trim();
        if (query) runQuery(query);
    });

    document.querySelectorAll(".hero-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const query = chip.getAttribute("data-query");
            document.getElementById("queryInput").value = query;
            switchTab("investigation");
            runQuery(query);
        });
    });

    document.getElementById("resetGraphBtn").addEventListener("click", () => {
        if (networkInstance) networkInstance.fit({ animation: true });
    });

    document.getElementById("showFullGraphBtn").addEventListener("click", async () => {
        try {
            const res = await fetch("/api/graph/full");
            const data = await res.json();
            renderVisNetwork(data.nodes, data.edges, "networkCanvas", false);
        } catch (err) {
            console.error("Failed to load full graph", err);
        }
    });

    const slider = document.getElementById("temporalYearSlider");
    slider.addEventListener("input", (e) => {
        const year = parseInt(e.target.value);
        document.getElementById("currentYearDisplay").innerText = year;
        loadTemporalSnapshot(year);
    });

    document.getElementById("refreshAttritionBtn").addEventListener("click", loadAttritionReport);

    const ghModal = document.getElementById("githubModal");
    document.getElementById("openGithubModalBtn").addEventListener("click", () => ghModal.classList.remove("hidden"));
    document.getElementById("closeGithubModalBtn").addEventListener("click", () => ghModal.classList.add("hidden"));
    document.getElementById("cancelGithubModalBtn").addEventListener("click", () => ghModal.classList.add("hidden"));

    document.getElementById("githubIngestForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const repo = document.getElementById("githubRepoInput").value.trim();
        const token = document.getElementById("githubTokenInput").value.trim() || null;
        const btn = document.getElementById("startGithubIngestBtn");
        
        btn.innerText = "Ingesting GitHub Repo...";
        btn.disabled = true;

        try {
            const res = await fetch("/api/ingest/github", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ repo, token, max_items: 15 })
            });
            const data = await res.json();
            if (res.ok) {
                alert(`✅ ${data.message}\nPRs: ${data.stats.prs_ingested} | Commits: ${data.stats.commits_ingested} | Decisions: ${data.stats.decisions_extracted}`);
                ghModal.classList.add("hidden");
                switchTab("investigation");
                const fullRes = await fetch("/api/graph/full");
                const fullData = await fullRes.json();
                renderVisNetwork(fullData.nodes, fullData.edges, "networkCanvas", false);
            } else {
                alert("GitHub Ingest Error: " + (data.detail || "Failed to fetch repository"));
            }
        } catch (err) {
            alert("Network Error: " + err.message);
        } finally {
            btn.innerText = "Ingest Live Graph";
            btn.disabled = false;
        }
    });

    const configModal = document.getElementById("configModal");
    document.getElementById("openConfigBtn").addEventListener("click", () => configModal.classList.remove("hidden"));
    document.getElementById("closeConfigBtn").addEventListener("click", () => configModal.classList.add("hidden"));
    document.getElementById("cancelConfigBtn").addEventListener("click", () => configModal.classList.add("hidden"));

    document.getElementById("configForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const uri = document.getElementById("neo4jUriInput").value.trim();
        const user = document.getElementById("neo4jUserInput").value.trim();
        const password = document.getElementById("neo4jPassInput").value.trim();
        const btn = document.getElementById("saveConfigBtn");

        btn.innerText = "Connecting...";
        btn.disabled = true;

        try {
            const res = await fetch("/api/connect", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ uri, user, password })
            });
            const data = await res.json();
            if (data.status === "success") {
                alert(data.message);
                configModal.classList.add("hidden");
                checkHealth();
                runQuery(document.getElementById("queryInput").value);
            } else {
                alert("Connection failed: " + data.message);
            }
        } catch (err) {
            alert("Network error: " + err.message);
        } finally {
            btn.innerText = "Connect & Reseed";
            btn.disabled = false;
        }
    });

    document.getElementById("closeDrawerBtn").addEventListener("click", () => {
        document.getElementById("nodeDetailDrawer").classList.add("hidden");
    });
}

function switchTab(tabId) {
    currentActiveTab = tabId;

    document.querySelectorAll(".view-panel").forEach(p => p.classList.add("hidden"));

    document.querySelectorAll(".nav-tab").forEach(t => {
        t.className = "nav-tab px-3.5 py-1.5 rounded-lg font-medium text-slate-400 hover:text-white transition flex items-center gap-1.5";
    });

    if (tabId === "investigation") {
        document.getElementById("sectionInvestigation").classList.remove("hidden");
        document.getElementById("tabInvestigation").className = "nav-tab px-3.5 py-1.5 rounded-lg font-medium transition bg-cyan-500/20 text-cyan-300 border border-cyan-500/30";
        if (networkInstance) networkInstance.fit();
    } else if (tabId === "compare") {
        document.getElementById("sectionCompare").classList.remove("hidden");
        document.getElementById("tabCompare").className = "nav-tab px-3.5 py-1.5 rounded-lg font-medium transition bg-cyan-500/20 text-cyan-300 border border-cyan-500/30";
        runComparison(document.getElementById("queryInput").value);
    } else if (tabId === "temporal") {
        document.getElementById("sectionTemporal").classList.remove("hidden");
        document.getElementById("tabTemporal").className = "nav-tab px-3.5 py-1.5 rounded-lg font-medium transition bg-cyan-500/20 text-cyan-300 border border-cyan-500/30";
        loadTemporalSnapshot(parseInt(document.getElementById("temporalYearSlider").value));
    } else if (tabId === "analytics") {
        document.getElementById("sectionAnalytics").classList.remove("hidden");
        document.getElementById("tabAnalytics").className = "nav-tab px-3.5 py-1.5 rounded-lg font-medium transition bg-purple-500/20 text-purple-300 border border-purple-500/30";
        loadAttritionReport();
    }
}

async function checkHealth() {
    try {
        const res = await fetch("/api/health");
        const data = await res.json();
        const badge = document.getElementById("neo4jBadge");
        const txt = document.getElementById("neo4jStatusText");

        if (data.neo4j_connected) {
            txt.innerText = "Neo4j AuraDB (Cloud)";
            txt.className = "text-emerald-300 font-bold";
            badge.className = "flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-mono bg-emerald-950/40 border-emerald-700/60";
        } else {
            txt.innerText = "Neo4j Engine (Ready)";
            txt.className = "text-cyan-300";
            badge.className = "flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-mono bg-slate-900 border-slate-800";
        }
    } catch (e) {
        console.error("Health check error", e);
    }
}

async function runQuery(queryText) {
    const submitBtn = document.getElementById("submitBtn");
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Tracing...</span>`;

    try {
        const res = await fetch("/api/query", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: queryText })
        });
        const data = await res.json();
        renderResults(data);

        if (data.subgraph && data.subgraph.nodes) {
            renderVisNetwork(data.subgraph.nodes, data.subgraph.edges, "networkCanvas", false);
        }

        if (currentActiveTab === "compare") {
            runComparison(queryText);
        }
    } catch (err) {
        console.error("Query execution failed", err);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>Trace</span><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>`;
    }
}

async function runComparison(queryText) {
    try {
        const res = await fetch("/api/compare", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: queryText })
        });
        const data = await res.json();

        const vec = data.vector_search_result;
        document.getElementById("vectorScore").innerText = vec.top_similarity_score ? `${Math.round(vec.top_similarity_score * 100)}% Cosine Match` : "N/A";
        document.getElementById("vectorDoc").innerText = vec.retrieved_document || "General Doc";
        document.getElementById("vectorAnswer").innerText = `"${vec.generated_answer}"`;
        document.getElementById("vectorFlaw").innerText = vec.flaw_explanation;

        const g = data.whytrace_graph_result;
        if (g.confidence.is_refusal) {
            document.getElementById("graphRuling").innerText = "REFUSAL (No documented consensus)";
            document.getElementById("graphAnswer").innerText = g.confidence.refusal_reason;
        } else if (g.active_decision) {
            document.getElementById("graphRuling").innerText = g.active_decision.title || g.active_decision.summary;
            let ans = `ACTIVE RULING: ${g.active_decision.summary}. `;
            if (g.superseded_decisions && g.superseded_decisions.length > 0) {
                const s = g.superseded_decisions[0];
                ans += `Quietly superseded prior policy from ${s.date ? s.date.slice(0, 10) : 'earlier'} following incident/PR review. `;
            }
            if (g.person_to_ask) {
                ans += `Contact ${g.person_to_ask.name} (${g.person_to_ask.handle}) for institutional context.`;
            }
            document.getElementById("graphAnswer").innerText = ans;
        }
    } catch (err) {
        console.error("Comparison load error", err);
    }
}

async function loadTemporalSnapshot(year) {
    try {
        const res = await fetch(`/api/graph/temporal?year=${year}`);
        const data = await res.json();
        renderVisNetwork(data.nodes, data.edges, "temporalCanvas", true);
    } catch (err) {
        console.error("Failed to load temporal graph", err);
    }
}

async function loadAttritionReport() {
    try {
        const res = await fetch("/api/analytics/attrition");
        const data = await res.json();
        
        document.getElementById("orphanCount").innerText = `${data.summary.orphan_entity_count} (${data.summary.orphan_risk_percentage}%)`;
        document.getElementById("activeDecCount").innerText = `${data.summary.active_decisions} Active / ${data.summary.superseded_decisions} Dead`;

        const tbody = document.getElementById("orphanTableBody");
        if (data.orphan_entities.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="py-4 text-center text-slate-500">No high-risk orphan entities detected.</td></tr>`;
        } else {
            tbody.innerHTML = data.orphan_entities.map(e => `
                <tr class="border-b border-slate-800/60 hover:bg-slate-900/50">
                    <td class="py-2.5 px-3 font-bold text-white">${e.name}</td>
                    <td class="py-2.5 px-3 text-slate-400">${e.path}</td>
                    <td class="py-2.5 px-3">
                        <span class="px-2 py-0.5 rounded text-[10px] ${e.risk_level === 'CRITICAL' ? 'bg-rose-950 text-rose-400 border border-rose-800' : 'bg-amber-950 text-amber-400 border border-amber-800'}">
                            ${e.risk_level}
                        </span>
                    </td>
                    <td class="py-2.5 px-3 text-slate-300">${e.reason}</td>
                </tr>
            `).join('');
        }
    } catch (err) {
        console.error("Failed to load attrition analytics", err);
    }
}

function renderResults(data) {
    const container = document.getElementById("resultsContent");
    const conf = data.confidence || { score: 0, percentage: 0, signals: [] };

    let html = "";

    if (conf.is_refusal) {
        html += `
            <div class="p-4 rounded-xl bg-amber-950/30 border border-amber-600/60 text-amber-200 space-y-2 glow-border">
                <div class="flex items-center gap-2 font-bold text-amber-400 text-sm">
                    <svg class="w-5 h-5 shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
                    <span>HONEST GRAPH REFUSAL TRIGGERED</span>
                </div>
                <p class="text-xs leading-relaxed text-slate-300">${conf.refusal_reason}</p>
                <div class="text-[11px] font-mono text-amber-300/80 pt-1 border-t border-amber-800/40">
                    WhyTrace refuses to fabricate institutional intent when the graph lacks provenance.
                </div>
            </div>
        `;
    }

    if (data.active_decision) {
        const d = data.active_decision;
        html += `
            <div class="p-4 rounded-xl bg-[#0c1626] border-2 border-emerald-500/70 space-y-2.5 glow-emerald">
                <div class="flex items-center justify-between">
                    <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-bold uppercase tracking-wide">
                        ● Active Governing Decision
                    </span>
                    <span class="text-[11px] font-mono text-slate-400">${d.timestamp ? d.timestamp.slice(0, 10) : ''}</span>
                </div>
                <h3 class="text-sm font-bold text-white tracking-tight">${d.title || d.summary}</h3>
                <p class="text-xs text-slate-300 leading-relaxed">${d.rationale || d.summary}</p>
                <div class="flex items-center gap-2 pt-1 text-[11px] font-mono text-emerald-400/90">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                    <span>Enforced via Neo4j Graph Lineage</span>
                </div>
            </div>
        `;
    }

    if (data.superseded_decisions && data.superseded_decisions.length > 0) {
        html += `
            <div class="p-4 rounded-xl bg-[#140f1a] border border-rose-800/60 space-y-3">
                <div class="flex items-center justify-between">
                    <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-800 font-bold uppercase">
                        ⚠ Superseded (Dead) Decisions Caught by Graph
                    </span>
                    <span class="text-[10px] font-mono text-rose-400 font-semibold">Traversed via [:SUPERSEDES*]</span>
                </div>
        `;

        data.superseded_decisions.forEach(sd => {
            html += `
                <div class="p-3 rounded-lg bg-rose-950/20 border border-rose-900/40 text-xs space-y-1">
                    <div class="flex items-center justify-between text-slate-400">
                        <span class="line-through font-mono text-slate-300">${sd.summary}</span>
                        <span class="font-mono text-[10px]">${sd.date ? sd.date.slice(0, 10) : ''}</span>
                    </div>
                    <div class="text-[11px] text-rose-300/90 font-mono mt-1">
                        ↳ Overridden: ${sd.overridden_by && sd.overridden_by[0] ? sd.overridden_by[0].reason : 'Overridden by later pull request'}
                    </div>
                </div>
            `;
        });

        html += `</div>`;
    }

    html += `
        <div class="p-4 rounded-xl bg-[#0a0f1d] border border-slate-800 space-y-2.5">
            <div class="flex items-center justify-between text-xs">
                <span class="font-semibold text-slate-300 flex items-center gap-1.5">
                    <svg class="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                    Topological Graph Confidence
                </span>
                <span class="font-mono font-bold ${conf.score >= 0.7 ? 'text-emerald-400' : (conf.score >= 0.35 ? 'text-amber-400' : 'text-rose-400')}">
                    ${conf.percentage}% — ${conf.status_label}
                </span>
            </div>

            <div class="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-800">
                <div class="h-full rounded-full transition-all duration-700 ${conf.score >= 0.7 ? 'bg-gradient-to-r from-emerald-500 to-teal-400' : (conf.score >= 0.35 ? 'bg-amber-400' : 'bg-rose-500')}" style="width: ${conf.percentage}%"></div>
            </div>

            <div class="grid grid-cols-2 gap-2 pt-2 text-[10px] font-mono text-slate-400">
                ${conf.signals.map(s => `
                    <div class="flex items-center justify-between p-1.5 rounded bg-slate-900/60 border border-slate-800">
                        <span>${s.name}</span>
                        <span class="${s.status === 'VERIFIED' || s.status === 'ACTIVE' || s.status === 'FOUND' ? 'text-emerald-400' : 'text-slate-600'}">${s.weight}</span>
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    if (data.person_to_ask) {
        const p = data.person_to_ask;
        html += `
            <div class="p-3.5 rounded-xl bg-[#0f172a] border border-slate-800 flex items-center justify-between text-xs">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-full bg-gradient-to-tr from-purple-500 to-cyan-500 flex items-center justify-center font-bold text-white text-sm">
                        ${p.name.charAt(0)}
                    </div>
                    <div>
                        <div class="font-bold text-white flex items-center gap-1.5">
                            <span>${p.name}</span>
                            <span class="text-[10px] font-mono text-cyan-400">${p.handle}</span>
                        </div>
                        <div class="text-[11px] text-slate-400">${p.role}</div>
                    </div>
                </div>
                <div class="text-right">
                    <span class="inline-block px-2 py-0.5 rounded text-[10px] font-mono ${p.is_active ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-slate-800 text-slate-400'}">
                        ${p.is_active ? '● Active Maintainer' : 'Exited'}
                    </span>
                </div>
            </div>
        `;
    }

    if (data.evidence_chain && data.evidence_chain.length > 0) {
        html += `
            <div class="space-y-2 pt-1">
                <div class="text-xs font-semibold text-slate-400 flex items-center gap-1.5 px-1">
                    <svg class="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>
                    Verifiable Evidence Chain (${data.evidence_chain.length} Artifacts)
                </div>
        `;

        data.evidence_chain.forEach(item => {
            const isIncident = item.type === "INCIDENT";
            const borderCol = isIncident ? "border-rose-900/60 bg-rose-950/20" : "border-slate-800 bg-[#0a0f1d]";
            const badgeCol = isIncident ? "bg-rose-950 text-rose-400 border-rose-800" : "bg-cyan-950 text-cyan-400 border-cyan-800";

            html += `
                <div class="p-3 rounded-xl border ${borderCol} text-xs space-y-1.5">
                    <div class="flex items-center justify-between">
                        <span class="text-[10px] font-mono px-2 py-0.5 rounded border ${badgeCol} font-semibold">
                            ${item.badge}
                        </span>
                        <span class="text-[10px] font-mono text-slate-400">${item.date ? item.date.slice(0, 10) : ''}</span>
                    </div>
                    <div class="font-semibold text-slate-200">${item.title}</div>
                    <p class="text-[11px] text-slate-400 leading-relaxed">${item.detail}</p>
                </div>
            `;
        });

        html += `</div>`;
    }

    container.innerHTML = html;
}

function renderVisNetwork(nodesRaw, edgesRaw, containerId, isTemporal = false) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!isTemporal) {
        document.getElementById("graphStats").innerText = `Nodes: ${nodesRaw.length} | Edges: ${edgesRaw.length}`;
    }

    const nodes = nodesRaw.map(n => {
        let color = "#38bdf8";
        let shape = "dot";
        let size = 18;

        const label = n.label || (n.labels ? n.labels[0] : "Node");

        if (label === "CodeEntity") {
            color = "#06b6d4";
            shape = "hexagon";
            size = 24;
        } else if (label === "Decision") {
            if (n.status === "SUPERSEDED") {
                color = "#f43f5e";
                size = 20;
            } else {
                color = "#10b981";
                size = 22;
            }
            shape = "diamond";
        } else if (label === "Incident") {
            color = "#ef4444";
            shape = "triangle";
            size = 22;
        } else if (label === "PullRequest") {
            color = "#f59e0b";
            size = 18;
        } else if (label === "Commit") {
            color = "#a855f7";
            size = 14;
        } else if (label === "Person") {
            color = "#ec4899";
            shape = "star";
            size = 20;
        }

        return {
            id: n.id,
            label: n.name || n.title || n.summary || n.sha || n.id,
            title: `Type: ${label}\nID: ${n.id}`,
            color: {
                background: color,
                border: "#ffffff",
                highlight: { background: "#ffffff", border: color }
            },
            shape: shape,
            size: size,
            font: { color: "#f8fafc", face: "JetBrains Mono", size: 11 },
            raw: n
        };
    });

    const edges = edgesRaw.map(e => {
        const isSupersedes = e.type === "SUPERSEDES";
        return {
            from: e.source,
            to: e.target,
            label: e.type,
            arrows: "to",
            color: isSupersedes ? { color: "#f43f5e", highlight: "#ff0055" } : { color: "#475569", highlight: "#38bdf8" },
            dashes: isSupersedes,
            width: isSupersedes ? 2.5 : 1.2,
            font: { color: isSupersedes ? "#f43f5e" : "#94a3b8", size: 9, align: "middle", face: "JetBrains Mono" }
        };
    });

    const data = {
        nodes: new vis.DataSet(nodes),
        edges: new vis.DataSet(edges)
    };

    const options = {
        physics: {
            solver: "forceAtlas2Based",
            forceAtlas2Based: {
                gravitationalConstant: -38,
                centralGravity: 0.01,
                springLength: 95,
                springConstant: 0.08
            },
            stabilization: { iterations: 100 }
        },
        interaction: {
            hover: true,
            tooltipDelay: 100,
            zoomView: true
        }
    };

    if (isTemporal) {
        if (temporalNetworkInstance) temporalNetworkInstance.destroy();
        temporalNetworkInstance = new vis.Network(container, data, options);
    } else {
        if (networkInstance) networkInstance.destroy();
        networkInstance = new vis.Network(container, data, options);
        networkInstance.on("click", (params) => {
            if (params.nodes.length > 0) {
                const selectedId = params.nodes[0];
                const rawNode = nodesRaw.find(n => n.id === selectedId);
                if (rawNode) showNodeDrawer(rawNode);
            }
        });
    }
}

function showNodeDrawer(node) {
    const drawer = document.getElementById("nodeDetailDrawer");
    document.getElementById("drawerNodeType").innerText = node.label || (node.labels ? node.labels[0] : "NODE");
    document.getElementById("drawerNodeTitle").innerText = node.name || node.title || node.summary || node.id;

    const propsContainer = document.getElementById("drawerNodeProps");
    let propHtml = "";
    for (const [k, v] of Object.entries(node)) {
        if (k !== "raw") {
            propHtml += `
                <div class="border-b border-slate-800/60 pb-1">
                    <span class="text-cyan-400">${k}:</span> 
                    <span class="text-slate-300">${typeof v === 'object' ? JSON.stringify(v) : v}</span>
                </div>
            `;
        }
    }
    propsContainer.innerHTML = propHtml;
    drawer.classList.remove("hidden");
}
