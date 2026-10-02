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
  ["abAsset", "mAsset", "btAsset", "anAsset"].forEach(id => { $(id).innerHTML = opts; });
  const so = Object.entries(STRATS).map(([k, v]) => `<option value="${k}">${v.name}</option>`).join("");
  $("abStrategy").innerHTML = so;
  $("abStrategy").value = "ai_ensemble";
  $("btStrategy").innerHTML = so;
  $("hStrat").innerHTML = '<option value="">Todas estratégias</option>' + so;
  renderStrats();
  loadKb();
  loadHistory();
  loadAnalysis();
  refresh();
  setInterval(refresh, 2000);
}

document.querySelectorAll("#nav button").forEach(b => {
  b.onclick = () => {
    document.querySelectorAll("#nav button").forEach(x => x.classList.remove("on"));
    document.querySelectorAll(".page").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    $("p-" + b.dataset.p).classList.add("on");
  };
});

function setAcc(m) {
  ACCOUNT = m;
  $("accReal").className = "b " + (m === "REAL" ? "def" : "ghost");
  $("accDemo").className = "b " + (m === "PRACTICE" ? "def" : "ghost");
  $("accPill").textContent = m;
  api("/api/broker/account/" + m).catch(() => {});
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

async function abStart() {
  await api("/api/autobot/start", {
    asset: $("abAsset").value, amount: parseFloat($("abAmount").value),
    expiry: parseInt($("abExpiry").value), strategy: $("abStrategy").value,
    min_confidence: parseInt($("abConf").value),
  });
  refresh();
}
async function abStop() { await api("/api/autobot/stop", {}); refresh(); }
async function manual(dir) {
  const r = await api("/api/trades", {asset: $("mAsset").value,
    amount: parseFloat($("mAmount").value), expiry: parseInt($("mExpiry").value), direction: dir});
  if (!r.ok) alert(r.detail || "erro");
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
    $("accPill").textContent = st.account;
    const s = st.summary || {};
    $("dPnl").textContent = (s.pnl >= 0 ? "+" : "") + "$" + (s.pnl ?? 0);
    $("dPnl").className = "v mono " + ((s.pnl ?? 0) >= 0 ? "win" : "loss");
    $("dWr").textContent = (s.win_rate ?? 0) + "%";
    $("dOps").textContent = s.trades ?? 0;
    $("abPill").className = "pill " + (st.autobot ? "on" : "off");
    $("abPill").textContent = st.autobot ? "ON" : "OFF";
    $("abPhase").textContent = st.phase;
    $("riskMsg").textContent = st.risk?.state?.paused ? st.risk.state.pause_reason : "";
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
    $("abReasons").innerHTML = (ls?.reasons || []).map(r => `<span class="tag">${r}</span>`).join("");
    // countdown do trade aberto mais antigo
    const ot = st.open_trades || [];
    if (ot.length) {
      const rem = Math.max(0, Math.round(ot[0].open_ts + ot[0].expiry - Date.now() / 1000));
      const mm = String(Math.floor(rem / 60)).padStart(2, "0"), ss = String(rem % 60).padStart(2, "0");
      $("countdown").textContent = `${mm}:${ss}`;
      $("openBody").innerHTML = ot.map(t =>
        `<tr><td>${t.asset} ${t.direction.toUpperCase()} $${t.amount}</td><td class="mono">${t.expiry}s</td></tr>`).join("");
      $("noOpen").style.display = "none";
    } else {
      $("countdown").textContent = "—";
      $("openBody").innerHTML = "";
      $("noOpen").style.display = "block";
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
