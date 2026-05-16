"""Standalone Tedial POC FastAPI app.

Run from a runtime that has FastAPI/httpx/uvicorn, for example:

    E:\MITAS\venvs\asr\Scripts\python.exe -m uvicorn core.api.tedial.app:create_app --factory --reload
"""

TEDIAL_POC_HTML = """<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MITAS Tedial</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1d232a;
      --muted: #65717f;
      --line: #d9dee6;
      --accent: #0f766e;
      --accent-strong: #0b5d56;
      --warn: #a15c00;
      --bad: #b42318;
      --ok: #15803d;
      --ink: #111827;
      --shadow: 0 14px 36px rgba(17, 24, 39, 0.10);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 "Segoe UI", Arial, sans-serif;
    }

    button,
    input {
      font: inherit;
    }

    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto auto 1fr;
    }

    .topbar {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 0 24px;
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      font-weight: 700;
      color: var(--ink);
    }

    .brand-mark {
      width: 28px;
      height: 28px;
      display: grid;
      place-items: center;
      border-radius: 6px;
      background: #111827;
      color: white;
      font-size: 12px;
      letter-spacing: 0;
      flex: 0 0 auto;
    }

    .tabs {
      display: flex;
      gap: 4px;
      align-items: center;
      padding: 8px 24px 0;
      background: #ffffff;
      border-bottom: 1px solid var(--line);
      overflow-x: auto;
    }

    .tab {
      appearance: none;
      border: 1px solid transparent;
      border-bottom: 0;
      border-radius: 8px 8px 0 0;
      color: var(--muted);
      background: transparent;
      padding: 10px 14px;
      text-decoration: none;
      white-space: nowrap;
    }

    .tab.active {
      color: var(--ink);
      background: var(--bg);
      border-color: var(--line);
      font-weight: 700;
    }

    .workspace {
      width: min(1180px, calc(100vw - 32px));
      margin: 20px auto 32px;
      display: grid;
      gap: 16px;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }

    .toolbar {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 12px;
      align-items: center;
      padding: 16px;
    }

    .session {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
      flex-wrap: wrap;
    }

    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 32px;
      padding: 5px 10px;
      border-radius: 999px;
      background: #eef2f7;
      color: var(--muted);
      border: 1px solid var(--line);
      font-weight: 700;
    }

    .dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: currentColor;
    }

    .status.connected {
      background: #e8f5ee;
      color: var(--ok);
      border-color: #bfe5ce;
    }

    .status.connecting {
      background: #fff7e7;
      color: var(--warn);
      border-color: #f3d199;
    }

    .status.error,
    .status.expired {
      background: #fff0ef;
      color: var(--bad);
      border-color: #f4b8b2;
    }

    .actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
    }

    .remember {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      min-height: 34px;
      white-space: nowrap;
    }

    .button {
      appearance: none;
      border: 1px solid var(--line);
      border-radius: 7px;
      min-height: 34px;
      padding: 7px 12px;
      background: #ffffff;
      color: var(--text);
      cursor: pointer;
    }

    .button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #ffffff;
      font-weight: 700;
    }

    .button.primary:hover {
      background: var(--accent-strong);
    }

    .button:disabled {
      opacity: 0.55;
      cursor: wait;
    }

    .searchbar {
      display: grid;
      grid-template-columns: minmax(160px, 1fr) auto;
      gap: 10px;
      padding: 16px;
      border-top: 1px solid var(--line);
    }

    .searchbar input {
      min-width: 0;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 8px 11px;
      background: #ffffff;
      color: var(--text);
    }

    .meta {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 16px;
      color: var(--muted);
      border-bottom: 1px solid var(--line);
      min-height: 48px;
    }

    .results {
      display: grid;
      gap: 10px;
      padding: 12px;
    }

    .empty {
      padding: 32px 16px;
      text-align: center;
      color: var(--muted);
    }

    .result {
      display: grid;
      grid-template-columns: 152px minmax(0, 1fr) auto;
      gap: 14px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      padding: 10px;
      min-height: 100px;
    }

    .thumb {
      width: 152px;
      aspect-ratio: 16 / 9;
      border-radius: 6px;
      object-fit: cover;
      background: #e9edf2;
      border: 1px solid #ccd3dc;
    }

    .result h3 {
      margin: 0 0 8px;
      font-size: 16px;
      line-height: 1.3;
      color: var(--ink);
      overflow-wrap: anywhere;
    }

    .fields {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 5px 16px;
      margin: 0;
      color: var(--muted);
      font-size: 12px;
    }

    .fields div {
      min-width: 0;
      overflow-wrap: anywhere;
    }

    .fields dt {
      display: inline;
      font-weight: 700;
      color: #46515f;
    }

    .fields dd {
      display: inline;
      margin: 0;
    }

    .row-actions {
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: flex-end;
      min-width: 96px;
      flex-wrap: wrap;
    }

    .message {
      min-height: 22px;
      overflow-wrap: anywhere;
    }

    .modal {
      position: fixed;
      inset: 0;
      display: none;
      background: rgba(15, 23, 42, 0.58);
      z-index: 20;
      padding: 24px;
    }

    .modal.open {
      display: grid;
      place-items: center;
    }

    .login-panel {
      width: min(1120px, 100%);
      height: min(760px, calc(100vh - 48px));
      display: grid;
      grid-template-rows: auto 1fr;
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 24px 70px rgba(0, 0, 0, 0.28);
      overflow: hidden;
    }

    .preview-panel {
      width: min(980px, 100%);
      max-height: calc(100vh - 48px);
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 24px 70px rgba(0, 0, 0, 0.28);
      overflow: hidden;
    }

    .login-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      font-weight: 700;
    }

    .preview-body {
      display: grid;
      gap: 12px;
      padding: 14px;
      overflow: auto;
    }

    .preview-video {
      width: 100%;
      max-height: 46vh;
      aspect-ratio: 16 / 9;
      background: #111827;
      border-radius: 7px;
    }

    .preview-links {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }

    .import-plan {
      margin: 0;
      max-height: 220px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 10px;
      background: #f8fafc;
      color: #253142;
      font: 12px/1.45 Consolas, "Courier New", monospace;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    iframe {
      width: 100%;
      height: 100%;
      border: 0;
      background: #ffffff;
    }

    @media (max-width: 760px) {
      .topbar,
      .tabs {
        padding-left: 14px;
        padding-right: 14px;
      }

      .toolbar,
      .searchbar,
      .result {
        grid-template-columns: 1fr;
      }

      .actions,
      .row-actions {
        justify-content: flex-start;
      }

      .thumb {
        width: 100%;
      }

      .fields {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark">M</span>
        <span>MITAS</span>
      </div>
      <a class="button" href="/docs">API</a>
    </header>

    <nav class="tabs" aria-label="MITAS">
      <span class="tab active">Tedial</span>
      <a class="tab" href="/docs">Swagger</a>
    </nav>

    <section class="workspace" aria-label="Tedial">
      <div class="panel">
        <div class="toolbar">
          <div class="session">
            <span id="statusBadge" class="status">
              <span class="dot"></span>
              <span id="statusText">Ba&#287;l&#305; de&#287;il</span>
            </span>
            <span id="cookieText" class="message">0 cookie</span>
          </div>
          <div class="actions">
            <label class="remember">
              <input id="remember" type="checkbox" />
              <span>Beni hat&#305;rla</span>
            </label>
            <button id="connectBtn" class="button primary" type="button">Ba&#287;lan</button>
            <button id="healthBtn" class="button" type="button">Yenile</button>
            <button id="forgetBtn" class="button" type="button">&#199;&#305;k</button>
          </div>
        </div>

        <form id="searchForm" class="searchbar">
          <input id="searchInput" name="searchField" autocomplete="off" value="tr-*" aria-label="Tedial arama" />
          <button id="searchBtn" class="button primary" type="submit">Ara</button>
        </form>
      </div>

      <div class="panel">
        <div class="meta">
          <strong>Sonu&#231;lar</strong>
          <span id="summary">Haz&#305;r</span>
        </div>
        <div id="results" class="results">
          <div class="empty">Tedial aramas&#305; bekleniyor.</div>
        </div>
      </div>
    </section>
  </main>

  <div id="loginModal" class="modal" role="dialog" aria-modal="true" aria-label="Tedial login">
    <div class="login-panel">
      <div class="login-head">
        <span>Tedial Login</span>
        <button id="closeLoginBtn" class="button" type="button">Kapat</button>
      </div>
      <iframe id="loginFrame" title="Tedial login"></iframe>
    </div>
  </div>

  <div id="previewModal" class="modal" role="dialog" aria-modal="true" aria-label="Tedial onizleme">
    <div class="preview-panel">
      <div class="login-head">
        <span id="previewTitle">Tedial asset</span>
        <button id="closePreviewBtn" class="button" type="button">Kapat</button>
      </div>
      <div class="preview-body">
        <video id="previewVideo" class="preview-video" controls preload="metadata"></video>
        <div class="preview-links">
          <a id="previewMpdLink" class="button" href="#" target="_blank" rel="noreferrer">MPD</a>
          <a id="previewMediaLink" class="button" href="#" target="_blank" rel="noreferrer">Media proxy</a>
          <button id="enqueueBtn" class="button primary" type="button">Kuyru&#287;a al</button>
          <button id="runAsrBtn" class="button primary" type="button">ASR</button>
          <button id="runOcrBtn" class="button" type="button">OCR</button>
          <button id="runBothBtn" class="button" type="button">ASR+OCR</button>
          <span id="previewStatus" class="message">Haz&#305;r</span>
        </div>
        <pre id="importPlan" class="import-plan">{}</pre>
      </div>
    </div>
  </div>

  <script>
    const statusBadge = document.querySelector("#statusBadge");
    const statusText = document.querySelector("#statusText");
    const cookieText = document.querySelector("#cookieText");
    const summary = document.querySelector("#summary");
    const results = document.querySelector("#results");
    const connectBtn = document.querySelector("#connectBtn");
    const healthBtn = document.querySelector("#healthBtn");
    const forgetBtn = document.querySelector("#forgetBtn");
    const remember = document.querySelector("#remember");
    const searchForm = document.querySelector("#searchForm");
    const searchInput = document.querySelector("#searchInput");
    const searchBtn = document.querySelector("#searchBtn");
    const loginModal = document.querySelector("#loginModal");
    const loginFrame = document.querySelector("#loginFrame");
    const closeLoginBtn = document.querySelector("#closeLoginBtn");
    const previewModal = document.querySelector("#previewModal");
    const previewTitle = document.querySelector("#previewTitle");
    const previewVideo = document.querySelector("#previewVideo");
    const previewStatus = document.querySelector("#previewStatus");
    const previewMpdLink = document.querySelector("#previewMpdLink");
    const previewMediaLink = document.querySelector("#previewMediaLink");
    const enqueueBtn = document.querySelector("#enqueueBtn");
    const runAsrBtn = document.querySelector("#runAsrBtn");
    const runOcrBtn = document.querySelector("#runOcrBtn");
    const runBothBtn = document.querySelector("#runBothBtn");
    const importPlan = document.querySelector("#importPlan");
    const closePreviewBtn = document.querySelector("#closePreviewBtn");
    let loginPoll = null;
    let jobPoll = null;
    let previewItem = null;

    function setBusy(button, busy) {
      button.disabled = busy;
    }

    function setSummary(text) {
      summary.textContent = text;
    }

    function needsReconnect(error) {
      const text = String(error && error.message ? error.message : error).toLowerCase();
      return text.includes("not connected")
        || text.includes("expired")
        || text.includes("reconnect")
        || text.includes("session");
    }

    function statusLabel(status) {
      const labels = {
        connected: "Ba\u011fl\u0131",
        connecting: "Ba\u011flan\u0131yor",
        disconnected: "Ba\u011fl\u0131 de\u011fil",
        expired: "S\u00fcresi doldu",
        error: "Hata"
      };
      return labels[status] || status || "Bilinmiyor";
    }

    function renderStatus(data) {
      const status = data.status || "disconnected";
      statusBadge.className = "status " + status;
      statusText.textContent = statusLabel(status);
      const names = Array.isArray(data.cookie_names) ? data.cookie_names : [];
      cookieText.textContent = names.length + " cookie" + (names.length ? " (" + names.join(", ") + ")" : "");
      remember.checked = Boolean(data.remember);
      return status;
    }

    async function getJson(url, options = {}) {
      const response = await fetch(url, options);
      let body = null;
      try {
        body = await response.json();
      } catch {
        body = {};
      }
      if (!response.ok) {
        const detail = body.detail || response.statusText;
        throw new Error(detail);
      }
      return body;
    }

    async function getText(url) {
      const response = await fetch(url);
      const text = await response.text();
      if (!response.ok) {
        throw new Error(text || response.statusText);
      }
      return text;
    }

    async function loadStatus(useHealth = false) {
      const data = await getJson(useHealth ? "/api/tedial/session/health" : "/api/tedial/session");
      return renderStatus(data);
    }

    function openLogin(url) {
      loginFrame.src = url;
      loginModal.classList.add("open");
      window.clearInterval(loginPoll);
      loginPoll = window.setInterval(async () => {
        try {
          const status = await loadStatus(false);
          if (status === "connected") {
            closeLogin();
            setSummary("Tedial oturumu ba\u011fland\u0131");
          }
        } catch (error) {
          setSummary(error.message);
        }
      }, 1800);
    }

    function closeLogin() {
      loginModal.classList.remove("open");
      loginFrame.src = "about:blank";
      window.clearInterval(loginPoll);
      loginPoll = null;
      loadStatus(false).catch((error) => setSummary(error.message));
    }

    async function startSession() {
      setBusy(connectBtn, true);
      try {
        const data = await getJson("/api/tedial/session/start", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({remember: remember.checked})
        });
        renderStatus(data);
        openLogin(data.login_url || "/api/tedial/login/");
      } catch (error) {
        setSummary(error.message);
      } finally {
        setBusy(connectBtn, false);
      }
    }

    async function forgetSession() {
      setBusy(forgetBtn, true);
      try {
        const data = await getJson("/api/tedial/session/forget", {method: "POST"});
        renderStatus(data);
        results.innerHTML = '<div class="empty">Tedial aramas&#305; bekleniyor.</div>';
        setSummary("Oturum kapat\u0131ld\u0131");
      } catch (error) {
        setSummary(error.message);
      } finally {
        setBusy(forgetBtn, false);
      }
    }

    function valueOrDash(value) {
      return value === null || value === undefined || value === "" ? "-" : String(value);
    }

    function manifestUrl(item) {
      if (!item.repository_id || !item.asset_id) {
        return "";
      }
      return "/api/tedial/assets/" + encodeURIComponent(item.asset_id)
        + "/manifest?repository_id=" + encodeURIComponent(item.repository_id);
    }

    function importPlanUrl(item) {
      if (!item.repository_id || !item.asset_id) {
        return "";
      }
      const params = new URLSearchParams({
        repository_id: item.repository_id,
        sequence_id: item.sequence_id || "",
        title: item.title || "",
        asset_type: item.asset_type || ""
      });
      return "/api/tedial/assets/" + encodeURIComponent(item.asset_id) + "/import-plan?" + params.toString();
    }

    function firstBaseUrl(mpdText) {
      const match = mpdText.match(/<BaseURL>([^<]+)<\\/BaseURL>/);
      return match ? match[1].trim() : "";
    }

    function buildImportPlan(item, mpd, mediaUrl) {
      return {
        source: "tedial",
        title: item.title || null,
        repository_id: item.repository_id || null,
        asset_id: item.asset_id || null,
        sequence_id: item.sequence_id || null,
        asset_type: item.asset_type || null,
        manifest_url: mpd || null,
        media_proxy_url: mediaUrl || null,
        keyframe_proxy_url: item.keyframe_url ? "/api/tedial/keyframe?url=" + encodeURIComponent(item.keyframe_url) : null,
        mitas_job_draft: {
          media_id: item.asset_id ? "tedial_" + item.asset_id : "tedial_asset",
          pipeline_name: "asr",
          step_name: "tedial_lowres_import",
          status: "pending",
          input_artifacts: [mpd, mediaUrl].filter(Boolean)
        },
        generated_at: new Date().toISOString()
      };
    }

    function enqueuePayload(item) {
      return {
        repository_id: item.repository_id,
        sequence_id: item.sequence_id || null,
        title: item.title || null,
        asset_type: item.asset_type || null
      };
    }

    async function enqueueItem(item, options = {}) {
      if (!item.repository_id || !item.asset_id) {
        throw new Error("Repository veya asset bilgisi eksik");
      }
      const result = await getJson("/api/tedial/assets/" + encodeURIComponent(item.asset_id) + "/enqueue", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(enqueuePayload(item))
      });
      if (options.showModal) {
        previewItem = item;
        previewTitle.textContent = item.title || "Tedial asset";
        previewMpdLink.href = manifestUrl(item) || "#";
        previewMediaLink.href = "#";
        previewVideo.removeAttribute("src");
        importPlan.textContent = JSON.stringify(result, null, 2);
        previewModal.classList.add("open");
      }
      const job = result.job || {};
      setSummary((result.created ? "Job olu\u015ftu: " : "Job zaten var: ") + (job.job_id || "-"));
      previewStatus.textContent = (result.created ? "Kuyru\u011fa al\u0131nd\u0131: " : "Kuyrukta mevcut: ") + (job.job_id || "-");
      return result;
    }

    function closePreview() {
      previewVideo.pause();
      previewVideo.removeAttribute("src");
      previewVideo.load();
      previewModal.classList.remove("open");
      previewItem = null;
      window.clearInterval(jobPoll);
      jobPoll = null;
    }

    async function runJob(jobId, modules) {
      const data = await getJson("/api/tedial/jobs/" + encodeURIComponent(jobId) + "/run", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({modules, background: true})
      });
      importPlan.textContent = JSON.stringify(data, null, 2);
      previewStatus.textContent = modules.join("+").toUpperCase() + " calisiyor: " + jobId;
      pollJob(jobId);
      return data;
    }

    function pollJob(jobId) {
      window.clearInterval(jobPoll);
      jobPoll = window.setInterval(async () => {
        try {
          const job = await getJson("/api/tedial/jobs/" + encodeURIComponent(jobId));
          importPlan.textContent = JSON.stringify(job, null, 2);
          previewStatus.textContent = "Job " + job.status + ": " + jobId;
          if (["done", "failed", "partial", "cancelled", "skipped"].includes(job.status)) {
            window.clearInterval(jobPoll);
            jobPoll = null;
            setSummary("Job " + job.status + ": " + jobId);
          }
        } catch (error) {
          previewStatus.textContent = error.message;
        }
      }, 2500);
    }

    async function runPreviewModules(modules) {
      if (!previewItem) {
        return;
      }
      setBusy(runAsrBtn, true);
      setBusy(runOcrBtn, true);
      setBusy(runBothBtn, true);
      try {
        const result = await enqueueItem(previewItem, {showModal: false});
        const jobId = result.job && result.job.job_id;
        if (!jobId) {
          throw new Error("Job id alinamadi");
        }
        await runJob(jobId, modules);
      } catch (error) {
        if (needsReconnect(error)) {
          previewStatus.textContent = "Tedial oturumu gerekli";
          await startSession();
        } else {
          previewStatus.textContent = error.message;
        }
      } finally {
        setBusy(runAsrBtn, false);
        setBusy(runOcrBtn, false);
        setBusy(runBothBtn, false);
      }
    }

    async function openPreview(item) {
      const mpd = manifestUrl(item);
      previewItem = item;
      previewTitle.textContent = item.title || "Tedial asset";
      previewStatus.textContent = "Manifest okunuyor";
      previewVideo.removeAttribute("src");
      previewMpdLink.href = mpd || "#";
      previewMediaLink.href = "#";
      importPlan.textContent = JSON.stringify(buildImportPlan(item, mpd, ""), null, 2);
      previewModal.classList.add("open");
      if (!mpd) {
        previewStatus.textContent = "Repository veya asset bilgisi eksik";
        return;
      }
      try {
        const mpdText = await getText(mpd);
        const mediaUrl = firstBaseUrl(mpdText);
        let plan = buildImportPlan(item, mpd, mediaUrl);
        try {
          plan = await getJson(importPlanUrl(item));
          plan.media_proxy_url = mediaUrl || null;
        } catch {
          plan.media_proxy_url = mediaUrl || null;
        }
        importPlan.textContent = JSON.stringify(plan, null, 2);
        if (mediaUrl) {
          previewMediaLink.href = mediaUrl;
          previewVideo.src = mediaUrl;
          previewStatus.textContent = "MPD ve media proxy haz\u0131r";
        } else {
          previewStatus.textContent = "MPD i\u00e7inde BaseURL bulunamad\u0131";
        }
      } catch (error) {
        previewStatus.textContent = error.message;
      }
    }

    function renderResults(items) {
      if (!items.length) {
        results.innerHTML = '<div class="empty">Sonuc yok.</div>';
        return;
      }
      results.innerHTML = "";
      for (const item of items) {
        const article = document.createElement("article");
        article.className = "result";

        const img = document.createElement("img");
        img.className = "thumb";
        img.alt = "";
        if (item.keyframe_url) {
          img.src = "/api/tedial/keyframe?url=" + encodeURIComponent(item.keyframe_url);
        }

        const body = document.createElement("div");
        const title = document.createElement("h3");
        title.textContent = item.title || "(baslik yok)";
        const fields = document.createElement("dl");
        fields.className = "fields";
        const pairs = [
          ["Repository", item.repository_id],
          ["Asset", item.asset_id],
          ["Sequence", item.sequence_id],
          ["Tip", item.asset_type]
        ];
        for (const [label, value] of pairs) {
          const wrap = document.createElement("div");
          const dt = document.createElement("dt");
          const dd = document.createElement("dd");
          dt.textContent = label + ": ";
          dd.textContent = valueOrDash(value);
          wrap.append(dt, dd);
          fields.append(wrap);
        }
        body.append(title, fields);

        const actions = document.createElement("div");
        actions.className = "row-actions";
        const mpd = manifestUrl(item);
        if (mpd) {
          const previewButton = document.createElement("button");
          previewButton.className = "button primary";
          previewButton.type = "button";
          previewButton.textContent = "\u00d6nizle";
          previewButton.addEventListener("click", () => openPreview(item));
          actions.append(previewButton);
        }
        if (mpd) {
          const importButton = document.createElement("button");
          importButton.className = "button";
          importButton.type = "button";
          importButton.textContent = "\u0130\u00e7e al";
          importButton.addEventListener("click", async () => {
            importButton.disabled = true;
            try {
              await enqueueItem(item, {showModal: true});
            } catch (error) {
              setSummary(error.message);
            } finally {
              importButton.disabled = false;
            }
          });
          actions.append(importButton);
        }
        if (mpd) {
          const asrButton = document.createElement("button");
          asrButton.className = "button";
          asrButton.type = "button";
          asrButton.textContent = "ASR";
          asrButton.addEventListener("click", async () => {
            asrButton.disabled = true;
            try {
              await openPreview(item);
              await runPreviewModules(["asr"]);
            } catch (error) {
              setSummary(error.message);
            } finally {
              asrButton.disabled = false;
            }
          });
          actions.append(asrButton);
        }
        if (mpd) {
          const link = document.createElement("a");
          link.className = "button";
          link.href = mpd;
          link.target = "_blank";
          link.rel = "noreferrer";
          link.textContent = "MPD";
          actions.append(link);
        }

        article.append(img, body, actions);
        results.append(article);
      }
    }

    async function runSearch(event) {
      event.preventDefault();
      const query = searchInput.value.trim();
      if (!query) {
        searchInput.focus();
        return;
      }
      setBusy(searchBtn, true);
      setSummary("Aran\u0131yor");
      try {
        const data = await getJson("/api/tedial/search", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({searchField: query})
        });
        renderResults(data.items || []);
        setSummary((data.count || 0) + " sonu\u00e7");
      } catch (error) {
        if (needsReconnect(error)) {
          setSummary("Tedial oturumu gerekli");
          await startSession();
        } else {
          setSummary(error.message);
        }
      } finally {
        setBusy(searchBtn, false);
      }
    }

    connectBtn.addEventListener("click", startSession);
    healthBtn.addEventListener("click", async () => {
      setBusy(healthBtn, true);
      try {
        await loadStatus(true);
        setSummary("Durum guncellendi");
      } catch (error) {
        setSummary(error.message);
      } finally {
        setBusy(healthBtn, false);
      }
    });
    forgetBtn.addEventListener("click", forgetSession);
    closeLoginBtn.addEventListener("click", closeLogin);
    closePreviewBtn.addEventListener("click", closePreview);
    enqueueBtn.addEventListener("click", async () => {
      if (!previewItem) {
        return;
      }
      setBusy(enqueueBtn, true);
      try {
        const result = await enqueueItem(previewItem, {showModal: false});
        importPlan.textContent = JSON.stringify(result, null, 2);
      } catch (error) {
        previewStatus.textContent = error.message;
      } finally {
        setBusy(enqueueBtn, false);
      }
    });
    runAsrBtn.addEventListener("click", () => runPreviewModules(["asr"]));
    runOcrBtn.addEventListener("click", () => runPreviewModules(["ocr"]));
    runBothBtn.addEventListener("click", () => runPreviewModules(["asr", "ocr"]));
    searchForm.addEventListener("submit", runSearch);
    loadStatus(false).catch((error) => setSummary(error.message));
  </script>
</body>
</html>
"""


def create_app():
    try:
        from fastapi import FastAPI
        from fastapi import Request
        from fastapi.responses import HTMLResponse
        from fastapi.responses import RedirectResponse
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("Tedial POC app requires fastapi in the active runtime") from exc

    from core.api.tedial.router import create_tedial_router

    app = FastAPI(title="MITAS Tedial POC", version="0.1.0")
    app.include_router(create_tedial_router())

    @app.get("/", include_in_schema=False)
    async def index() -> RedirectResponse:
        return RedirectResponse(url="/tedial", status_code=307)

    @app.get("/tedial", include_in_schema=False)
    async def tedial_ui() -> HTMLResponse:
        return HTMLResponse(TEDIAL_POC_HTML)

    @app.get("/iTClient/{path:path}", include_in_schema=False)
    async def redirect_itclient_path(path: str, request: Request) -> RedirectResponse:
        suffix = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(url=f"/api/tedial/login/iTClient/{path}{suffix}", status_code=307)

    return app
