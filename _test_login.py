import asyncio
from pyquotex.stable_api import Quotex

async def go():
    c = Quotex(email="matiasdomingos70@gmail.com", password="mj33mk", lang="pt")
    ok, msg = await c.connect()
    print("CONNECT", ok, msg)
    if ok:
        try:
            print("BALANCE", await c.get_balance())
            prof = await c.get_profile()
            print("PROFILE", getattr(prof, "nick_name", prof))
        except Exception as e:
            print("ERR2", e)
        await c.close()

asyncio.run(go())
