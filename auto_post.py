"""
auto_post.py — RayPhoneAI GitHub Actions 自動投稿スクリプト
=============================================================
GitHub Secrets に以下を登録してください:
  GEMINI_API_KEY  : GeminiのAPIキー
  NOTE_EMAIL      : noteのメールアドレス
  NOTE_PASSWORD   : noteのパスワード
  BLOG_URL        : https://rayphoneai.github.io/ray/
  NOTE_URL        : https://note.com/rayphone
  NOTE_SHOP_URL   : https://note.com/rayphone/n/nf6e5688f3939
  GH_TOKEN        : GitHubのPersonal Access Token (repo権限)
  GH_USER         : rayphoneai
  GH_REPO         : ray
  X_COOKIES_B64   : X(Twitter)のCookieをBase64エンコードしたもの (任意)
  X_AUTO          : "true" でX自動投稿ON
"""

import os, sys, json, time, base64, re, requests
from pathlib import Path
from datetime import datetime

# ── 環境変数 ───────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
NOTE_EMAIL     = os.getenv("NOTE_EMAIL", "")
NOTE_PASSWORD  = os.getenv("NOTE_PASSWORD", "")
BLOG_URL       = os.getenv("BLOG_URL", "https://rayphoneai.github.io/ray/").rstrip("/")
NOTE_URL       = os.getenv("NOTE_URL", "https://note.com/rayphone")
NOTE_SHOP_URL  = os.getenv("NOTE_SHOP_URL", NOTE_URL)
GH_TOKEN       = os.getenv("GH_TOKEN", "")
GH_USER        = os.getenv("GH_USER", "rayphoneai")
GH_REPO        = os.getenv("GH_REPO", "ray")
X_COOKIES_B64  = os.getenv("X_COOKIES_B64", "")
X_AUTO         = os.getenv("X_AUTO", "false").lower() == "true"
HEADLESS       = os.getenv("HEADLESS", "true").lower() == "true"
CAT_INDEX_FILE = os.getenv("CAT_INDEX_FILE", "cat_index.txt")

# カテゴリローテーション
CATEGORIES = [
    "Claude活用Tips",
    "士業向けAI活用",
    "商品開発xAI",
    "副業xAI",
    "プロンプト集解説",
]

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ── カテゴリインデックス管理 ─────────────────────────────
def get_cat_index():
    if Path(CAT_INDEX_FILE).exists():
        try:
            return int(Path(CAT_INDEX_FILE).read_text().strip())
        except Exception:
            pass
    return 0

def save_cat_index(idx):
    Path(CAT_INDEX_FILE).write_text(str(idx))

# ── Gemini API ──────────────────────────────────────────────
def gemini(prompt, max_tokens=4000):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.8}
    }
    r = requests.post(url, json=body, timeout=120)
    r.raise_for_status()
    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        raise Exception(f"Gemini応答エラー: {data}")

def strip_preamble(text):
    lines = text.split("\n")
    start = 0
    for i, l in enumerate(lines[:5]):
        t = l.strip()
        if not t:
            continue
        if re.match(r"^(はい|承知|了解|執筆|Rayphone|---|\/\*|では|かしこまり)", t):
            start = i + 1
        else:
            break
    return "\n".join(lines[start:]).lstrip("---\n").strip() or text

# ── GitHub articles.json プッシュ ──────────────────────────
def push_articles(arts):
    if not GH_TOKEN or not GH_USER or not GH_REPO:
        log("GitHub設定が未完了のためスキップ")
        return
    path = "articles.json"
    url = f"https://api.github.com/repos/{GH_USER}/{GH_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    content_b64 = base64.b64encode(json.dumps(arts, ensure_ascii=False, indent=2).encode()).decode()
    # 既存SHAを取得
    sha = ""
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha", "")
    body = {"message": f"Auto: add article {datetime.now().strftime('%Y-%m-%d %H:%M')}", "content": content_b64}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=headers, json=body)
    if r.status_code in (200, 201):
        log(f"✓ GitHub articles.json 更新完了")
    else:
        log(f"✗ GitHub更新失敗: {r.status_code} {r.text[:200]}")

# ── SVG アイキャッチ生成 ─────────────────────────────────
def generate_eyecatch_svg(title, cat, art_id):
    raw = re.sub(r"[【-】「-』].*?[【-】「-』]|\u3010.*?\u3011", "", title).strip()
    short  = raw[:18]
    short2 = raw[18:36]
    idx = abs(int(str(art_id)[-2:])) % 10
    cat_u = cat.upper()

    def t2(x, y, size, color, text, anchor="start", weight="900"):
        return '<text x="{}" y="{}" font-size="{}" font-weight="{}" fill="{}" text-anchor="{}" font-family="Arial,sans-serif">{}</text>'.format(
            x, y, size, weight, color, anchor, text)

    def extra(x, y, size, color):
        if not short2:
            return ""
        return t2(x, y, size, color, short2)

    svg = [
        # 0: 白×左オレンジ縦帯
        '<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="1280" height="670" fill="#fff"/>'
        '<rect x="0" y="0" width="6" height="670" fill="#FF6B00"/>'
        '<circle cx="1000" cy="335" r="220" fill="none" stroke="rgba(255,107,0,.12)" stroke-width="40"/>'
        '<rect x="0" y="600" width="1280" height="70" fill="#1A1A1A"/>'
        + t2(50,140,10,"#FF6B00",cat_u,weight="700") + t2(50,280,60,"#1A1A1A",short) + extra(50,350,60,"#1A1A1A")
        + t2(50,638,13,"#FF6B00","RayPhoneAI",weight="700") + "</svg>",

        # 1: 白×右ハーフブラック
        '<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="1280" height="670" fill="#fff"/>'
        '<rect x="700" y="0" width="580" height="670" fill="#1A1A1A"/>'
        '<rect x="0" y="0" width="1280" height="4" fill="#FF6B00"/>'
        '<rect x="700" y="0" width="4" height="670" fill="#FF6B00"/>'
        + t2(50,140,10,"#FF6B00",cat_u,weight="700") + t2(50,280,60,"#1A1A1A",short) + extra(50,350,60,"#1A1A1A")
        + "</svg>",

        # 2: マガジン白×黒ヘッダー
        '<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="1280" height="670" fill="#F8F8F8"/>'
        '<rect x="0" y="0" width="1280" height="80" fill="#1A1A1A"/>'
        '<rect x="0" y="78" width="1280" height="4" fill="#FF6B00"/>'
        + t2(40,52,13,"#FF6B00","RAYPHONEAI",weight="700")
        + t2(80,270,66,"#1A1A1A",short) + extra(80,345,66,"#1A1A1A")
        + '<rect x="0" y="610" width="1280" height="60" fill="#1A1A1A"/>'
        + t2(640,648,11,"rgba(255,107,0,.8)","AI BLOG — RAYPHONEAI.COM","middle","400")
        + "</svg>",

        # 3: 白×斜め黒帯
        '<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="1280" height="670" fill="#fff"/>'
        '<polygon points="800,0 1280,0 1280,670 480,670" fill="#1A1A1A"/>'
        '<rect x="0" y="0" width="1280" height="4" fill="#FF6B00"/>'
        + t2(60,140,10,"#FF6B00",cat_u,weight="700") + t2(60,280,62,"#1A1A1A",short) + extra(60,352,62,"#1A1A1A")
        + "</svg>",

        # 4: ミニマル白×縦ライン
        '<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="1280" height="670" fill="#fafafa"/>'
        '<rect x="0" y="610" width="1280" height="60" fill="#1A1A1A"/>'
        '<rect x="60" y="180" width="2" height="260" fill="#FF6B00"/>'
        + t2(85,230,10,"#FF6B00",cat_u,weight="700") + t2(85,330,62,"#1A1A1A",short) + extra(85,402,62,"#1A1A1A")
        + t2(640,648,11,"#FF6B00","RAYPHONEAI","middle","700")
        + "</svg>",

        # 5: 白×下部黒バー
        '<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="1280" height="670" fill="#fff"/>'
        '<rect x="0" y="430" width="1280" height="240" fill="#1A1A1A"/>'
        '<rect x="0" y="428" width="1280" height="4" fill="#FF6B00"/>'
        + t2(80,130,10,"#FF6B00",cat_u,weight="700") + t2(80,250,64,"#1A1A1A",short) + extra(80,328,64,"#1A1A1A")
        + t2(80,510,13,"#fff","RayPhoneAI — Rayphone","start","400")
        + "</svg>",

        # 6: 白×左縦ライン
        '<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="1280" height="670" fill="#fff"/>'
        '<rect x="0" y="0" width="4" height="670" fill="#FF6B00"/>'
        '<rect x="0" y="620" width="1280" height="50" fill="#1A1A1A"/>'
        + t2(50,130,10,"#FF6B00",cat_u,weight="700") + t2(50,280,62,"#1A1A1A",short) + extra(50,352,62,"#1A1A1A")
        + t2(640,648,11,"#FF6B00","RAYPHONEAI","middle","700")
        + "</svg>",

        # 7: 白×オレンジ上帯×黒下帯
        '<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="1280" height="670" fill="#fff"/>'
        '<rect x="0" y="0" width="1280" height="100" fill="#FF6B00"/>'
        '<rect x="0" y="580" width="1280" height="90" fill="#1A1A1A"/>'
        + t2(640,62,22,"#fff","RAYPHONEAI","middle")
        + t2(80,270,64,"#1A1A1A",short) + extra(80,345,64,"#1A1A1A")
        + "</svg>",

        # 8: 白×額縁
        '<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="1280" height="670" fill="#fff"/>'
        '<rect x="30" y="30" width="1220" height="610" fill="none" stroke="#1A1A1A" stroke-width="2"/>'
        '<rect x="30" y="30" width="300" height="4" fill="#FF6B00"/>'
        '<rect x="950" y="30" width="300" height="4" fill="#FF6B00"/>'
        + t2(640,180,11,"#FF6B00",cat_u,"middle","700")
        + t2(640,320,62,"#1A1A1A",short,"middle") + (t2(640,392,62,"#1A1A1A",short2,"middle") if short2 else "")
        + t2(640,490,12,"#bbb","RAYPHONEAI","middle","400")
        + "</svg>",

        # 9: 白×三角ブラック
        '<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="1280" height="670" fill="#fff"/>'
        '<polygon points="700,0 1280,0 1280,670" fill="#1A1A1A"/>'
        '<line x1="700" y1="0" x2="1280" y2="670" stroke="#FF6B00" stroke-width="3"/>'
        '<rect x="0" y="0" width="1280" height="4" fill="#FF6B00"/>'
        + t2(60,140,10,"#FF6B00",cat_u,weight="700") + t2(60,290,64,"#1A1A1A",short) + extra(60,364,64,"#1A1A1A")
        + "</svg>",
    ]
    return svg[idx]


# ── メイン処理 ───────────────────────────────────────────
def main():
    log("=== RayPhoneAI 自動投稿開始 ===")

    # カテゴリ決定
    cat_idx = get_cat_index()
    cat = CATEGORIES[cat_idx % len(CATEGORIES)]
    log(f"カテゴリ: {cat} (idx={cat_idx})")

    # ── STEP 1: 記事企画生成 ──────────────────────────────
    log("[1/5] 記事企画を生成中...")
    plan_prompt = f"""あなたはRayphone（プロンプト設計士・商品開発15年・Claude副業月収15万）のブログ「RayPhoneAI」の記事企画担当です。
カテゴリ「{cat}」で、AIを活用した実践的な記事企画を1件作成してください。

JSON形式で出力:
{{"title":"記事タイトル（30字以内）","target":"ターゲット読者","keywords":"SEOキーワード","hook":"読者の悩みや課題"}}

JSONのみ出力。前置き不要。"""
    
    plan_text = gemini(plan_prompt, 500)
    try:
        clean = re.sub(r"```json|```", "", plan_text).strip()
        meta = json.loads(clean)
    except Exception:
        meta = {"title": f"{cat}でAIを活用する方法", "target": "AI初心者", "keywords": f"{cat} AI活用", "hook": "AIをうまく使いたい"}
    log(f"✓ タイトル: {meta['title']}")

    # ── STEP 2: ブログ記事本文生成（3000字）─────────────
    log("[2/5] ブログ記事を生成中（約3000字）...")
    art_prompt = f"""あなたはRayphone（プロンプト設計士・商品開発15年・Claude副業月収15万達成）のブログライターです。

【タイトル】{meta['title']}
【カテゴリ】{cat}
【ターゲット】{meta.get('target','AI初心者のビジネスパーソン')}
【文字数】約3000字
【SEO】{meta.get('keywords', cat+' AI活用')}

【絶対禁止】# ## * ** などのマークダウン記号は使用禁止。見出しは【】形式。箇条書きは「・」。

【構成】
タイトル行
【はじめに】（200字）
【見出し1〜4】（各500〜600字・Claudeのプロンプト例を必ず1つ以上含める）
【まとめ】（CTAでnote: {NOTE_URL}に誘導）

Rayphoneの一人称・体験談必須。合計約3000字。"""

    article_content = strip_preamble(gemini(art_prompt, 4500))
    log(f"✓ 記事生成完了 ({len(article_content)}字)")

    # ── STEP 3: アイキャッチSVG生成 ─────────────────────
    log("[3/5] アイキャッチを生成中...")
    art_id = int(datetime.now().timestamp() * 1000)
    svg_code = generate_eyecatch_svg(meta['title'], cat, art_id)
    log(f"✓ アイキャッチ生成完了 ({len(svg_code)}字)")

    # ── STEP 4: articles.jsonにプッシュ ─────────────────
    log("[4/5] GitHubにarticles.jsonをプッシュ中...")
    art_url = f"{BLOG_URL}/?id={art_id}"
    new_art = {
        "id": art_id,
        "title": meta['title'],
        "cat": cat,
        "content": article_content,
        "svg": svg_code,
        "date": datetime.now().strftime("%Y.%m.%d"),
        "status": "published",
        "url": art_url,
    }

    # 既存のarticles.jsonを取得
    arts = []
    if GH_TOKEN and GH_USER and GH_REPO:
        url = f"https://api.github.com/repos/{GH_USER}/{GH_REPO}/contents/articles.json"
        headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            try:
                existing = base64.b64decode(r.json()["content"]).decode("utf-8")
                arts = json.loads(existing)
            except Exception:
                arts = []
    arts.insert(0, new_art)
    push_articles(arts)
    log(f"✓ ブログURL: {art_url}")

    # ── STEP 5a: note専用コンテンツ生成 & 投稿 ──────────
    log("[5/5] note専用コンテンツを生成中...")
    note_prompt = f"""あなたはRayphoneです。ブログ記事のnote専用コンテンツ（約2,000字）を執筆してください。

【ブログ記事】タイトル：{meta['title']}
カテゴリ：{cat}
ブログURL：{art_url}
本文抜粋：
{article_content[:600]}...

【構成（合計約2,000字）】
はじめに（300字・読者の悩みへの問いかけから）
この記事で解決できること（200字・「・」箇条書き3つ）

▼ ブログ記事はこちら
{art_url}

なぜこの記事が有効なのか——深掘り解説（1,000字）
Rayphoneからの一言（300字・プロンプト設計士Rayphoneとして締める）

【絶対禁止】# * などのマークダウン記号・見出しの【】は禁止。見出しには■を使う。箇条書きは「・」。
【必須】▼ ブログ記事はこちら の下のURLは必ずそのまま出力すること。URLを消すことは絶対禁止。
「はい」「承知」などの前置き・承諾文は一切出力禁止。本文のみ出力すること。"""

    note_content = strip_preamble(gemini(note_prompt, 3500))
    log(f"✓ note用コンテンツ生成完了 ({len(note_content)}字)")

    # note投稿
    log("noteに投稿中...")
    try:
        # note_poster.pyのpost_to_note関数を利用
        sys.path.insert(0, str(Path(__file__).parent))
        from note_poster import post_to_note
        note_title = f"【深掘り】{meta['title']}"
        result = post_to_note(note_title, note_content, svg_code, publish=True, blog_url=art_url)
        if result["ok"]:
            log(f"✓ note投稿完了: {result.get('url','')}")
        else:
            log(f"✗ note投稿失敗: {result.get('message','')}")
    except Exception as e:
        log(f"✗ note投稿エラー: {e}")

    # ── STEP 5b: X投稿 ────────────────────────────────
    if X_AUTO and X_COOKIES_B64:
        log("Xに投稿中...")
        try:
            post_to_x_actions(note_content, art_url)
        except Exception as e:
            log(f"✗ X投稿エラー: {e}")

    # ── カテゴリインデックスを進める ─────────────────────
    next_idx = (cat_idx + 1) % len(CATEGORIES)
    save_cat_index(next_idx)
    log(f"次回カテゴリ: {CATEGORIES[next_idx]} (idx={next_idx})")

    log("=== 完了 ===")


def post_to_x_actions(content, art_url):
    """GitHub Actions環境でX投稿（Cookieファイル方式）"""
    if not X_COOKIES_B64:
        log("X Cookieが未設定のためスキップ")
        return

    import json as _json
    cookie_file = Path("/tmp/x_cookies.json")
    cookie_file.write_bytes(base64.b64decode(X_COOKIES_B64))
    log(f"✓ X Cookieを復元")

    # 概要100字
    cleaned = re.sub(r"■[^\n]*|【[^】]*】|#\S+|https?://\S+", "", content)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    summary = cleaned[:95]
    tweet = f"{summary}\n\n{art_url}"

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        cookies = _json.loads(cookie_file.read_text())
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        if "login" in page.url:
            log("✗ X Cookieが期限切れ。ローカルで再取得してください")
            browser.close()
            return

        # 作成ボタン→テキスト入力→投稿
        for sel in ['[data-testid="SideNav_NewTweet_Button"]', 'a[href="/compose/post"]']:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    time.sleep(2)
                    break
            except Exception:
                continue

        for sel in ['[data-testid="tweetTextarea_0"]', 'div[role="textbox"]']:
            try:
                ed = page.locator(sel).first
                if ed.is_visible(timeout=5000):
                    ed.click()
                    time.sleep(0.5)
                    ed.type(tweet[:270], delay=20)
                    time.sleep(1.5)
                    break
            except Exception:
                continue

        for sel in ['[data-testid="tweetButton"]', 'button:has-text("ポストする")', 'button:has-text("Post")']:
            try:
                btn = page.locator(sel).last
                if btn.is_visible(timeout=3000):
                    btn.click()
                    time.sleep(3)
                    log("✓ X投稿完了")
                    break
            except Exception:
                continue

        browser.close()


if __name__ == "__main__":
    main()
