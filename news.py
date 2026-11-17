import feedparser
import html
import re
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# ビジネス系RSS（就活・お得の軸に使う）
BIZ_FEEDS = {
    "ITmedia": "https://rss.itmedia.co.jp/rss/2.0/itmedia_all.xml",
    "EE Times Japan": "https://rss.itmedia.co.jp/rss/2.0/eetimes.xml",
    "MONOist": "https://rss.itmedia.co.jp/rss/2.0/monoist.xml",
    "Yahoo経済": "https://news.yahoo.co.jp/rss/topics/business.xml",
    "Yahoo IT": "https://news.yahoo.co.jp/rss/topics/it.xml",
    "NHK経済": "https://www.nhk.or.jp/rss/news/cat5.xml",
    "東洋経済": "https://toyokeizai.net/list/feed/rss",
}

# 一般向けRSS（話のネタの軸に使う。専門外でも話せる話題）
TALK_FEEDS = {
    "Yahoo主要": "https://news.yahoo.co.jp/rss/topics/top-picks.xml",
    "Yahoo国内": "https://news.yahoo.co.jp/rss/topics/domestic.xml",
    "Yahooエンタメ": "https://news.yahoo.co.jp/rss/topics/entertainment.xml",
    "Yahooスポーツ": "https://news.yahoo.co.jp/rss/topics/sports.xml",
    "Yahoo科学": "https://news.yahoo.co.jp/rss/topics/science.xml",
}

# 就活: 業界ごとのキーワード（業界ごとに上限を設けて偏りを防ぐ）
INDUSTRIES = {
    "半導体・電子・計測": ["半導体", "ウエハ", "製造装置", "電子部品", "センサー",
                    "計測", "光学", "フォトニクス", "パワー半導体", "車載"],
    "通信・IT": ["通信", "5G", "6G", "光ファイバ", "クラウド", "SIer",
              "システム開発", "ソフトウェア", "生成AI", "DX", "サイバー", "データセンター"],
    "商社・素材": ["商社", "総合商社", "専門商社", "鉄鋼", "製鉄", "鋼材",
              "化学", "素材", "資源", "レアメタル"],
}
# 「動き」を表す言葉（面接で話せる材料になりやすい）
ACTIONS = ["提携", "買収", "増産", "設備投資", "新工場", "参入", "撤退", "決算",
           "最高益", "受注", "共同開発", "協業", "上方修正", "下方修正", "値上げ"]

SAVING = ["値上げ", "値下げ", "無料", "ポイント", "還元", "補助金", "給付", "節約",
          "キャンペーン", "割引", "NISA", "手数料", "料金プラン", "年末調整", "減税", "控除"]

# 話のネタから外す重い話題
TALK_NG = ["死亡", "死去", "逮捕", "容疑", "殺人", "事故", "火災", "遺体",
           "被害", "詐欺", "不明", "地震", "津波", "刺さ", "襲"]

PER_GROUP = 2    # 就活: 業界ごとの表示本数
PER_SAVE = 5     # お得の表示本数
PER_TALK = 6     # 話のネタの表示本数
BIZ_MAX_AGE = 72
TALK_MAX_AGE = 36
SUMMARY_LEN = 110

# 用語集: 記事に出てきた難しい言葉を、やさしい説明つきで表示します（自分で追加できます）
GLOSSARY = {
    "半導体": "電気の流れを細かく操る部品の材料。スマホやPCの頭脳に使われる",
    "ウエハ": "半導体の元になる、薄い円盤",
    "製造装置": "半導体などを作るための機械",
    "パワー半導体": "電気を効率よく制御する半導体。電気自動車などに使う",
    "電子部品": "スマホや家電の中に入っている小さな部品",
    "センサー": "光・温度・動きなどを読み取る部品",
    "計測": "長さや温度などを正確にはかること",
    "フォトニクス": "光を使う技術",
    "光ファイバ": "光で情報を送るケーブル",
    "5G": "高速で大量に通信できる、携帯電話の通信方式",
    "6G": "5Gの次の通信方式（開発中）",
    "クラウド": "自分のPCではなく、ネット上のサーバーにデータやソフトを置く仕組み",
    "SIer": "企業向けにシステムを作って納める会社",
    "システム開発": "企業などが使うソフトの仕組みを作ること",
    "DX": "ITを使って、仕事のやり方を変えること",
    "生成AI": "文章や画像を自分で作り出すAI",
    "データセンター": "たくさんのコンピューターを置いて管理する施設",
    "サイバー": "コンピューターやネットに関すること（攻撃や守りの話が多い）",
    "総合商社": "幅広い分野の商品を扱う、大きな商社",
    "専門商社": "特定の分野に強い商社",
    "商社": "商品を仕入れて売る、仲立ちをする会社",
    "鉄鋼": "鉄をつくる産業・その製品",
    "製鉄": "鉄鉱石から鉄をつくること",
    "鋼材": "建物や車に使う、鉄の材料",
    "レアメタル": "取れる量が少なく貴重な金属",
    "設備投資": "工場や機械にお金をかけること",
    "増産": "作る量を増やすこと",
    "提携": "会社どうしが協力すると約束すること",
    "買収": "他の会社を買い取ること",
    "協業": "会社どうしが一緒に事業をすること",
    "共同開発": "一緒に新しい製品を作ること",
    "決算": "一定期間のもうけを計算してまとめること",
    "最高益": "過去でいちばん大きいもうけ",
    "上方修正": "業績の予想を、よい方向に直すこと",
    "下方修正": "業績の予想を、悪い方向に直すこと",
    "受注": "注文を受けること",
    "参入": "新しい事業に入ること",
    "撤退": "事業をやめること",
    "NISA": "投資のもうけにかかる税金がゼロになる制度",
    "控除": "税金を計算するときに、引いてもらえる金額",
    "減税": "税金を減らすこと",
    "給付": "国などがお金を配ること",
    "還元": "ポイントやお金を利用者に返すこと",
    "補助金": "国などが出す、返さなくていいお金",
    "手数料": "サービスを使うときにかかる料金",
    "年末調整": "年末に、払いすぎた所得税を精算する手続き",
}
MAX_TERMS = 3

SCRIPT = r"""<script>
function cp(b){
  var t = "次の記事を、やさしい言葉で次の4つに整理してください。\n" +
          "①何が起きたか（結果）\n②その背景\n③今後の見通し\n" +
          "④業界の動きと、面接で言える一言\n\n記事: " + b.dataset.t + "\n" + b.dataset.u;
  navigator.clipboard.writeText(t).then(function(){ b.textContent = "コピーしました"; });
}
</script>"""


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


def glossary_for(i):
    text = i["title"] + i["body"]
    found = []
    for w in sorted(GLOSSARY, key=len, reverse=True):
        if w in text and not any(w in f for f in found):
            found.append(w)
    return found[:MAX_TERMS]


def card(i, label=None):
    meta = html.escape(i["source"])
    if label:
        meta = f"{html.escape(label)} ／ " + meta
    if i.get("hits"):
        meta += " ／ 注目語: " + html.escape("、".join(i["hits"]))
    summ = i["body"][:SUMMARY_LEN]
    summ_html = f"<div class='sum'>{html.escape(summ)}…</div>" if summ else ""
    terms = glossary_for(i)
    gl_html = ""
    if terms:
        lines = "<br>".join(f"▶ {html.escape(w)}＝{html.escape(GLOSSARY[w])}" for w in terms)
        gl_html = ("<div style='font-size:.8rem;background:#f1f5f9;padding:4px 8px;"
                   f"border-radius:6px;margin-top:4px'>{lines}</div>")
    btn = ("<button style='margin-top:6px;font-size:.75rem;padding:4px 10px' "
           f"data-t=\"{html.escape(i['title'])}\" data-u=\"{html.escape(i['link'])}\" "
           "onclick='cp(this)'>読み解き用にコピー</button>")
    return ("<div class='card'>"
            f"<a href='{html.escape(i['link'])}' target='_blank' rel='noopener'>"
            f"{html.escape(i['title'])}</a>{summ_html}{gl_html}"
            f"<div class='meta'>{meta}</div>{btn}</div>")


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
{SCRIPT}
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
    print(f"就活{len(job)}件 / 就活{len(save)}件")
