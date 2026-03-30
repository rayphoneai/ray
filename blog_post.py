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
            # 1280×670にアスペクト比を保ちながらクロップリサイズ
            try:
                from PIL import Image as _Img
                import io as _io
                img_orig = _Img.open(_io.BytesIO(png_bytes))
                target_w, target_h = 1280, 670
                orig_w, orig_h = img_orig.size
                target_ratio = target_w / target_h
                orig_ratio = orig_w / orig_h
                if orig_ratio > target_ratio:
                    # 横が余る → 横をクロップ
                    new_w = int(orig_h * target_ratio)
                    left = (orig_w - new_w) // 2
                    img_crop = img_orig.crop((left, 0, left + new_w, orig_h))
                else:
                    # 縦が余る → 縦をクロップ
                    new_h = int(orig_w / target_ratio)
                    top = (orig_h - new_h) // 2
                    img_crop = img_orig.crop((0, top, orig_w, top + new_h))
                img_resized = img_crop.resize((target_w, target_h), _Img.LANCZOS)
                buf = _io.BytesIO()
                img_resized.save(buf, format='PNG')
                resized_bytes = buf.getvalue()
                eyecatch_png = resized_bytes  # note用（正確な1280×670）
                svg_code = "data:image/png;base64," + base64.b64encode(resized_bytes).decode()
                log(f"✓ アイキャッチ画像生成完了({len(resized_bytes)//1024}KB / 1280×670)")
            except Exception:
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

    # カテゴリを進める
    next_idx = (cat_idx + 1) % len(CATEGORIES)
    save_cat_index(next_idx)
    log(f"次回カテゴリ: {CATEGORIES[next_idx]} (idx={next_idx})")
    log("=== 完了 ===")


print("✓ 全関数定義完了。main()を実行します", flush=True)

if __name__ == "__main__":
    main()


print("✓ blog_post.py 読み込み完了", flush=True)

if __name__ == "__main__":
    main()
