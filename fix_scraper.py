with open("app.py", "r") as f:
    code = f.read()

old_start = "def scrape_linkedin(session):"
old_end = "    seen = set()\n    return [j for j in all_jobs if j[\"id\"] not in seen and not seen.add(j[\"id\"])]"

start_idx = code.find(old_start)
end_idx = code.find(old_end, start_idx)
if start_idx < 0 or end_idx < 0:
    print("ERROR: Cannot find function boundaries")
    exit(1)

end_idx += len(old_end)
before = code[:start_idx]
after = code[end_idx:]

new_func = '''def scrape_linkedin(session):
    platform = "linkedin"
    all_jobs = []
    terms = ["data engineer contract", "ETL data engineer", "data pipeline engineer", "analytics engineer contract"]
    for term in terms:
        for start in range(0, 100, 10):
            url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={quote_plus(term)}&f_TPR=r86400&f_JT=C&sortBy=DD&start={start}"
            try:
                resp = session.get(url, timeout=15)
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = [c for c in soup.find_all("li") if c.select_one("h3")]
                if not cards:
                    break
                for card in cards:
                    t = card.select_one("h3")
                    c = card.select_one("h4")
                    l = card.select_one("span.job-search-card__location")
                    a = card.select_one("a.base-card__full-link")
                    te = card.select_one("time")
                    if not t:
                        continue
                    title = t.get_text(strip=True)
                    company = c.get_text(strip=True) if c else "Unknown"
                    location = l.get_text(strip=True) if l else ""
                    href = a.get("href", "") if a else ""
                    posted_text = te.get_text(strip=True) if te else ""
                    tags = extract_tags(f"{title} {company} {location}")
                    match = match_job_to_resume(title, tags)
                    all_jobs.append({"id": make_job_id(title, company, platform), "title": title, "company": company, "location": location, "platform": platform, "salary": "Not listed", "url": href or url, "job_type": "Contract", "tags": json.dumps(tags), "description": posted_text, "posted_date": datetime.now().strftime("%Y-%m-%d"), "best_resume": match["best_resume"], "resume_file": match["best_file"], "match_score": match["match_score"], "alt_resume": match["alt_resume"]})
            except:
                pass
            time.sleep(1)
    seen = set()
    return [j for j in all_jobs if j["id"] not in seen and not seen.add(j["id"])]'''

code = before + new_func + after

with open("app.py", "w") as f:
    f.write(code)

import py_compile
try:
    py_compile.compile("app.py", doraise=True)
    print("Fixed! No errors.")
except py_compile.PyCompileError as e:
    print(f"Error: {e}")
