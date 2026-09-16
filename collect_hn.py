import requests, sqlite3, time

conn = sqlite3.connect("startups.db")
conn.execute("""CREATE TABLE IF NOT EXISTS hn_posts (
    id TEXT, title TEXT, url TEXT, points INT, comments INT,
    created_at INT, snapshot_at INT)""")

week_ago = int(time.time()) - 7 * 86400
r = requests.get("https://hn.algolia.com/api/v1/search_by_date", params={
    "tags": "show_hn",
    "numericFilters": f"created_at_i>{week_ago},points>20",
    "hitsPerPage": 100})
r.raise_for_status()
hits = r.json()["hits"]

now = int(time.time())
for h in hits:
    conn.execute("INSERT INTO hn_posts VALUES (?,?,?,?,?,?,?)",
        (h["objectID"], h.get("title"), h.get("url"), h.get("points"),
         h.get("num_comments"), h["created_at_i"], now))
conn.commit()
print("saved", len(hits), "posts")
