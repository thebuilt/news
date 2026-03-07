import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import pycountry
import requests
from dateutil import parser as dateparser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
KEYWORDS_FILE = os.path.join(ROOT, "keywords", "base_keywords.txt")

TODAY_UTC = datetime.now(timezone.utc).date()
TODAY_STR = TODAY_UTC.isoformat()
MAX_DAILY_ARTICLES = 1200

COUNTRY_CODE_ALIASES = {
    "UK": "GB",
    "EL": "GR",
}


def load_base_keywords():
    with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip()]


def normalize_term(t):
    return re.sub(r"\s+", " ", t.strip().lower())


def expand_keywords_from_wikidata(base_terms):
    terms = set(normalize_term(x) for x in base_terms)
    session = requests.Session()
    for term in base_terms:
        try:
            search = session.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbsearchentities",
                    "format": "json",
                    "language": "en",
                    "type": "item",
                    "limit": 1,
                    "search": term,
                },
                timeout=20,
            ).json()
            if not search.get("search"):
                continue
            qid = search["search"][0]["id"]
            entity = session.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": qid,
                    "props": "labels|aliases",
                },
                timeout=20,
            ).json()
            data = entity["entities"][qid]
            for _, obj in data.get("labels", {}).items():
                v = normalize_term(obj.get("value", ""))
                if v:
                    terms.add(v)
            for _, arr in data.get("aliases", {}).items():
                for a in arr:
                    v = normalize_term(a.get("value", ""))
                    if v:
                        terms.add(v)
        except Exception:
            continue
    return sorted(terms)


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def clean_url(url):
    if not url:
        return ""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}"


def country_name_from_code(code):
    if not code:
        return "Unknown"
    code = code.upper()
    if len(code) == 2:
        try:
            c = pycountry.countries.get(alpha_2=code)
            return c.name if c else "Unknown"
        except Exception:
            return "Unknown"
    if len(code) == 3:
        try:
            c = pycountry.countries.get(alpha_3=code)
            return c.name if c else "Unknown"
        except Exception:
            return "Unknown"
    return code.title()


def normalize_country_code(code):
    if not code:
        return "XX"
    code = str(code).strip().upper()
    if not code:
        return "XX"
    code = COUNTRY_CODE_ALIASES.get(code, code)
    if len(code) == 2 and pycountry.countries.get(alpha_2=code):
        return code
    if len(code) == 3:
        c = pycountry.countries.get(alpha_3=code)
        if c:
            return c.alpha_2
    return "XX"


def infer_country_from_domain(domain):
    if not domain:
        return ("XX", "Unknown")
    tld = domain.split(".")[-1].lower()
    if len(tld) == 2:
        try:
            c = pycountry.countries.get(alpha_2=tld.upper())
            if c:
                return (tld.upper(), c.name)
        except Exception:
            pass
    return ("XX", "Unknown")


INDIAN_OUTLET_HINTS = {
    "the hindu",
    "times of india",
    "hindustan times",
    "ndtv",
    "the indian express",
    "deccan herald",
    "business standard",
    "financial express",
    "india today",
    "mint",
    "livemint",
    "the wire",
    "scroll.in",
    "aninews",
    "pti",
}


def infer_country_from_outlet_name(name):
    if not name:
        return ("XX", "Unknown")
    lowered = name.strip().lower()
    for hint in INDIAN_OUTLET_HINTS:
        if hint in lowered:
            return ("IN", "India")
    return ("XX", "Unknown")


def fetch_gdelt(terms):
    articles = []
    startdt = TODAY_UTC.strftime("%Y%m%d") + "000000"
    enddt = TODAY_UTC.strftime("%Y%m%d") + "235959"

    for group in chunks(terms[:120], 12):
        query = " OR ".join([f'"{t}"' for t in group])
        try:
            r = requests.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params={
                    "query": query,
                    "mode": "ArtList",
                    "maxrecords": 120,
                    "format": "json",
                    "sort": "DateDesc",
                    "startdatetime": startdt,
                    "enddatetime": enddt,
                },
                timeout=30,
            )
            data = r.json()
            for a in data.get("articles", []):
                url = a.get("url", "")
                domain = urlparse(url).netloc.lower()
                source_code = normalize_country_code(a.get("sourcecountry"))
                if len(source_code) != 2:
                    source_code, source_country = infer_country_from_domain(domain)
                else:
                    source_country = country_name_from_code(source_code)

                seendate = a.get("seendate", "")
                try:
                    dt = datetime.strptime(seendate, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                except Exception:
                    dt = datetime.now(timezone.utc)

                articles.append(
                    {
                        "title": a.get("title", "").strip(),
                        "outlet": domain or "Unknown",
                        "country_code": source_code,
                        "country": source_country,
                        "date": dt.isoformat(),
                        "url": clean_url(url),
                        "source": "GDELT",
                    }
                )
                if len(articles) >= MAX_DAILY_ARTICLES:
                    return articles
        except Exception:
            continue
    return articles


def fetch_google_rss(terms):
    articles = []
    for group in chunks(terms[:120], 8):
        q = "(" + " OR ".join([f'"{t}"' for t in group]) + ") when:1d"
        try:
            resp = requests.get(
                "https://news.google.com/rss/search",
                params={"q": q, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
                timeout=30,
            )
            feed = feedparser.parse(resp.text)
            for e in feed.entries:
                link = e.get("link", "")
                source = e.get("source", {}) or {}
                outlet = source.get("title", "") or urlparse(link).netloc
                source_href = source.get("href", "")
                dt_raw = e.get("published", "") or e.get("updated", "")
                try:
                    dt = dateparser.parse(dt_raw).astimezone(timezone.utc)
                except Exception:
                    dt = datetime.now(timezone.utc)

                source_domain = urlparse(source_href).netloc.lower()
                link_domain = urlparse(link).netloc.lower()
                ccode, cname = infer_country_from_domain(source_domain)
                if ccode == "XX":
                    ccode, cname = infer_country_from_domain(link_domain)
                if ccode == "XX":
                    ccode, cname = infer_country_from_outlet_name(outlet)
                ccode = normalize_country_code(ccode)
                cname = country_name_from_code(ccode) if ccode != "XX" else cname

                articles.append(
                    {
                        "title": e.get("title", "").strip(),
                        "outlet": outlet.strip() if outlet else "Unknown",
                        "country_code": ccode,
                        "country": cname,
                        "date": dt.isoformat(),
                        "url": clean_url(link),
                        "source": "GoogleNewsRSS",
                    }
                )
                if len(articles) >= MAX_DAILY_ARTICLES:
                    return articles
        except Exception:
            continue
    return articles


def dedupe(items):
    seen = set()
    out = []
    for a in items:
        key = (a["url"], a["title"].lower())
        if not a["title"] or not a["url"] or key in seen:
            continue
        seen.add(key)
        out.append(a)
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def prune_old_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    keep_from = TODAY_UTC - timedelta(days=6)
    for fn in os.listdir(DATA_DIR):
        if not fn.endswith(".json"):
            continue
        if fn == "latest.json" or fn == "index.json":
            continue
        try:
            d = datetime.strptime(fn.replace(".json", ""), "%Y-%m-%d").date()
            if d < keep_from:
                os.remove(os.path.join(DATA_DIR, fn))
        except Exception:
            pass


def build_index():
    files = []
    for fn in os.listdir(DATA_DIR):
        if re.match(r"^\d{4}-\d{2}-\d{2}\.json$", fn):
            files.append(fn.replace(".json", ""))
    files.sort(reverse=True)
    with open(os.path.join(DATA_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"dates": files}, f, ensure_ascii=False, indent=2)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    base_terms = load_base_keywords()
    terms = expand_keywords_from_wikidata(base_terms)

    gdelt = fetch_gdelt(terms)
    grss = fetch_google_rss(terms)
    articles = dedupe(gdelt + grss)[:MAX_DAILY_ARTICLES]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": TODAY_STR,
        "total": len(articles),
        "articles": articles,
    }

    day_file = os.path.join(DATA_DIR, f"{TODAY_STR}.json")
    with open(day_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    with open(os.path.join(DATA_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    prune_old_files()
    build_index()


if __name__ == "__main__":
    main()
