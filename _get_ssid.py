import json, re
from playwright.sync_api import sync_playwright

FOUND = []
def on_ws(ws):
    def on_frame(payload):
        if "session" in payload:
            m = re.search(r'"session"\s*:\s*"([^"]+)"', payload)
            if m:
                FOUND.append(m.group(1))
                print("SSID:", m.group(1)[:40])
    try:
        ws.on("framereceived", on_frame)
        ws.on("framesent", on_frame)
    except Exception:
        pass

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:29229")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    page.on("websocket", on_ws)
    page.goto("https://qxbroker.com/pt/sign-in", timeout=60000)
    page.wait_for_timeout(8000)
    forms = page.eval_on_selector_all(
        "form", "els => els.map(e => ({id:e.id, cls:e.className, n:e.querySelectorAll('input').length}))")
    print("FORMS:", json.dumps(forms))
    # form de login = o que tem email+password mas sem checkboxes de registo
    login_sel = None
    for f in forms:
        n = page.eval_on_selector(
            f"form#{f['id']}" if f["id"] else "form",
            "e => ({em:e.querySelectorAll('input[name=email]').length, pw:e.querySelectorAll('input[type=password]').length, cb:e.querySelectorAll('input[type=checkbox]').length})"
        ) if f["id"] else None
        print(f, n)
    # heurística: usar o form que contém o botão 'Entrar'
    btns = page.locator("button:has-text('Entrar')")
    print("Entrar btns:", btns.count())
    if btns.count():
        form = page.locator("form", has=page.locator("button:has-text('Entrar')")).first
        form.locator("input[name=email]").fill("matiasdomingos70@gmail.com")
        form.locator("input[type=password]").fill("mj33mk")
        form.locator("button[type=submit], button:has-text('Entrar')").first.click()
        print("submitted")
    for _ in range(25):
        if FOUND or page.url != "https://qxbroker.com/pt/sign-in" and "sign-in" not in page.url:
            break
        page.wait_for_timeout(1500)
    print("URL:", page.url)
    print("RESULT:", FOUND[0] if FOUND else "NONE")
    page.close()
