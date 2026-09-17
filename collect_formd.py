import argparse, re, sqlite3, time, datetime
import xml.etree.ElementTree as ET
import requests

HEADERS = {"User-Agent": "John Goebel jjgoebel@uchicago.edu"}

conn = sqlite3.connect("startups.db")
# accession_number is a PRIMARY KEY here (not append-only like the other
# tables) because Form D filings are immutable historical facts, not
# periodic snapshots -- INSERT OR IGNORE just skips ones we already have.
conn.execute("""CREATE TABLE IF NOT EXISTS form_d_filings (
    accession_number TEXT PRIMARY KEY,
    cik TEXT,
    issuer_name TEXT,
    form_type TEXT,
    filing_date TEXT,
    state TEXT,
    industry TEXT,
    total_amount_sold TEXT,
    total_offering_amount TEXT)""")
conn.commit()


def get_with_retry(url, retries=3):
    for attempt in range(retries):
        try:
            return requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            if attempt == retries - 1:
                print(f"  giving up on {url}: {e}")
                return None
            time.sleep(2 * (attempt + 1))  # brief backoff before retrying


def daterange(start, end):
    day = start
    while day <= end:
        yield day
        day += datetime.timedelta(days=1)


def index_url(day):
    quarter = (day.month - 1) // 3 + 1
    return f"https://www.sec.gov/Archives/edgar/daily-index/{day.year}/QTR{quarter}/form.{day.strftime('%Y%m%d')}.idx"


def fetch_day_filings(day):
    """Return [(form_type, cik, accession_number), ...] for Form D/D-A filings on this day."""
    r = get_with_retry(index_url(day))
    time.sleep(0.15)  # stay under SEC's 10 req/sec limit
    if r is None or r.status_code != 200:
        return []  # weekend/holiday (no index published), or gave up after retries

    filings = []
    for line in r.text.splitlines():
        tokens = line.split()
        if not tokens or tokens[0] not in ("D", "D/A"):
            continue
        # last token is a path like edgar/data/2115466/0001231919-26-001189.txt
        match = re.search(r"edgar/data/(\d+)/([\d-]+)\.txt$", tokens[-1])
        if match:
            filings.append((tokens[0], match.group(1), match.group(2)))
    return filings


def fetch_filing_detail(cik, accession_number):
    url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/"
           f"{accession_number.replace('-', '')}/primary_doc.xml")
    r = get_with_retry(url)
    time.sleep(0.15)
    if r is None or r.status_code != 200:
        return None

    root = ET.fromstring(r.text)
    return {
        "issuer_name": root.findtext("primaryIssuer/entityName"),
        "state": root.findtext("primaryIssuer/issuerAddress/stateOrCountry"),
        "industry": root.findtext("offeringData/industryGroup/industryGroupType"),
        "total_amount_sold": root.findtext("offeringData/offeringSalesAmounts/totalAmountSold"),
        "total_offering_amount": root.findtext("offeringData/offeringSalesAmounts/totalOfferingAmount"),
    }


parser = argparse.ArgumentParser()
parser.add_argument("--start", help="YYYY-MM-DD, default: 7 days ago")
parser.add_argument("--end", help="YYYY-MM-DD, default: today")
args = parser.parse_args()

today = datetime.date.today()
start = datetime.date.fromisoformat(args.start) if args.start else today - datetime.timedelta(days=7)
end = datetime.date.fromisoformat(args.end) if args.end else today

total_seen = 0
total_new = 0

for day in daterange(start, end):
    day_filings = fetch_day_filings(day)
    day_new = 0

    for form_type, cik, accession_number in day_filings:
        detail = fetch_filing_detail(cik, accession_number)
        if detail is None:
            continue
        cur = conn.execute("""INSERT OR IGNORE INTO form_d_filings VALUES
            (?,?,?,?,?,?,?,?,?)""",
            (accession_number, cik, detail["issuer_name"], form_type,
             day.isoformat(), detail["state"], detail["industry"],
             detail["total_amount_sold"], detail["total_offering_amount"]))
        conn.commit()
        if cur.rowcount:
            day_new += 1

    total_seen += len(day_filings)
    total_new += day_new
    print(f"{day.isoformat()}: {len(day_filings)} Form D/D-A filings, {day_new} new")

print(f"\nDone. {total_seen} filings checked, {total_new} newly saved "
      f"({total_seen - total_new} already in form_d_filings).")
