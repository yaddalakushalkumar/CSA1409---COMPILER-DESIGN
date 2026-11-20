/**
 * app.js - Frontend Orchestrator for Multi-Language Visual Compiler System
 * Manages editor interaction, multi-language switching (C, Python, Java, C++),
 * D3.js syntax tree rendering, diagnostics rendering, and VM console updates.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const codeEditor = document.getElementById("codeEditor");
  const lineNumbers = document.getElementById("lineNumbers");
  const editorStats = document.getElementById("editorStats");
  const sourceMetrics = document.getElementById("sourceMetrics");
  const langSelect = document.getElementById("langSelect");
  const sampleSelect = document.getElementById("sampleSelect");
  const editorLanguageLabel = document.getElementById("editorLanguageLabel");
  const btnCompile = document.getElementById("btnCompile");
  const btnClear = document.getElementById("btnClear");

  // Tab Buttons & Panes
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  // Tree Controls
  const btnAstMode = document.getElementById("btnAstMode");
  const btnCstMode = document.getElementById("btnCstMode");
  const treeSearchInput = document.getElementById("treeSearchInput");
  const btnZoomIn = document.getElementById("btnZoomIn");
  const btnZoomOut = document.getElementById("btnZoomOut");
  const btnResetZoom = document.getElementById("btnResetZoom");
  const nodeInspector = document.getElementById("nodeInspector");
  const inspectNodeName = document.getElementById("inspectNodeName");
  const inspectNodeDetails = document.getElementById("inspectNodeDetails");
  const btnCloseInspector = document.getElementById("btnCloseInspector");

  // Token filters
  const tokenFilterInput = document.getElementById("tokenFilterInput");
  const categoryPills = document.querySelectorAll(".category-pills .pill");

  // State
  let allSamples = [];
  let currentLanguage = "c";
  let currentCompilation = null;
  let currentTreeMode = "AST";
  let currentTokenCategory = "all";
  let d3ZoomBehavior = null;
  let d3SvgGroup = null;

  // ==========================================
  // 1. Editor Line Numbers & Events
  // ==========================================
  function updateLineNumbers() {
    const lines = codeEditor.value.split("\n");
    const nums = [];
    for (let i = 1; i <= lines.length; i++) {
      nums.push(i);
    }
    lineNumbers.innerHTML = nums.join("<br>");
    sourceMetrics.textContent = `${codeEditor.value.length} chars | ${lines.length} lines`;
  }

  function updateCursorPos() {
    const pos = codeEditor.selectionStart;
    const lines = codeEditor.value.substring(0, pos).split("\n");
    const line = lines.length;
    const col = lines[lines.length - 1].length + 1;
    editorStats.textContent = `Line ${line}, Col ${col}`;
  }

  codeEditor.addEventListener("input", () => {
    updateLineNumbers();
    debounceCompile();
  });

  codeEditor.addEventListener("keyup", updateCursorPos);
  codeEditor.addEventListener("click", updateCursorPos);

  // Tab indentation support
  codeEditor.addEventListener("keydown", (e) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const start = codeEditor.selectionStart;
      const end = codeEditor.selectionEnd;
      codeEditor.value = codeEditor.value.substring(0, start) + "    " + codeEditor.value.substring(end);
      codeEditor.selectionStart = codeEditor.selectionEnd = start + 4;
      updateLineNumbers();
    }
  });

  codeEditor.addEventListener("scroll", () => {
    lineNumbers.scrollTop = codeEditor.scrollTop;
  });

  btnClear.addEventListener("click", () => {
    codeEditor.value = "";
    updateLineNumbers();
    compileCode();
  });

  // Debounced auto-compile
  let compileTimer = null;
  function debounceCompile() {
    clearTimeout(compileTimer);
    compileTimer = setTimeout(() => {
      compileCode();
    }, 700);
  }

  // ==========================================
  // 2. Language Switcher & Samples Loader
  // ==========================================
  langSelect.addEventListener("change", (e) => {
    currentLanguage = e.target.value;
    const selectedText = langSelect.options[langSelect.selectedIndex].text;
    if (editorLanguageLabel) {
      editorLanguageLabel.textContent = `Source Code (${selectedText})`;
    }
    populateSamplesForLanguage();
  });

  async function loadAllSamples() {
    try {
      const res = await fetch("/api/samples");
      if (!res.ok) return;
      allSamples = await res.json();
      populateSamplesForLanguage();
    } catch (err) {
      console.warn("Could not load samples list:", err);
    }
  }

  function populateSamplesForLanguage() {
    sampleSelect.innerHTML = '<option value="">-- Choose Sample Program --</option>';
    const filtered = allSamples.filter(s => s.language === currentLanguage || (currentLanguage === "c" && !s.language));

    filtered.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.path;
      opt.textContent = `${s.filename} (${s.title})`;
      sampleSelect.appendChild(opt);
    });

    if (filtered.length > 0) {
      sampleSelect.value = filtered[0].path;
      loadSampleContent(filtered[0].path);
    }
  }

  async function loadSampleContent(path) {
    if (!path) return;
    try {
      const res = await fetch(`/api/samples/${path}`);
      if (!res.ok) return;
      const data = await res.json();
      codeEditor.value = data.code;
      updateLineNumbers();
      compileCode();
    } catch (err) {
      console.error("Error loading sample content:", err);
    }
  }

  sampleSelect.addEventListener("change", (e) => {
    loadSampleContent(e.target.value);
  });

  // ==========================================
  // 3. Tab Navigation & Stepper Clicks
  // ==========================================
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      switchTab(btn.dataset.tab);
    });
  });

  document.querySelectorAll(".pipeline-step").forEach(step => {
    step.addEventListener("click", () => {
      const targetTab = step.dataset.tab;
      if (targetTab) switchTab(targetTab);
    });
  });

  function switchTab(tabId) {
    tabBtns.forEach(b => b.classList.toggle("active", b.dataset.tab === tabId));
    tabPanes.forEach(p => p.classList.toggle("active", p.id === tabId));

    if (tabId === "tabTree" && currentCompilation) {
      setTimeout(() => renderTree(), 50);
    }
  }

  // ==========================================
  // 4. Multi-Stage Compilation API Request
  // ==========================================
  btnCompile.addEventListener("click", () => {
    compileCode();
  });

  async function compileCode() {
    const code = codeEditor.value;
    btnCompile.disabled = true;
    btnCompile.innerHTML = "Analyzing...";

    try {
      const res = await fetch("/api/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: code,
          language: currentLanguage,
          execute: true
        })
      });

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}`);
      }

      currentCompilation = await res.json();
      renderAllViews(currentCompilation);

    } catch (err) {
      console.error("Compilation fault:", err);
    } finally {
      btnCompile.disabled = false;
      btnCompile.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        Compile & Run
      `;
    }
  }

  function renderAllViews(data) {
    updatePipelineStepper(data.pipeline_status);
    updateDiagnostics(data.diagnostics);
    renderTree();
    updateTokenTable(data.tokens);
    updateSymbolTable(data.symbols);
    updateTacAndOptimizer(data.raw_tac, data.optimized_tac, data.optimization_logs, data.optimization_metrics);
    updateVmConsole(data.execution);
  }

  // ==========================================
  // 5. Pipeline Stepper Status Updates
  // ==========================================
  function updatePipelineStepper(status) {
    const mapping = {
      stepLexer: status.lexical,
      stepParser: status.syntactic,
      stepSemantic: status.semantic,
      stepIcg: status.icg,
      stepOptimizer: status.optimizer,
      stepVm: status.vm
    };

    for (const [stepId, st] of Object.entries(mapping)) {
      const el = document.getElementById(stepId);
      if (!el) continue;
      const dot = el.querySelector(".step-status");
      if (!dot) continue;

      dot.className = "step-status";
      if (st === "success") dot.classList.add("status-success");
      else if (st === "error") dot.classList.add("status-error");
      else if (st === "skipped") dot.classList.add("status-skipped");
      else dot.classList.add("status-pending");
    }
  }

  // ==========================================
  // 6. Diagnostics & Errors Panel
  // ==========================================
  function updateDiagnostics(diagnostics) {
    const diagCount = document.getElementById("diagCount");
    const diagSummary = document.getElementById("diagSummary");
    const diagList = document.getElementById("diagList");

    diagCount.textContent = diagnostics.length;
    diagList.innerHTML = "";

    if (!diagnostics || diagnostics.length === 0) {
      diagSummary.className = "diagnostics-summary";
      diagSummary.innerHTML = `✓ ${currentCompilation ? currentCompilation.language_name : 'Source'} multi-stage analysis complete. Zero errors detected!`;
      return;
    }

    diagSummary.className = "diagnostics-summary has-errors";
    diagSummary.innerHTML = `⚠️ Multi-stage analysis detected <strong>${diagnostics.length} diagnostic items</strong>.`;

    diagnostics.forEach(d => {
      const card = document.createElement("div");
      const sevClass = d.severity === "ERROR" ? "diag-error" : (d.severity === "WARNING" ? "diag-warning" : "diag-hint");
      card.className = `diag-card ${sevClass}`;

      let suggestionHtml = "";
      if (d.suggestion) {
        suggestionHtml = `
          <div class="diag-suggestion">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path></svg>
            <span><strong>Suggestion:</strong> ${escapeHtml(d.suggestion)}</span>
          </div>
        `;
      }

      let snippetHtml = "";
      if (d.snippet) {
        snippetHtml = `<div class="diag-snippet">${escapeHtml(d.snippet)}</div>`;
      }

      card.innerHTML = `
        <div class="diag-header">
          <div class="diag-title">
            <span class="diag-badge ${d.severity === 'ERROR' ? 'badge-err' : 'badge-warn'}">${d.severity}</span>
            <span>${d.stage} (${d.code})</span>
          </div>
          <span class="diag-loc">Line ${d.line}, Col ${d.column}</span>
        </div>
        <div class="diag-msg">${escapeHtml(d.message)}</div>
        ${snippetHtml}
        ${suggestionHtml}
      `;

      card.addEventListener("click", () => {
        highlightEditorLine(d.line);
      });

      diagList.appendChild(card);
    });
  }

  function highlightEditorLine(lineNum) {
    const lines = codeEditor.value.split("\n");
    let charOffset = 0;
    for (let i = 0; i < lineNum - 1 && i < lines.length; i++) {
      charOffset += lines[i].length + 1;
    }
    codeEditor.focus();
    codeEditor.selectionStart = charOffset;
    codeEditor.selectionEnd = charOffset + (lines[lineNum - 1] ? lines[lineNum - 1].length : 0);
    updateCursorPos();
  }

  // ==========================================
  // 7. Interactive D3.js Syntax Tree Visualizer
  // ==========================================
  btnAstMode.addEventListener("click", () => {
    btnAstMode.classList.add("active");
    btnCstMode.classList.remove("active");
    currentTreeMode = "AST";
    renderTree();
  });

  btnCstMode.addEventListener("click", () => {
    btnCstMode.classList.add("active");
    btnAstMode.classList.remove("active");
    currentTreeMode = "CST";
    renderTree();
  });

  function renderTree() {
    const svgEl = document.getElementById("treeSvg");
    const container = document.getElementById("treeContainer");
    svgEl.innerHTML = "";

    if (!currentCompilation) return;
    const treeData = (currentTreeMode === "AST") ? currentCompilation.ast : currentCompilation.cst;
    if (!treeData || Object.keys(treeData).length === 0) {
      return;
    }

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 600;

    const svg = d3.select("#treeSvg")
      .attr("width", "100%")
      .attr("height", "100%")
      .attr("viewBox", `0 0 ${width} ${height}`);

    d3SvgGroup = svg.append("g").attr("class", "tree-main-group");

    d3ZoomBehavior = d3.zoom()
      .scaleExtent([0.15, 3])
      .on("zoom", (event) => {
        d3SvgGroup.attr("transform", event.transform);
      });

    svg.call(d3ZoomBehavior);

    const root = d3.hierarchy(treeData);
    const dx = 42;
    const dy = 160;
    const treeLayout = d3.tree().nodeSize([dx, dy]);
    treeLayout(root);

    d3SvgGroup.selectAll(".tree-link")
      .data(root.links())
      .enter()
      .append("path")
      .attr("class", "tree-link")
      .attr("d", d3.linkHorizontal()
        .x(d => d.y)
        .y(d => d.x)
      );

    d3SvgGroup.selectAll(".link-label")
      .data(root.links().filter(d => d.target.data.edgeLabel))
      .enter()
      .append("text")
      .attr("class", "link-label")
      .attr("x", d => (d.source.y + d.target.y) / 2)
      .attr("y", d => (d.source.x + d.target.x) / 2 - 4)
      .attr("text-anchor", "middle")
      .text(d => d.target.data.edgeLabel);

    const catColors = {
      Root: "#a855f7",
      Declaration: "#3b82f6",
      Statement: "#06b6d4",
      ControlFlow: "#f59e0b",
      Scope: "#6366f1",
      Expression: "#ec4899",
      Literal: "#eab308",
      Identifier: "#10b981",
      "I/O": "#14b8a6",
      Terminal: "#64748b",
      NonTerminal: "#3b82f6"
    };

    const node = d3SvgGroup.selectAll(".tree-node")
      .data(root.descendants())
      .enter()
      .append("g")
      .attr("class", "tree-node")
      .attr("transform", d => `translate(${d.y},${d.x})`)
      .on("click", (event, d) => {
        openNodeInspector(d.data);
      });

    node.append("circle")
      .attr("r", 7)
      .attr("fill", d => catColors[d.data.category] || "#3b82f6")
      .attr("stroke", "#0f172a");

    node.append("text")
      .attr("dy", "0.32em")
      .attr("x", d => d.children ? -12 : 12)
      .attr("text-anchor", d => d.children ? "end" : "start")
      .text(d => d.data.name);

    const initialTransform = d3.zoomIdentity.translate(80, height / 2).scale(0.85);
    svg.call(d3ZoomBehavior.transform, initialTransform);
  }

  function openNodeInspector(data) {
    inspectNodeName.textContent = data.name || "AST Node";
    let html = `
      <p><strong>Category:</strong> <span class="badge">${data.category || 'N/A'}</span></p>
      <p><strong>Coordinates:</strong> Line ${data.line || 1}, Col ${data.column || 1}</p>
    `;
    if (data.details) {
      html += `<p><strong>Details:</strong> ${escapeHtml(data.details)}</p>`;
    }
    if (data.inferred_type) {
      html += `<p><strong>Inferred Type:</strong> <code style="color:#38bdf8">${data.inferred_type}</code></p>`;
    }
    inspectNodeDetails.innerHTML = html;
    nodeInspector.style.display = "block";

    if (data.line) {
      highlightEditorLine(data.line);
    }
  }

  btnCloseInspector.addEventListener("click", () => {
    nodeInspector.style.display = "none";
  });

  btnZoomIn.addEventListener("click", () => {
    if (d3ZoomBehavior) d3.select("#treeSvg").transition().duration(200).call(d3ZoomBehavior.scaleBy, 1.3);
  });
  btnZoomOut.addEventListener("click", () => {
    if (d3ZoomBehavior) d3.select("#treeSvg").transition().duration(200).call(d3ZoomBehavior.scaleBy, 0.7);
  });
  btnResetZoom.addEventListener("click", () => {
    renderTree();
  });

  treeSearchInput.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase().trim();
    if (!d3SvgGroup) return;

    d3SvgGroup.selectAll(".tree-node circle")
      .attr("r", 7)
      .attr("stroke", "#0f172a");

    if (!q) return;

    d3SvgGroup.selectAll(".tree-node").filter(d => {
      const name = (d.data.name || "").toLowerCase();
      const det = (d.data.details || "").toLowerCase();
      return name.includes(q) || det.includes(q);
    }).select("circle")
      .attr("r", 12)
      .attr("stroke", "#ffffff");
  });

  // ==========================================
  // 8. Token Stream Inspector
  // ==========================================
  function updateTokenTable(tokens) {
    const tbody = document.getElementById("tokenTableBody");
    tbody.innerHTML = "";
    if (!tokens) return;

    const filterText = (tokenFilterInput.value || "").toLowerCase().trim();

    tokens.forEach((t, idx) => {
      if (currentTokenCategory !== "all" && t.category !== currentTokenCategory) return;
      if (filterText && !t.lexeme.toLowerCase().includes(filterText) && !t.type.toLowerCase().includes(filterText)) return;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="color:var(--text-dim)">${idx + 1}</td>
        <td><code>${escapeHtml(t.type)}</code></td>
        <td><span class="tok-badge tok-${t.category}">${t.category}</span></td>
        <td><strong>${escapeHtml(t.lexeme)}</strong></td>
        <td style="color:#fbbf24">${t.value !== null ? escapeHtml(String(t.value)) : '-'}</td>
        <td style="color:var(--text-muted)">${t.line}:${t.column}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  tokenFilterInput.addEventListener("input", () => {
    if (currentCompilation) updateTokenTable(currentCompilation.tokens);
  });

  categoryPills.forEach(pill => {
    pill.addEventListener("click", () => {
      categoryPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      currentTokenCategory = pill.dataset.cat;
      if (currentCompilation) updateTokenTable(currentCompilation.tokens);
    });
  });

  // ==========================================
  // 9. Symbol Table Inspector
  // ==========================================
  function updateSymbolTable(symbols) {
    const tbody = document.getElementById("symbolTableBody");
    tbody.innerHTML = "";
    if (!symbols) return;

    symbols.forEach(s => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="color:#38bdf8; font-weight:600">${escapeHtml(s.name)}</td>
        <td><code style="color:#a855f7">${s.type}</code></td>
        <td><span class="badge">${s.kind}</span></td>
        <td>${s.scope_name} (ID: ${s.scope_id})</td>
        <td>${s.scope_depth !== undefined ? s.scope_depth : 0}</td>
        <td style="color:#fbbf24">+${s.offset}B</td>
        <td>Line ${s.line}</td>
        <td>${s.initialized ? '<span style="color:#10b981">✓ Yes</span>' : '<span style="color:#f59e0b">No</span>'}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ==========================================
  // 10. Intermediate Code (TAC) & Optimizer View
  // ==========================================
  function updateTacAndOptimizer(rawTac, optTac, logs, metrics) {
    document.getElementById("mOrigCount").textContent = metrics.original_instructions || 0;
    document.getElementById("mOptCount").textContent = metrics.optimized_instructions || 0;
    document.getElementById("mRedPct").textContent = metrics.reduction_percentage || "0.0%";
    document.getElementById("mOptApp").textContent = metrics.optimizations_applied || 0;

    const rawBox = document.getElementById("rawTacListing");
    rawBox.innerHTML = (rawTac || []).map(q => {
      const cmt = q.comment ? `<span class="tac-cmt">  // ${escapeHtml(q.comment)}</span>` : "";
      return `<div class="tac-line"><span class="tac-idx">${q.index}:</span><span class="tac-text">${escapeHtml(q.text)}</span>${cmt}</div>`;
    }).join("");

    const optBox = document.getElementById("optTacListing");
    optBox.innerHTML = (optTac || []).map(q => {
      const cmt = q.comment ? `<span class="tac-cmt">  // ${escapeHtml(q.comment)}</span>` : "";
      return `<div class="tac-line"><span class="tac-idx">${q.index}:</span><span class="tac-text">${escapeHtml(q.text)}</span>${cmt}</div>`;
    }).join("");

    const logBox = document.getElementById("optLogsList");
    if (!logs || logs.length === 0) {
      logBox.innerHTML = "<div style='color:var(--text-dim); padding:4px;'>No optimizations were necessary for this program structure.</div>";
    } else {
      logBox.innerHTML = logs.map(l => `
        <div class="opt-log-item">
          [<span class="opt-log-pass">${escapeHtml(l.pass)}</span>] ${escapeHtml(l.details)}
          <br><span style="color:var(--text-dim)">&nbsp;&nbsp;Before: ${escapeHtml(l.original)} ➔ After: ${escapeHtml(l.optimized)}</span>
        </div>
      `).join("");
    }
  }

  // ==========================================
  // 11. Virtual Machine Execution Console
  // ==========================================
  function updateVmConsole(exec) {
    const stdoutTerminal = document.getElementById("stdoutTerminal");
    const vmStatusBadge = document.getElementById("vmStatusBadge");
    const vmSuccess = document.getElementById("vmSuccess");
    const vmSteps = document.getElementById("vmSteps");
    const vmTime = document.getElementById("vmTime");
    const memoryGrid = document.getElementById("memoryGrid");
    const traceTbody = document.getElementById("traceTableBody");

    if (!exec) return;

    if (exec.stdout) {
      stdoutTerminal.textContent = exec.stdout;
      stdoutTerminal.style.color = "#34d399";
    } else if (exec.runtime_error) {
      stdoutTerminal.textContent = `[RUNTIME ERROR]\n${exec.runtime_error}`;
      stdoutTerminal.style.color = "#f87171";
    } else {
      stdoutTerminal.textContent = "(Program executed without standard output)";
      stdoutTerminal.style.color = "#94a3b8";
    }

    if (exec.success) {
      vmStatusBadge.className = "badge badge-success";
      vmStatusBadge.textContent = "Finished (0)";
      vmSuccess.textContent = "SUCCESS";
      vmSuccess.style.color = "#10b981";
    } else {
      vmStatusBadge.className = "badge badge-error";
      vmStatusBadge.textContent = "Error";
      vmSuccess.textContent = "FAILED";
      vmSuccess.style.color = "#ef4444";
    }

    vmSteps.textContent = exec.total_steps || 0;
    vmTime.textContent = `${exec.execution_time_ms || 0} ms`;

    memoryGrid.innerHTML = "";
    const vars = exec.variables || {};
    if (Object.keys(vars).length === 0) {
      memoryGrid.innerHTML = "<span style='color:var(--text-dim); font-size:11px'>No variables in scope</span>";
    } else {
      for (const [k, v] of Object.entries(vars)) {
        const row = document.createElement("div");
        row.className = "mem-row";
        row.innerHTML = `<span class="mem-var">${escapeHtml(k)}</span><span class="mem-val">${escapeHtml(String(v))}</span>`;
        memoryGrid.appendChild(row);
      }
    }

    traceTbody.innerHTML = "";
    (exec.trace || []).slice(0, 50).forEach(st => {
      const tr = document.createElement("tr");
      const memSnap = JSON.stringify(st.memory_snapshot || {});
      tr.innerHTML = `
        <td style="color:var(--text-dim)">${st.step}</td>
        <td><code>${st.pc}</code></td>
        <td style="color:#38bdf8"><strong>${escapeHtml(st.instruction)}</strong></td>
        <td style="color:#fbbf24; font-size:11px">${escapeHtml(memSnap)}</td>
      `;
      traceTbody.appendChild(tr);
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  loadAllSamples();
});
