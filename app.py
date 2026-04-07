#!/usr/bin/env python3
import os, csv, json, sqlite3, hashlib, time, logging
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus
from flask import Flask, jsonify, render_template, request
import requests as http_requests
from bs4 import BeautifulSoup

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("JobRadar")
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "jobs.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, title TEXT, company TEXT, location TEXT,
            platform TEXT, salary TEXT, url TEXT, job_type TEXT, tags TEXT,
            description TEXT, posted_date TEXT, scraped_at TEXT,
            is_new INTEGER DEFAULT 1, best_resume TEXT, resume_file TEXT,
            match_score INTEGER DEFAULT 0, alt_resume TEXT
        );
    """)
    conn.commit()
    conn.close()

init_db()

RESUME_PROFILES = {
    "General": {"file": "Nikhil_Raj_Yammani.docx", "label": "General DE",
        "skills": ["python","scala","java","spark","hadoop","hive","kafka","flink","sql","aws","azure","gcp","s3","glue","data factory","dataproc","snowflake","redshift","bigquery","synapse"]},
    "Azure": {"file": "Nikhil_Raj_Yammani__Azure_.docx", "label": "Azure DE",
        "skills": ["azure","azure data factory","adf","azure functions","databricks","scala spark","snowflake","spring boot","scala","azure cloud","azure synapse"]},
    "DataModeling": {"file": "Nikhil_Raj_Yammani__DM_.docx", "label": "Data Modeling",
        "skills": ["data model","dimensional","erwin","kimball","inmon","star schema","snowflake schema","data warehouse","dwh","ods","redshift","snowflake","data architecture"]},
    "GCP": {"file": "Nikhil_Raj_Yammani__GCP_.docx", "label": "GCP DE",
        "skills": ["gcp","google cloud","dataproc","bigquery","pub/sub","cloud functions","cloud run","gcs","cloud storage","cloud composer","beam","pyspark","pandas"]},
    "Snowflake": {"file": "Nikhil_Raj_Yammani__SFDE_-1.docx", "label": "Snowflake DE",
        "skills": ["snowflake","dbt","dbt core","cdc","incremental","elt","idempotent","multi-account","data sharing","snowpipe"]},
    "BigData": {"file": "NIkhil_Raj_Yammani__BD_.docx", "label": "Big Data DE",
        "skills": ["hadoop","hdfs","yarn","hive","hbase","spark core","spark sql","spark streaming","ozone","kafka","scala","mapreduce"]},
}

TECH_KEYWORDS = ["Python","SQL","Spark","AWS","Azure","GCP","Snowflake","Databricks","Kafka","Airflow","dbt","Docker","Kubernetes","Scala","Java","Flink","Terraform","Redshift","BigQuery","PostgreSQL","MongoDB","ETL","ELT","Delta Lake","Hive","Presto","Trino","Fivetran","MLflow","Hadoop","SSIS","Tableau","Power BI","Looker","CI/CD","Git"]

def extract_tags(text):
    return [kw for kw in TECH_KEYWORDS if kw.lower() in text.lower()]

def match_job_to_resume(title, tags, desc=""):
    text = f"{title} {' '.join(tags) if isinstance(tags, list) else tags} {desc}".lower()
    tl = title.lower() if title else ""
    scores = {"General":0,"Azure":0,"DataModeling":0,"GCP":0,"Snowflake":0,"BigData":0}
    for name, p in RESUME_PROFILES.items():
        for s in p["skills"]:
            if s in text: scores[name] += 15
            if s in tl: scores[name] += 10
    if any(k in tl for k in ["azure","databricks","adf","fabric","synapse","microsoft"]): scores["Azure"] += 40
    if any(k in tl for k in ["gcp","google cloud","bigquery","dataproc"]): scores["GCP"] += 40
    if any(k in tl for k in ["snowflake","dbt"]): scores["Snowflake"] += 40
    if any(k in tl for k in ["hadoop","hdfs","hive","hbase","big data"]): scores["BigData"] += 40
    if any(k in tl for k in ["data model","warehouse architect","data architect","dimensional","dwh"]): scores["DataModeling"] += 40
    if any(k in tl for k in ["aws","redshift","glue"]): scores["General"] += 30
    if any(k in tl for k in ["etl","pipeline","data engineer"]): scores["General"] += 20
    if "spark" in tl or "pyspark" in tl: scores["BigData"] += 25; scores["General"] += 15
    if "kafka" in tl: scores["BigData"] += 25
    if any(k in tl for k in ["informatica","talend","ssis"]): scores["General"] += 25
    if any(k in tl for k in ["power bi","tableau","looker"]): scores["DataModeling"] += 20
    if any(k in tl for k in ["oracle","pl/sql"]): scores["General"] += 20
    for k in scores: scores[k] = min(scores[k], 100)
    if all(v == 0 for v in scores.values()): scores["General"] = 30
    best = max(scores, key=scores.get)
    ss = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return {"best_resume": RESUME_PROFILES[best]["label"], "best_file": RESUME_PROFILES[best]["file"],
            "match_score": scores[best], "alt_resume": RESUME_PROFILES[ss[1][0]]["label"] if len(ss)>1 else ""}

def make_job_id(title, company, platform):
    return hashlib.md5(f"{title.lower().strip()}|{company.lower().strip()}|{platform}".encode()).hexdigest()[:12]

def get_session():
    s = http_requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
    return s

def scrape_linkedin(session):
    platform = "linkedin"
    all_jobs = []
    for term in ["data engineer contract", "ETL data engineer", "data pipeline engineer", "analytics engineer contract"]:
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={quote_plus(term)}&f_TPR=r86400&f_JT=C&sortBy=DD&start=0"
        try:
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            for card in soup.find_all("li"):
                t = card.select_one("h3")
                c = card.select_one("h4")
                l = card.select_one("span.job-search-card__location")
                a = card.select_one("a.base-card__full-link")
                te = card.select_one("time")
                if not t: continue
                title = t.get_text(strip=True)
                company = c.get_text(strip=True) if c else "Unknown"
                location = l.get_text(strip=True) if l else ""
                href = a.get("href", "") if a else ""
                posted_text = te.get_text(strip=True) if te else ""
                tags = extract_tags(f"{title} {company} {location}")
                match = match_job_to_resume(title, tags)
                all_jobs.append({"id": make_job_id(title, company, platform), "title": title, "company": company,
                    "location": location, "platform": platform, "salary": "Not listed", "url": href or url,
                    "job_type": "Contract", "tags": json.dumps(tags), "description": posted_text,
                    "posted_date": datetime.now().strftime("%Y-%m-%d"),
                    "best_resume": match["best_resume"], "resume_file": match["best_file"],
                    "match_score": match["match_score"], "alt_resume": match["alt_resume"]})
        except: pass
        time.sleep(1)
    seen = set()
    return [j for j in all_jobs if j["id"] not in seen and not seen.add(j["id"])]

def run_scrape():
    log.info("Starting scrape...")
    session = get_session()
    conn = get_db()
    all_jobs = scrape_linkedin(session)
    new_count = 0
    for job in all_jobs:
        cur = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job["id"],))
        if not cur.fetchone():
            conn.execute("""INSERT INTO jobs (id,title,company,location,platform,salary,url,job_type,tags,description,posted_date,scraped_at,best_resume,resume_file,match_score,alt_resume)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job["id"],job["title"],job["company"],job["location"],job["platform"],job["salary"],job["url"],
                 job["job_type"],job["tags"],job["description"],job["posted_date"],datetime.now().isoformat(),
                 job["best_resume"],job["resume_file"],job["match_score"],job["alt_resume"]))
            new_count += 1
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()
    log.info(f"Done: {len(all_jobs)} found, {new_count} new, {total} total")
    return {"found": len(all_jobs), "new": new_count, "total": total}

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/jobs")
def api_jobs():
    conn = get_db()
    cur = conn.execute("SELECT * FROM jobs ORDER BY match_score DESC, scraped_at DESC")
    rows = cur.fetchall()
    jobs = []
    search = request.args.get("search", "").lower()
    for row in rows:
        job = dict(row)
        if search and search not in f"{job['title']} {job['company']} {job['tags']}".lower(): continue
        job["tags"] = json.loads(job["tags"]) if job["tags"] else []
        jobs.append(job)
    conn.close()
    return jsonify({"jobs": jobs, "total": len(jobs)})

@app.route("/api/stats")
def api_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    rc = {r["best_resume"]: r["cnt"] for r in conn.execute("SELECT best_resume, COUNT(*) as cnt FROM jobs GROUP BY best_resume ORDER BY cnt DESC")}
    pc = {r["platform"]: r["cnt"] for r in conn.execute("SELECT platform, COUNT(*) as cnt FROM jobs GROUP BY platform ORDER BY cnt DESC")}
    ls = conn.execute("SELECT MAX(scraped_at) FROM jobs").fetchone()[0]
    conn.close()
    return jsonify({"total": total, "resume_counts": rc, "platform_counts": pc, "last_scrape": ls})

@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    return jsonify(run_scrape())

# Auto-scrape on startup and every 30 minutes
import threading

def auto_scrape_loop():
    while True:
        try:
            run_scrape()
        except Exception as e:
            log.warning(f"Auto-scrape error: {e}")
        time.sleep(1800)  # 30 minutes

# Run first scrape on startup
with app.app_context():
    try:
        run_scrape()
        log.info("Initial scrape complete")
    except:
        pass

# Start background scraper thread
scraper_thread = threading.Thread(target=auto_scrape_loop, daemon=True)
scraper_thread.start()
log.info("Auto-scraper started (every 30 min)")

# Auto-scrape on startup and every 30 minutes
import threading

def auto_scrape_loop():
    while True:
        try:
            run_scrape()
        except Exception as e:
            log.warning(f"Auto-scrape error: {e}")
        time.sleep(1800)  # 30 minutes

# Run first scrape on startup
with app.app_context():
    try:
        run_scrape()
        log.info("Initial scrape complete")
    except:
        pass

# Start background scraper thread
scraper_thread = threading.Thread(target=auto_scrape_loop, daemon=True)
scraper_thread.start()
log.info("Auto-scraper started (every 30 min)")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
