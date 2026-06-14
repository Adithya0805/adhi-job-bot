import requests
import asyncio
import os
from telegram import Bot
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# Adhi's exact profile targeting
QUERIES = [
    # Tamil Nadu
    "Generative AI Engineer fresher Chennai",
    "LLM Engineer entry level Chennai",
    "Machine Learning Engineer 0-2 years Chennai",
    "AI Developer fresher Coimbatore",
    "Data Scientist junior Tamil Nadu",
    "Python AI Developer fresher Chennai",
    "NLP Engineer fresher Tamil Nadu",
    "MLOps Engineer trainee Chennai",
    # Bengaluru
    "Generative AI Engineer fresher Bangalore",
    "LLM Developer entry level Bangalore",
    "Machine Learning fresher Bangalore",
    "AI Engineer junior Bangalore",
    "Deep Learning Engineer fresher Bangalore",
    # Hyderabad
    "AI Engineer fresher Hyderabad",
    "Machine Learning Engineer entry level Hyderabad",
    # Remote India
    "Generative AI remote fresher India",
    "LangChain LLM Engineer remote India",
    "FastAPI AI Developer remote fresher",
]

# Adhi's skill keywords for match scoring
SKILL_KEYWORDS = [
    "python", "langchain", "langgraph", "fastapi", "llm",
    "generative ai", "rag", "machine learning", "deep learning",
    "nlp", "aws", "bedrock", "pinecone", "vector", "transformer",
    "huggingface", "openai", "gemini", "next.js", "tensorflow",
    "pytorch", "scikit", "data science", "mlops", "ai engineer"
]

# Block senior/irrelevant roles
BLOCK_KEYWORDS = [
    "senior", "lead", "manager", "director", "head of",
    "principal", "architect", "5+ years", "7+ years", "10+ years",
    "vp ", "chief", "internship only", "unpaid"
]

def score_job(title, company):
    text = (title + " " + company).lower()
    
    # Block irrelevant
    for block in BLOCK_KEYWORDS:
        if block in text:
            return -1
    
    # Score by skill match
    score = 0
    matched = []
    for skill in SKILL_KEYWORDS:
        if skill in text:
            score += 1
            matched.append(skill)
    
    return score, matched

def scrape_linkedin(query):
    q = query.replace(" ", "%20")
    url = f"https://www.linkedin.com/jobs/search?keywords={q}&f_E=1,2&f_TPR=r259200"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for card in soup.select(".base-card")[:5]:
            title = card.select_one(".base-search-card__title")
            company = card.select_one(".base-search-card__subtitle")
            location = card.select_one(".job-search-card__location")
            link = card.select_one("a.base-card__full-link")
            if title and company and link:
                clean_link = link["href"].split("?")[0]
                # Verify link is real
                if "linkedin.com/jobs" not in clean_link:
                    continue
                jobs.append({
                    "title": title.text.strip(),
                    "company": company.text.strip(),
                    "location": location.text.strip() if location else query.split()[-1],
                    "link": clean_link
                })
        return jobs
    except Exception as e:
        print(f"Error: {query} — {e}")
        return []

async def notify(msg):
    bot = Bot(token=BOT_TOKEN)
    # Split if message too long for Telegram
    if len(msg) > 4000:
        chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
        for chunk in chunks:
            await bot.send_message(chat_id=CHAT_ID, text=chunk, parse_mode="HTML")
            await asyncio.sleep(1)
    else:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

async def main():
    all_jobs = []
    seen = set()

    for q in QUERIES:
        jobs = scrape_linkedin(q)
        for j in jobs:
            key = f"{j['title'].lower()}-{j['company'].lower()}"
            if key not in seen:
                seen.add(key)
                result = score_job(j["title"], j["company"])
                if result == -1:
                    continue  # blocked keyword
                score, matched = result
                j["score"] = score
                j["matched"] = matched
                all_jobs.append(j)

    if not all_jobs:
        await notify("⚠️ Bot ran — no jobs found this round. Retrying in 6hrs.")
        return

    # Sort by match score — best first
    all_jobs.sort(key=lambda x: x["score"], reverse=True)

    total = len(all_jobs)
    high_match = [j for j in all_jobs if j["score"] >= 2]
    low_match  = [j for j in all_jobs if j["score"] < 2]

    msg = f"🔥 <b>Adhi Job Bot Report</b>\n"
    msg += f"📊 <b>{total} jobs found</b> | ✅ {len(high_match)} high match | 🔸 {len(low_match)} low match\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    if high_match:
        msg += f"⭐ <b>HIGH MATCH JOBS ({len(high_match)})</b>\n\n"
        for j in high_match[:10]:
            msg += f"▸ <b>{j['title']}</b>\n"
            msg += f"🏢 {j['company']}\n"
            msg += f"📍 {j['location']}\n"
            msg += f"🎯 Match: {j['score']}/5"
            if j['matched']:
                msg += f" | Skills: {', '.join(j['matched'][:3])}"
            msg += f"\n🔗 {j['link']}\n\n"

    if low_match:
        msg += f"🔸 <b>OTHER JOBS ({len(low_match)})</b>\n\n"
        for j in low_match[:5]:
            msg += f"▸ <b>{j['title']}</b> @ {j['company']}\n"
            msg += f"📍 {j['location']}\n"
            msg += f"🔗 {j['link']}\n\n"

    await notify(msg)
    print(f"Done. {total} jobs sent. {len(high_match)} high match.")

if __name__ == "__main__":
    asyncio.run(main())
