import re, sqlite3, time
import requests

conn = sqlite3.connect("startups.db")
conn.execute("""CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    domain TEXT,
    hiring_provider TEXT,
    hiring_board_token TEXT)""")
conn.execute("""CREATE TABLE IF NOT EXISTS job_snapshots (
    company_id INTEGER, provider TEXT, open_roles INT,
    engineering_roles INT, snapshot_at INT)""")
conn.commit()


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# Each function returns a list of (title, department) tuples on success,
# or None if that provider has no board under this token.
def greenhouse_jobs(token):
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", timeout=30)
    if r.status_code != 200:
        return None
    jobs = r.json().get("jobs", [])
    return [(j.get("title", ""), " ".join(d.get("name", "") for d in j.get("departments", [])))
             for j in jobs]


def lever_jobs(token):
    r = requests.get(f"https://api.lever.co/v0/postings/{token}",
        params={"mode": "json"}, timeout=30)
    if r.status_code != 200:
        return None
    postings = r.json()
    if not isinstance(postings, list):
        return None
    return [(p.get("text", ""), p.get("categories", {}).get("team", "")) for p in postings]


def ashby_jobs(token):
    r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{token}", timeout=30)
    if r.status_code != 200:
        return None
    jobs = r.json().get("jobs", [])
    return [(j.get("title", ""), j.get("departmentName") or j.get("teamName") or "")
             for j in jobs]


PROVIDERS = {"greenhouse": greenhouse_jobs, "lever": lever_jobs, "ashby": ashby_jobs}

BOARD_URL_PATTERNS = [
    ("greenhouse", re.compile(r"greenhouse\.io/(?:embed/job_board\?for=)?([a-zA-Z0-9_-]+)")),
    ("lever", re.compile(r"lever\.co/([a-zA-Z0-9_-]+)")),
    ("ashby", re.compile(r"ashbyhq\.com/([a-zA-Z0-9_-]+)")),
]


def discover_from_careers_page(domain):
    try:
        r = requests.get(f"https://{domain}/careers", timeout=30,
            headers={"User-Agent": "startup-searcher-bot"})
    except requests.RequestException:
        return None, None
    if r.status_code != 200:
        return None, None
    for provider, pattern in BOARD_URL_PATTERNS:
        match = pattern.search(r.text)
        if match:
            return provider, match.group(1)
    return None, None


def discover_provider(name, domain):
    slug = slugify(name)
    for provider, fetch in PROVIDERS.items():
        try:
            jobs = fetch(slug)
        except requests.RequestException:
            jobs = None
        if jobs is not None:
            return provider, slug
    return discover_from_careers_page(domain)


def is_engineering(title, department):
    return "engineer" in f"{title} {department}".lower()


now = int(time.time())
companies = conn.execute("""SELECT id, name, domain, hiring_provider, hiring_board_token
    FROM companies WHERE domain IS NOT NULL AND domain != ''""").fetchall()

boards_found = 0
snapshots_saved = 0

for company_id, name, domain, provider, token in companies:
    if not provider or not token:
        provider, token = discover_provider(name, domain)
        if provider and token:
            conn.execute("""UPDATE companies SET hiring_provider = ?, hiring_board_token = ?
                WHERE id = ?""", (provider, token, company_id))
            conn.commit()

    if provider and token:
        boards_found += 1
        try:
            jobs = PROVIDERS[provider](token)
        except requests.RequestException:
            jobs = None

        if jobs is not None:
            open_roles = len(jobs)
            engineering_roles = sum(1 for title, dept in jobs if is_engineering(title, dept))
            conn.execute("INSERT INTO job_snapshots VALUES (?,?,?,?,?)",
                (company_id, provider, open_roles, engineering_roles, now))
            conn.commit()
            snapshots_saved += 1
            print(f"{name}: {provider}, {open_roles} open roles ({engineering_roles} engineering)")
        else:
            print(f"{name}: {provider} board found but fetching roles failed")
    else:
        print(f"{name}: no job board found")

    time.sleep(1)  # be polite between companies

print(f"\nChecked {len(companies)} companies. Found job boards for {boards_found}. "
      f"Saved {snapshots_saved} snapshot(s).")
