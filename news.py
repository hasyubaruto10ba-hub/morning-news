import feedparser
import html
import re
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

BIZ_FEEDS = {
    "ITmedia": "https://rss.itmedia.co.jp/rss/2.0/itmedia_all.xml",
    "EE Times Japan": "https://rss.itmedia.co.jp/rss/2.0/eetimes.xml",
    "MONOist": "https://rss.itmedia.co.jp/rss/2.0/monoist.xml",
    "Yahoo経済": "https://news.yahoo.co.jp/rss/topics/business.xml",
    "Yahoo IT": "https://news.yahoo.co.jp/rss/topics/it.xml",
    "NHK経済": "https://www.nhk.or.jp/rss/news/cat5.xml",
    "東洋経済": "https://toyokeizai.net/list/feed/rss",
}

TALK_FEEDS = {
    "Yahoo主要": "https://news.yahoo.co.jp/rss/topics/top-picks.xml",
    "Yahoo国内": "https://news.yahoo.co.jp/rss/topics/domestic.xml",
    "Yahooエンタメ": "https://news.yahoo.co.jp/rss/topics/entertainment.xml",
    "Yahooスポーツ": "https://news.yahoo.co.jp/rss/topics/sports.xml",
    "Yahoo科学": "https://news.yahoo.co.jp/rss/topics/science.xml",
}

INDUSTRIES = {
    "半導体・電子・計測": ["半導体", "ウエハ", "製造装置", "電子部品", "センサー",
                    "計測", "光学", "フォトニクス", "パワー半導体", "車載"],
    "通信・IT": ["通信", "5G", "6G", "光ファイバ", "クラウド", "SIer",
              "システム開発", "ソフトウェア", "生成AI", "DX", "サイバー", "データセンター"],
    "商社・素材": ["商社", "総合商社", "専門商社", "鉄鋼", "製鉄", "鋼材",
              "化学", "素材", "資源", "レアメタル"],
}
ACTIONS = ["提携", "買収", "増産", "設備投資", "新工場", "参入", "撤退", "決算",
           "最高益", "受注", "共同開発", "協業", "上方修正", "下方修正", "値上げ"]

SAVING = ["値上げ", "値下げ", "無料", "ポイント", "還元", "補助金", "給付", "節約",
          "キャンペーン", "割引", "NISA", "手数料", "料金プラン", "年末調整", "減税", "控除"]

TALK_NG = ["死亡", "死去", "逮捕", "容疑", "殺人", "事故", "火災", "遺体",
           "被害", "詐欺", "不明", "地震", "津波", "刺さ", "襲"]

PER_GROUP = 2
PER_SAVE = 5
PER_TALK = 6
BIZ_MAX_AGE = 72
TALK_MAX_AGE = 36
SUMMARY_LEN = 110


def clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(text or ""))).strip()


def score(title, body, words):
    hits = [w for w in words if w in title or w in body]
    return sum(2 if w in title else 1 for w in hits), hits


def fetch(feeds, now, max_age, seen, errors):
    out = []
    for name, url in feeds.items():
        try:
            d = feedparser.parse(url)
            if not d.entries:
                errors.append(f"{name}: 記事を取得できませんでした")
                continue
            for e in d.entries[:60]:
                title = clean(e.get("title", ""))
                link = e.get("link", "")
                if not title or not link or link in seen or title in seen:
                    continue
                ts = e.get("published_parsed") or e.get("updated_parsed")
                if ts:
                    t = datetime(*ts[:6], tzinfo=timezone.utc)
                    if now - t > timedelta(hours=max_age):
                        continue
                seen.add(link)
                seen.add(title)
                out.append({"title": title, "link": link, "source": name,
                            "body": clean(e.get("summary", ""))})
        except Exception as ex:
            errors.append(f"{name}: エラー {ex}")
    return out


def pick_job(entries):
    scored = []
    for e in entries:
        best = None
        for g, words in INDUSTRIES.items():
            s, h = score(e["title"], e["body"], words)
            if s > 0 and (best is None or s > best[1]):
                best = (g, s, h)
        if not best:
            continue
        a_s, a_h = score(e["title"], e["body"], ACTIONS)
        scored.append({**e, "group": best[0], "score": best[1] + a_s * 2,
                       "hits": best[2] + a_h})
    scored.sort(key=lambda x: -x["score"])
    picked, count = [], {}
    for s in scored:
        if count.get(s["group"], 0) >= PER_GROUP:
            continue
        picked.append(s)
        count[s["group"]] = count.get(s["group"], 0) + 1
    return picked


def pick_save(entries, used):
    scored = []
    for e in entries:
        if e["link"] in used:
            continue
        s, h = score(e["title"], e["body"], SAVING)
        if s > 0:
            scored.append({**e, "score": s, "hits": h})
    scored.sort(key=lambda x: -x["score"])
    return scored[:PER_SAVE]


def pick_talk(entries):
    by_source = {}
    for e in entries:
        if any(w in e["title"] for w in TALK_NG):
            continue
        by_source.setdefault(e["source"], []).append(e)
    picked, i = [], 0
    while len(picked) < PER_TALK and any(by_source.values()):
        for src in list(by_source):
            if by_source[src] and len(picked) < PER_TALK:
                picked.append({**by_source[src].pop(0), "hits": []})
        i += 1
        if i > 20:
            break
    return picked


def card(i, label=None):
    meta = html.escape(i["source"])
    if label:
        meta = f"{html.escape(label)} ／ " + meta
    if i.get("hits"):
        meta += " ／ 注目語: " + html.escape("、".join(i["hits"]))
    summ = i["body"][:SUMMARY_LEN]
    summ_html = f"<div class='sum'>{html.escape(summ)}…</div>" if summ else ""
    return ("<div class='card'>"
            f"<a href='{html.escape(i['link'])}' target='_blank' rel='noopener'>"
            f"{html.escape(i['title'])}</a>{summ_html}"
            f"<div class='meta'>{meta}</div></div>")


def section(title, items, hint="", label_key=None):
    parts = [f"<h2>{html.escape(title)}</h2>"]
    if hint:
        parts.append(f"<p class='hint'>{html.escape(hint)}</p>")
    if not items:
        parts.append("<p class='none'>該当なし</p>")
    for i in items:
        parts.append(card(i, i.get(label_key) if label_key else None))
    return "".join(parts)


def render(job, save, talk, errors, now):
    body = (section("就活に使える", job,
                    "面接で言う型: ①何が起きたか ②志望業界への影響 ③自分の考え",
                    "group")
            + section("生活のお得", save)
            + section("話のネタ（誰でも話せる話題）", talk))
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
.sum{{font-size:.85rem;color:#333;margin-top:2px}}
.meta{{font-size:.75rem;color:#666;margin-top:2px}} .none{{color:#999}}
.hint{{font-size:.8rem;color:#2563eb}}
.err{{font-size:.75rem;color:#b45309;margin-top:2rem}}
</style></head><body>
<h1>朝ニュース</h1>
<p class="meta">更新: {now.strftime('%Y-%m-%d %H:%M')} JST</p>
{body}
{err}
</body></html>"""


if __name__ == "__main__":
    now = datetime.now(JST)
    errors, seen = [], set()
    biz = fetch(BIZ_FEEDS, now, BIZ_MAX_AGE, seen, errors)
    talk_src = fetch(TALK_FEEDS, now, TALK_MAX_AGE, seen, errors)
    job = pick_job(biz)
    save = pick_save(biz, {j["link"] for j in job})
    talk = pick_talk(talk_src)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(render(job, save, talk, errors, now))
    print(f"就活{len(job)}件 / お得{len(save)}件 / 話のネタ{len(talk)}件 / エラー: {errors}")
