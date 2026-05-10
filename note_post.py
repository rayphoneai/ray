"""
note_post.py — RayPhoneAI note自動投稿スクリプト（v4.0 独立運用版）

【v4.0 変更点】
1. ★ ブログ依存を完全廃止 ★
   - 旧: GitHub の articles.json から最新記事を取得 → ブログ更新が前提だった
   - 新: note_post.py 内で記事を直接生成（CATEGORIES ローテーションで Gemini に書かせる）
2. タイトルサニタイズ追加
   - 【深堀り】【完全版】【保存版】等の先頭括弧装飾を自動除去
   - スキ数低下要因として観測されたため
3. 投稿時刻を 12:00 JST → 21:30 JST に変更（cron 側で対応）
   - AI/副業/ノウハウ系noteのゴールデンタイム狙い
4. articles.json は引き続きアーカイブ＆重複防止用に使用（push_articles で更新）

【v3.1 までの内容】
- 投稿済みチェック（articles.json の note_posted_at フラグ）
- 当日二重投稿ガード
- 投稿成功後、自動的に articles.json を更新してGitHubに反映
- 初期化モード（NOTE_INIT_MODE で過去記事を一括マーク）
- Gemini API 完全対応（claude_xx 引数の互換は維持）
- アイキャッチ画像生成、Playwrightによるnote投稿
"""
import sys
print("=== note_post.py 起動（Gemini版 v4.0 独立運用） ===", flush=True)
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

GEMINI_MODEL          = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_HASHTAG_MODEL  = os.getenv("GEMINI_HASHTAG_MODEL", "gemini-2.5-flash-lite")
CLAUDE_MODEL          = GEMINI_MODEL
CLAUDE_HASHTAG_MODEL  = GEMINI_HASHTAG_MODEL

NOTE_EMAIL       = os.getenv("NOTE_EMAIL", "")
NOTE_PASSWORD    = os.getenv("NOTE_PASSWORD", "")
BLOG_URL         = os.getenv("BLOG_URL", "https://rayphoneai.github.io/ray/").rstrip("/")
NOTE_URL         = os.getenv("NOTE_URL", "https://note.com/rayphone")
NOTE_SHOP_URL    = os.getenv("NOTE_SHOP_URL", "")
NOTE_COOKIES_B64 = os.getenv("NOTE_COOKIES_B64", "")
GH_TOKEN         = os.getenv("GH_TOKEN", "")
GH_USER          = os.getenv("GH_USER", "rayphoneai")
GH_REPO          = os.getenv("GH_REPO", "ray")
HEADLESS         = os.getenv("HEADLESS", "true").lower() == "true"

EYECATCH_MODEL   = os.getenv("EYECATCH_MODEL", "gemini-2.5-flash-image")

# ★ v3.1 追加: 初期化モード
# "" (デフォルト)    : 通常モード
# "mark_latest"     : 最新記事のみ投稿済みフラグ付与して終了
# "mark_all"        : 全記事を投稿済みフラグ付与して終了
NOTE_INIT_MODE   = os.getenv("NOTE_INIT_MODE", "").strip().lower()


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

# ── Gemini API（軽量呼び出し用） ─────────────────────────────
def gemini(prompt, max_tokens=4000):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_HASHTAG_MODEL}:generateContent?key={GEMINI_API_KEY}")
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.9}
    }
    for attempt in range(3):
        try:
            r = requests.post(url, json=body, timeout=120)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                wait = (attempt + 1) * 10
                log(f"Gemini API {r.status_code} → {wait}秒後にリトライ({attempt+1}/3)...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            try:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception:
                raise Exception(f"Gemini応答エラー: {r.text[:300]}")
        except requests.exceptions.HTTPError:
            if attempt < 2:
                wait = (attempt + 1) * 10
                log(f"Gemini HTTPエラー → {wait}秒後にリトライ({attempt+1}/3)...")
                time.sleep(wait)
            else:
                raise

def strip_preamble(text):
    if not text:
        return ""
    lines = text.split("\n")
    for i, l in enumerate(lines[:5]):
        t = l.strip()
        if not t:
            continue
        if re.match(r"^(はい|承知|了解|執筆|Rayphone|---|\/\*|では|かしこまり)", t):
            continue
        return "\n".join(lines[i:]).lstrip("---\n").strip()
    return text.strip()

# =================================================================
# claude(): Gemini API版
# =================================================================
_CLAUDE_SYS = (
    "あなたは日本語ブログ記事のプロフェッショナルライターです。以下を厳守してください:\n"
    "・「はい」「承知しました」などの前置き・承諾文は絶対に出力しない\n"
    "・# ## ### などのマークダウン見出しを出力しない（見出しは ■ を使う）\n"
    "・**太字** *斜体* ``` などのマークダウン装飾を一切使わない\n"
    "・箇条書きは - * ではなく「・」を使う\n"
    "・指定された本文のみを出力する（メタ的な説明・補足を書かない）"
)

def claude(prompt, max_tokens=3500, temperature=0.8, model=None):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 未設定")
    use_model = model or GEMINI_MODEL
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{use_model}:generateContent?key={GEMINI_API_KEY}")

    body = {
        "system_instruction": {"parts": [{"text": _CLAUDE_SYS}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max(int(max_tokens), 1024),
            "temperature": temperature,
        },
    }

    last_err_body = ""
    for attempt in range(3):
        try:
            r = requests.post(url, json=body, timeout=180)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                wait = (attempt + 1) * 10
                log(f"Gemini API {r.status_code} ({use_model}) → {wait}秒後にリトライ({attempt+1}/3)...")
                time.sleep(wait)
                continue
            if not r.ok:
                last_err_body = (r.text or "")[:500]
                log(f"Gemini APIエラー詳細: status={r.status_code} model={use_model} body={last_err_body}")
            r.raise_for_status()
            data = r.json()
            text = ""
            candidates = data.get("candidates", [])
            if candidates:
                cand = candidates[0]
                parts = cand.get("content", {}).get("parts", [])
                for part in parts:
                    if "text" in part:
                        text += part.get("text", "")
                finish_reason = cand.get("finishReason", "")
                if not text and finish_reason and finish_reason != "STOP":
                    raise RuntimeError(f"Gemini生成中断: {finish_reason}")
            return strip_preamble(text.strip())
        except requests.exceptions.HTTPError as e:
            if attempt < 2:
                wait = (attempt + 1) * 10
                log(f"Gemini HTTPエラー: {e} → {wait}秒後にリトライ({attempt+1}/3)...")
                time.sleep(wait)
            else:
                if last_err_body:
                    log(f"Gemini API最終失敗 body={last_err_body}")
                raise
    raise RuntimeError("Gemini API 呼び出しが3回失敗")

# ── GitHub articles.json プッシュ ────────────────────────────
def push_articles(arts):
    if not GH_TOKEN:
        log("GitHub未設定のためスキップ")
        return False
    url = f"https://api.github.com/repos/{GH_USER}/{GH_REPO}/contents/articles.json"
    sha = ""
    r = requests.get(url, headers=_gh_headers())
    if r.status_code == 200:
        sha = r.json().get("sha", "")
    content_b64 = base64.b64encode(json.dumps(arts, ensure_ascii=False, indent=2).encode()).decode()
    body = {"message": f"Auto: note_posted flag {datetime.now().strftime('%Y-%m-%d %H:%M')}", "content": content_b64}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=_gh_headers(), json=body)
    if r.status_code in (200, 201):
        log("✓ GitHub articles.json 更新完了")
        return True
    else:
        log(f"✗ GitHub更新失敗: {r.status_code} {r.text[:200]}")
        return False

# ── アイキャッチ画像生成（Gemini）────────────────────────────
def generate_eyecatch_image(title: str, cat: str) -> bytes | None:
    model = EYECATCH_MODEL
    if model == "svg":
        return None

    prompt = (
        f"High quality professional blog header image, 16:9 ratio. "
        f"Color palette ONLY: white (#FFFFFF), black (#1A1A1A), orange (#FF6B00). "
        f"Style: modern Japanese tech blog, minimal geometric design, "
        f"bold shapes, clean layout with strong visual impact. "
        f"Use large geometric elements: rectangles, lines, circles, triangles. "
        f"No text, no letters, no characters whatsoever. "
        f"Category theme hint: {cat}. "
        f"High contrast, professional, visually striking."
    )

    try:
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
            for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                if "inlineData" in part:
                    img_bytes = base64.b64decode(part["inlineData"]["data"])
                    return img_bytes
            log(f"note: 画像データが見つかりません: {str(data)[:200]}")
            return None

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
                img_bytes = base64.b64decode(images[0]["bytesBase64Encoded"])
                return img_bytes
            log(f"note: Imagen応答に画像なし: {str(data)[:200]}")
            return None
        else:
            log(f"note: 未知のモデル: {model}")
            return None
    except Exception as e:
        log(f"note: 画像生成エラー ({model}): {e}")
        return None


def _overlay_japanese_text(img_bytes: bytes, title: str, cat: str) -> bytes:
    """Pillowで日本語テキストをGemini生成画像に合成する（既存処理・変更なし）"""
    try:
        import io as _io, urllib.request as _ur, tempfile as _tf, os as _os
        from PIL import Image as _Img, ImageDraw as _Draw, ImageFont as _Font

        font_path = "/tmp/NotoSansJP-Bold.ttf"
        if not _os.path.exists(font_path):
            try:
                font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf"
                _ur.urlretrieve(font_url, font_path)
            except Exception:
                try:
                    font_url2 = "https://moji.or.jp/wp-content/ipafont/IPAexfont/IPAexfont00401.zip"
                    import zipfile as _zf
                    zip_path = "/tmp/ipafont.zip"
                    _ur.urlretrieve(font_url2, zip_path)
                    with _zf.ZipFile(zip_path) as z:
                        for n in z.namelist():
                            if n.endswith('.ttf') and 'Gothic' in n:
                                z.extract(n, "/tmp/")
                                _os.rename(f"/tmp/{n}", font_path)
                                break
                except Exception:
                    font_path = None

        img = _Img.open(_io.BytesIO(img_bytes)).convert("RGBA")
        target_w, target_h = 1280, 670
        img = img.resize((target_w, target_h), _Img.LANCZOS)

        draw = _Draw.Draw(img)

        if font_path and _os.path.exists(font_path):
            try:
                font_title = _Font.truetype(font_path, 64)
                font_cat   = _Font.truetype(font_path, 26)
                font_logo  = _Font.truetype(font_path, 22)
            except Exception:
                font_title = font_cat = font_logo = _Font.load_default()
        else:
            font_title = font_cat = font_logo = _Font.load_default()

        overlay = _Img.new("RGBA", (target_w, target_h), (0,0,0,0))
        ov_draw = _Draw.Draw(overlay)
        ov_draw.rectangle([0, 0, 780, target_h], fill=(255,255,255,210))
        img = _Img.alpha_composite(img, overlay)
        draw = _Draw.Draw(img)

        cat_w = len(cat) * 17 + 24
        draw.rectangle([60, 140, 60 + cat_w, 178], fill=(255,107,0,255))
        draw.text((72, 145), cat, fill=(255,255,255,255), font=font_cat)

        title_y = 200
        line_h = 80
        words = [title[i:i+12] for i in range(0, len(title), 12)]
        for j, line in enumerate(words[:3]):
            suffix = "…" if j == 2 and len(title) > 36 else ""
            draw.text((60, title_y + j * line_h), line + suffix, fill=(26,26,26,255), font=font_title)

        draw.text((60, target_h - 45), "RayPhoneAI", fill=(255,107,0,255), font=font_logo)

        img = img.convert("RGB")
        buf = _io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        log("note: 日本語テキストオーバーレイ完了")
        return buf.getvalue()
    except Exception as e:
        log(f"note: テキストオーバーレイエラー: {e} → 元画像を使用")
        return img_bytes


def post_to_note(title: str, body: str, svg_code: str, eyecatch_png: bytes = b"") -> dict:
    """既存のPlaywrightベースのnote投稿処理（変更なし）"""
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

            try:
                import tempfile as _tf, subprocess as _sp
                png = None

                if eyecatch_png:
                    _ptmp = _tf.NamedTemporaryFile(suffix=".png", delete=False)
                    _ptmp.write(eyecatch_png)
                    _ptmp.close()
                    png = _ptmp.name
                    log("note: Gemini生成PNGを使用")
                elif svg_code and "<svg" in svg_code:
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

            try:
                page.keyboard.press("Escape")
                time.sleep(1)
            except Exception:
                pass

            for _ in range(3):
                try:
                    close_btn = page.locator('button:has-text("閉じる")').first
                    if close_btn.is_visible(timeout=1500):
                        close_btn.click()
                        log("note: AIパネルを閉じました")
                        time.sleep(1)
                    else:
                        break
                except Exception:
                    break

            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(2)

            try:
                all_btns = page.locator('button').all_text_contents()
                log(f"note: 公開前ボタン一覧: {[b.strip() for b in all_btns if b.strip()][:10]}")
            except Exception:
                pass

            pub_ok = False
            for sel in ['button:has-text("公開に進む")', 'button:has-text("投稿設定へ")', 'button:has-text("公開設定")']:
                try:
                    b = page.locator(sel).first
                    if b.is_visible(timeout=8000):
                        b.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        b.click(timeout=5000)
                        log(f"note: 公開ボタン: {sel}")
                        pub_ok = True
                        break
                except Exception:
                    pass

            if not pub_ok:
                try:
                    result = page.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll('button'));
                        const pub = btns.find(b => b.textContent.includes('公開に進む') || b.textContent.includes('投稿設定へ'));
                        if (pub) { pub.click(); return pub.textContent.trim(); }
                        return null;
                    }""")
                    if result:
                        log(f"note: 公開ボタン(JS): {result}")
                        pub_ok = True
                        time.sleep(8)
                except Exception as e:
                    log(f"note: JS公開ボタン失敗: {e}")

            if not pub_ok:
                btns = page.locator('button').all_text_contents()
                log(f"note: 公開ボタンなし、現在URL={page.url}")
                log(f"note: ボタン一覧: {[b.strip() for b in btns if b.strip()][:15]}")
                page.screenshot(path="debug_note_pub.png")
                browser.close()
                return {"ok": False, "message": "note公開ボタン見つからず"}

            confirm_ok = False
            for wait_i in range(20):
                time.sleep(1)
                if 'editor.note.com/notes/' in page.url and '/publish' in page.url:
                    pass
                elif 'note.com' in page.url and 'editor' not in page.url:
                    log(f"note: URL変化で投稿完了を検知: {page.url}")
                    confirm_ok = True
                    break
                for sel in ['button:has-text("投稿する")', 'button:has-text("今すぐ公開")', 'button:has-text("公開する")']:
                    try:
                        b = page.locator(sel).first
                        if b.is_visible(timeout=500):
                            b.click()
                            log(f"note: 投稿確認: {sel} ({wait_i+1}秒後)")
                            time.sleep(5)
                            confirm_ok = True
                            break
                    except Exception:
                        pass
                if confirm_ok:
                    break

            if not confirm_ok:
                btns = page.locator('button').all_text_contents()
                log(f"note: 現在URL={page.url}")
                log(f"note: ボタン一覧: {[b.strip() for b in btns if b.strip()][:10]}")
                page.screenshot(path="debug_note_confirm.png")
                browser.close()
                return {"ok": False, "message": "note投稿確認ボタン見つからず"}

            final_url = page.url
            browser.close()
            log(f"note: 最終URL={final_url}")

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


# ── 投稿済み管理ヘルパ（v3.1 新設） ──────────────────────────
def _is_posted(art: dict) -> bool:
    """投稿済みかどうかを判定"""
    return bool(art.get("note_posted_at"))

def _today_already_posted(arts: list) -> bool:
    """本日すでにnote投稿済みの記事があるか"""
    today = datetime.now().strftime("%Y-%m-%d")
    return any((a.get("note_posted_at") or "").startswith(today) for a in arts)

def _find_target_article(arts: list):
    """未投稿の記事を1件取得（先頭=最新から探索）"""
    for i, a in enumerate(arts):
        if not _is_posted(a):
            return i, a
    return None, None


# ── タイトルサニタイズ（v4.0 新設） ─────────────────────────
def sanitize_title(title: str) -> str:
    """note タイトルから先頭の括弧装飾を除去する。

    対象パターン:
      【深堀り】〇〇 → 〇〇
      【完全版】〇〇 → 〇〇
      [保存版] 〇〇 → 〇〇
      『初心者向け』〇〇 → 〇〇
      ★決定版★〇〇 → 〇〇

    観測データ: 【深堀り】を外したらスキ数が増えた → 装飾系は除去方針
    """
    if not title:
        return ""
    t = title.strip()

    # 先頭の括弧装飾を最大3回まで剥がす（複数連結対策）
    pattern = r'^\s*[【\[『「★☆\*][^】\]』」★☆\*]{1,15}[】\]』」★☆\*]\s*[:：\-―ー\s]*'
    for _ in range(3):
        new_t = re.sub(pattern, '', t)
        if new_t == t:
            break
        t = new_t

    # 先頭の余計な記号・空白を除去
    t = t.lstrip('・-—:: 　')
    return t.strip()


# ── 記事生成（v4.0 新設：ブログ非依存） ──────────────────────
def generate_note_article(category: str) -> tuple[str, str]:
    """指定カテゴリで note 記事のタイトルと本文を生成する。

    Returns:
        (title, body) のタプル。title は sanitize_title 済み。
    """
    log(f"記事生成開始: カテゴリ={category}")

    # ── ステップ1: タイトル生成 ──
    title_prompt = f"""カテゴリ「{category}」の note 記事タイトルを1つだけ出力してください。

【厳守事項】
・25〜32字以内
・読者(個人事業主・クリエイター・ライター)が「自分のことだ」と感じる具体性
・実用的・行動につながる表現
・煽り表現禁止(絶対・必ず・全員・100%・誰でも・神・最強・革命)
・先頭に【】[]『』★☆等の括弧装飾を絶対に使わない(【深堀り】【完全版】【保存版】等)
・「:」「|」「→」等の記号使用は最小限
・タイトル本文のみ1行で出力(説明・前置き・引用符・番号付け禁止)"""

    title_raw = claude(title_prompt, max_tokens=200, temperature=0.9)
    # 1行目だけ取り出してサニタイズ
    title = title_raw.split('\n')[0].strip().strip('"').strip("'")
    title = sanitize_title(title)
    if not title or len(title) < 5:
        # フォールバック: カテゴリ名そのままで仮タイトル
        title = f"{category}の現場ノウハウを共有します"
    log(f"✓ タイトル: {title}")

    # ── ステップ2: 本文生成 ──
    body_prompt = f"""タイトル: {title}
カテゴリ: {category}

上記の note 記事の本文を 2000〜2500字で書いてください。
あなたは Rayphone(プロンプト設計士・商品開発15年・Claude副業月収15万達成)です。
読者は個人事業主・クリエイター・ライターで、AIを実務に取り入れたい層です。

■本文構成
■はじめに(約200字) ― 読者が抱えている悩みに寄り添う導入
■本論セクション1(約700字) ― 具体的な事例または失敗談+学び
■本論セクション2(約700字) ― 実践的なノウハウ・手順
■今すぐ試せるアクション(約400字) ― 実際に使えるプロンプト例を1つ以上含める
■Rayphoneからの一言(約200字) ― 締め、読者への問いかけや共感

■禁止事項
・# ## ### マークダウン見出し → 必ず ■ を使う
・**太字** *斜体* ``` 等のマークダウン記号一切禁止
・箇条書きは - * ではなく「・」を使う
・「はい」「承知しました」等の前置き・承諾文禁止
・煽り表現(絶対・必ず・全員・100%・誰でも)を避ける
・本文のみ出力(タイトル・自己紹介・メタ説明は不要)"""

    body = claude(body_prompt, max_tokens=4000, temperature=0.85)
    log(f"✓ 本文生成完了({len(body)}字)")

    return title, body


# ── note専用メイン（v3.1 冪等性対応版） ──────────────────────
def main_note():
    """note自動投稿のメインフロー（v4.0 独立運用版）

    旧版: GitHubの articles.json から最新ブログ記事を取得して投稿
    新版: ブログ非依存。CATEGORIES ローテーションで Gemini に直接記事を書かせて投稿
    """
    import requests as _req

    log("=== note自動投稿開始（Gemini版 v4.0 独立運用） ===")
    log(f"使用モデル: 本文={GEMINI_MODEL} / ハッシュタグ={GEMINI_HASHTAG_MODEL}")
    if NOTE_INIT_MODE:
        log(f"⚠ 初期化モード: NOTE_INIT_MODE={NOTE_INIT_MODE}")

    # ── articles.json を取得（重複防止＆アーカイブ用、なければ空配列）──
    arts = []
    if GH_USER and GH_REPO:
        try:
            r = _req.get(
                f"https://raw.githubusercontent.com/{GH_USER}/{GH_REPO}/main/articles.json",
                timeout=30
            )
            if r.status_code == 200:
                arts = r.json()
                log(f"既存記事アーカイブ: {len(arts)}件")
            else:
                log(f"articles.json 取得スキップ(status={r.status_code}) → 新規アーカイブとして開始")
        except Exception as e:
            log(f"articles.json 取得エラー(無視して続行): {e}")

    # ============================================================
    # ★ 初期化モード（既存記事を投稿済みとしてマークするだけで終了）
    # ============================================================
    if NOTE_INIT_MODE == "mark_latest":
        if arts and not _is_posted(arts[0]):
            arts[0]["note_posted_at"] = datetime.now().isoformat()
            arts[0]["note_url"] = "manually_marked_initial"
            push_articles(arts)
            log(f"✓ 初期化(mark_latest): 最新記事「{arts[0].get('title','')}」をマーク完了")
        else:
            log("マーク対象なし、または最新記事は既にマーク済みです")
        return

    if NOTE_INIT_MODE == "mark_all":
        marked = 0
        now_iso = datetime.now().isoformat()
        for a in arts:
            if not _is_posted(a):
                a["note_posted_at"] = now_iso
                a["note_url"] = "manually_marked_initial"
                marked += 1
        if marked:
            push_articles(arts)
        log(f"✓ 初期化(mark_all): {marked}件をマーク完了")
        return

    # ============================================================
    # ★ 当日二重投稿ガード
    # ============================================================
    if _today_already_posted(arts):
        today = datetime.now().strftime("%Y-%m-%d")
        log(f"⚠ 本日({today})はすでにnote投稿済みのためスキップします")
        return

    # ============================================================
    # ★ カテゴリを決定（cat_index で順番にローテーション）
    # ============================================================
    cat_idx = get_cat_index()
    category = CATEGORIES[cat_idx % len(CATEGORIES)]
    log(f"今回のカテゴリ: {category}（cat_index={cat_idx}）")

    # ============================================================
    # ★ v4.0: 記事を内部で生成（ブログ非依存）
    # ============================================================
    try:
        title, content = generate_note_article(category)
    except Exception as e:
        log(f"✗ 記事生成エラー: {e}")
        log(traceback.format_exc()[:500])
        return

    # 念のため再サニタイズ（generate_note_article 内でも実施済み）
    title = sanitize_title(title)
    log(f"投稿予定タイトル: {title}")
    log(f"本文: {len(content)}字")

    # ============================================================
    # ★ note 投稿用の本文を整形（生成本文をそのまま使用 + ハッシュタグ付与）
    # ============================================================
    note_body = content.strip()

    # ── ハッシュタグ生成 ──
    try:
        hashtag_text = claude(
            f"以下のnote記事に合うハッシュタグを5個生成してください。\n"
            f"タイトル：{title}\nカテゴリ：{category}\n"
            f"本文抜粋：{note_body[:300]}\n\n"
            f"【出力形式】#タグ1 #タグ2 #タグ3 #タグ4 #タグ5\n"
            f"【ルール】#をつける。日本語OK。記事内容に直結した具体的なタグ。"
            f"スペース区切りで1行のみ出力。前置き・説明文禁止。",
            max_tokens=1024,
            temperature=0.5,
            model=GEMINI_HASHTAG_MODEL,
        )
        tags = re.findall(r'#\S+', hashtag_text)[:5]
    except Exception as e:
        log(f"ハッシュタグ生成エラー(フォールバックを使用): {e}")
        tags = []

    if len(tags) >= 3:
        note_body += "\n\n" + " ".join(tags)
        log(f"ハッシュタグ: {' '.join(tags)}")
    else:
        cat_tag = "#" + category.replace(" ", "").replace("xAI", "AI活用")
        fallback = f"{cat_tag} #AI活用 #Claude #副業 #プロンプト設計"
        note_body += f"\n\n{fallback}"
        log(f"ハッシュタグ（フォールバック）: {fallback}")

    log(f"noteコンテンツ最終({len(note_body)}字)")

    # ── アイキャッチ ──
    eyecatch_png = b""
    try:
        png_bytes = generate_eyecatch_image(title, category)
        if png_bytes:
            eyecatch_png = png_bytes
            log(f"✓ アイキャッチ生成完了({len(png_bytes)//1024}KB)")
        else:
            log("アイキャッチ生成失敗 → なしで続行")
    except Exception as e:
        log(f"アイキャッチ生成エラー(なしで続行): {e}")

    # ── note投稿 ──
    note_result = post_to_note(title, note_body, "", eyecatch_png=eyecatch_png)

    # ============================================================
    # ★ 投稿成功時: アーカイブに追加 + cat_index 進行
    # ============================================================
    if note_result["ok"]:
        note_url_posted = note_result.get('url', NOTE_URL)
        new_article = {
            "id": str(int(time.time())),
            "title": title,
            "content": content,
            "cat": category,
            "created_at": datetime.now().isoformat(),
            "note_posted_at": datetime.now().isoformat(),
            "note_url": note_url_posted,
            "source": "note_post.py v4.0 (independent)",
        }
        arts.insert(0, new_article)  # 先頭=最新

        if push_articles(arts):
            log(f"✓ note投稿完了 + アーカイブ追加: {note_url_posted}")
        else:
            log(f"⚠ note投稿は成功したが、アーカイブ保存に失敗")
            log(f"  → 同日の重複ガードが効かない可能性あり。手動で articles.json に追記推奨")

        # 次回用にカテゴリインデックスを進める
        try:
            save_cat_index((cat_idx + 1) % len(CATEGORIES))
            log(f"✓ cat_index 進行: {cat_idx} → {(cat_idx + 1) % len(CATEGORIES)}")
        except Exception as e:
            log(f"⚠ cat_index 更新失敗(無視): {e}")
    else:
        log(f"✗ note投稿失敗: {note_result.get('message','')}")

    log("=== 完了 ===")


print("✓ note_post.py 読み込み完了", flush=True)

if __name__ == "__main__":
    main_note()
