with open("app.py", "r") as f:
    code = f.read()

# Add background scheduler that scrapes every 30 minutes
old_main = '''if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)'''

new_main = '''# Auto-scrape on startup and every 30 minutes
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
    app.run(host="0.0.0.0", port=port, debug=False)'''

code = code.replace(old_main, new_main)

with open("app.py", "w") as f:
    f.write(code)

import py_compile
try:
    py_compile.compile("app.py", doraise=True)
    print("Added auto-scraping! No errors.")
except py_compile.PyCompileError as e:
    print(f"Error: {e}")
