What each file does — plain and simple:
FilePurposemain.pyThe brain. Searches Naukri + Indeed → finds jobs → sends to Telegramrequirements.txtTells GitHub what Python libraries to installjob_bot.ymlThe schedule. GitHub runs your bot every 6 hours automaticallyBash setupOne-time setup: creates bot + pushes code to GitHub

How the flow works:
Every 6 hours (automatic)
GitHub Actions wakes up
→ installs Python + libraries
→ runs main.py
→ main.py searches Naukri & Indeed
→ finds fresher ML/SDE jobs
→ sends list to your Telegram
→ you tap links from phone → apply

The 2 secrets you store in GitHub (never in code):

TELEGRAM_BOT_TOKEN → your bot's password (from BotFather)
TELEGRAM_CHAT_ID → your Telegram account ID (so bot knows who to message)

GitHub injects these at runtime via os.environ["..."] — safe, never exposed.

Now here's the agent prompt you can give to any AI agent (Claude, ChatGPT, Cursor, etc.) to build or extend this:


Agent Prompt — Job Automation Bot
You are a Python automation agent. Build a job scraping and Telegram notification bot with the following specs:
Goal: Scrape fresher job listings from Naukri.com and Indeed India every 6 hours and send formatted alerts to a Telegram chat.
Tech stack: Python 3.11, BeautifulSoup4, requests, python-telegram-bot 20.x, GitHub Actions for scheduling.
Search targets:

Roles: ML Engineer, Data Science Trainee, SDE Trainee, AI Engineer
Locations: Chennai, Bengaluru, Remote India
Experience: Fresher / 0-1 year only

Output format per job (Telegram message):
🔥 Job Title @ Company [Platform]
📍 Location | 🗓 Date posted
🔗 Apply link
Requirements:

Secrets via environment variables: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
Deduplication: don't re-send jobs already sent (use a seen_jobs.json file)
Error handling: if scrape fails, send a warning message, don't crash
GitHub Actions yml: runs on schedule 0 */6 * * * and supports manual trigger
Add LinkedIn Easy Apply scraping using Playwright (headless) as optional module

Deliverables: main.py, requirements.txt, .github/workflows/job_bot.yml, seen_jobs.json (empty init), README with setup steps.

import { useState } from "react";

const TABS = ["Dashboard", "Setup Guide", "Scripts"];

const JOBS = [
  { id: 1, title: "ML Engineer - Fresher", company: "Wipro", platform: "LinkedIn", location: "Chennai", status: "applied", date: "2025-06-03" },
  { id: 2, title: "Data Science Trainee", company: "TCS", platform: "Naukri", location: "Bengaluru", status: "pending", date: "2025-06-04" },
  { id: 3, title: "SDE Trainee - AI", company: "Infosys", platform: "Indeed", location: "Remote", status: "applied", date: "2025-06-04" },
  { id: 4, title: "AI Engineer", company: "Cognizant", platform: "LinkedIn", location: "Bengaluru", status: "pending", date: "2025-06-04" },
];

const STATUS_COLOR = {
  applied: { bg: "#E1F5EE", color: "#0F6E56", label: "Applied" },
  pending: { bg: "#FAEEDA", color: "#854F0B", label: "Pending" },
  rejected: { bg: "#FCEBEB", color: "#A32D2D", label: "Rejected" },
};

const PLATFORM_COLOR = {
  LinkedIn: "#E6F1FB",
  Naukri: "#EEEDFE",
  Indeed: "#FAEEDA",
};

const SCRIPTS = [
  {
    title: "1. main.py — Job Scraper & Applier",
    lang: "python",
    code: `import requests
from bs4 import BeautifulSoup
import telegram
import json, time, os

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

SEARCH_QUERIES = [
    "ML Engineer fresher Chennai",
    "Data Science trainee Bengaluru",
    "SDE trainee AI remote India",
]

def notify(msg):
    bot = telegram.Bot(token=BOT_TOKEN)
    bot.send_message(chat_id=CHAT_ID, text=msg)

def scrape_naukri(query):
    # Uses Naukri public search
    q = query.replace(" ", "+")
    url = f"https://www.naukri.com/jobs-in-india?k={q}"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []
    for card in soup.select(".jobTuple")[:5]:
        title = card.select_one(".title")
        comp  = card.select_one(".subTitle")
        link  = card.select_one("a.title")
        if title and comp:
            jobs.append({
                "title": title.text.strip(),
                "company": comp.text.strip(),
                "link": link["href"] if link else "",
                "platform": "Naukri"
            })
    return jobs

def scrape_indeed(query):
    q = query.replace(" ", "+")
    url = f"https://in.indeed.com/jobs?q={q}&l=India"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []
    for card in soup.select(".job_seen_beacon")[:5]:
        title = card.select_one(".jobTitle")
        comp  = card.select_one(".companyName")
        link  = card.select_one("a")
        if title and comp:
            jobs.append({
                "title": title.text.strip(),
                "company": comp.text.strip(),
                "link": "https://in.indeed.com" + (link["href"] if link else ""),
                "platform": "Indeed"
            })
    return jobs

def main():
    all_jobs = []
    for q in SEARCH_QUERIES:
        all_jobs += scrape_naukri(q)
        all_jobs += scrape_indeed(q)
        time.sleep(2)

    if not all_jobs:
        notify("⚠️ Job bot ran — no new jobs found today.")
        return

    msg = f"🔥 Adhi Job Bot — {len(all_jobs)} new jobs found!\\n\\n"
    for j in all_jobs[:10]:
        msg += f"▸ {j['title']} @ {j['company']} [{j['platform']}]\\n"
        if j['link']:
            msg += f"  {j['link'][:60]}\\n"
        msg += "\\n"

    notify(msg)
    print(f"Sent {len(all_jobs)} jobs to Telegram.")

if __name__ == "__main__":
    main()`,
  },
  {
    title: "2. requirements.txt",
    lang: "text",
    code: `requests==2.31.0
beautifulsoup4==4.12.2
python-telegram-bot==20.7
lxml==4.9.3`,
  },
  {
    title: "3. .github/workflows/job_bot.yml",
    lang: "yaml",
    code: `name: Adhi Job Bot

on:
  schedule:
    # Runs every 6 hours
    - cron: '0 */6 * * *'
  workflow_dispatch:  # manual trigger

jobs:
  scrape-and-notify:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run job bot
        env:
          TELEGRAM_BOT_TOKEN: \${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: \${{ secrets.TELEGRAM_CHAT_ID }}
        run: python main.py`,
  },
  {
    title: "4. Telegram Bot Setup (one-time)",
    lang: "bash",
    code: `# Step 1: Create bot via BotFather on Telegram
# Message @BotFather → /newbot → get TOKEN

# Step 2: Get your Chat ID
# Message your bot once, then run:
curl https://api.telegram.org/bot<TOKEN>/getUpdates
# Look for "chat":{"id": XXXXXXXXX}

# Step 3: Add secrets to GitHub repo
# Go to: Repo → Settings → Secrets → Actions
# Add: TELEGRAM_BOT_TOKEN  →  your token
# Add: TELEGRAM_CHAT_ID    →  your chat id

# Step 4: Push code and enable Actions
git init
git add .
git commit -m "Adhi job bot v1"
git remote add origin https://github.com/Adithya0805/job-bot.git
git push -u origin main`,
  },
];

export default function App() {
  const [tab, setTab] = useState(0);
  const [copied, setCopied] = useState(null);
  const [jobs, setJobs] = useState(JOBS);
  const [filter, setFilter] = useState("all");

  const stats = {
    total: jobs.length,
    applied: jobs.filter((j) => j.status === "applied").length,
    pending: jobs.filter((j) => j.status === "pending").length,
  };

  const filtered = filter === "all" ? jobs : jobs.filter((j) => j.status === filter);

  function copyCode(idx, text) {
    navigator.clipboard.writeText(text);
    setCopied(idx);
    setTimeout(() => setCopied(null), 1500);
  }

  return (
    <div style={{ fontFamily: "var(--font-sans)", padding: "1rem 0", color: "var(--color-text-primary)" }}>
      <h2 style={{ fontSize: 18, fontWeight: 500, margin: "0 0 4px" }}>
        <i className="ti ti-robot" style={{ fontSize: 18, marginRight: 8 }} aria-hidden="true"></i>
        Adhi Job Automation
      </h2>
      <p style={{ fontSize: 13, color: "var(--color-text-secondary)", margin: "0 0 1.25rem" }}>
        GitHub Actions → scrapes Naukri, Indeed, LinkedIn every 6hrs → Telegram alerts to phone
      </p>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: "1.25rem", borderBottom: "0.5px solid var(--color-border-tertiary)", paddingBottom: 0 }}>
        {TABS.map((t, i) => (
          <button
            key={t}
            onClick={() => setTab(i)}
            style={{
              background: "none",
              border: "none",
              borderBottom: tab === i ? "2px solid var(--color-text-primary)" : "2px solid transparent",
              padding: "6px 12px",
              fontSize: 13,
              fontWeight: tab === i ? 500 : 400,
              color: tab === i ? "var(--color-text-primary)" : "var(--color-text-secondary)",
              cursor: "pointer",
              borderRadius: 0,
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* TAB 0 — Dashboard */}
      {tab === 0 && (
        <div>
          {/* Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10, marginBottom: "1.25rem" }}>
            {[
              { label: "Total tracked", value: stats.total, icon: "ti-briefcase" },
              { label: "Applied", value: stats.applied, icon: "ti-check" },
              { label: "Pending", value: stats.pending, icon: "ti-clock" },
              { label: "Platforms", value: 3, icon: "ti-world" },
            ].map((s) => (
              <div key={s.label} style={{ background: "var(--color-background-secondary)", borderRadius: "var(--border-radius-md)", padding: "12px 14px" }}>
                <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: "0 0 4px" }}>
                  <i className={`ti ${s.icon}`} style={{ fontSize: 13, marginRight: 5 }} aria-hidden="true"></i>
                  {s.label}
                </p>
                <p style={{ fontSize: 22, fontWeight: 500, margin: 0 }}>{s.value}</p>
              </div>
            ))}
          </div>

          {/* Filter */}
          <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
            {["all", "applied", "pending"].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  fontSize: 12,
                  padding: "4px 10px",
                  borderRadius: "var(--border-radius-md)",
                  border: filter === f ? "1.5px solid var(--color-border-primary)" : "0.5px solid var(--color-border-tertiary)",
                  background: filter === f ? "var(--color-background-primary)" : "none",
                  fontWeight: filter === f ? 500 : 400,
                  cursor: "pointer",
                  color: "var(--color-text-primary)",
                }}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>

          {/* Job list */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {filtered.map((j) => (
              <div
                key={j.id}
                style={{
                  background: "var(--color-background-primary)",
                  border: "0.5px solid var(--color-border-tertiary)",
                  borderRadius: "var(--border-radius-lg)",
                  padding: "12px 14px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ flex: 1 }}>
                    <p style={{ fontSize: 13, fontWeight: 500, margin: "0 0 2px" }}>{j.title}</p>
                    <p style={{ fontSize: 12, color: "var(--color-text-secondary)", margin: "0 0 8px" }}>{j.company} · {j.location}</p>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 20, background: PLATFORM_COLOR[j.platform] || "#eee", color: "var(--color-text-secondary)" }}>
                        {j.platform}
                      </span>
                      <span style={{
                        fontSize: 11, padding: "2px 8px", borderRadius: 20,
                        background: STATUS_COLOR[j.status].bg,
                        color: STATUS_COLOR[j.status].color,
                      }}>
                        {STATUS_COLOR[j.status].label}
                      </span>
                    </div>
                  </div>
                  <span style={{ fontSize: 11, color: "var(--color-text-tertiary)", whiteSpace: "nowrap", marginLeft: 8 }}>{j.date}</span>
                </div>
              </div>
            ))}
          </div>

          <p style={{ fontSize: 12, color: "var(--color-text-tertiary)", marginTop: 14, textAlign: "center" }}>
            <i className="ti ti-info-circle" aria-hidden="true" style={{ marginRight: 4 }}></i>
            Live data populates after bot runs on GitHub Actions
          </p>
        </div>
      )}

      {/* TAB 1 — Setup Guide */}
      {tab === 1 && (
        <div>
          {[
            {
              step: "1",
              title: "Create Telegram Bot",
              icon: "ti-brand-telegram",
              color: "#E6F1FB",
              textColor: "#185FA5",
              items: [
                "Open Telegram → search @BotFather",
                "Send /newbot → give it a name",
                "Copy the TOKEN it gives you",
                "Message your new bot once (any text)",
                "Run the curl command in Scripts tab to get CHAT_ID",
              ],
            },
            {
              step: "2",
              title: "Create GitHub Repo",
              icon: "ti-brand-github",
              color: "#F1EFE8",
              textColor: "#444441",
              items: [
                "Go to github.com → New repository",
                'Name it: "adhi-job-bot" (private)',
                "Add the 3 files from Scripts tab",
                "Go to Settings → Secrets → Actions",
                "Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID",
              ],
            },
            {
              step: "3",
              title: "Enable GitHub Actions",
              icon: "ti-player-play",
              color: "#E1F5EE",
              textColor: "#0F6E56",
              items: [
                "Go to Actions tab in your repo",
                'Click "Enable workflows"',
                'Click "Run workflow" to test manually',
                "Check Telegram — you should get job alerts",
                "Auto-runs every 6 hours after that",
              ],
            },
            {
              step: "4",
              title: "Monitor from Phone",
              icon: "ti-device-mobile",
              color: "#EEEDFE",
              textColor: "#534AB7",
              items: [
                "All alerts come to Telegram on your phone",
                "Tap links to open jobs in browser",
                "Apply manually for jobs that need it",
                "GitHub Actions runs even when phone is off",
                "Free tier: 2000 mins/month (way more than enough)",
              ],
            },
          ].map((s) => (
            <div
              key={s.step}
              style={{
                background: "var(--color-background-primary)",
                border: "0.5px solid var(--color-border-tertiary)",
                borderRadius: "var(--border-radius-lg)",
                padding: "14px",
                marginBottom: 10,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: s.color, display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <i className={`ti ${s.icon}`} style={{ fontSize: 16, color: s.textColor }} aria-hidden="true"></i>
                </div>
                <p style={{ fontSize: 14, fontWeight: 500, margin: 0 }}>Step {s.step}: {s.title}</p>
              </div>
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {s.items.map((item, i) => (
                  <li key={i} style={{ fontSize: 13, color: "var(--color-text-secondary)", marginBottom: 4, lineHeight: 1.5 }}>{item}</li>
                ))}
              </ul>
            </div>
          ))}

          <div style={{
            background: "#FAEEDA", borderRadius: "var(--border-radius-md)",
            padding: "10px 14px", fontSize: 12, color: "#633806", marginTop: 4,
          }}>
            <i className="ti ti-bulb" aria-hidden="true" style={{ marginRight: 6 }}></i>
            <strong>Total cost: ₹0.</strong> GitHub Actions free tier + Telegram Bot API = completely free. Runs 24/7 without your laptop.
          </div>
        </div>
      )}

      {/* TAB 2 — Scripts */}
      {tab === 2 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {SCRIPTS.map((s, idx) => (
            <div
              key={idx}
              style={{
                background: "var(--color-background-primary)",
                border: "0.5px solid var(--color-border-tertiary)",
                borderRadius: "var(--border-radius-lg)",
                overflow: "hidden",
              }}
            >
              <div style={{
                display: "flex", justifyContent: "space-between", alignItems: "center",
                padding: "10px 14px", borderBottom: "0.5px solid var(--color-border-tertiary)",
                background: "var(--color-background-secondary)",
              }}>
                <p style={{ fontSize: 12, fontWeight: 500, margin: 0 }}>{s.title}</p>
                <button
                  onClick={() => copyCode(idx, s.code)}
                  style={{
                    fontSize: 11, padding: "3px 10px", borderRadius: "var(--border-radius-md)",
                    border: "0.5px solid var(--color-border-secondary)",
                    background: copied === idx ? "#E1F5EE" : "none",
                    color: copied === idx ? "#0F6E56" : "var(--color-text-secondary)",
                    cursor: "pointer",
                  }}
                >
                  <i className={`ti ${copied === idx ? "ti-check" : "ti-copy"}`} style={{ fontSize: 12, marginRight: 4 }} aria-hidden="true"></i>
                  {copied === idx ? "Copied!" : "Copy"}
                </button>
              </div>
              <pre style={{
                margin: 0, padding: "12px 14px",
                fontSize: 11, lineHeight: 1.6,
                overflowX: "auto",
                color: "var(--color-text-secondary)",
                fontFamily: "var(--font-mono)",
                maxHeight: 200,
                overflowY: "auto",
              }}>
                {s.code}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
