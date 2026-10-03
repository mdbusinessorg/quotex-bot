import json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:29229")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    page.goto("https://qxbroker.com/pt/sign-in", timeout=60000)
    page.wait_for_timeout(8000)
    inputs = page.eval_on_selector_all("input", "els => els.map(e => ({name:e.name,type:e.type,id:e.id,ph:e.placeholder}))")
    buttons = page.eval_on_selector_all("button", "els => els.map(e => ({type:e.type,id:e.id,txt:e.innerText.slice(0,40)}))")
    print(json.dumps(inputs, indent=1)[:2000])
    print(json.dumps(buttons, indent=1)[:2000])
    page.close()
