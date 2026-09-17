import os, sqlite3, sys, time, datetime
import requests
from dotenv import load_dotenv

load_dotenv()
token = os.environ["GITHUB_TOKEN"]

conn = sqlite3.connect("startups.db")
conn.execute("""CREATE TABLE IF NOT EXISTS github_repos (
    full_name TEXT, owner TEXT, stars INT, forks INT, description TEXT,
    homepage TEXT, language TEXT, created_at TEXT, snapshot_at INT)""")

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

cutoff = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
query = f"created:>={cutoff} stars:>=50"

now = int(time.time())
per_page = 100
page = 1
total_saved = 0
all_repos = []

while True:
    r = requests.get("https://api.github.com/search/repositories", headers=headers, params={
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
        "page": page}, timeout=30)

    if r.status_code in (403, 429) and r.headers.get("X-RateLimit-Remaining") == "0":
        reset_at = int(r.headers.get("X-RateLimit-Reset", 0))
        wait_seconds = max(0, reset_at - int(time.time()))
        print(f"Rate limited. Resets in {wait_seconds} seconds.")
        sys.exit(1)
    r.raise_for_status()

    data = r.json()
    items = data["items"]

    for repo in items:
        all_repos.append(repo)
        conn.execute("INSERT INTO github_repos VALUES (?,?,?,?,?,?,?,?,?)",
            (repo["full_name"], repo["owner"]["login"], repo["stargazers_count"],
             repo["forks_count"], repo.get("description"), repo.get("homepage"),
             repo.get("language"), repo["created_at"], now))
    conn.commit()
    total_saved += len(items)

    print(f"page {page}: fetched {len(items)} repos (total so far: {total_saved} of {data['total_count']})")

    fetched = page * per_page
    if fetched >= data["total_count"] or fetched >= 1000 or len(items) == 0:
        break
    page += 1
    time.sleep(2)  # respect GitHub search rate limits between page requests

print("saved", total_saved, "repos")

top10 = sorted(all_repos, key=lambda r: r["stargazers_count"], reverse=True)[:10]
print("\nTop 10 by stars:")
for repo in top10:
    print(f"{repo['stargazers_count']:>6} stars  {repo['full_name']}")
