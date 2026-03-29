"""
auto_post.py — RayPhoneAI GitHub Actions 自動投稿スクリプト
"""
import sys
print("=== auto_post.py 起動 ===", flush=True)
print(f"Python: {sys.version}", flush=True)

try:
    import os, json, time, base64, re, random, requests, traceback
    from pathlib import Path
    from datetime import datetime
    print("✓ 基本ライブラリ読み込み完了", flush=True)
except Exception as e:
    print(f"✗ ライブラリ読み込みエラー: {e}", flush=True)
    sys.exit(1)

# ── 環境変数 ────────────────────────────────────────────────
print("環境変数を読み込み中...", flush=True)
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
NOTE_EMAIL       = os.getenv("NOTE_EMAIL", "")
NOTE_PASSWORD    = os.getenv("NOTE_PASSWORD", "")
BLOG_URL         = os.getenv("BLOG_URL", "https://rayphoneai.github.io/ray/").rstrip("/")
NOTE_URL         = os.getenv("NOTE_URL", "https://note.com/rayphone")
NOTE_SHOP_URL    = os.getenv("NOTE_SHOP_URL", "")
NOTE_COOKIES_B64 = os.getenv("NOTE_COOKIES_B64", "")
GH_TOKEN         = os.getenv("GH_TOKEN", "")
GH_USER          = os.getenv("GH_USER", "rayphoneai")
GH_REPO          = os.getenv("GH_REPO", "ray")
X_COOKIES_B64    = os.getenv("X_COOKIES_B64", "")
X_AUTO           = os.getenv("X_AUTO", "false").lower() == "true"
HEADLESS         = os.getenv("HEADLESS", "true").lower() == "true"
# アイキャッチ生成モデル
# svg                       : SVG生成（無料・デフォルト）
# gemini-2.5-flash-image    : Nano Banana（安定版・無料枠500枚/日）
# gemini-3.1-flash-image-preview : Nano Banana 2（最新・高品質）
# imagen-4.0-fast-generate-001   : Imagen 4 Fast（有料・最安$0.02/枚）
# imagen-4.0-generate-001        : Imagen 4 Standard（有料・$0.04/枚）
EYECATCH_MODEL   = os.getenv("EYECATCH_MODEL", "gemini-2.5-flash-image")
# アイキャッチ生成モデル（空=SVG生成、それ以外=Gemini Imagen）
# 選択肢: imagen-3.0-generate-008 / imagen-3.0-fast-generate-001 / gemini-2.0-flash-preview-image-generation
EYECATCH_MODEL   = os.getenv("EYECATCH_MODEL", "imagen-3.0-generate-008")

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

# ── カテゴリインデックス（GitHub永続化） ─────────────────────
def _gh_headers():
    return {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def get_cat_index():
    if GH_TOKEN:
        try:
            r = requests.get(
                f"https://api.github.com/repos/{GH_USER}/{GH_REPO}/contents/cat_index.txt",
                headers=_gh_headers(), timeout=10)
            if r.status_code == 200:
                return int(base64.b64decode(r.json()["content"]).decode().strip())
        except Exception:
            pass
    try:
        return int(Path("cat_index.txt").read_text().strip())
    except Exception:
        return 0

def save_cat_index(idx):
    Path("cat_index.txt").write_text(str(idx))
    if not GH_TOKEN:
        return
    try:
        url = f"https://api.github.com/repos/{GH_USER}/{GH_REPO}/contents/cat_index.txt"
        sha = ""
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        if r.status_code == 200:
            sha = r.json().get("sha", "")
        body = {"message": f"chore: cat_index={idx}", "content": base64.b64encode(str(idx).encode()).decode()}
        if sha:
            body["sha"] = sha
        requests.put(url, json=body, headers=_gh_headers(), timeout=10)
    except Exception:
        pass

# ── Gemini API ───────────────────────────────────────────────
def gemini(prompt, max_tokens=4000):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}")
    r = requests.post(url, json={
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.9}
    }, timeout=120)
    r.raise_for_status()
    try:
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        raise Exception(f"Gemini応答エラー: {r.text[:300]}")

def strip_preamble(text):
    lines = text.split("\n")
    for i, l in enumerate(lines[:5]):
        t = l.strip()
        if not t:
            continue
        if re.match(r"^(はい|承知|了解|執筆|Rayphone|---|\/\*|では|かしこまり)", t):
            continue
        return "\n".join(lines[i:]).lstrip("---\n").strip()
    return text.strip()

# ── GitHub articles.json プッシュ ────────────────────────────
def push_articles(arts):
    if not GH_TOKEN:
        log("GitHub未設定のためスキップ")
        return
    url = f"https://api.github.com/repos/{GH_USER}/{GH_REPO}/contents/articles.json"
    sha = ""
    r = requests.get(url, headers=_gh_headers())
    if r.status_code == 200:
        sha = r.json().get("sha", "")
    content_b64 = base64.b64encode(json.dumps(arts, ensure_ascii=False, indent=2).encode()).decode()
    body = {"message": f"Auto: article {datetime.now().strftime('%Y-%m-%d %H:%M')}", "content": content_b64}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=_gh_headers(), json=body)
    if r.status_code in (200, 201):
        log("✓ GitHub articles.json 更新完了")
    else:
        log(f"✗ GitHub更新失敗: {r.status_code} {r.text[:200]}")

# ── SVG アイキャッチ生成 ─────────────────────────────────────
def generate_eyecatch_svg(title, cat, art_id):
    raw    = re.sub(r"[【】「」『』]", "", title).strip()
    short  = raw[:18]
    short2 = raw[18:36] if len(raw) > 18 else ""
    idx    = abs(int(str(art_id)[-2:])) % 10
    cu     = cat.upper()

    # テキスト生成ヘルパー
    def t(x, y, sz, color, text, anchor="start", weight="900"):
        return (f'<text x="{x}" y="{y}" font-size="{sz}" font-weight="{weight}" '
                f'fill="{color}" text-anchor="{anchor}" '
                f'font-family="Arial,sans-serif">{text}</text>')

    # Y座標が暗い帯(#1A1A1A)に入るか判定 → 入れば白、外ならデフォルト色を返す
    def safe(default_color, y, dark_y_ranges):
        for y0, y1 in dark_y_ranges:
            if y0 <= y <= y1:
                return "#fff"
        return default_color

    # X座標が暗い帯に入るか判定
    def safe_x(default_color, x, dark_x_ranges):
        for x0, x1 in dark_x_ranges:
            if x0 <= x <= x1:
                return "#fff"
        return default_color

    def ex(x, y, sz, color):
        return t(x, y, sz, color, short2) if short2 else ""

    s = [
        # 0: 白×左オレンジ縦帯 / 下部黒帯(y=600-670)
        (lambda dr=[(600,670)]: (
            f'<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="1280" height="670" fill="#fff"/>'
            f'<rect x="0" y="0" width="8" height="670" fill="#FF6B00"/>'
            f'<rect x="0" y="600" width="1280" height="70" fill="#1A1A1A"/>'
            + t(80,120,10,"#FF6B00",cu,weight="700")
            + t(80,260,62,safe("#1A1A1A",260,dr),short)
            + ex(80,332,62,safe("#1A1A1A",332,dr))
            + t(80,638,13,safe("#FF6B00",638,dr),"RayPhoneAI",weight="700")
            + '</svg>'
        ))(),

        # 1: 白左半分×黒右半分 / テキストは白エリア(x<650)
        (lambda dxr=[(650,1280)]: (
            f'<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="1280" height="670" fill="#fff"/>'
            f'<rect x="650" y="0" width="630" height="670" fill="#1A1A1A"/>'
            f'<rect x="0" y="0" width="1280" height="4" fill="#FF6B00"/>'
            f'<rect x="648" y="0" width="4" height="670" fill="#FF6B00"/>'
            + t(50,120,10,"#FF6B00",cu,weight="700")
            + t(50,270,58,safe_x("#1A1A1A",50,dxr),short)
            + ex(50,338,58,safe_x("#1A1A1A",50,dxr))
            + t(870,335,13,"#FF6B00","RayPhoneAI","middle","700")
            + '</svg>'
        ))(),

        # 2: マガジン / 上部黒帯(y=0-90) + 下部黒帯(y=600-670)
        (lambda dr=[(0,90),(600,670)]: (
            f'<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="1280" height="670" fill="#F8F8F8"/>'
            f'<rect x="0" y="0" width="1280" height="90" fill="#1A1A1A"/>'
            f'<rect x="0" y="88" width="1280" height="4" fill="#FF6B00"/>'
            f'<rect x="0" y="600" width="1280" height="70" fill="#1A1A1A"/>'
            + t(640,52,16,safe("#FF6B00",52,dr),"RAYPHONEAI","middle","700")
            + t(80,270,62,safe("#1A1A1A",270,dr),short)
            + ex(80,342,62,safe("#1A1A1A",342,dr))
            + t(640,638,11,safe("rgba(255,107,0,.9)",638,dr),"AI BLOG — RAYPHONEAI.COM","middle","400")
            + '</svg>'
        ))(),

        # 3: 右斜め黒帯 / テキストは左白エリア(x<500)
        (lambda: (
            f'<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="1280" height="670" fill="#fff"/>'
            f'<polygon points="850,0 1280,0 1280,670 550,670" fill="#1A1A1A"/>'
            f'<rect x="0" y="0" width="1280" height="4" fill="#FF6B00"/>'
            + t(60,120,10,"#FF6B00",cu,weight="700")
            + t(60,270,58,"#1A1A1A",short)
            + ex(60,338,58,"#1A1A1A")
            + t(950,200,13,"#FF6B00","RayPhoneAI","middle","700")
            + '</svg>'
        ))(),

        # 4: ミニマル / 下部黒帯(y=620-670)
        (lambda dr=[(620,670)]: (
            f'<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="1280" height="670" fill="#fafafa"/>'
            f'<rect x="0" y="620" width="1280" height="50" fill="#1A1A1A"/>'
            f'<rect x="60" y="160" width="3" height="280" fill="#FF6B00"/>'
            + t(90,210,10,"#FF6B00",cu,weight="700")
            + t(90,320,60,safe("#1A1A1A",320,dr),short)
            + ex(90,392,60,safe("#1A1A1A",392,dr))
            + t(640,648,11,safe("#FF6B00",648,dr),"RAYPHONEAI","middle","700")
            + '</svg>'
        ))(),

        # 5: 白上部×黒下帯(y=460-670)
        (lambda dr=[(460,670)]: (
            f'<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="1280" height="670" fill="#fff"/>'
            f'<rect x="0" y="460" width="1280" height="210" fill="#1A1A1A"/>'
            f'<rect x="0" y="458" width="1280" height="4" fill="#FF6B00"/>'
            + t(80,110,10,"#FF6B00",cu,weight="700")
            + t(80,240,60,safe("#1A1A1A",240,dr),short)
            + ex(80,310,60,safe("#1A1A1A",310,dr))
            + t(80,530,14,safe("#FF6B00",530,dr),"RayPhoneAI × Rayphone","start","400")
            + '</svg>'
        ))(),

        # 6: 白×左縦ライン / 下部黒帯(y=625-670)
        (lambda dr=[(625,670)]: (
            f'<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="1280" height="670" fill="#fff"/>'
            f'<rect x="0" y="0" width="5" height="670" fill="#FF6B00"/>'
            f'<rect x="0" y="625" width="1280" height="45" fill="#1A1A1A"/>'
            + t(60,120,10,"#FF6B00",cu,weight="700")
            + t(60,270,60,safe("#1A1A1A",270,dr),short)
            + ex(60,342,60,safe("#1A1A1A",342,dr))
            + t(640,648,11,safe("#FF6B00",648,dr),"RAYPHONEAI","middle","700")
            + '</svg>'
        ))(),

        # 7: オレンジ上帯(y=0-90)×白中央×黒下帯(y=590-670)
        (lambda dr=[(0,90),(590,670)]: (
            f'<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="1280" height="670" fill="#fff"/>'
            f'<rect x="0" y="0" width="1280" height="90" fill="#FF6B00"/>'
            f'<rect x="0" y="590" width="1280" height="80" fill="#1A1A1A"/>'
            + t(640,55,18,safe("#fff",55,dr),"RAYPHONEAI","middle","700")
            + t(80,230,60,safe("#1A1A1A",230,dr),short)
            + ex(80,302,60,safe("#1A1A1A",302,dr))
            + t(80,636,13,safe("#FF6B00",636,dr),"Rayphone","start","400")
            + '</svg>'
        ))(),

        # 8: 白×額縁 / 暗い領域なし
        (lambda: (
            f'<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="1280" height="670" fill="#fff"/>'
            f'<rect x="30" y="30" width="1220" height="610" fill="none" stroke="#1A1A1A" stroke-width="2"/>'
            f'<rect x="30" y="30" width="280" height="4" fill="#FF6B00"/>'
            f'<rect x="970" y="30" width="280" height="4" fill="#FF6B00"/>'
            + t(640,100,11,"#FF6B00",cu,"middle","700")
            + t(640,300,60,"#1A1A1A",short,"middle")
            + (t(640,372,60,"#1A1A1A",short2,"middle") if short2 else "")
            + t(640,490,12,"#bbb","RAYPHONEAI","middle","400")
            + '</svg>'
        ))(),

        # 9: 白左×黒右三角 / テキストは左白エリア(x<650)
        (lambda: (
            f'<svg viewBox="0 0 1280 670" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="1280" height="670" fill="#fff"/>'
            f'<polygon points="750,0 1280,0 1280,670" fill="#1A1A1A"/>'
            f'<line x1="750" y1="0" x2="1280" y2="670" stroke="#FF6B00" stroke-width="4"/>'
            f'<rect x="0" y="0" width="1280" height="4" fill="#FF6B00"/>'
            + t(60,120,10,"#FF6B00",cu,weight="700")
            + t(60,270,58,"#1A1A1A",short)
            + ex(60,342,58,"#1A1A1A")
            + t(980,200,13,"#FF6B00","RayPhoneAI","middle","700")
            + '</svg>'
        ))(),
    ]
    return s[idx]

# ── Gemini 画像生成アイキャッチ ──────────────────────────────
def generate_eyecatch_image(title: str, cat: str) -> bytes | None:
    """Gemini APIで画像を生成してPNGバイト列を返す。失敗時はNone。"""
    model = EYECATCH_MODEL
    if model == "svg":
        return None

    prompt = (
        f"Create a professional blog eyecatch image (16:9 ratio) for a Japanese AI blog called 'RayPhoneAI'. "
        f"Article title: '{title}'. Category: '{cat}'. "
        f"Design style: modern, minimal, white background with orange (#FF6B00) and dark (#1A1A1A) accents. "
        f"Include the text 'RayPhoneAI' subtly. "
        f"No faces, no people. Clean, professional tech blog aesthetic."
    )

    try:
        # Nano Banana系（gemini-2.5-flash-image, gemini-3.1-flash-image-preview）
        if "gemini" in model:
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model}:generateContent?key={GEMINI_API_KEY}")
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE"]}
            }
            r = requests.post(url, json=body, timeout=60)
            r.raise_for_status()
            data = r.json()
            # 画像データを取得
            for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    img_b64 = part["inlineData"]["data"]
                    return base64.b64decode(img_b64)
            log(f"note: 画像データが見つかりません: {str(data)[:200]}")
            return None

        # Imagen 4系（imagen-4.0-generate-001, imagen-4.0-fast-generate-001）
        elif "imagen" in model:
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model}:generateImages?key={GEMINI_API_KEY}")
            body = {
                "prompt": {"text": prompt},
                "imageGenerationConfig": {
                    "aspectRatio": "16:9",
                    "numberOfImages": 1
                }
            }
            r = requests.post(url, json=body, timeout=60)
            r.raise_for_status()
            data = r.json()
            images = data.get("images", [])
            if images:
                return base64.b64decode(images[0]["bytesBase64Encoded"])
            log(f"note: Imagen応答に画像なし: {str(data)[:200]}")
            return None

        else:
            log(f"note: 未知のモデル: {model}")
            return None

    except Exception as e:
        log(f"note: 画像生成エラー ({model}): {e}")
        return None


# ── X 投稿 ───────────────────────────────────────────────────
def post_to_x(url_to_post: str):
    if not X_COOKIES_B64:
        log("X Cookie未設定のためスキップ")
        return False
    log(f"X投稿URL: {url_to_post}")
    try:
        from playwright.sync_api import sync_playwright
        import json as _j
        cookies = _j.loads(base64.b64decode(X_COOKIES_B64).decode())
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=HEADLESS, args=["--no-sandbox","--disable-dev-shm-usage"])
            ctx = browser.new_context(
                viewport={"width":1280,"height":800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            ctx.add_cookies(cookies)
            page = ctx.new_page()

            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)
            log(f"X: URL={page.url}")
            if "login" in page.url or "i/flow" in page.url:
                log("✗ X Cookie期限切れ")
                browser.close()
                return False

            # 作成ボタン
            for sel in ['[data-testid="SideNav_NewTweet_Button"]']:
                try:
                    b = page.locator(sel).first
                    if b.is_visible(timeout=5000):
                        b.click()
                        time.sleep(3)
                        log(f"X: 作成ボタンクリック")
                        break
                except Exception:
                    pass

            # URL入力
            for sel in ['[data-testid="tweetTextarea_0"]', 'div[role="textbox"]']:
                try:
                    ed = page.locator(sel).first
                    if ed.is_visible(timeout=5000):
                        ed.click()
                        time.sleep(0.5)
                        ed.type(url_to_post, delay=25)
                        time.sleep(2)
                        val = ed.inner_text()
                        log(f"X: 入力確認({len(val)}文字)")
                        break
                except Exception as e:
                    log(f"X: 入力失敗 {e}")

            # ボタン有効化待ち
            for i in range(12):
                try:
                    dis = page.evaluate("()=>{ const b=document.querySelector('[data-testid=\"tweetButton\"]'); return b?(b.disabled||b.getAttribute('aria-disabled')==='true'):true; }")
                    if not dis:
                        log(f"X: ボタン有効化({i+1}秒)")
                        break
                except Exception:
                    pass
                time.sleep(1)

            # 投稿
            ok = False
            for sel in ['[data-testid="tweetButton"]', '[data-testid="tweetButtonInline"]']:
                try:
                    btn = page.locator(sel).last
                    if btn.is_visible(timeout=3000):
                        btn.click(timeout=8000)
                        time.sleep(5)
                        log(f"✓ X投稿完了: {page.url}")
                        ok = True
                        break
                except Exception:
                    pass
            if not ok:
                log("✗ X投稿ボタンクリック失敗")
            browser.close()
            return ok
    except Exception as e:
        log(f"✗ X投稿エラー: {traceback.format_exc()[:300]}")
        return False

# ── note 投稿 ─────────────────────────────────────────────────
def post_to_note(title: str, body: str, svg_code: str, eyecatch_png: bytes = b"") -> dict:
    log("note: 投稿開始...")
    try:
        from playwright.sync_api import sync_playwright
        import json as _j, tempfile, subprocess as _sp
        cookies = _j.loads(base64.b64decode(NOTE_COOKIES_B64).decode()) if NOTE_COOKIES_B64 else []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=HEADLESS,
                args=["--no-sandbox","--disable-dev-shm-usage"]
            )
            ctx = browser.new_context(
                viewport={"width":1280,"height":900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            if cookies:
                ctx.add_cookies(cookies)
                log(f"note: Cookie {len(cookies)}件")

            page = ctx.new_page()

            # ログイン確認
            page.goto("https://note.com/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            log(f"note: トップ URL={page.url}")

            if "/login" in page.url:
                log("note: Cookie無効→パスワードログイン")
                page.goto("https://note.com/login", wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
                for sel in ['input[name="email"]', 'input[type="email"]', 'input[placeholder*="mail"]']:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=3000):
                            el.type(NOTE_EMAIL, delay=40)
                            break
                    except Exception:
                        pass
                for sel in ['input[type="password"]']:
                    try:
                        el = page.locator(sel).first
                        el.wait_for(state="visible", timeout=5000)
                        el.type(NOTE_PASSWORD, delay=40)
                        break
                    except Exception:
                        pass
                for sel in ['button[type="submit"]', 'button:has-text("ログイン")']:
                    try:
                        b = page.locator(sel).first
                        if b.is_visible(timeout=3000):
                            b.click()
                            break
                    except Exception:
                        pass
                for i in range(60):
                    time.sleep(1)
                    if "/login" not in page.url:
                        log(f"note: ログイン成功({i+1}秒)")
                        break
                else:
                    browser.close()
                    return {"ok": False, "message": "noteログイン失敗"}
            else:
                log("note: Cookie認証OK")

            time.sleep(2)

            # 新規記事 - 両方のURLを試す
            editor_url = None
            for try_url in ["https://note.com/notes/new", "https://editor.note.com/new"]:
                try:
                    page.goto(try_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(5)
                    if "/login" not in page.url:
                        editor_url = page.url
                        log(f"note: エディタ={editor_url}")
                        break
                except Exception:
                    continue
            if not editor_url or "/login" in (editor_url or ""):
                browser.close()
                return {"ok": False, "message": "noteエディタ開けず"}

            # タイトル入力
            titled = False
            for sel in ['[placeholder*="タイトル"]', 'input[data-placeholder*="タイトル"]', '.title-input', 'h1[contenteditable]']:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=4000):
                        el.click()
                        el.type(title, delay=20)
                        log("note: タイトル入力完了")
                        titled = True
                        break
                except Exception:
                    pass
            if not titled:
                log("note: タイトル入力失敗（続行）")

            # 本文入力
            page.keyboard.press("Tab")
            time.sleep(1)
            try:
                for line in body.split("\n"):
                    page.keyboard.type(line, delay=3)
                    page.keyboard.press("Enter")
                log(f"note: 本文入力完了({len(body)}文字)")
            except Exception as e:
                log(f"note: 本文入力エラー: {e}")

            time.sleep(2)

            # アイキャッチ（失敗しても投稿は続行）
            try:
                import tempfile as _tf, subprocess as _sp
                png = None

                if eyecatch_png:
                    # Gemini生成PNGを直接使用
                    _ptmp = _tf.NamedTemporaryFile(suffix=".png", delete=False)
                    _ptmp.write(eyecatch_png)
                    _ptmp.close()
                    png = _ptmp.name
                    log("note: Gemini生成PNGを使用")
                elif svg_code and "<svg" in svg_code:
                    # SVG→PNG変換（subprocess経由）
                    tmp = _tf.NamedTemporaryFile(suffix=".svg", delete=False, mode="w", encoding="utf-8")
                    tmp.write(svg_code)
                    tmp.close()
                    png = tmp.name.replace(".svg", ".png")
                    conv = f"""
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b=pw.chromium.launch(headless=True,args=["--no-sandbox"])
    p=b.new_page()
    p.set_viewport_size({{"width":1280,"height":670}})
    import sys,time
    p.set_content(open(sys.argv[1]).read(),wait_until="networkidle")
    time.sleep(0.5)
    p.screenshot(path=sys.argv[2],clip={{"x":0,"y":0,"width":1280,"height":670}})
    b.close()
"""
                    sc = tmp.name + "_c.py"
                    open(sc, "w").write(conv)
                    r = _sp.run([sys.executable, sc, tmp.name, png], capture_output=True, timeout=30)
                    if r.returncode != 0:
                        raise Exception(r.stderr.decode()[:200])
                    log("note: SVG→PNG変換完了")

                if png:
                    # アイキャッチボタンをクリック
                    page.evaluate("window.scrollTo(0,0)")
                    time.sleep(1)
                    ec_clicked = False
                    for ec_sel in ['button[class*="sc-131cded0"]', 'button[aria-label*="アイキャッチ"]']:
                        try:
                            ec_btn = page.locator(ec_sel).first
                            if ec_btn.is_visible(timeout=3000):
                                ec_btn.scroll_into_view_if_needed()
                                ec_btn.click()
                                ec_clicked = True
                                time.sleep(2)
                                break
                        except Exception:
                            pass
                    if not ec_clicked:
                        page.evaluate("const b=document.querySelector('[class*=sc]');if(b){b.scrollIntoView();b.click();}")
                        time.sleep(2)

                    # ファイル選択
                    try:
                        with page.expect_file_chooser(timeout=10000) as fc:
                            for up_sel in ['button:has-text("画像をアップロード")', 'li:has-text("画像をアップロード")']:
                                try:
                                    up = page.locator(up_sel).first
                                    if up.is_visible(timeout=2000):
                                        up.click()
                                        break
                                except Exception:
                                    pass
                        fc.value.set_files(png)
                        time.sleep(5)
                        for _ in range(15):
                            try:
                                sv = page.locator('button:has-text("保存")').last
                                if sv.is_visible(timeout=500) and sv.inner_text().strip() == "保存":
                                    sv.click()
                                    time.sleep(3)
                                    log("note: アイキャッチ保存完了")
                                    break
                            except Exception:
                                pass
                            time.sleep(1)
                    except Exception as e:
                        log(f"note: アイキャッチアップロードスキップ: {e}")
            except Exception as e:
                log(f"note: アイキャッチエラー（スキップ）: {e}")
            time.sleep(3)

            # 公開に進む
            pub_ok = False
            for sel in ['button:has-text("公開に進む")', 'button:has-text("投稿設定へ")', 'button:has-text("公開設定")']:
                try:
                    b = page.locator(sel).first
                    if b.is_visible(timeout=8000):
                        b.click()
                        log(f"note: 公開ボタン: {sel}")
                        time.sleep(5)
                        pub_ok = True
                        break
                except Exception:
                    pass
            if not pub_ok:
                page.screenshot(path="debug_note_pub.png")
                browser.close()
                return {"ok": False, "message": "note公開ボタン見つからず"}

            # 投稿する
            confirm_ok = False
            for sel in ['button:has-text("投稿する")', 'button:has-text("今すぐ公開")', 'button:has-text("公開する")', 'button:has-text("公開")']:
                try:
                    b = page.locator(sel).first
                    if b.is_visible(timeout=10000):
                        b.click()
                        log(f"note: 投稿確認: {sel}")
                        time.sleep(5)
                        confirm_ok = True
                        break
                except Exception:
                    pass
            if not confirm_ok:
                page.screenshot(path="debug_note_confirm.png")
                browser.close()
                return {"ok": False, "message": "note投稿確認ボタン見つからず"}

            final_url = page.url
            browser.close()
            log(f"note: 最終URL={final_url}")

            # publish URLを記事URLに変換
            m = re.search(r'/notes/(n[a-f0-9]+)/', final_url)
            if m:
                urlname = NOTE_URL.rstrip("/").split("/")[-1]
                note_article_url = f"https://note.com/{urlname}/n/{m.group(1)}"
                log(f"note: 記事URL={note_article_url}")
                return {"ok": True, "url": note_article_url}
            return {"ok": True, "url": final_url}

    except Exception as e:
        log(f"note: エラー: {traceback.format_exc()[:400]}")
        return {"ok": False, "message": str(e)}


# ── メイン処理 ────────────────────────────────────────────────
def main():
    log("=== RayPhoneAI 自動投稿開始 ===")

    cat_idx = get_cat_index()
    cat = CATEGORIES[cat_idx % len(CATEGORIES)]
    log(f"カテゴリ: {cat} (idx={cat_idx})")

    # STEP 1: 記事企画
    log("[1/5] 記事企画を生成中...")
    seed_words = ["初心者でも即実践できる","上級者向け深掘り","意外と知らない","失敗から学んだ",
                  "現場で本当に使える","5分でわかる","収益につながる","時短を極める",
                  "プロが教える","実例で解説する","よくある間違いと対策","活用アイデア10選"]
    angles = ["初心者向け入門","実践者向け応用","業務効率化","副業・収益化","時短・自動化",
              "プロンプト設計","失敗事例と改善","ビフォーアフター事例","ステップバイステップ"]
    rand_word  = random.choice(seed_words)
    rand_angle = random.choice(angles)
    rand_num   = random.randint(1000, 9999)
    now_str    = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    plan_text = gemini(f"""あなたはRayphoneブログ「RayPhoneAI」の記事企画担当です。
カテゴリ「{cat}」で実践的な記事企画を1件作成してください。

生成日時: {now_str} / キーワードヒント: {rand_word}×{rand_angle} / シード: {rand_num}
毎回ユニークで具体的なタイトルにしてください。

JSONのみ出力（前置き不要）:
{{"title":"タイトル30字以内","target":"ターゲット読者","keywords":"SEOキーワード","hook":"読者の悩み"}}""", 500)

    try:
        meta = json.loads(re.sub(r"```json|```", "", plan_text).strip())
    except Exception:
        meta = {"title": f"{cat}×AI活用 実践{rand_num}", "target": "AI初心者", "keywords": f"{cat} AI", "hook": "AIをうまく使いたい"}
    log(f"✓ タイトル: {meta['title']}")

    # STEP 2: ブログ記事
    log("[2/5] ブログ記事を生成中（約3000字）...")
    article = strip_preamble(gemini(f"""あなたはRayphoneのブログライターです。

【タイトル】{meta['title']}
【カテゴリ】{cat}
【ターゲット】{meta.get('target','AI初心者のビジネスパーソン')}
【SEO】{meta.get('keywords', cat+' AI活用')}
【文字数】約3000字

【絶対禁止】# ## * ** などのマークダウン記号禁止。見出しは【】形式。箇条書きは「・」。
【構成】タイトル行→【はじめに】200字→【見出し1〜4】各500字（Claudeプロンプト例必須）→【まとめ】note: {NOTE_URL}へCTA

Rayphoneの一人称・体験談必須。""", 4500))
    log(f"✓ 記事生成完了({len(article)}字)")

    # STEP 3: アイキャッチ
    log(f"[3/5] アイキャッチを生成中... (モデル: {EYECATCH_MODEL})")
    art_id      = int(datetime.now().timestamp() * 1000)
    svg_code    = None
    eyecatch_png: bytes = b""

    if EYECATCH_MODEL == "svg":
        svg_code = generate_eyecatch_svg(meta['title'], cat, art_id)
        log(f"✓ アイキャッチSVG生成完了({len(svg_code)}字)")
    else:
        png_bytes = generate_eyecatch_image(meta['title'], cat)
        if png_bytes:
            eyecatch_png = png_bytes
            svg_code = "data:image/png;base64," + base64.b64encode(png_bytes).decode()
            log(f"✓ アイキャッチ画像生成完了({len(png_bytes)//1024}KB)")
        else:
            log("アイキャッチ画像生成失敗 → SVGにフォールバック")
            svg_code = generate_eyecatch_svg(meta['title'], cat, art_id)
            log(f"✓ アイキャッチSVG生成完了({len(svg_code)}字)")

    # STEP 4: GitHub push
    log("[4/5] GitHubにarticles.jsonをプッシュ中...")
    art_url = f"{BLOG_URL}/?id={art_id}"
    new_art = {
        "id": art_id, "title": meta['title'], "cat": cat,
        "content": article, "svg": svg_code,
        "date": datetime.now().strftime("%Y.%m.%d"),
        "status": "published", "url": art_url,
    }
    arts = []
    if GH_TOKEN:
        r = requests.get(
            f"https://api.github.com/repos/{GH_USER}/{GH_REPO}/contents/articles.json",
            headers=_gh_headers())
        if r.status_code == 200:
            try:
                arts = json.loads(base64.b64decode(r.json()["content"]).decode())
            except Exception:
                arts = []
    arts.insert(0, new_art)
    push_articles(arts)
    log(f"✓ ブログURL: {art_url}")

    # STEP 5a: note生成・投稿
    log("[5/5] note専用コンテンツを生成中...")
    note_body = strip_preamble(gemini(f"""あなたはRayphoneです。ブログ記事のnote版（約2000字）を書いてください。

【タイトル】{meta['title']}
【カテゴリ】{cat}
【ブログURL】{art_url}
【本文抜粋】{article[:500]}...

【構成】
■はじめに（300字）
■この記事で解決できること（箇条書き3つ）

▼ ブログ記事はこちら
{art_url}

■深掘り解説（1000字）
■Rayphoneからの一言（300字）

【禁止】# * マークダウン禁止。見出しは■。箇条書きは「・」。前置き・承諾文禁止。""", 3500))

    # URL強制置換（1回のre.subで確実に正しい記事URLに統一）
    note_body = re.sub(
        r'https://rayphoneai\.github\.io/ray(?:/?\?id=\d+|/?)',
        art_url,
        note_body
    )
    if art_url not in note_body:
        note_body += f"\n\n▼ ブログ記事はこちら\n{art_url}\n"
        log("note: URLを末尾に追加")
    m = re.search(r'https://rayphoneai\.github\.io/\S+', note_body)
    log(f"✓ noteコンテンツ生成完了({len(note_body)}字) / 記事URL: {m.group(0) if m else 'なし'}")

    log("noteに投稿中...")
    note_result = post_to_note(f"【深掘り】{meta['title']}", note_body, svg_code, eyecatch_png=eyecatch_png)
    if note_result["ok"]:
        log(f"✓ note投稿完了: {note_result.get('url','')}")
    else:
        log(f"✗ note投稿失敗: {note_result.get('message','')}")

    # STEP 5b: X投稿
    if X_AUTO and X_COOKIES_B64:
        log("Xに投稿中...")
        x_url = note_result.get("url", "") if note_result.get("ok") else art_url
        post_to_x(x_url)

    # カテゴリを進める
    next_idx = (cat_idx + 1) % len(CATEGORIES)
    save_cat_index(next_idx)
    log(f"次回カテゴリ: {CATEGORIES[next_idx]} (idx={next_idx})")
    log("=== 完了 ===")


print("✓ 全関数定義完了。main()を実行します", flush=True)

if __name__ == "__main__":
    main()
