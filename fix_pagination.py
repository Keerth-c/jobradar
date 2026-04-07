with open("app.py", "r") as f:
    code = f.read()

# Replace the LinkedIn scraper with one that paginates
old_func = '''def scrape_linkedin(session):
    platform = "linkedin"
    all_jobs = []
    for term in ["data engineer contract", "ETL data engineer", "data pipeline engineer", "analytics engineer contract"]:
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={quote_plus(term)}&f_TPR=r86400&f_JT=C&sortBy=DD&start=0"
        try:
            resp = session.get(url, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            for card in soup.find_all("li"):'''

new_func = '''def scrape_linkedin(session):
    platform = "linkedin"
    all_jobs = []
    for term in ["data engineer contract", "ETL data engineer", "data pipeline engineer", "analytics engineer contract"]:
        for start in range(0, 100, 10):
            url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={quote_plus(term)}&f_TPR=r86400&f_JT=C&sortBy=DD&start={start}"
            try:
                resp = session.get(url, timeout=15)
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = [c for c in soup.find_all("li") if c.select_one("h3")]
                if not cards:
                    break
                for card in cards:'''

code = code.replace(old_func, new_func)

# Fix the closing of the pagination loop
old_except = '''        except: pass
        time.sleep(1)'''

new_except = '''            except: pass
            time.sleep(1)'''

code = code.replace(old_except, new_except, 1)

with open("app.py", "w") as f:
    f.write(code)

import py_compile
try:
    py_compile.compile("app.py", doraise=True)
    print("Added pagination! Will fetch up to 100 jobs per search term.")
except py_compile.PyCompileError as e:
    print(f"Error: {e}")
