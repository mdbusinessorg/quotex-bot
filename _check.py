import re, json
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
        ws.on("framereceived", on_frame); ws.on("framesent", on_frame)
    except Exception:
        pass

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:29229")
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.on("websocket", on_ws)
    page.goto("https://qxbroker.com/pt/sign-in", timeout=60000)
    page.wait_for_timeout(8000)
    form = page.locator("form", has=page.locator("button:has-text('Entrar')")).first
    form.locator("input[name=email]").fill("matiasdomingos70@gmail.com")
    form.locator("input[type=password]").fill("mj33mk")
    page.locator("button:has-text('Entrar')").first.click()
    page.wait_for_timeout(12000)
    print("URL:", page.url)
    print("BODY:", page.evaluate("document.body.innerText")[:2000])
    print("SSID result:", FOUND[0] if FOUND else "NONE")
    page.close()
