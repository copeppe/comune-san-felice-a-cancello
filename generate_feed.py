import html, re, unicodedata, urllib.request, json
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

API_URL = "https://www.comune.sanfeliceacancello.ce.it/kapi/api/sito/novita?size=100"
SITE_URL = "https://www.comune.sanfeliceacancello.ce.it"
MAX_ITEMS = 50

def slugify(value):
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.replace("/", "").replace("'", "").replace("’", "").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")

def item_url(item):
    return f"{SITE_URL}/sito/avviso/{item['id']}-{slugify(item.get('cntTitle',''))}"

def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

def main():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "SanFeliceRSS/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    items = sorted(data.get("results", []),
                   key=lambda x: x.get("cntDataPubblicazione") or "", reverse=True)[:MAX_ITEMS]
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"><channel>',
        '<title>Comune di San Felice a Cancello – Novità</title>',
        f'<link>{SITE_URL}/sito/novita</link>',
        '<description>Novità del Comune di San Felice a Cancello</description>',
        '<language>it-it</language>',
        f'<lastBuildDate>{format_datetime(datetime.now(timezone.utc), usegmt=True)}</lastBuildDate>'
    ]
    for x in items:
        title = html.escape(str(x.get("cntTitle") or ""))
        desc = html.escape(re.sub(r"<[^>]+>", " ", str(x.get("cntDescrizione") or "")).strip())
        link = html.escape(item_url(x))
        pub = format_datetime(parse_date(x.get("cntDataPubblicazione")), usegmt=True)
        guid = html.escape(str(x.get("id") or link))
        parts += [f"<item><title>{title}</title><link>{link}</link>",
                  f'<guid isPermaLink="false">{guid}</guid><pubDate>{pub}</pubDate>',
                  f"<description>{desc}</description></item>"]
    parts += ["</channel></rss>"]
    Path("feed.xml").write_text("\n".join(parts) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
