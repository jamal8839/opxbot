import aiohttp
import asyncio
import telebot
import json
import os
from urllib.parse import urlparse
import threading

# ================= CONFIG =================
BOT_TOKEN = "8624893001:AAE3lyn3N-nwK3I6G0pZTEifsoo7iirwcJU"
ADMIN_ID = 1890133465

API_KEYS = ["5f0c27a375684c", "d8455300b2ec41", "de80f45752044b"]

MONITOR_INTERVAL = 90
ALERT_THRESHOLD = 0.01

bot = telebot.TeleBot(BOT_TOKEN)
DATA_FILE = "data.json"

# ================= DATA =================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return {"approved_users": [], "banned_users": [], "users": {}}
    return {"approved_users": [], "banned_users": [], "users": {}}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()

# ================= UTIL =================
def is_approved(uid):
    uid = str(uid)
    if int(uid) == ADMIN_ID:
        return True
    if uid in data.get("banned_users", []):
        return False
    return uid in data.get("approved_users", [])

def get_slug(url):
    try:
        parts = urlparse(url).path.strip('/').split('/')
        if "collection" in parts:
            index = parts.index("collection")
            return parts[index + 1]
    except:
        pass
    return None

# ================= ETH PRICE (COINGECKO + OTHERS) =================
async def get_eth_usd(session):
    # API 1: CoinGecko
    try:
        async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", timeout=5) as r:
            if r.status == 200:
                res = await r.json()
                return float(res["ethereum"]["usd"])
    except: pass

    # API 2: Coinbase
    try:
        async with session.get("https://api.coinbase.com/v2/prices/ETH-USD/spot", timeout=5) as r:
            if r.status == 200:
                res = await r.json()
                return float(res["data"]["amount"])
    except: pass

    # API 3: CryptoCompare
    try:
        async with session.get("https://min-api.cryptocompare.com/data/price?fsym=ETH&tsyms=USD", timeout=5) as r:
            if r.status == 200:
                res = await r.json()
                return float(res["USD"])
    except: pass

    # API 4: Binance
    try:
        async with session.get("https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT", timeout=5) as r:
            if r.status == 200:
                res = await r.json()
                return float(res["price"])
    except: pass
    
    return None

async def fetch_price(session, slug):
    url = f"https://api.opensea.io/api/v2/collections/{slug}/stats"
    for key in API_KEYS:
        try:
            async with session.get(url, headers={"X-API-KEY": key}, timeout=10) as r:
                if r.status == 200:
                    js = await r.json()
                    return js.get("total", {}).get("floor_price")
        except: continue
    return None

async def get_price(session, slug, retries=2):
    for _ in range(retries):
        p = await fetch_price(session, slug)
        if p is not None: return float(p)
        await asyncio.sleep(1)
    return None

async def fetch_contract_address(session, slug):
    url = f"https://api.opensea.io/api/v2/collections/{slug}"
    for key in API_KEYS:
        try:
            async with session.get(url, headers={"X-API-KEY": key}, timeout=10) as r:
                if r.status == 200:
                    js = await r.json()
                    contracts = js.get("contracts", [])
                    if contracts: return contracts[0].get("address")
        except: continue
    return None

# ================= ADMIN =================
@bot.message_handler(commands=['users'])
def list_all_users(msg):
    if msg.chat.id != ADMIN_ID:
        return
    approved = data.get("approved_users", [])
    banned = data.get("banned_users", [])
    all_user_info = data.get("users", {})
    
    text = "👥 *User Management List*\n\n"
    text += "✅ *Approved Users:*\n"
    if approved:
        for uid in approved:
            info = all_user_info.get(uid, {}).get("info", "Unknown User")
            text += f"• `{uid}` - {info}\n"
    else:
        text += "No approved users.\n"
    
    text += "\n🚫 *Banned Users:*\n"
    if banned:
        for uid in banned:
            info = all_user_info.get(uid, {}).get("info", "Unknown User")
            text += f"• `{uid}` - {info}\n"
    else:
        text += "No banned users.\n"
    bot.reply_to(msg, text, parse_mode="Markdown")

@bot.message_handler(commands=['approve'])
def approve(msg):
    if msg.chat.id != ADMIN_ID:
        return
    try:
        args = msg.text.split()
        if len(args) < 2: return bot.reply_to(msg, "Usage: /approve <user_id>")
        uid = str(args[1])
        if uid in data.get("banned_users", []):
            data["banned_users"].remove(uid)
        if uid not in data.get("approved_users", []):
            data["approved_users"].append(uid)
        save_data()
        bot.reply_to(msg, f"✅ Approved {uid}")
    except Exception as e:
        bot.reply_to(msg, f"Error: {str(e)}")

@bot.message_handler(commands=['ban'])
def ban(msg):
    if msg.chat.id != ADMIN_ID:
        return
    try:
        args = msg.text.split()
        if len(args) < 2: return bot.reply_to(msg, "Usage: /ban <user_id>")
        uid = str(args[1])
        if uid in data.get("approved_users", []):
            data["approved_users"].remove(uid)
        if uid not in data.get("banned_users", []):
            data.setdefault("banned_users", []).append(uid)
        save_data()
        bot.reply_to(msg, f"🚫 Banned {uid}")
    except Exception as e:
        bot.reply_to(msg, f"Error: {str(e)}")

@bot.message_handler(commands=['unban'])
def unban(msg):
    if msg.chat.id != ADMIN_ID:
        return
    try:
        args = msg.text.split()
        if len(args) < 2: return bot.reply_to(msg, "Usage: /unban <user_id>")
        uid = str(args[1])
        if uid in data.get("banned_users", []):
            data["banned_users"].remove(uid)
            save_data()
            bot.reply_to(msg, f"✅ Unbanned {uid}")
        else:
            bot.reply_to(msg, "User not in ban list.")
    except Exception as e:
        bot.reply_to(msg, f"Error: {str(e)}")

@bot.message_handler(commands=['broadcast'])
def broadcast(msg):
    if msg.chat.id != ADMIN_ID:
        return
    text = msg.text.replace("/broadcast", "").strip()
    if not text:
        return bot.reply_to(msg, "Usage: /broadcast <message>")
    users = data.get("users", {}).keys()
    count = 0
    for uid in users:
        try:
            bot.send_message(int(uid), f"📢 *Broadcast Message:*\n\n{text}", parse_mode="Markdown")
            count += 1
        except: continue
    bot.reply_to(msg, f"✅ Sent to {count} users.")

# ================= COMMANDS =================
@bot.message_handler(commands=['start'])
def start(msg):
    uid = str(msg.chat.id)
    first_name = msg.from_user.first_name or "Unknown"
    username = f"@{msg.from_user.username}" if msg.from_user.username else "No Username"
    
    if uid not in data["users"]:
        data["users"][uid] = {"collections": {}, "mode": "normal", "info": f"{first_name} ({username})"}
        save_data()
    else:
        data["users"][uid]["info"] = f"{first_name} ({username})"
        save_data()

    bot.reply_to(
        msg,
        f"🚀 *Bot Active!*\n\n"
        f"📌 Your ID:\n```{uid}```\n\n"
        f"📌 Mode: `{data['users'][uid]['mode']}`\n\n"
        f"📋 *Commands:*\n"
        f"➕ /add <link>\n"
        f"📋 /list\n"
        f"🔍 /getaddress <link>\n"
        f"❌ /remove <slug>\n"
        f"🗑️ /removeall\n"
        f"🔁 /mode normal | spam",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['getaddress'])
def get_address_cmd(msg):
    if not is_approved(msg.chat.id):
        return
    try:
        slug = get_slug(msg.text.split()[1])
        if not slug: return bot.reply_to(msg, "❌ Invalid OpenSea Link")
        async def run():
            async with aiohttp.ClientSession() as session:
                address = await fetch_contract_address(session, slug)
                if address:
                    bot.reply_to(msg, f"📄 *Collection:* `{slug}`\n📍 *Contract:* `{address}`", parse_mode="Markdown")
                else:
                    bot.reply_to(msg, "❌ Could not find contract address.")
        asyncio.run(run())
    except: bot.reply_to(msg, "Usage: /getaddress <link>")

@bot.message_handler(commands=['add'])
def add(msg):
    uid = str(msg.chat.id)
    if not is_approved(uid):
        return bot.reply_to(msg, "❌ *You are not approved!*\n\n📞 Contact Developer: @SK1Z0V41", parse_mode="Markdown")
    try:
        slug = get_slug(msg.text.split()[1])
        if slug in data["users"][uid]["collections"]:
            return bot.reply_to(msg, f"⚠️ {slug} already listed")
        async def run():
            async with aiohttp.ClientSession() as session:
                price = await get_price(session, slug)
                eth = await get_eth_usd(session)
                usd = f" (${round(price*eth,2):,})" if price and eth else ""
                data["users"][uid]["collections"][slug] = {"last": price or 0}
                save_data()
                bot.send_message(uid, f"✅ {slug}\n💰 {price} ETH{usd}")
        asyncio.run(run())
    except: bot.reply_to(msg, "Usage: /add <link>")

@bot.message_handler(commands=['list'])
def list_cmd(msg):
    uid = str(msg.chat.id)
    cols = data["users"].get(uid, {}).get("collections", {})
    if not cols: return bot.reply_to(msg, "📭 Empty")
    text = "📋 Your Collections:\n\n"
    for slug in cols: text += f"• {slug}\n"
    bot.reply_to(msg, text)

@bot.message_handler(commands=['remove'])
def remove(msg):
    uid = str(msg.chat.id)
    try:
        slug = msg.text.split()[1]
        if slug not in data["users"][uid]["collections"]:
            return bot.reply_to(msg, "❌ Not found")
        del data["users"][uid]["collections"][slug]
        save_data()
        bot.reply_to(msg, f"🗑️ Removed {slug}")
    except: bot.reply_to(msg, "Usage: /remove <slug>")

@bot.message_handler(commands=['removeall'])
def removeall(msg):
    uid = str(msg.chat.id)
    data["users"][uid]["collections"] = {}
    save_data()
    bot.reply_to(msg, "🗑️ All removed")

@bot.message_handler(commands=['mode'])
def set_mode(msg):
    uid = str(msg.chat.id)
    try:
        mode = msg.text.split()[1].lower()
        if mode not in ["normal", "spam"]:
            return bot.reply_to(msg, "Use: /mode normal or /mode spam")
        data["users"][uid]["mode"] = mode
        save_data()
        bot.reply_to(msg, f"🔔 Mode → {mode}")
    except: bot.reply_to(msg, "Usage: /mode normal or /mode spam")

# ================= MONITOR =================
async def monitor():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                eth = await get_eth_usd(session)
                for uid, udata in list(data["users"].items()):
                    if not is_approved(uid): continue
                    mode = udata.get("mode", "normal")
                    slugs = list(udata["collections"].keys())
                    tasks = [get_price(session, slug) for slug in slugs]
                    prices = await asyncio.gather(*tasks)
                    for slug, price in zip(slugs, prices):
                        if price is None: continue
                        last = udata["collections"][slug].get("last", 0)
                        
                        if last == 0:
                            data["users"][uid]["collections"][slug]["last"] = price
                            continue

                        change = ((price - last) / last * 100) if last else 0
                        usd = f" (${round(price*eth,2):,})" if price and eth else ""
                        
                        should_alert = False
                        if mode == "spam":
                            should_alert = True
                        elif mode == "normal" and abs(change) >= ALERT_THRESHOLD:
                            should_alert = True

                        if should_alert:
                            link = f"https://opensea.io/collection/{slug}"
                            emoji = "📈" if change > 0 else "📉"
                            message = (f"🔔 *{slug}*\n💰 {price} ETH{usd}\n{emoji} {change:+.4f}%\n\n🔗 [View on OpenSea]({link})")
                            try:
                                bot.send_message(int(uid), message, parse_mode="Markdown", disable_web_page_preview=True)
                                data["users"][uid]["collections"][slug]["last"] = price
                            except: pass
                save_data()
            except Exception as e:
                print(f"Monitor Error: {e}")
            await asyncio.sleep(MONITOR_INTERVAL)

def run_async():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(monitor())

threading.Thread(target=run_async, daemon=True).start()
bot.infinity_polling()
