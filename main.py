import requests
import asyncio
import os
import json
import hashlib
from google import genai
from google.genai import types
from telegram import Bot
from bs4 import BeautifulSoup
from datetime import datetime
import urllib.parse
import logging
import sys

# ── LOGGING ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── ENV VARS ───────────────────────────────────────────────
BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
SEEN_FILE  = "seen_jobs.json"

if not BOT_TOKEN or not CHAT_ID or not GEMINI_KEY:
    logger.error("Missing TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, or GEMINI_API_KEY.")
    sys.exit(1)

client = genai.Client(api_key=GEMINI_KEY)

# ── CANDIDATE PROFILE ──────────────────────────────────────
ADHI_PROFILE = """
Name: Adithya (Adhi)
Degree: B.Tech AI & Data Science — 2025 Fresher, CGPA 8.0
Core Stack: Python, LangChain, LangGraph, FastAPI, AWS Bedrock, Pinecone RAG, Next.js, Supabase, Gemini API
Flagship Projects:
  - MediGuard V2: Multi-agent clinical AI system (LangGraph + AWS Bedrock + Pinecone + FastAPI + Next.js)
  - TownRise AI: Real estate intelligence platform (Gemini API + Next.js + Supabase)
  - Adhi Job Bot: Automated job scraper (Python + GitHub Actions + Telegram)
Certifications: AWS re/Start, BCG Data Science Simulation
Target Roles: AI Engineer, ML Engineer, GenAI Developer, LLM Engineer, Python Developer,
              Data Scientist, Data Analyst, Software Engineer
Experience Level: Fresher — 0 to 2 years only
Location Priority: Tamil Nadu (primary) > Remote India > Bangalore > Hyderabad
Company Preference: AI-first startups, product companies, funded tech companies
                    over IT service body shops
"""

# ── ZONE 1: TAMIL NADU — widest net ───────────────────────
TAMIL_NADU_QUERIES = [
    '("Generative AI" OR "LLM" OR "AI Engineer" OR "Machine Learning" OR "NLP" OR "Computer Vision" OR "MLOps" OR "GenAI" OR "Deep Learning") AND (fresher OR "entry level" OR trainee OR junior OR associate) AND (Chennai OR "Tamil Nadu" OR Coimbatore OR Madurai OR Trichy OR Salem OR Vellore OR Erode OR Tirupur OR Tirunelveli)',
    '(Python OR FastAPI OR Django OR "Data Scientist" OR "Data Analyst" OR "Data Engineer" OR Backend OR "Software Engineer" OR Developer OR IT) AND (fresher OR "entry level" OR trainee OR junior OR associate) AND (Chennai OR "Tamil Nadu" OR Coimbatore OR Madurai OR Trichy OR Salem OR Vellore OR Erode)',
]

# ── ZONE 2: BANGALORE + HYDERABAD — AI/ML specific ────────
METRO_QUERIES = [
    '("Generative AI" OR "LLM" OR "Machine Learning" OR "AI Engineer" OR "GenAI" OR "Python AI" OR "Data Scientist" OR "LLM Engineer") AND (fresher OR "entry level" OR junior OR trainee OR associate) AND (Bangalore OR Bengaluru)',
    '("Generative AI" OR "LLM" OR "Machine Learning" OR "AI Engineer" OR "GenAI" OR "Data Scientist" OR "LLM Engineer") AND (fresher OR "entry level" OR junior OR trainee OR associate) AND Hyderabad',
]

# ── ZONE 3: REMOTE INDIA — high skill-match only ──────────
REMOTE_QUERIES = [
    '("AI Engineer" OR "Machine Learning" OR "Generative AI" OR "LLM" OR "Python Developer" OR "Data Scientist" OR "GenAI") AND (fresher OR "entry level" OR junior OR trainee) AND (remote AND India)',
]

# ── HARD BLOCK WORDS ───────────────────────────────────────
BLOCK_WORDS = [
    # Seniority
    "senior", "lead", "manager", "director", "head of", "principal",
    "architect", "vp ", "vice president", "chief", "staff engineer",
    # Experience
    "3+ years", "4+ years", "5+ years", "6+ years", "7+ years", "8+ years",
    "10+ years", "minimum 3", "minimum 5", "at least 3",
    # Foreign locations
    "canada", "usa", "united states", "uk", "united kingdom",
    "australia", "germany", "france", "singapore", "dubai", "uae",
    "malaysia", "philippines", "europe", "emea", "apac",
    "north america", "latin america", "worldwide", "global remote",
    "remote (us", "remote (uk", "remote (canada",
    # Compensation
    "unpaid", "no stipend",
]

# ── INDIA CITY CONFIRMATIONS ───────────────────────────────
INDIA_CITIES = [
    "india", "chennai", "bangalore", "bengaluru", "hyderabad",
    "mumbai", "pune", "delhi", "coimbatore", "madurai", "trichy",
    "tiruchirappalli", "salem", "vellore", "erode", "tirupur",
    "tirunelveli", "tamil nadu", "karnataka", "telangana",
    "maharashtra", "remote india", "pan india",
]

# ── FOREIGN LOCATION SIGNALS ───────────────────────────────
FOREIGN_WORDS = [
    "usa", "united states", "uk", "united kingdom", "canada",
    "australia", "germany", "france", "singapore", "dubai", "uae",
    "europe", "worldwide", "global remote", "emea", "apac",
    "remote (us", "remote (uk", "remote (canada",
]

# ── TIER 1 COMPANIES (score 10) ────────────────────────────
TIER1_COMPANIES = [
    "zoho", "freshworks", "chargebee", "razorpay", "postman",
    "browserstack", "paypal", "amazon", "google", "microsoft",
    "groww", "phonepe", "swiggy", "zomato", "cred", "meesho",
    "sigmoid", "latentview", "saama", "mu sigma", "tredence",
    "innovaccer", "darwinbox", "kissflow", "leadsquared",
    "agnikul", "pixxel", "netapp", "atlassian",
]

# ── IT BODY SHOPS (show only if skill_match > 8) ───────────
IT_BODY_SHOPS = [
    "tcs", "tata consultancy", "wipro", "infosys", "cognizant",
    "accenture", "capgemini", "hcl", "tech mahindra", "l&t",
    "ltimindtree", "mphasis", "hexaware", "mindtree", "birlasoft",
    "persistent", "cyient", "sonata", "mastech",
]

# ── HELPERS ────────────────────────────────────────────────
def load_seen():
    try:
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
    except Exception as e:
        logger.error(f"Error loading seen jobs: {e}")
    return set()

def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)
    except Exception as e:
        logger.error(f"Error saving seen jobs: {e}")

def make_key(title, company):
    return hashlib.md5(f"{title.lower().strip()}-{company.lower().strip()}".encode()).hexdigest()

def is_blocked(title, company, location):
    text = f"{title} {company} {location}".lower()
    return any(b in text for b in BLOCK_WORDS)

def is_foreign_remote(location):
    loc = location.lower()
    return any(f in loc for f in FOREIGN_WORDS)

def is_india_confirmed(location):
    loc = location.lower()
    return any(c in loc for c in INDIA_CITIES)

def get_company_tier(company):
    name = company.lower()
    if any(t in name for t in TIER1_COMPANIES):
        return 1
    if any(s in name for s in ["tech", "ai", "labs", "studio", "works",
                                 "soft", "solutions", "systems", "data",
                                 "analytics", "intelligence", "ventures"]):
        return 2
    return 3

def get_location_score(location):
    loc = location.lower()
    TN_CITIES = ["chennai", "coimbatore", "madurai", "tamil nadu", "vellore",
                 "trichy", "tiruchirappalli", "salem", "erode", "tirupur",
                 "tirunelveli", "tn,", "tamilnadu"]
    if any(c in loc for c in TN_CITIES):
        return 10
    if "remote" in loc and is_india_confirmed(loc):
        return 9
    if any(c in loc for c in ["bangalore", "bengaluru"]):
        return 8
    if "hyderabad" in loc:
        return 7
    return 5

def calculate_final_score(gemini_result, location, company):
    loc_score  = get_location_score(location)
    tier       = get_company_tier(company)
    tier_score = {1: 10, 2: 7, 3: 3}.get(tier, 5)

    skill_match   = gemini_result.get("skill_match", 5)
    role_growth   = gemini_result.get("role_growth", 5)
    accessibility = gemini_result.get("accessibility", 5)

    return round(
        skill_match   * 0.35 +
        tier_score    * 0.25 +
        role_growth   * 0.20 +
        loc_score     * 0.10 +
        accessibility * 0.10,
        1
    )

# ── SCRAPER ────────────────────────────────────────────────
def scrape_linkedin(query, mode="tn"):
    q   = urllib.parse.quote(query)
    url = f"https://www.linkedin.com/jobs/search?keywords={q}&f_E=1,2&f_TPR=r604800"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r    = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for card in soup.select(".base-card, .base-search-card")[:15]:
            title    = card.select_one(".base-search-card__title")
            company  = card.select_one(".base-search-card__subtitle, .base-search-card__subtitle a")
            location = card.select_one(".job-search-card__location")
            link     = card.select_one("a.base-card__full-link, a.base-search-card__full-link")

            if not (title and company and link):
                continue

            loc_text  = location.text.strip() if location else ""
            link_href = link["href"].split("?")[0]

            # Only accept real LinkedIn job view links
            if "linkedin.com/jobs/view" not in link_href and "linkedin.com/jobs/" not in link_href:
                continue

            # Remote mode: must confirm India location
            if mode == "remote":
                if is_foreign_remote(loc_text):
                    continue
                if not is_india_confirmed(loc_text):
                    continue

            jobs.append({
                "title":    title.text.strip(),
                "company":  company.text.strip(),
                "location": loc_text,
                "link":     link_href,
                "mode":     mode,
            })
        return jobs
    except Exception as e:
        logger.error(f"Scrape error [{query[:60]}]: {e}")
        return []

# ── GEMINI BATCH ANALYZER ──────────────────────────────────
async def analyze_all_jobs(jobs):
    """One Gemini call for all jobs — zero rate limit risk."""
    if not jobs:
        return []

    jobs_text = ""
    for i, j in enumerate(jobs, 1):
        jobs_text += f"{i}. Title: {j['title']} | Company: {j['company']} | Location: {j['location']}\n"

    prompt = f"""
You are a personal AI career radar built exclusively for one candidate.
Think like a senior technical recruiter who knows this candidate's every skill, project, and goal.

CANDIDATE PROFILE:
{ADHI_PROFILE}

You have {len(jobs)} job listings to analyze:
{jobs_text}

SCORING CRITERIA:
- skill_match (0-10): How closely the job title + company stack matches Python, LangChain, LangGraph, FastAPI, AWS Bedrock, Pinecone, GenAI
- role_growth (0-10): Long-term career growth potential for an AI Engineer path
- accessibility (0-10): Realistic chance a 2025 fresher with a strong portfolio gets this role

RELEVANCE RULES (set is_relevant = false if ANY of these apply):
- Role requires 3+ years experience
- Title contains Senior, Lead, Manager, Director, Head, Principal, Architect, VP, Chief
- Location is outside India (Canada, USA, UK, Australia, Germany, France, Singapore, Dubai, UAE, etc.)
- Compensation is unpaid or stipend below ₹10,000/month
- Completely unrelated to AI, ML, Data, Python, or Software Engineering

RETURN ONLY a JSON array — no explanation, no markdown, no extra text:
[
  {{
    "index": 1,
    "skill_match": <0-10>,
    "role_growth": <0-10>,
    "accessibility": <0-10>,
    "is_relevant": <true or false>,
    "reason": "<one sharp sentence: why this job fits or doesn't fit Adhi specifically>"
  }},
  ...
]
Return analysis for ALL {len(jobs)} jobs in order. Array must have exactly {len(jobs)} elements.
"""
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini batch error: {e}")
        return [
            {
                "index": i + 1,
                "skill_match": 5,
                "role_growth": 5,
                "accessibility": 5,
                "is_relevant": True,
                "reason": "Could not analyze — manual review needed",
            }
            for i in range(len(jobs))
        ]

# ── TELEGRAM HELPERS ───────────────────────────────────────
async def send_telegram_message(bot, msg):
    if len(msg) > 4000:
        for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
            await bot.send_message(chat_id=CHAT_ID, text=chunk, parse_mode="HTML", disable_web_page_preview=True)
            await asyncio.sleep(1)
    else:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML", disable_web_page_preview=True)

async def send_reminder(bot, top_jobs):
    logger.info("Waiting 2 hours before sending apply reminder...")
    await asyncio.sleep(7200)
    msg  = "⏰ <b>Apply Reminder — Adhi!</b>\n\n"
    msg += "⚡ These are still waiting. First applicants win:\n\n"
    for i, j in enumerate(top_jobs, 1):
        msg += f"{i}. <b>{j['title']}</b> @ {j['company']}\n"
        msg += f"   🎯 Score: {j['final_score']}/10\n"
        msg += f"   🔗 {j['link']}\n\n"
    msg += "💪 MediGuard V2 + TownRise AI = elite portfolio. Use it.\n"
    msg += "🎓 AWS re/Start + BCG Simulation = credibility. Show it."
    try:
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML", disable_web_page_preview=True)
        logger.info("Reminder sent.")
    except Exception as e:
        logger.error(f"Reminder error: {e}")

# ── MAIN ───────────────────────────────────────────────────
async def main():
    seen     = load_seen()
    raw_jobs = []
    new_seen = set()

    # ── ZONE 1: Tamil Nadu sweep ───────────────────────────
    logger.info("ZONE 1 — Sweeping Tamil Nadu (all roles)...")
    for q in TAMIL_NADU_QUERIES:
        for j in scrape_linkedin(q, mode="tn"):
            key = make_key(j["title"], j["company"])
            if key not in seen and key not in new_seen:
                if not is_blocked(j["title"], j["company"], j["location"]):
                    new_seen.add(key)
                    raw_jobs.append(j)

    # ── ZONE 2: Metro AI/ML only ───────────────────────────
    logger.info("ZONE 2 — Sweeping Bangalore + Hyderabad (AI/ML only)...")
    for q in METRO_QUERIES:
        for j in scrape_linkedin(q, mode="metro"):
            key = make_key(j["title"], j["company"])
            if key not in seen and key not in new_seen:
                if not is_blocked(j["title"], j["company"], j["location"]):
                    new_seen.add(key)
                    raw_jobs.append(j)

    # ── ZONE 3: Remote India high-match only ───────────────
    logger.info("ZONE 3 — Sweeping Remote India (high skill-match only)...")
    for q in REMOTE_QUERIES:
        for j in scrape_linkedin(q, mode="remote"):
            key = make_key(j["title"], j["company"])
            if key not in seen and key not in new_seen:
                if not is_blocked(j["title"], j["company"], j["location"]):
                    new_seen.add(key)
                    raw_jobs.append(j)

    async with Bot(token=BOT_TOKEN) as bot:
        if not raw_jobs:
            logger.info("No new jobs found since last run.")
            await bot.send_message(
                chat_id=CHAT_ID,
                text="✅ <b>Adhi Job Radar</b> ran — no new jobs since last check.\nNext sweep in 3 days.",
                parse_mode="HTML",
            )
            return

        # Cap at 30 for Gemini context window safety
        raw_jobs = raw_jobs[:30]
        logger.info(f"Found {len(raw_jobs)} new raw jobs. Running single Gemini batch analysis...")

        gemini_results = await analyze_all_jobs(raw_jobs)

        analyzed_jobs = []
        for j, result in zip(raw_jobs, gemini_results):
            if not result.get("is_relevant", False):
                continue

            skill_match   = result.get("skill_match", 0)
            company_lower = j["company"].lower()

            # Block IT body shops unless exceptional skill match
            if any(shop in company_lower for shop in IT_BODY_SHOPS) and skill_match <= 8:
                continue

            j["analysis"]    = result
            j["final_score"] = calculate_final_score(result, j["location"], j["company"])
            j["tier"]        = get_company_tier(j["company"])

            # Minimum score gate
            if j["final_score"] < 5.0:
                continue

            analyzed_jobs.append(j)

        save_seen(seen.union(new_seen))

        if not analyzed_jobs:
            logger.info("No jobs passed the AI relevancy and score filters.")
            await bot.send_message(
                chat_id=CHAT_ID,
                text="✅ <b>Adhi Job Radar</b> — scanned jobs but none cleared the quality bar (score > 5.0).\nNext sweep in 3 days.",
                parse_mode="HTML",
            )
            return

        # ── Sort: TN first, then by score ─────────────────
        analyzed_jobs.sort(
            key=lambda x: (x["mode"] != "tn", -x["final_score"])
        )

        top_jobs    = analyzed_jobs[:10]
        tn_count    = sum(1 for j in analyzed_jobs if j["mode"] == "tn")
        metro_count = sum(1 for j in analyzed_jobs if j["mode"] == "metro")
        remote_count= sum(1 for j in analyzed_jobs if j["mode"] == "remote")

        tier_badge = {1: "🏆 TIER 1", 2: "⭐ TIER 2", 3: "🔹 TIER 3"}
        mode_label = {"tn": "🏙 Tamil Nadu", "metro": "🌆 Metro", "remote": "🌐 Remote India"}

        now = datetime.now().strftime("%d %b %Y, %I:%M %p")
        msg  = f"🤖 <b>Adhi Career Radar — {now}</b>\n"
        msg += f"<i>1 Gemini call. Every job handpicked for your resume.</i>\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"🔍 Scanned: <b>{len(raw_jobs)}</b> raw jobs\n"
        msg += f"🤖 AI Filtered: <b>{len(analyzed_jobs)}</b> relevant\n"
        msg += f"📤 Top Picks: <b>{len(top_jobs)}</b>\n"
        msg += f"🏙 TN: <b>{tn_count}</b>  🌆 Metro: <b>{metro_count}</b>  🌐 Remote: <b>{remote_count}</b>\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"🎯 <b>YOUR TOP {len(top_jobs)} MATCHES</b>\n\n"

        for i, j in enumerate(top_jobs, 1):
            badge  = tier_badge.get(j["tier"], "🔹")
            zone   = mode_label.get(j["mode"], "📍")
            score  = j["final_score"]
            reason = j["analysis"]["reason"]
            filled = int(score)
            bar    = "█" * filled + "░" * (10 - filled)

            msg += f"<b>{i}. {j['title']}</b>\n"
            msg += f"🏢 {j['company']}  {badge}\n"
            msg += f"{zone}  |  📍 {j['location']}\n"
            msg += f"🎯 [{bar}] {score}/10\n"
            msg += f"💡 {reason}\n"
            msg += f"🔗 {j['link']}\n\n"

        msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"⚡ <b>Apply top 5 within 24hrs.</b> Early bird wins.\n"
        msg += f"📅 Next alert in <b>3 days</b>."

        await send_telegram_message(bot, msg)

        if top_jobs:
            await send_reminder(bot, top_jobs[:5])

        logger.info(f"Done. Sent {len(top_jobs)} AI-curated jobs to Telegram.")

if __name__ == "__main__":
    asyncio.run(main())
