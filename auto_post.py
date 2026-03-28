"""
auto_post.py — RayPhoneAI GitHub Actions 自動投稿スクリプト
"""
import sys
print("=== auto_post.py 起動 ===", flush=True)
print(f"Python: {sys.version}", flush=True)

try:
    import os, json, time, base64, re, requests
    from pathlib import Path
    from datetime import datetime
    print("✓ 基本ライブラリ読み込み完了", flush=True)
except Exception as e:
    print(f"✗ ライブラリ読み込みエラー: {e}", flush=True)
    sys.exit(1)

# ── 環境変数 ───────────────────────────────────────────────
print("環境変数を読み込み中...", flush=True)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
NOTE_EMAIL     = os.getenv("NOTE_EMAIL", "")
NOTE_PASSWORD  = os.getenv("NOTE_PASSWORD", "")
BLOG_URL       = os.getenv("BLOG_URL", "https://rayphoneai.github.io/ray/").rstrip("/")
NOTE_URL       = os.getenv("NOTE_URL", "https://note.com/rayphone")
NOTE_SHOP_URL  = os.getenv("NOTE_SHOP_URL", NOTE_URL)
NOTE_COOKIES_B64 = os.getenv("NOTE_COOKIES_B64", "")  # noteのCookie（GitHub Secret）
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

print("✓ CATEGORIES定義完了", flush=True)

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

    # note投稿（Playwright headless方式）
    log("noteに投稿中...")
    note_result = {"ok": False, "message": "未試行"}
    try:
        note_result = post_to_note_playwright(
            f"【深掘り】{meta['title']}", note_content, svg_code, art_url
        )
    except Exception as e:
        log(f"✗ note投稿エラー: {e}")
        note_result = {"ok": False, "message": str(e)}

    if note_result["ok"]:
        log(f"✓ note投稿完了: {note_result.get('url','')}")
    else:
        log(f"✗ note投稿失敗: {note_result.get('message','')}")

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
    log(f"✓ X Cookieを復元: {len(base64.b64decode(X_COOKIES_B64))}bytes")

    # 概要を。で終わるよう整形（見出し・冒頭ノイズを除去）
    cleaned = re.sub(r"【[^】]*】|■[^\n]*|#\S+|https?://\S+", "", content)
    cleaned = re.sub(r"(こんにちは[、,]?\s*Rayphone(です)?。?)", "", cleaned)
    cleaned = re.sub(r"^(はじめに|まとめ)\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    _url_part = "\n\n" + art_url
    _max_body = 275 - len(_url_part)
    _pos = cleaned.rfind("。", 0, _max_body)
    if _pos > 0:
        _body = cleaned[:_pos + 1]
    else:
        for _e in ["！", "？"]:
            _p = cleaned.rfind(_e, 0, _max_body)
            if _p > 0:
                _body = cleaned[:_p + 1]
                break
        else:
            _body = cleaned[:_max_body].rstrip()
    tweet = _body + _url_part
    log(f"X投稿文 ({len(tweet)}文字): {tweet[:50]}...")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            cookies = _json.loads(cookie_file.read_text())
            ctx.add_cookies(cookies)
            page = ctx.new_page()

            log("X: x.com/homeにアクセス中...")
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)
            log(f"X: URL = {page.url}")

            if "login" in page.url or "i/flow" in page.url:
                log("✗ X Cookieが期限切れ。export_x_cookies.pyを再実行してください")
                browser.close()
                return

            # 作成ボタンクリック
            btn_clicked = False
            for sel in ['[data-testid="SideNav_NewTweet_Button"]', 'a[href="/compose/post"]', '[aria-label="ポストを作成"]']:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        time.sleep(2)
                        log(f"X: 作成ボタンクリック: {sel}")
                        btn_clicked = True
                        break
                except Exception as e:
                    log(f"X: ボタン試行失敗 {sel}: {e}")
                    continue
            if not btn_clicked:
                log("X: 作成ボタンが見つかりません")
                page.screenshot(path="debug_x_no_button.png")

            # テキストエリアに入力
            typed = False
            for sel in ['[data-testid="tweetTextarea_0"]', 'div[role="textbox"][aria-multiline="true"]']:
                try:
                    ed = page.locator(sel).first
                    if ed.is_visible(timeout=5000):
                        ed.click()
                        time.sleep(1)
                        # keyboard.type()でReactのonChangeを発火
                        page.keyboard.type(tweet, delay=8)
                        time.sleep(2)
                        val = ed.inner_text()
                        log(f"X: テキスト確認 ({len(val)}文字): {val[:30]}...")
                        if len(val) > 5:
                            typed = True
                            log(f"X: テキスト入力完了: {sel}")
                            break
                except Exception as e:
                    log(f"X: テキストエリア試行失敗 {sel}: {e}")
                    continue

            if not typed:
                log("✗ X: テキストエリアが見つかりません")
                page.screenshot(path="debug_x_no_editor.png")
                browser.close()
                return

            # 投稿ボタンが有効化されるまで最大10秒待機
            log("X: 投稿ボタンの有効化を待機中...")
            time.sleep(2)
            for wait_i in range(10):
                try:
                    btn_check = page.locator('[data-testid="tweetButton"]').last
                    if btn_check.is_visible(timeout=1000):
                        is_dis = page.evaluate("() => { const b = document.querySelector('[data-testid=\"tweetButton\"]'); return b ? b.disabled : true; }")
                        if not is_dis:
                            log(f"X: ボタン有効化確認 ({wait_i+1}秒)")
                            break
                except Exception:
                    pass
                time.sleep(1)

            posted = False
            for sel in ['[data-testid="tweetButton"]', '[data-testid="tweetButtonInline"]']:
                try:
                    btn = page.locator(sel).last
                    if not btn.is_visible(timeout=3000):
                        continue
                    log(f"X: ボタン発見: {sel}")
                    # dispatch_eventでReactの合成クリックを発火
                    btn.dispatch_event('click')
                    time.sleep(4)
                    # 投稿後のURL変化やエラーダイアログを確認
                    cur_url = page.url
                    log(f"X: 投稿後URL: {cur_url}")
                    log(f"✓ X投稿完了: {sel}")
                    posted = True
                    break
                except Exception as e:
                    log(f"X: 投稿ボタン試行失敗 {sel}: {str(e)[:100]}")
                    continue

            if not posted:
                # 最終手段1: テキストエリアにフォーカスしてCtrl+Enter
                try:
                    ed = page.locator('[data-testid="tweetTextarea_0"]').first
                    ed.click()
                    time.sleep(0.5)
                    page.keyboard.press("Control+Enter")
                    time.sleep(4)
                    log("✓ X: Ctrl+Enterで送信")
                    posted = True
                except Exception as e:
                    log(f"X: Ctrl+Enter失敗: {e}")

            if not posted:
                # 最終手段2: ボタンにフォーカスしてSpaceキー
                try:
                    btn = page.locator('[data-testid="tweetButton"]').last
                    btn.focus()
                    time.sleep(0.3)
                    page.keyboard.press("Space")
                    time.sleep(4)
                    log("✓ X: Spaceキーで送信")
                    posted = True
                except Exception as e:
                    log(f"X: Spaceキー失敗: {e}")

            if not posted:
                log("✗ X: 投稿ボタンが見つかりません")
                page.screenshot(path="debug_x_no_post_btn.png")

            browser.close()
    except Exception as e:
        log(f"✗ X投稿エラー: {e}")


def post_to_note_playwright(title: str, body: str, svg_code: str, art_url: str) -> dict:
    """Playwright headlessでnoteに投稿（Cookie方式優先）"""
    log("note: 投稿を開始します...")
    try:
        import json as _json
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )

            # Cookie読み込み
            if NOTE_COOKIES_B64:
                try:
                    cookies = _json.loads(base64.b64decode(NOTE_COOKIES_B64).decode())
                    ctx.add_cookies(cookies)
                    log(f"note: Cookie読み込み {len(cookies)}件")
                except Exception as e:
                    log(f"note: Cookie読み込みエラー: {e}")

            page = ctx.new_page()

            # ログイン確認
            page.goto("https://note.com/", wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)
            log(f"note: トップページ URL={page.url}")

            if "/login" in page.url:
                log("note: Cookie無効 → ログインを試みます")
                page.goto("https://note.com/login", wait_until="domcontentloaded", timeout=20000)
                time.sleep(3)
                for sel in ['input[placeholder*="mail"]', 'input[type="email"]']:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=3000):
                            el.type(NOTE_EMAIL, delay=40)
                            break
                    except Exception:
                        continue
                pw_el = page.locator('input[type="password"]').first
                pw_el.wait_for(state="visible", timeout=5000)
                pw_el.type(NOTE_PASSWORD, delay=40)
                time.sleep(0.5)
                for sel in ['button[type="submit"]', 'button:has-text("ログイン")']:
                    try:
                        b = page.locator(sel).first
                        if b.is_visible(timeout=2000):
                            b.click()
                            break
                    except Exception:
                        continue
                for i in range(60):
                    time.sleep(1)
                    if "/login" not in page.url:
                        log(f"note: ログイン成功 ({i+1}秒)")
                        break
                    if i % 10 == 9:
                        log(f"note: ログイン待機 {i+1}秒...")
                else:
                    browser.close()
                    return {"ok": False, "message": "noteログイン失敗（Cookieを再取得してください）"}
            else:
                log("note: Cookie認証成功")

            time.sleep(2)

            # 新規記事ページ
            log("note: 新規記事ページへ...")
            page.goto("https://note.com/notes/new", wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)
            log(f"note: エディタURL={page.url}")

            if "/login" in page.url:
                browser.close()
                return {"ok": False, "message": "noteセッション切れ"}

            # タイトル入力
            for sel in ['[placeholder*="タイトル"]', 'input.title', 'textarea']:
                try:
                    t = page.locator(sel).first
                    if t.is_visible(timeout=3000):
                        t.click()
                        t.type(title, delay=20)
                        log("note: タイトル入力完了")
                        break
                except Exception:
                    continue

            # 本文入力
            page.keyboard.press("Tab")
            time.sleep(0.5)
            try:
                for line in body.split("\n"):
                    page.keyboard.type(line, delay=3)
                    page.keyboard.press("Enter")
                log(f"note: 本文入力完了 ({len(body)}文字)")
            except Exception as e:
                log(f"note: 本文入力エラー {e}")

            time.sleep(2)

            # アイキャッチ（SVG→PNG変換してアップロード）
            if svg_code and '<svg' in svg_code:
                try:
                    import tempfile
                    tmp_svg = tempfile.NamedTemporaryFile(suffix=".svg", delete=False, mode='w', encoding='utf-8')
                    tmp_svg.write(svg_code)
                    tmp_svg.close()
                    png_path = tmp_svg.name.replace(".svg", ".png")
                    # subprocess経由でPNG変換（同一プロセス内のPlaywright二重起動を回避）
                    import subprocess as _sp, sys as _sys
                    svg_script = f"""
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    p = b.new_page()
    p.set_viewport_size({{"width": 1280, "height": 670}})
    p.set_content("<!DOCTYPE html><html><body style='margin:0;padding:0;background:#fff;'>{{}}</body></html>".format(open(sys.argv[1]).read()), wait_until="networkidle")
    import time; time.sleep(0.5)
    p.screenshot(path=sys.argv[2], clip={{"x":0,"y":0,"width":1280,"height":670}})
    b.close()
"""
                    script_path = tmp_svg.name + "_conv.py"
                    with open(script_path, 'w') as sf: sf.write(svg_script)
                    r = _sp.run([_sys.executable, script_path, tmp_svg.name, png_path], capture_output=True, timeout=30)
                    if r.returncode != 0:
                        raise Exception(f"PNG変換失敗: {r.stderr.decode()[:200]}")
                    log("note: SVG→PNG変換完了")
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(1)
                    eyecatch_btn = page.locator('button[class*="sc-131cded0"]').first
                    if eyecatch_btn.count() > 0:
                        eyecatch_btn.scroll_into_view_if_needed()
                        eyecatch_btn.click()
                        time.sleep(2)
                    else:
                        page.evaluate("const b=document.querySelector('button[class*=\"sc-131cded0\"]');if(b){b.scrollIntoView();b.click();}")
                        time.sleep(2)
                    with page.expect_file_chooser(timeout=15000) as fc_info:
                        for sel2 in ['button:has-text("画像をアップロード")', 'li:has-text("画像をアップロード")']:
                            try:
                                b2 = page.locator(sel2).first
                                if b2.is_visible(timeout=2000):
                                    b2.click()
                                    break
                            except Exception:
                                continue
                    fc_info.value.set_files(png_path)
                    time.sleep(4)
                    for _ in range(15):
                        time.sleep(1)
                        try:
                            save_btn = page.locator('button:has-text("保存")').last
                            if save_btn.is_visible(timeout=500) and save_btn.inner_text().strip() == "保存":
                                save_btn.click()
                                time.sleep(3)
                                log("note: アイキャッチ保存完了")
                                break
                        except Exception:
                            continue
                except Exception as e:
                    log(f"note: アイキャッチエラー（スキップ）: {e}")

            time.sleep(2)

            # 公開
            pub_clicked = False
            for sel in ['button:has-text("公開に進む")', 'button:has-text("投稿設定へ")']:
                try:
                    b = page.locator(sel).first
                    if b.is_visible(timeout=5000):
                        b.click()
                        log(f"note: 公開ボタン: {sel}")
                        time.sleep(4)
                        pub_clicked = True
                        break
                except Exception:
                    continue

            if not pub_clicked:
                log("note: 公開ボタンが見つかりません")
                page.screenshot(path="debug_note_publish.png")
                browser.close()
                return {"ok": False, "message": "note公開ボタンが見つかりません"}

            confirm_clicked = False
            for sel in ['button:has-text("投稿する")', 'button:has-text("今すぐ公開")', 'button:has-text("公開する")']:
                try:
                    b = page.locator(sel).first
                    if b.is_visible(timeout=5000):
                        b.click()
                        log(f"note: 投稿確認: {sel}")
                        time.sleep(4)
                        confirm_clicked = True
                        break
                except Exception:
                    continue

            if not confirm_clicked:
                log("note: 投稿確認ボタンが見つかりません")
                page.screenshot(path="debug_note_confirm.png")
                browser.close()
                return {"ok": False, "message": "note投稿確認ボタンが見つかりません"}

            note_url = page.url
            browser.close()
            log(f"note: 最終URL={note_url}")
            return {"ok": True, "message": "note投稿完了", "url": note_url}

    except Exception as e:
        import traceback
        log(f"note: エラー詳細: {traceback.format_exc()[:300]}")
        return {"ok": False, "message": f"note Playwright エラー: {e}"}


def post_to_note_api(title: str, body: str, art_url: str) -> dict:
    """note.com APIで記事を投稿（GitHub Actions向け）"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ja,en;q=0.9",
        "Referer": "https://note.com/",
        "Origin": "https://note.com",
    })

    # 1. ログインページにアクセスしてCSRFトークンを取得
    r = session.get("https://note.com/login", timeout=15)
    log(f"note: ログインページ {r.status_code}")

    # 2. ログイン（新エンドポイント）
    login_data = {"login": NOTE_EMAIL, "password": NOTE_PASSWORD}
    r = session.post(
        "https://note.com/api/v3/users/sign_in",
        json=login_data,
        headers={"Content-Type": "application/json"},
        timeout=15
    )
    log(f"note: ログイン試行 status={r.status_code}")
    if r.status_code not in (200, 201):
        # v2も試す
        r = session.post(
            "https://note.com/api/v2/sessions",
            json={"login": NOTE_EMAIL, "password": NOTE_PASSWORD},
            timeout=15
        )
        log(f"note: v2ログイン試行 status={r.status_code}")
        if r.status_code not in (200, 201):
            return {"ok": False, "message": f"noteログイン失敗: {r.status_code} {r.text[:300]}"}

    log("note API: ログイン成功")

    # 3. 下書き作成
    note_data = {
        "draft": {
            "kind": "text",
            "name": title,
            "body": body,
            "status": "draft",
        }
    }
    r = session.post(
        "https://note.com/api/v1/text_notes",
        json=note_data,
        timeout=30
    )
    log(f"note: 下書き作成 status={r.status_code}")
    if r.status_code not in (200, 201):
        return {"ok": False, "message": f"note下書き作成失敗: {r.status_code} {r.text[:200]}"}

    note_key = r.json().get("data", {}).get("key", "")
    if not note_key:
        return {"ok": False, "message": f"note記事キーが取得できませんでした: {r.text[:200]}"}
    log(f"note API: 下書き作成完了 key={note_key}")

    # 4. 公開
    publish_data = {"draft": {"status": "published"}}
    r = session.put(f"https://note.com/api/v1/text_notes/{note_key}", json=publish_data, timeout=15)
    log(f"note: 公開 status={r.status_code}")
    if r.status_code not in (200, 201):
        return {"ok": False, "message": f"note公開失敗: {r.status_code} {r.text[:200]}"}

    data = r.json().get("data", {})
    urlname = data.get("user", {}).get("urlname", "") or data.get("user", {}).get("nickname", "")
    note_url = f"https://note.com/{urlname}/n/{note_key}" if urlname else f"https://note.com/n/{note_key}"
    log(f"✓ note API投稿完了: {note_url}")
    return {"ok": True, "message": "note投稿完了", "url": note_url}

print("✓ 全関数定義完了。main()を実行します", flush=True)

if __name__ == "__main__":
    main()
