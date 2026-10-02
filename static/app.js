let account = "PRACTICE";

function setAcc(m) {
  account = m;
  document.getElementById("accDemo").classList.toggle("on", m === "PRACTICE");
  document.getElementById("accReal").classList.toggle("on", m === "REAL");
  if (connected) fetch("/api/account/" + m, {method: "POST"});
}
let connected = false;

async function api(path, body) {
  const r = await fetch(path, body ? {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : undefined);
  return r.json();
}

async function login() {
  document.getElementById("err").textContent = "";
  const res = await api("/api/login", {
    email: email.value || null, password: password.value || null,
    ssid: ssid.value || null, account,
  });
  if (!res.ok) { document.getElementById("err").textContent = "Falhou: " + res.msg; return; }
  connected = true;
  document.getElementById("balance").textContent = "$" + Number(res.balance).toFixed(2);
  document.getElementById("err").textContent = "Ligado.";
  document.getElementById("err").style.color = "var(--green)";
}

async function start() {
  const res = await api("/api/start", {
    asset: asset.value.trim(), amount: parseFloat(amount.value),
    expiry: parseInt(expiry.value), strategy: strategy.value,
  });
  if (!res.ok) alert(res.msg || "Não iniciou");
  refresh();
}

async function stop() { await api("/api/stop", {}); refresh(); }

async function loadStrategies() {
  const s = await api("/api/strategies");
  strategy.innerHTML = Object.entries(s).map(([k, v]) => `<option value="${k}">${v.name}</option>`).join("");
}

async function refresh() {
  const st = await api("/api/status");
  document.getElementById("runPill").className = "pill " + (st.running ? "on" : "off");
  document.getElementById("runPill").textContent = st.running ? "A operar" : "Parado";
  if (st.balance != null) document.getElementById("balance").textContent = "$" + Number(st.balance).toFixed(2);
  document.getElementById("account").textContent = st.account || "—";
  document.getElementById("signal").textContent = st.last_signal ? `${st.last_signal.asset} → ${st.last_signal.signal || "sem sinal"}` : "—";
  document.getElementById("open").textContent = st.open_trade ? `${st.open_trade.dir.toUpperCase()} $${st.open_trade.amount}` : "—";
  document.getElementById("btnStart").disabled = st.running;
  document.getElementById("btnStop").disabled = !st.running;

  const sb = document.getElementById("statsBody");
  sb.innerHTML = Object.entries(st.history_stats || {}).map(([k, s]) =>
    `<tr><td>${k}</td><td>${s.trades}</td><td>${s.win_rate}%</td><td class="${s.pnl >= 0 ? "win" : "loss"}">$${s.pnl}</td></tr>`).join("");

  const h = await api("/api/history");
  document.getElementById("tradesBody").innerHTML = (h.trades || []).slice(0, 50).map(t =>
    `<tr><td>${new Date(t.ts * 1000).toLocaleTimeString()}</td><td>${t.asset}</td>
     <td>${t.direction}</td><td>$${t.amount}</td>
     <td class="${t.result === "win" ? "win" : "loss"}">${t.result === "win" ? "+" : ""}${t.profit ?? t.result}</td></tr>`).join("");
}

loadStrategies();
refresh();
setInterval(refresh, 3000);
