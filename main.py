import requests
import asyncio
import os
import json
import hashlib
from telegram import Bot
from bs4 import BeautifulSoup
from datetime import datetime

BOT_TOKEN    = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID      = os.environ["TELEGRAM_CHAT_ID"]
SEEN_FILE    = "seen_jobs.json"

# ─── TAMIL NADU — ALL JOB TYPES ───────────────────────────
TAMIL_NADU_QUERIES = [
    # AI & ML
    "AI Engineer fresher Chennai",
    "Machine Learning Engineer entry level Chennai",
    "Generative AI Developer fresher Tamil Nadu",
    "LLM Engineer fresher Chennai",
    "Data Scientist junior Tamil Nadu",
    "NLP Engineer fresher Chennai",
    "MLOps Engineer trainee Chennai",
    "Computer Vision Engineer fresher Tamil Nadu",
    "Deep Learning Developer fresher Coimbatore",
    # Software & Python
    "Python Developer fresher Chennai",
    "Software Engineer fresher Chennai",
    "Backend Developer entry level Chennai",
    "Full Stack Developer fresher Tamil Nadu",
    "Django Developer fresher Chennai",
    "FastAPI Developer entry level Tamil Nadu",
    # Data
    "Data Analyst fresher Chennai",
    "Business Intelligence fresher Tamil Nadu",
    "Data Engineer entry level Chennai",
    # Other IT
    "Software Trainee Chennai",
    "IT Fresher Tamil Nadu",
    "Junior Developer Coimbatore",
    "Associate Engineer fresher Tamil Nadu",
]

# ─── REMOTE INDIA ONLY ────────────────────────────────────
REMOTE_INDIA_QUERIES = [
    "AI Engineer remote India fresher",
    "Machine Learning remote India entry level",
    "Python Developer remote India fresher",
    "Data Scientist remote India junior",
    "Generative AI remote India fresher",
    "LLM Developer remote India entry level",
    "Backend Developer remote India fresher",
    "Full Stack Developer remote India fresher",
    "Data Analyst remote India entry level",
    "Software Engineer remote India fresher",
]

# ─── SCORING ──────────────────────────────────────────────
SKILL_KEYWORDS = [
    "python", "langchain", "langgraph", "fastapi", "llm",
    "generative ai", "rag", "machine learning", "deep learning",
    "nlp", "aws", "bedrock", "pinecone", "vector",
    "huggingface", "openai", "gemini", "tensorflow",
    "pytorch", "scikit", "data science", "mlops",
    "django", "flask", "react", "nextjs", "sql",
    "mongodb", "postgresql", "docker", "git", "api"
]

BLOCK_KEYWORDS = [
    "senior", "lead", "manager", "director", "head of",
    "principal", "architect", "5+ years", "7+ years", "10+ years",
    "vp ", "chief", "unpaid",
    # Block all international
    "usa", "uk", "canada", "australia", "germany",
    "singapore", "dubai", "uae", "europe", "us only",
    "united states", "united kingdom", "remote (us",
    "remote (uk", "onsite usa", "onsite uk", "malaysia",
    "philippines", "pakistan", "bangladesh"
]

INDIA_CONFIRM = [
    "india", "chennai", "bangalore", "bengaluru", "hyderabad",
    "mumbai", "pune", "delhi", "coimbatore", "madurai",
    "tamil nadu", "karnataka", "telangana", "maharashtra"
]

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def make_key(title, company):
    raw = f"{title.lower()}-{company.lower()}"
    return hashlib.md5(raw.encode()).hexdigest()

def score_job(title, company, location):
    text = (title + " " + company + " " + location).lower()

    # Hard block
    for block in BLOCK_KEYWORDS:
        if block in text:
            return -1, []

    # Must confirm India location for remote jobs
    score = 0
    matched = []

    for skill in SKILL_KEYWORDS:
        if skill in text:
            score += 1
            matched.append(skill)

    # Bonus for Tamil Nadu
    tn_cities = ["chennai", "coimbatore", "madurai", "trichy",
                 "salem", "vellore", "tamil nadu", "tamilnadu",
                 "erode", "tirunelveli", "tirupur"]
    for city in tn_cities:
        if city in text:
            score += 2
            break

    # Bonus for fresher/entry level
    if any(w in text for w in ["fresher", "entry level", "trainee", "0-2", "junior", "associate"]):
        score += 1

    return score, matched

def scrape_linkedin(query, remote_mode=False):
    q = query.replace(" ", "%20")
    url = f"https://www.linkedin.com/jobs/search?keywords={q}&f_E=1,2&f_TPR=r604800"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for card in soup.select(".base-card")[:5]:
            title    = card.select_one(".base-search-card__title")
            company  = card.select_one(".base-search-card__subtitle")
            location = card.select_one(".job-search-card__location")
            link     = card.select_one("a.base-card__full-link")

            if not (title and company and link):
                continue

            loc_text = location.text.strip() if location else ""

            # For remote — confirm India location
            if remote_mode:
                loc_lower = loc_text.lower()
                is_india = any(c in loc_lower for c in INDIA_CONFIRM)
                is_foreign = any(b in loc_lower for b in [
                    "usa", "uk", "canada", "australia", "germany",
                    "singapore", "dubai", "europe", "united states"
                ])
                if is_foreign or not is_india:
                    continue

            clean_link = link["href"].split("?")[0]
            if "linkedin.com/jobs" not in clean_link:
                continue

            jobs.append({
                "title":    title.text.strip(),
                "company":  company.text.strip(),
                "location": loc_text,
                "link":     clean_link
            })
        return jobs
    except Exception as e:
        print(f"Error: {query} — {e}")
        return []

async def send_message(bot, msg):
    if len(msg) > 4000:
        chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
        for chunk in chunks:
            await bot.send_message(chat_id=CHAT_ID, text=chunk, parse_mode="HTML")
            await asyncio.sleep(1)
    else:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

async def send_reminder(bot, top_jobs):
    await asyncio.sleep(7200)  # 2 hours
    msg  = "⏰ <b>Apply Reminder — Adhi!</b>\n\n"
    msg += "Did you apply to these yet?\n\n"
    for i, j in enumerate(top_jobs[:5], 1):
        msg += f"{i}. <b>{j['title']}</b> @ {j['company']}\n"
        msg += f"   🔗 {j['link']}\n\n"
    msg += "⚡ <b>Apply NOW. First applicants get 3x responses.</b>"
    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

async def main():
    bot  = Bot(token=BOT_TOKEN)
    seen = load_seen()
    all_jobs = []
    new_seen = set()

    # ── Tamil Nadu scrape ──
    print("Scraping Tamil Nadu...")
    for q in TAMIL_NADU_QUERIES:
        for j in scrape_linkedin(q, remote_mode=False):
            key = make_key(j["title"], j["company"])
            if key in seen:
                continue  # already sent before
            new_seen.add(key)
            score, matched = score_job(j["title"], j["company"], j["location"])
            if score == -1:
                continue
            j["score"]   = score
            j["matched"] = matched
            j["type"]    = "tn"
            all_jobs.append(j)

    # ── Remote India scrape ──
    print("Scraping Remote India...")
    for q in REMOTE_INDIA_QUERIES:
        for j in scrape_linkedin(q, remote_mode=True):
            key = make_key(j["title"], j["company"])
            if key in seen:
                continue
            new_seen.add(key)
            score, matched = score_job(j["title"], j["company"], j["location"])
            if score == -1:
                continue
            j["score"]   = score
            j["matched"] = matched
            j["type"]    = "remote"
            all_jobs.append(j)

    # Save seen jobs
    save_seen(seen.union(new_seen))

    if not all_jobs:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="✅ Bot ran — no NEW jobs since last check. All fresh next run in 3 days.",
            parse_mode="HTML"
        )
        return

    all_jobs.sort(key=lambda x: x["score"], reverse=True)

    tn_jobs     = [j for j in all_jobs if j["type"] == "tn"]
    remote_jobs = [j for j in all_jobs if j["type"] == "remote"]
    high_match  = [j for j in all_jobs if j["score"] >= 3]

    now = datetime.now().strftime("%d %b %Y")

    msg  = f"🔥 <b>Adhi Job Bot — {now}</b>\n"
    msg += f"📅 <i>Fresh jobs since last 3 days</i>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 Total New: <b>{len(all_jobs)}</b>\n"
    msg += f"🏙 Tamil Nadu: <b>{len(tn_jobs)}</b>\n"
    msg += f"🌐 Remote India: <b>{len(remote_jobs)}</b>\n"
    msg += f"⭐ High Match: <b>{len(high_match)}</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    if tn_jobs:
        msg += f"🏙 <b>TAMIL NADU JOBS ({len(tn_jobs)})</b>\n\n"
        for j in tn_jobs[:15]:
            stars = "⭐" * min(j["score"], 5)
            msg += f"▸ <b>{j['title']}</b>\n"
            msg += f"🏢 {j['company']} | 📍 {j['location']}\n"
            msg += f"🎯 {stars} {j['score']}/7"
            if j["matched"]:
                msg += f" | {', '.join(j['matched'][:2])}"
            msg += f"\n🔗 {j['link']}\n\n"

    if remote_jobs:
        msg += f"🌐 <b>REMOTE INDIA JOBS ({len(remote_jobs)})</b>\n\n"
        for j in remote_jobs[:10]:
            stars = "⭐" * min(j["score"], 5)
            msg += f"▸ <b>{j['title']}</b>\n"
            msg += f"🏢 {j['company']} | 📍 {j['location']}\n"
            msg += f"🎯 {stars} {j['score']}/7\n"
            msg += f"🔗 {j['link']}\n\n"

    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"⚡ <b>Apply within 48hrs. Next alert in 3 days.</b>"

    await send_message(bot, msg)

    # Reminder after 2 hours
    top = high_match[:5] if high_match else all_jobs[:5]
    asyncio.create_task(send_reminder(bot, top))

    print(f"Done. TN: {len(tn_jobs)} | Remote: {len(remote_jobs)} | High: {len(high_match)}")

if __name__ == "__main__":
    asyncio.run(main())
