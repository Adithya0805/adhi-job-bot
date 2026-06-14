import requests
import asyncio
import os
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler
from bs4 import BeautifulSoup
from datetime import datetime
import json

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

TAMIL_NADU_QUERIES = [
    "AI Engineer fresher Chennai startups",
    "Machine Learning Engineer entry level Chennai",
    "Generative AI Developer fresher Chennai",
    "Data Scientist junior Coimbatore",
    "Python AI Developer entry level Chennai",
    "LLM Engineer fresher Tamil Nadu",
    "NLP Engineer entry level Chennai",
    "Data Analyst AI fresher Madurai",
    "MLOps Engineer trainee Chennai",
    "Computer Vision Engineer fresher Chennai",
    "AI Research Engineer entry level Tamil Nadu",
    "Deep Learning Developer fresher Coimbatore",
]

REMOTE_INDIA_QUERIES = [
    "Generative AI Engineer remote India fresher",
    "LLM Developer remote India entry level",
    "Machine Learning Engineer remote India 0-2 years",
    "Python AI Developer remote India fresher",
    "RAG Engineer remote India entry level",
    "FastAPI AI Developer remote India fresher",
    "LangChain Developer remote India junior",
    "Data Scientist remote India fresher",
]

SKILL_KEYWORDS = [
    "python", "langchain", "langgraph", "fastapi", "llm",
    "generative ai", "rag", "machine learning", "deep learning",
    "nlp", "aws", "bedrock", "pinecone", "vector database",
    "transformer", "huggingface", "openai", "gemini", "nextjs",
    "tensorflow", "pytorch", "scikit-learn", "data science",
    "mlops", "ai engineer", "large language model", "chatbot",
    "computer vision", "entry level", "fresher", "trainee"
]

BLOCK_KEYWORDS = [
    "senior", "lead", "manager", "director", "head of",
    "principal", "architect", "5+ years", "7+ years", "10+ years",
    "vp ", "chief", "unpaid", "usa", "uk", "canada", "australia",
    "germany", "singapore", "dubai", "uae", "europe", "us only",
    "united states", "united kingdom", "remote (us", "remote (uk"
]

def score_job(title, company, location):
    text = (title + " " + company + " " + location).lower()
    for block in BLOCK_KEYWORDS:
        if block in text:
            return -1, []
    score = 0
    matched = []
    for skill in SKILL_KEYWORDS:
        if skill in text:
            score += 1
            matched.append(skill)
    tn_cities = ["chennai", "coimbatore", "madurai", "trichy", "salem",
                 "erode", "vellore", "tamil nadu", "tamilnadu"]
    for city in tn_cities:
        if city in text:
            score += 2
            break
    if any(w in text for w in ["fresher", "entry level", "trainee", "0-2", "junior"]):
        score += 1
    return score, matched

def scrape_linkedin(query, location_filter="india"):
    q = query.replace(" ", "%20")
    url = f"https://www.linkedin.com/jobs/search?keywords={q}&f_E=1,2&f_TPR=r259200"
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
            foreign = ["usa", "uk", "canada", "australia", "germany",
                      "singapore", "dubai", "europe", "united states",
                      "united kingdom", "remote (us", "remote (uk"]
            if any(f in loc_text.lower() for f in foreign):
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
        print(f"Scrape error: {query} — {e}")
        return []

async def send_message(bot, msg):
    if len(msg) > 4000:
        chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
        for chunk in chunks:
            await bot.send_message(chat_id=CHAT_ID, text=chunk, parse_mode="HTML")
            await asyncio.sleep(1)
    else:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

async def send_apply_reminders(bot, top_jobs):
    """Send reminder 2 hours after job alert — top 5 jobs only"""
    await asyncio.sleep(7200)  # 2 hour wait
    
    reminder = "⏰ <b>Apply Reminder — Adhi did you apply?</b>\n\n"
    reminder += "Top jobs from today's alert:\n\n"
    
    for i, j in enumerate(top_jobs[:5], 1):
        reminder += f"{i}. <b>{j['title']}</b> @ {j['company']}\n"
        reminder += f"   🔗 {j['link']}\n\n"
    
    reminder += "⚡ <b>Apply NOW. Early applicants get 3x more responses.</b>\n"
    reminder += "Every hour you wait = more competition ahead of you."
    
    await bot.send_message(chat_id=CHAT_ID, text=reminder, parse_mode="HTML")

async def send_weekly_report(bot, all_jobs, tn_jobs, remote_jobs, high_match):
    """Send every Monday 9AM via scheduled run"""
    today = datetime.now()
    if today.weekday() != 0:  # 0 = Monday
        return
    
    report  = f"📊 <b>Weekly Job Hunt Report — {today.strftime('%d %b %Y')}</b>\n"
    report += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    report += f"🔍 Jobs Scanned This Week\n"
    report += f"   Tamil Nadu: <b>{len(tn_jobs)}</b>\n"
    report += f"   Remote India: <b>{len(remote_jobs)}</b>\n"
    report += f"   Total: <b>{len(all_jobs)}</b>\n\n"
    report += f"⭐ High Match Jobs: <b>{len(high_match)}</b>\n\n"
    
    if high_match:
        report += f"🏆 <b>Top 3 This Week:</b>\n"
        for j in high_match[:3]:
            report += f"▸ {j['title']} @ {j['company']}\n"
            report += f"  📍 {j['location']} | 🎯 {j['score']}/7\n\n"
    
    report += f"━━━━━━━━━━━━━━━━━━━━\n"
    report += f"💪 <b>Adhi — consistency beats talent.</b>\n"
    report += f"Apply to minimum 5 jobs today. Your MediGuard V2 + TownRise AI = strong portfolio. Use it."
    
    await bot.send_message(chat_id=CHAT_ID, text=report, parse_mode="HTML")

async def main():
    bot = Bot(token=BOT_TOKEN)
    all_jobs = []
    seen = set()

    # Scrape Tamil Nadu
    print("Scraping Tamil Nadu...")
    for q in TAMIL_NADU_QUERIES:
        for j in scrape_linkedin(q):
            key = f"{j['title'].lower()}-{j['company'].lower()}"
            if key not in seen:
                seen.add(key)
                score, matched = score_job(j["title"], j["company"], j["location"])
                if score == -1:
                    continue
                j["score"]   = score
                j["matched"] = matched
                j["type"]    = "tn"
                all_jobs.append(j)

    # Scrape Remote India
    print("Scraping Remote India...")
    for q in REMOTE_INDIA_QUERIES:
        for j in scrape_linkedin(q):
            key = f"{j['title'].lower()}-{j['company'].lower()}"
            if key not in seen:
                seen.add(key)
                score, matched = score_job(j["title"], j["company"], j["location"])
                if score == -1:
                    continue
                j["score"]   = score
                j["matched"] = matched
                j["type"]    = "remote"
                all_jobs.append(j)

    if not all_jobs:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="⚠️ Bot ran — no matching jobs found. Retrying in 6hrs.",
            parse_mode="HTML"
        )
        return

    all_jobs.sort(key=lambda x: x["score"], reverse=True)

    tn_jobs     = [j for j in all_jobs if j["type"] == "tn"]
    remote_jobs = [j for j in all_jobs if j["type"] == "remote"]
    high_match  = [j for j in all_jobs if j["score"] >= 3]

    # Main job alert
    now = datetime.now().strftime("%d %b %Y | %I:%M %p")
    msg  = f"🔥 <b>Adhi Job Bot — {now}</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 Total: <b>{len(all_jobs)}</b> | "
    msg += f"🏙 TN: <b>{len(tn_jobs)}</b> | "
    msg += f"🌐 Remote: <b>{len(remote_jobs)}</b> | "
    msg += f"⭐ High Match: <b>{len(high_match)}</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    if tn_jobs:
        msg += f"🏙 <b>TAMIL NADU ({len(tn_jobs)} jobs)</b>\n\n"
        for j in tn_jobs[:12]:
            stars = "⭐" * min(j["score"], 5)
            msg += f"▸ <b>{j['title']}</b>\n"
            msg += f"🏢 {j['company']} | 📍 {j['location']}\n"
            msg += f"🎯 {stars} {j['score']}/7"
            if j["matched"]:
                msg += f" | {', '.join(j['matched'][:2])}"
            msg += f"\n🔗 {j['link']}\n\n"

    if remote_jobs:
        msg += f"🌐 <b>REMOTE INDIA ({len(remote_jobs)} jobs)</b>\n\n"
        for j in remote_jobs[:8]:
            stars = "⭐" * min(j["score"], 5)
            msg += f"▸ <b>{j['title']}</b>\n"
            msg += f"🏢 {j['company']} | 📍 {j['location']}\n"
            msg += f"🎯 {stars} {j['score']}/7\n"
            msg += f"🔗 {j['link']}\n\n"

    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"⚡ <b>Apply within 24hrs. First applicants win.</b>"

    await send_message(bot, msg)

    # Weekly report on Mondays
    await send_weekly_report(bot, all_jobs, tn_jobs, remote_jobs, high_match)

    # Apply reminder after 2 hours (top jobs only)
    top_jobs = high_match[:5] if high_match else all_jobs[:5]
    asyncio.create_task(send_apply_reminders(bot, top_jobs))

    print(f"Done. TN: {len(tn_jobs)} | Remote: {len(remote_jobs)} | High match: {len(high_match)}")

if __name__ == "__main__":
    asyncio.run(main())
