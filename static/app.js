let TOK = localStorage.getItem("qtok") || "";
let ACCOUNT = "REAL";
let STRATS = {};
let ASSETS = [];

const $ = id => document.getElementById(id);

async function api(path, body) {
  const r = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: {"Content-Type": "application/json", "x-token": TOK},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (r.status === 401) { showLogin(); throw new Error("auth"); }
  return r.json();
}

function showLogin() { $("loginScr").style.display = "flex"; $("app").style.display = "none"; }

async function login() {
  const r = await fetch("/api/auth/login", {method: "POST",
    headers: {"Content-Type": "application/json"}, body: JSON.stringify({password: $("pw").value})});
  if (!r.ok) { $("loginErr").textContent = "Password errada."; return; }
  TOK = (await r.json()).token;
  localStorage.setItem("qtok", TOK);
  boot();
}

async function boot() {
  $("loginScr").style.display = "none";
  $("app").style.display = "flex";
  STRATS = await api("/api/strategies");
  ASSETS = await api("/api/assets");
  const opts = Object.entries(ASSETS).map(([k]) => `<option>${k}</option>`).join("");
  ["btAsset", "anAsset", "chAsset"].forEach(id => { $(id).innerHTML = opts; });
  const so = Object.entries(STRATS).map(([k, v]) => `<option value="${k}">${v.name}</option>`).join("");
  $("btStrategy").innerHTML = so;
  $("hStrat").innerHTML = '<option value="">Todas estratégias</option>' + so;
  renderStrats();
  loadKb();
  loadHistory();
  loadAnalysis();
  loadInsight();
  loadPatterns();
  loadProfile();
  loadChart();
  refresh();
  setInterval(refresh, 2000);
  setInterval(loadChart, 10000);
  setInterval(loadPatterns, 15000);
  setInterval(loadProfile, 15000);
  loadSignals();
  setInterval(loadSignals, 3000);
}

let _sigTs = 0;
async function loadSignals() {
  try {
    const mc = ($("sigMinConf") && $("sigMinConf").value) || 55;
    const r = await api("/api/signals?min_conf=" + mc);
    _sigTs = r.ts || Date.now() / 1000;
    $("sigScan").textContent = r.connected === false ? "bot offline (SIM)"
      : r.warming ? "a preparar dados…"
      : `${r.scanned} pares · ${new Date(r.ts * 1000).toLocaleTimeString()}`;
    const sigs = r.signals || [];
    $("noSig").style.display = sigs.length ? "none" : "block";
    $("sigBody").innerHTML = sigs.slice(0, 20).map(s => `
      <div class="card" style="border-left:3px solid ${s.signal === "call" ? "var(--g)" : "var(--r)"}${s.watch ? ";opacity:.7" : ""}">
        <div class="row" style="align-items:center">
          <b style="font-size:16px">${s.asset}</b>
          ${s.watch ? '<span class="tag" style="font-size:10.5px">OBSERVAÇÃO</span>' : ""}
          <span class="pill ${s.signal}" style="font-size:13px;padding:5px 12px">${s.action}</span>
        </div>
        <div class="sig" style="margin-top:8px">
          <span class="tag">conf ${s.confidence}%</span>
          <span class="tag">votos ${s.votes}</span>
          <span class="tag">expiração ${s.suggested_expiry >= 60 ? (s.suggested_expiry / 60) + " min" : s.suggested_expiry + "s"}</span>
          ${s.expires_in != null ? `<span class="tag" style="color:var(--y)">⏱ ${s.expires_in}s</span>` : ""}
          ${s.stale ? '<span class="tag" style="color:var(--r)">atrasado</span>' : ""}
        </div>
        <div class="disc">${s.reasons.join(" · ")}</div>
        <button class="b ${s.signal === "call" ? "go" : "stop"}" style="margin-top:10px;width:100%"
          onclick="enterManual('${s.asset}','${s.signal}',${s.suggested_expiry})">${s.action}</button>
      </div>`).join("");
  } catch (e) {}
}
setInterval(() => {
  if ($("sigAgo") && _sigTs)
    $("sigAgo").textContent = Math.max(0, Math.round(Date.now() / 1000 - _sigTs)) + "s";
}, 1000);

async function enterManual(asset, dir, expiry) {
  const amt = parseFloat(($("sigAmount") && $("sigAmount").value) || 10);
  const exp = parseInt(($("sigExpiry") && $("sigExpiry").value) || 0) || expiry;
  const r = await api("/api/trades", {asset, amount: amt, expiry: exp, direction: dir});
  if (r.ok) {
    refresh();
    if ((r.mode || "").toUpperCase() === "SIM")
      alert("Ordem SIMULADA — o bot não está ligado à tua conta Quotex. Liga em Conta & Ligação.");
  } else { alert(r.detail || "ordem rejeitada"); }
}

document.querySelectorAll("#nav button").forEach(b => {
  b.onclick = () => {
    document.querySelectorAll("#nav button").forEach(x => x.classList.remove("on"));
    document.querySelectorAll(".page").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    $("p-" + b.dataset.p).classList.add("on");
  };
});

async function setAcc(m) {
  ACCOUNT = m;
  $("accReal").className = "b " + (m === "REAL" ? "def" : "ghost");
  $("accDemo").className = "b " + (m === "PRACTICE" ? "def" : "ghost");
  if ($("accReal2")) $("accReal2").className = "b " + (m === "REAL" ? "def" : "ghost");
  if ($("accDemo2")) $("accDemo2").className = "b " + (m === "PRACTICE" ? "def" : "ghost");
  $("accPill").textContent = m;
  try {
    const r = await api("/api/broker/account/" + m);
    if (r && r.balance != null)
      $("connMsg").textContent = `Conta ${m === "REAL" ? "REAL" : "DEMO"} ativa — saldo $${Number(r.balance).toFixed(2)}`;
    refresh(); loadProfile();
  } catch (e) {
    $("connMsg").textContent = "Falha ao trocar de conta.";
  }
}

async function brokerConnect() {
  $("connMsg").textContent = "A ligar...";
  const r = await api("/api/broker/connect", {
    email: $("qEmail").value || null, password: $("qPass").value || null,
    ssid: $("qSsid").value || null, account: ACCOUNT,
  });
  $("connMsg").textContent = r.ok ? "Ligado. Saldo: $" + Number(r.balance).toFixed(2) : "Falhou: " + r.msg;
  $("connMsg").style.color = r.ok ? "var(--g)" : "var(--r)";
}


function renderStrats() {
  api("/api/history/stats").then(st => {
    $("stratGrid").innerHTML = Object.entries(STRATS).map(([k, v]) => {
      const s = st.by_strategy[k] || {};
      return `<div class="card"><b>${v.name}</b>
        <div class="disc" style="margin:6px 0">${v.desc}</div>
        <div class="sig">
          <span class="tag">trades: ${s.trades ?? 0}</span>
          <span class="tag">win: ${s.win_rate ?? 0}%</span>
          <span class="tag">P/L: $${s.pnl ?? 0}</span>
          <span class="tag">PF: ${s.profit_factor ?? "—"}</span>
          <span class="tag">DD: $${s.drawdown ?? 0}</span>
        </div>
        <button class="b ghost" style="margin-top:10px" onclick="quickBt('${k}')">▶ BACKTEST</button>
      </div>`;
    }).join("");
  });
}

function quickBt(sid) {
  document.querySelector('#nav button[data-p="backtest"]').click();
  $("btStrategy").value = sid;
  runBt();
}

async function runBt() {
  const r = await api("/api/backtest", {strategy: $("btStrategy").value,
    asset: $("btAsset").value, n_candles: parseInt($("btN").value)});
  if (!r.ok) { alert(r.error); return; }
  $("btRes").style.display = "block";
  $("btTrades").textContent = r.trades;
  $("btWr").textContent = r.win_rate + "%";
  $("btPnl").textContent = "$" + r.pnl;
  $("btPnl").className = "v mono " + (r.pnl >= 0 ? "win" : "loss");
  $("btPeriod").textContent = r.period_analyzed;
  $("btDisc").textContent = r.disclaimer;
  const cv = $("btCurve"), ctx = cv.getContext("2d"), d = r.curve;
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (d.length > 1) {
    const mn = Math.min(...d, 0), mx = Math.max(...d, 1);
    ctx.strokeStyle = "#6366f1"; ctx.lineWidth = 2; ctx.beginPath();
    d.forEach((v, i) => {
      const x = i / (d.length - 1) * cv.width, y = cv.height - 4 - (v - mn) / (mx - mn) * (cv.height - 8);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.stroke();
  }
}

async function loadHistory() {
  const q = new URLSearchParams();
  if ($("hDays").value) q.set("days", $("hDays").value);
  if ($("hResult").value) q.set("result", $("hResult").value);
  if ($("hStrat").value) q.set("strategy", $("hStrat").value);
  const rows = await api("/api/trades?" + q);
  $("hBody").innerHTML = rows.map(t =>
    `<tr><td>${new Date(t.ts * 1000).toLocaleString()}</td><td>${t.asset}</td>
     <td>${t.direction}</td><td>$${t.amount}</td><td>${t.strategy}</td>
     <td class="mono">${t.entry?.toFixed(4) ?? "—"}</td><td class="mono">${t.exit?.toFixed(4) ?? "—"}</td>
     <td class="${t.result === "win" ? "win" : "loss"}">${(t.result || "").toUpperCase()}</td>
     <td class="mono ${t.pnl >= 0 ? "win" : "loss"}">${t.pnl >= 0 ? "+" : ""}$${t.pnl}</td></tr>`).join("");
}

async function loadAnalysis() {
  const r = await api("/api/analysis/" + $("anAsset").value);
  if (r.error) { $("anBody").textContent = r.error; return; }
  $("anBody").innerHTML = `
    <div class="sig">
      <span class="tag">Trend: ${r.trend}</span><span class="tag">Momentum: ${r.momentum}</span>
      <span class="tag">Vol: ${r.volatility}</span><span class="tag">RSI: ${r.rsi}</span>
      <span class="tag">MACD: ${r.macd}</span><span class="tag">EMA: ${r.ema}</span>
      <span class="tag">Consenso: ${r.signal_agreement}</span>
      <span class="tag">Confiança: ${r.confidence}%</span>
    </div>
    <div class="mono" style="margin-top:10px;font-size:18px">Decisão: <b>${r.decision}</b></div>`;
}

async function loadKb() {
  const kb = await api("/api/knowledge");
  $("kbBody").innerHTML = kb.map(cat =>
    `<div class="card"><b>${cat.category}</b>` +
    cat.items.map(i =>
      `<div style="margin-top:10px"><b>${i.title}</b> <span class="tag">${i.author}</span>
       <div class="disc">${i.summary}</div>
       <div class="disc">Fonte: ${i.source}</div></div>`).join("") + "</div>").join("");
}

async function refresh() {
  try {
    const st = await api("/api/status");
    if (st.balance != null) $("dBalance").textContent = "$" + Number(st.balance).toFixed(2);
    if (st.account && st.account !== ACCOUNT) setAcc(st.account);
    $("accPill").textContent = st.account;
    const s = st.summary || {};
    $("dPnl").textContent = (s.pnl >= 0 ? "+" : "") + "$" + (s.pnl ?? 0);
    $("dPnl").className = "v mono " + ((s.pnl ?? 0) >= 0 ? "win" : "loss");
    $("dWr").textContent = (s.win_rate ?? 0) + "%";
    $("dOps").textContent = s.trades ?? 0;
    $("rState").textContent = st.risk?.state?.paused ? st.risk.state.pause_reason : "";
    if (st.risk?.config && !$("rMaxTrade").value) {
      $("rMaxTrade").value = st.risk.config.max_amount_per_trade;
      $("rDailyLoss").value = st.risk.config.max_daily_loss;
      $("rConsec").value = st.risk.config.max_consecutive_losses;
      $("rSim").value = st.risk.config.max_simultaneous;
      $("rCool").value = st.risk.config.cooldown_sec;
      $("rTarget").value = st.risk.config.daily_target;
    }
    const ls = st.last_signal;
    $("dSignal").innerHTML = ls ? `${ls.asset}: <b>${(ls.signal || "sem sinal").toUpperCase()}</b>
      <span class="tag">conf ${ls.confidence}%</span> <span class="tag">${ls.risk}</span>` : "—";
    // countdown do trade aberto mais antigo
    const ot = st.open_trades || [];
    if (ot.length) {
      const rem = Math.max(0, Math.round(ot[0].open_ts + ot[0].expiry - Date.now() / 1000));
      const mm = String(Math.floor(rem / 60)).padStart(2, "0"), ss = String(rem % 60).padStart(2, "0");
      $("openBody").innerHTML = ot.map(t =>
        `<tr><td>${t.asset} ${t.direction.toUpperCase()} $${t.amount}</td><td class="mono">${t.expiry}s</td></tr>`).join("");
      $("noOpen").style.display = "none";
    } else {
      $("openBody").innerHTML = "";
      $("noOpen").style.display = "block";
    }
  } catch (e) {}
}

// ---------------- gráfico de candles em tempo real ----------------
async function loadChart() {
  try {
    const r = await api(`/api/candles/${$("chAsset").value}?period=${$("chPeriod").value}&n=100`);
    if (!r.candles || !r.candles.length) return;
    drawCandles(r.candles);
  } catch (e) {}
}

function drawCandles(cds) {
  const cv = $("chart"), ctx = cv.getContext("2d");
  const W = cv.width = cv.clientWidth * 2, H = cv.height = 560;
  ctx.clearRect(0, 0, W, H);
  const n = cds.length, pad = 14, pw = W - pad * 2, ph = H - pad * 2;
  const hi = Math.max(...cds.map(c => c.high)), lo = Math.min(...cds.map(c => c.low));
  const span = (hi - lo) || 1;
  const y = v => pad + (hi - v) / span * ph;
  const cw = Math.max(2, pw / n);
  // grid
  ctx.strokeStyle = "#1d2536"; ctx.lineWidth = 1;
  for (let i = 1; i < 5; i++) {
    ctx.beginPath(); ctx.moveTo(0, pad + ph * i / 5); ctx.lineTo(W, pad + ph * i / 5); ctx.stroke();
  }
  ctx.font = "20px ui-monospace"; ctx.fillStyle = "#8b93a8"; ctx.textAlign = "left";
  for (let i = 0; i <= 5; i++) {
    const v = hi - span * i / 5;
    ctx.fillText(v.toFixed(v > 100 ? 1 : 5), 6, y(v) - 4);
  }
  cds.forEach((c, i) => {
    const x = pad + i * cw + cw * 0.15, w = cw * 0.7;
    const up = c.close >= c.open;
    ctx.strokeStyle = up ? "#22e58c" : "#ff5c6c";
    ctx.fillStyle = up ? "#22e58c" : "#ff5c6c";
    ctx.beginPath(); ctx.moveTo(x + w / 2, y(c.high)); ctx.lineTo(x + w / 2, y(c.low)); ctx.stroke();
    const yo = y(c.open), yc = y(c.close);
    ctx.fillRect(x, Math.min(yo, yc), w, Math.max(1.5, Math.abs(yc - yo)));
  });
  // preço atual
  const last = cds[n - 1].close;
  ctx.strokeStyle = "#7c5cff"; ctx.setLineDash([6, 4]);
  ctx.beginPath(); ctx.moveTo(0, y(last)); ctx.lineTo(W, y(last)); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = "#7c5cff"; ctx.textAlign = "right";
  ctx.fillText(last.toFixed(last > 100 ? 1 : 5), W - 8, y(last) - 5);
}

// ---------------- padrões ----------------
async function loadPatterns() {
  try {
    const r = await api(`/api/patterns/${$("chAsset").value}?period=${$("chPeriod").value}`);
    if (r.error) { $("patBody").innerHTML = `<div class="disc">${r.error}</div>`; return; }
    const agg = r.aggregate;
    $("patAgg").innerHTML = `<span class="pill ${agg === "call" ? "call" : agg === "put" ? "put" : "off"}">
      Sinal: ${agg.toUpperCase()}</span>
      <span class="tag">bullish ${r.bullish}</span><span class="tag">bearish ${r.bearish}</span>
      <span class="tag">score ${r.score}</span>`;
    $("patBody").innerHTML = (r.patterns || []).slice(-14).reverse().map(p =>
      `<div class="pat"><b>${p.pattern}</b>
        <span class="d"><span class="pill ${p.direction}">${p.direction.toUpperCase()}</span>
        <span class="tag">${Math.round(p.strength * 100)}%</span></span></div>`).join("")
      || '<div class="disc">Sem padrões agora.</div>';
  } catch (e) {}
}

// ---------------- AI insight ----------------
async function loadInsight() {
  try {
    const r = await api("/api/ai/insight/" + $("anAsset").value);
    $("aiText").textContent = r.text || r.error || "";
    $("aiSrc").textContent = r.source === "groq" ? "Groq AI" : "local";
  } catch (e) {}
}

// ---------------- perfil ----------------
async function loadProfile() {
  try {
    const r = await api("/api/profile");
    $("connState").innerHTML = r.connected
      ? '<span style="color:var(--g)">● Quotex ligada</span>'
      : '<span style="color:var(--amber)">● modo SIM</span>';
    if (r.connected) {
      $("profBody").innerHTML = `
        <div class="sig"><span class="pill real">${(r.account || "").toUpperCase()}</span></div>
        <table style="margin-top:8px">
          ${r.nickname ? `<tr><td>Nick</td><td><b>${r.nickname}</b></td></tr>` : ""}
          ${r.email ? `<tr><td>Email</td><td>${r.email}</td></tr>` : ""}
          <tr><td>Saldo DEMO</td><td class="mono win">$${Number(r.demo_balance).toFixed(2)}</td></tr>
          <tr><td>Saldo REAL</td><td class="mono ${r.live_balance > 0 ? "win" : "loss"}">$${Number(r.live_balance).toFixed(2)}</td></tr>
          <tr><td>Conta ativa</td><td class="mono"><b>$${Number(r.current_balance ?? 0).toFixed(2)}</b></td></tr>
        </table>`;
    } else {
      $("profBody").innerHTML = `<div class="disc">Modo simulador — liga a tua conta Quotex ao lado.
        Saldo SIM: $${Number(r.balance ?? 0).toFixed(2)}</div>`;
    }
  } catch (e) {}
}

async function saveRisk() {
  await api("/api/risk", {
    max_amount_per_trade: parseFloat($("rMaxTrade").value),
    max_daily_loss: parseFloat($("rDailyLoss").value),
    max_consecutive_losses: parseInt($("rConsec").value),
    max_simultaneous: parseInt($("rSim").value),
    cooldown_sec: parseInt($("rCool").value),
    daily_target: parseFloat($("rTarget").value),
  });
}
async function resumeRisk() { await api("/api/risk/resume", {}); refresh(); }

if (TOK) boot(); else showLogin();
