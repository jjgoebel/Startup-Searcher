import sqlite3, os, datetime

conn = sqlite3.connect("startups.db")
lines = []

# --- HN posts ---
hn_snapshot = conn.execute("SELECT MAX(snapshot_at) FROM hn_posts").fetchone()[0]
hn_count = 0
hn_rows = []
if hn_snapshot is not None:
    hn_count = conn.execute("SELECT COUNT(*) FROM hn_posts WHERE snapshot_at = ?",
        (hn_snapshot,)).fetchone()[0]
    hn_rows = conn.execute("""SELECT id, title, url, points, comments FROM hn_posts
        WHERE snapshot_at = ? ORDER BY points DESC LIMIT 15""", (hn_snapshot,)).fetchall()

# --- GitHub repos ---
gh_snapshot = conn.execute("SELECT MAX(snapshot_at) FROM github_repos").fetchone()[0]
gh_count = 0
gh_rows = []
if gh_snapshot is not None:
    gh_count = conn.execute("SELECT COUNT(*) FROM github_repos WHERE snapshot_at = ?",
        (gh_snapshot,)).fetchone()[0]
    gh_rows = conn.execute("""SELECT full_name, stars, language, description, homepage
        FROM github_repos WHERE snapshot_at = ? ORDER BY stars DESC LIMIT 15""",
        (gh_snapshot,)).fetchall()

lines.append(f"Snapshot: {hn_count} HN posts, {gh_count} GitHub repos\n")

lines.append("## Top 15 Show HN posts\n")
for id, title, url, points, comments in hn_rows:
    link = url if url else f"https://news.ycombinator.com/item?id={id}"
    lines.append(f"- [{title}]({link}) — {points} points, {comments} comments")

lines.append("\n## Top 15 GitHub repos\n")
for full_name, stars, language, description, homepage in gh_rows:
    repo_link = f"[{full_name}](https://github.com/{full_name})"
    parts = [repo_link, f"{stars} stars"]
    if language:
        parts.append(language)
    if description:
        parts.append(description)
    if homepage:
        parts.append(homepage)
    lines.append("- " + " — ".join(parts))

os.makedirs("reports", exist_ok=True)
report_path = f"reports/{datetime.date.today().isoformat()}.md"
with open(report_path, "w") as f:
    f.write("\n".join(lines) + "\n")

print("wrote", report_path)
