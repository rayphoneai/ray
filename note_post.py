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
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.9}
    }
    # 503などの一時エラーに対してリトライ（最大3回）
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

def generate_eyecatch_image(title: str, cat: str) -> bytes | None:
    """Gemini APIで画像を生成してPNGバイト列を返す。失敗時はNone。"""
    model = EYECATCH_MODEL
    if model == "svg":
        return None

    # テキストなし・高品質デザイン画像のみ生成
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
                    img_bytes = base64.b64decode(part["inlineData"]["data"])
                    return img_bytes
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
    """Pillowで日本語テキストをGemini生成画像に合成する"""
    try:
        import io as _io, urllib.request as _ur, tempfile as _tf, os as _os
        from PIL import Image as _Img, ImageDraw as _Draw, ImageFont as _Font

        # Noto Sans JPフォントをダウンロード（なければシステムフォントを使用）
        font_path = "/tmp/NotoSansJP-Bold.ttf"
        if not _os.path.exists(font_path):
            try:
                font_url = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf"
                _ur.urlretrieve(font_url, font_path)
            except Exception:
                # フォールバック: IPAゴシック
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
        # 1280x670にリサイズ
        target_w, target_h = 1280, 670
        img = img.resize((target_w, target_h), _Img.LANCZOS)

        draw = _Draw.Draw(img)

        # フォントサイズ設定
        if font_path and _os.path.exists(font_path):
            try:
                font_title = _Font.truetype(font_path, 64)
                font_cat   = _Font.truetype(font_path, 26)
                font_logo  = _Font.truetype(font_path, 22)
            except Exception:
                font_title = font_cat = font_logo = _Font.load_default()
        else:
            font_title = font_cat = font_logo = _Font.load_default()

        # 半透明白背景をテキストエリアに追加（左側約60%）
        overlay = _Img.new("RGBA", (target_w, target_h), (0,0,0,0))
        ov_draw = _Draw.Draw(overlay)
        ov_draw.rectangle([0, 0, 780, target_h], fill=(255,255,255,210))
        img = _Img.alpha_composite(img, overlay)
        draw = _Draw.Draw(img)

        # カテゴリラベル（オレンジ背景）
        cat_w = len(cat) * 17 + 24
        draw.rectangle([60, 140, 60 + cat_w, 178], fill=(255,107,0,255))
        draw.text((72, 145), cat, fill=(255,255,255,255), font=font_cat)

        # タイトル（12文字で改行、最大3行）
        title_y = 200
        line_h = 80
        words = [title[i:i+12] for i in range(0, len(title), 12)]
        for j, line in enumerate(words[:3]):
            suffix = "…" if j == 2 and len(title) > 36 else ""
            draw.text((60, title_y + j * line_h), line + suffix, fill=(26,26,26,255), font=font_title)

        # RayPhoneAI ロゴ（左下）
        draw.text((60, target_h - 45), "RayPhoneAI", fill=(255,107,0,255), font=font_logo)

        # PNG出力
        img = img.convert("RGB")
        buf = _io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        log("note: 日本語テキストオーバーレイ完了")
        return buf.getvalue()

    except Exception as e:
        log(f"note: テキストオーバーレイエラー: {e} → 元画像を使用")
        return img_bytes



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

            # Escapeキーで全パネル・ダイアログを閉じる
            try:
                page.keyboard.press("Escape")
                time.sleep(1)
            except Exception:
                pass

            # AIアシスタントパネルが開いていれば閉じる
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

            # スクロールを一番上に戻してから公開ボタンを探す
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(2)

            # 現在のボタン一覧をログに出してデバッグ
            try:
                all_btns = page.locator('button').all_text_contents()
                log(f"note: 公開前ボタン一覧: {[b.strip() for b in all_btns if b.strip()][:10]}")
            except Exception:
                pass

            # 公開に進む（見つからない場合はJSでも試みる）
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
                # JSで直接クリックを試みる
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

            # 最大20秒待って「投稿する」モーダルを探す
            confirm_ok = False
            for wait_i in range(20):
                time.sleep(1)
                # URLが変わっていれば既に投稿完了
                if 'editor.note.com/notes/' in page.url and '/publish' in page.url:
                    # publish URLにいる → 投稿ボタンを探す
                    pass
                elif 'note.com' in page.url and 'editor' not in page.url:
                    # 記事ページに遷移済み → 投稿完了
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

# ── X（@rayphone_com）にnoteリンク付きで投稿 ─────────────────
def post_x_with_note_link(title, cat, note_url, blog_url):
    """note投稿完了後、XにnoteリンクつきのCTA投稿をする"""
    import base64 as _b64, json as _json, time as _time

    log("X投稿中...")
    try:
        # ツイート本文を生成（140字以内に収める）
        short_title = title[:24] + "..." if len(title) > 24 else title
        tweet_lines = [
            f"【新着note】{short_title}",
            "",
            f"#{cat.replace(' ', '').replace('xAI','AI活用')} #Claude活用 #AI副業",
            "",
            f"▼ noteで読む",
            note_url,
        ]
        tweet = "\n".join(tweet_lines)

        # Cookie認証でX GraphQL API投稿
        cookies_json = _b64.b64decode(X_COOKIES_B64).decode("utf-8")
        cookies = _json.loads(cookies_json)

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = browser.new_context()
            ctx.add_cookies(cookies)
            page = ctx.new_page()
            # networkidleではなくdomcontentloadedで待機（X.comは非同期が多くタイムアウトしやすい）
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
            _time.sleep(4)

            # ツイート入力欄
            page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=20000)
            page.click('[data-testid="tweetTextarea_0"]')
            page.keyboard.type(tweet)
            _time.sleep(1)

            # 投稿ボタン
            page.click('[data-testid="tweetButtonInline"]')
            _time.sleep(3)
            browser.close()
        log(f"✓ X投稿完了: {short_title}")
    except Exception as e:
        log(f"⚠ X投稿失敗（続行）: {e}")


# ── note専用メイン ─────────────────────────────────────────
def main_note():
    """GitHubの最新記事をnoteに自動投稿する"""
    import requests as _req

    log("=== note自動投稿開始 ===")

    # GitHubから最新のarticles.jsonを取得
    arts = []
    if GH_USER and GH_REPO:
        try:
            r = _req.get(
                f"https://raw.githubusercontent.com/{GH_USER}/{GH_REPO}/main/articles.json",
                timeout=30
            )
            if r.status_code == 200:
                arts = r.json()
                log(f"記事取得: {len(arts)}件")
        except Exception as e:
            log(f"記事取得エラー: {e}")

    if not arts:
        log("投稿対象の記事が見つかりません")
        return

    art = arts[0]
    title   = art.get("title", "")
    content = art.get("content", "")
    svg     = art.get("svg", "")
    cat     = art.get("cat", "AI活用")
    art_url = art.get("url", "") or f"{BLOG_URL}/?id={art.get('id','')}"

    log(f"投稿対象: {title}")
    log(f"ブログ本文: {len(content)}字")

    # ブログ全文を使ってnote深掘り版を生成
    note_body = strip_preamble(gemini(f"""あなたはRayphone（プロンプト設計士・商品開発15年・Claude副業月収15万達成）です。
下記のブログ記事を元に、noteで深掘り解説する記事（約2000字）を書いてください。

【ブログタイトル】{title}
【カテゴリ】{cat}
【ブログURL】{art_url}
【ブログ本文（全文）】
{content}

■構成
■はじめに（200字）―ブログの要点をnote読者向けに噛み砕く
■ブログでは語れなかった深掘り（800字）―実体験・失敗談・応用例を追加
■読者が今すぐ試せるアクション（400字）―具体的なプロンプト例を1つ以上
■Rayphoneからの一言（200字）―締め

▼ ブログ記事はこちら（必ず本文中にそのまま記載）
{art_url}

【禁止】# * マークダウン記号禁止。見出しは■。箇条書きは「・」。前置き・承諾文禁止。
ブログと同じ情報を繰り返すのではなく、必ず「ブログの続き・深掘り」として書くこと。""", 3500))

    if art_url not in note_body:
        note_body += f"\n\n▼ ブログ記事はこちら\n{art_url}\n"

    # 記事に合ったハッシュタグを5個生成（本文も渡して精度を上げる）
    hashtag_text = strip_preamble(gemini(
        f"以下のnote記事に合うハッシュタグを5個生成してください。\n"
        f"タイトル：{title}\nカテゴリ：{cat}\n"
        f"本文抜粋：{note_body[:300]}\n\n"
        f"【出力形式】#タグ1 #タグ2 #タグ3 #タグ4 #タグ5\n"
        f"【ルール】#をつける。日本語OK。記事内容に直結した具体的なタグ。"
        f"スペース区切りで1行のみ出力。前置き・説明文禁止。", 80
    ))
    tags = re.findall(r'#\S+', hashtag_text)[:5]
    if len(tags) >= 3:
        note_body += "\n\n" + " ".join(tags)
        log(f"ハッシュタグ: {' '.join(tags)}")
    else:
        # フォールバック
        cat_tag = "#" + cat.replace(" ", "").replace("xAI", "AI活用")
        fallback = f"{cat_tag} #AI活用 #Claude #副業 #プロンプト設計"
        note_body += f"\n\n{fallback}"
        log(f"ハッシュタグ（フォールバック）: {fallback}")

    log(f"noteコンテンツ生成完了({len(note_body)}字)")

    # アイキャッチPNG生成
    eyecatch_png = b""
    png_bytes = generate_eyecatch_image(title, art.get("cat", "AI活用"))
    if png_bytes:
        eyecatch_png = png_bytes
        log(f"✓ アイキャッチ生成完了({len(png_bytes)//1024}KB)")
    else:
        log("アイキャッチ生成失敗 → SVGで代用")

    # note投稿
    note_result = post_to_note(f"【深掘り】{title}", note_body, svg, eyecatch_png=eyecatch_png)
    if note_result["ok"]:
        note_url_posted = note_result.get('url', NOTE_URL)
        log(f"✓ note投稿完了: {note_url_posted}")

        # X（@rayphone_com）にnoteリンク付きでツイート
        if X_AUTO and X_COOKIES_B64:
            post_x_with_note_link(title, cat, note_url_posted, art_url)
        else:
            log("X自動投稿はスキップ（X_AUTO=false または クッキー未設定）")
    else:
        log(f"✗ note投稿失敗: {note_result.get('message','')}")

    log("=== 完了 ===")


print("✓ note_post.py 読み込み完了", flush=True)

if __name__ == "__main__":
    main_note()
