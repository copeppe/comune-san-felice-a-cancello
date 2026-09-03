import html
import re
import unicodedata
import urllib.request
import json
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

API_URL = "https://www.comune.sanfeliceacancello.ce.it/kapi/api/sito/novita?size=100"
DETAIL_URL = "https://www.comune.sanfeliceacancello.ce.it/kapi/api/sito/detail/5829/{id}?profondita=4"
SITE_URL = "https://www.comune.sanfeliceacancello.ce.it"
MAX_ITEMS = 50


def fetch_json(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SanFeliceRSS/2.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def slugify(value):
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.replace("/", "").replace("'", "").replace("’", "").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def item_url(item):
    return f"{SITE_URL}/sito/avviso/{item['id']}-{slugify(item.get('cntTitle', ''))}"


def parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def clean_html(value):
    """Converte una descrizione HTML in testo leggibile per il feed RSS."""
    if not value:
        return ""
    value = str(value)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p\s*>", "\n\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def get_detail_description(item_id):
    """Recupera la descrizione completa dalla API di dettaglio."""
    try:
        data = fetch_json(DETAIL_URL.format(id=item_id))

        # Per le notizie il record principale è l'oggetto radice:
        # rootId == id della notizia.
        if str(data.get("rootId")) == str(item_id):
            desc = data.get("cntDescrizione")
            if desc:
                return clean_html(desc)

            desc = data.get("cntDescrizioneEstesa")
            if desc:
                return clean_html(desc)

        # Fallback robusto: cerca ricorsivamente un oggetto con id/rootId uguale.
        def find_record(obj):
            if isinstance(obj, dict):
                if (
                    str(obj.get("id")) == str(item_id)
                    or str(obj.get("rootId")) == str(item_id)
                ):
                    if obj.get("cntDescrizione"):
                        return clean_html(obj["cntDescrizione"])
                    if obj.get("cntDescrizioneEstesa"):
                        return clean_html(obj["cntDescrizioneEstesa"])

                for value in obj.values():
                    found = find_record(value)
                    if found:
                        return found

            elif isinstance(obj, list):
                for value in obj:
                    found = find_record(value)
                    if found:
                        return found

            return ""

        return find_record(data)

    except Exception as exc:
        print(f"ATTENZIONE: impossibile recuperare il dettaglio {item_id}: {exc}")
        return ""


def main():
    data = fetch_json(API_URL)

    items = sorted(
        data.get("results", []),
        key=lambda x: x.get("cntDataPubblicazione") or "",
        reverse=True
    )[:MAX_ITEMS]

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
        item_id = x.get("id")

        # Manteniamo il titolo che già usa il feed funzionante.
        title = html.escape(str(x.get("cntTitle") or ""))

        # Prima proviamo la descrizione completa del dettaglio.
        desc = get_detail_description(item_id)

        # Fallback: se il dettaglio non è disponibile, usiamo quella
        # eventualmente presente nell'elenco delle novità.
        if not desc:
            desc = clean_html(x.get("cntDescrizione") or "")

        desc = html.escape(desc)
        link = html.escape(item_url(x))
        pub = format_datetime(
            parse_date(x.get("cntDataPubblicazione")),
            usegmt=True
        )
        guid = html.escape(str(item_id or link))

        parts += [
            f"<item><title>{title}</title><link>{link}</link>",
            f'<guid isPermaLink="false">{guid}</guid><pubDate>{pub}</pubDate>',
            f"<description>{desc}</description></item>"
        ]

    parts += ["</channel></rss>"]
    Path("feed.xml").write_text("\n".join(parts) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
