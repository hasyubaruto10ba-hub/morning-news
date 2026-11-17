import feedparser
import html
import re
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

FEEDS = {
    "ITmedia": "https://rss.itmedia.co.jp/rss/2.0/itmedia_all.xml",
    "EE Times Japan": "https://rss.itmedia.co.jp/rss/2.0/eetimes.xml",
    "MONOist": "https://rss.itmedia.co.jp/rss/2.0/monoist.xml",
    "Yahoo経済": "https://news.yahoo.co.jp/rss/topics/business.xml",
    "Yahoo IT": "https://news.yahoo.co.jp/rss/topics/it.xml",
    "NHK経済": "https://www.nhk.or.jp/rss/news/cat5.xml",
}

CATEGORIES = {
    "就活に使える": [
        "半導体", "ウエハ", "製造装置", "電子部品", "センサー", "計測", "光通信",
        "通信", "5G", "6G", "クラウド", "システム開発", "SIer", "DX", "生成AI",
        "ソフトウェア", "商社", "鉄鋼", "製鉄", "化学", "設備投資", "増産",
        "提携", "買収", "決算",
    ],
    "生活のお得": [
        "値上げ", "値下げ", "無料", "ポイント", "還元", "補助金", "給付",
        "節約", "キャンペーン", "割引", "NISA", "手数料", "料金プラン", "年末調整",
    ],
    "話のネタ": [
        "世界初", "発売", "登場", "公開", "人気", "調査", "研究", "実験",
        "宇宙", "新型", "最大", "話題",
    ],
}

PER_CATEGORY = 2
MAX_AGE_HOURS = 48


def clean(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def score(title, body, words):
    hits = [w for w in words if w in title or w in body]
    s = sum(2 if w in title else 1 for w in hits)
    return s, hits


def collect():
    now = datetime.now(JST)
    seen = set()
    items = []
    errors = []
    for name, url in FEEDS.items():
        try:
            d = feedparser.parse(url)
            if not d.entries:
                errors.append(f"{name}: 記事を取得できませんでした")
                continue
            for e in d.entries[:50]:
                title = clean(e.get("title", ""))
                link = e.get("link", "")
                if not title or not link or link in seen or title in seen:
                    continue
                ts = e.get("published_parsed") or e.get("updated_parsed")
                if ts:
                    t = datetime(*ts[:6], tzinfo=timezone.utc)
                    if now - t > timedelta(hours=MAX_AGE_HOURS):
                        continue
                body = clean(e.get("summary", ""))
                best = None
                for cat, words in CATEGORIES.items():
                    s, hits = score(title, body, words)
                    if s > 0 and (best is None or s > best[1]):
                        best = (cat, s, hits)
                if best:
                    seen.add(link)
                    seen.add(title)
                    items.append({
                        "cat": best[0], "score": best[1], "hits": best[2],
                        "title": title, "link": link, "source": name,
                    })
        except Exception as ex:
            errors.append(f"{name}: エラー {ex}")
    return items, errors, now


def render(items, errors, now):
    parts = []
    for cat in CATEGORIES:
        top = sorted([i for i in items if i["cat"] == cat],
                     key=lambda x: -x["score"])[:PER_CATEGORY]
        parts.append(f"<h2>{html.escape(cat)}</h2>")
        if not top:
            parts.append("<p class='none'>該当なし</p>")
        for i in top:
            reason = "、".join(i["hits"])
            parts.append(
                "<div class='card'>"
                f"<a href='{html.escape(i['link'])}' target='_blank' rel='noopener'>"
                f"{html.escape(i['title'])}</a>"
                f"<div class='meta'>{html.escape(i['source'])} ／ 理由: {html.escape(reason)}</div>"
                "</div>"
            )
    err = ""
    if errors:
        err = "<p class='err'>" + "<br>".join(html.escape(e) for e in errors) + "</p>"
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>朝ニュース</title>
<style>
body{{font-family:sans-serif;max-width:640px;margin:0 auto;padding:16px;line-height:1.6}}
h1{{font-size:1.3rem}} h2{{font-size:1.1rem;margin-top:1.6rem;border-left:4px solid #3b82f6;padding-left:8px}}
.card{{padding:10px 0;border-bottom:1px solid #ddd}}
.card a{{color:#111;text-decoration:none;font-weight:bold}}
.meta{{font-size:.8rem;color:#666}} .none{{color:#999}}
.err{{font-size:.75rem;color:#b45309;margin-top:2rem}}
</style></head><body>
<h1>朝ニュース</h1>
<p class="meta">更新: {now.strftime('%Y-%m-%d %H:%M')} JST</p>
{''.join(parts)}
{err}
</body></html>"""


if __name__ == "__main__":
    items, errors, now = collect()
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(render(items, errors, now))
    print(f"{len(items)}件を選別。エラー: {errors}")
