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

# ── Claude API SVGアイキャッチ生成（管理画面と同方式・文字化けなし）──────────
STYLES = {
    'split':    'ノワール×幾何学：黒背景・オレンジの細いライングリッド・左側にタイトル・右に幾何学装飾',
    'namecard': 'マガジン：白背景・極太黒タイポグラフィ・オレンジのアクセントライン',
    'diagonal': 'テック：黒背景・斜め分割でオレンジゾーン・細いグリッドライン',
    'bold':     'シネマティック：暗背景・上下黒帯・中央にタイトル・オレンジのアクセントライン',
    'minimal':  'ブループリント：暗背景・同心円や設計図風装飾・オレンジ細線',
    'frame':    'アーキテクチャ：黒背景・右側に幾何学構造物・左にミニマルテキスト',
    'center':   'サイバーパンク：極暗背景・オレンジのネオン細枠・中央にタイトル',
}

def generate_eyecatch_claude(title: str, cat: str) -> str | None:
    """Claude APIでSVGアイキャッチを生成して返す（管理画面と同方式）"""
    import random
    style_key = random.choice(list(STYLES.keys()))
    style_desc = STYLES[style_key]
    short = title[:18]

    prompt = f"""RayPhoneAIブログのアイキャッチSVG（1280×670）を生成。

タイトル：{short}
カテゴリ：{cat}
スタイル：クール・モダン・スタイリッシュ
レイアウト参考：{style_desc}

viewBox="0 0 1280 670" width="1280" height="670"
カラー：白#fff（メイン背景）・黒#1A1A1A（アクセント）・オレンジ#FF6B00（ポイント）・rgba透明度
font-family="Arial,sans-serif"

【必須デザイン方針】
・タイトルは18文字以内・font-size 52〜66px・font-weight="900"・fill="#1A1A1A"
・グラフィック要素（幾何学・細線・ドット・円など）で余白を豊かに使う
・テキストは小さめ（カテゴリ：font-size 10〜12px・letter-spacing 4〜6）
・"RayPhoneAI"の文字を小さく品よく入れる

<svg...></svg>のみ出力。前置き一切不要。"""

    try:
        result = gemini(prompt, 2000)
        m = re.search(r'<svg[\s\S]*</svg>', result, re.IGNORECASE)
        if m:
            log(f"✓ SVGアイキャッチ生成完了(スタイル:{style_key})")
            return m.group(0)
        log("SVGアイキャッチ: SVGタグ未検出")
        return None
    except Exception as e:
        log(f"SVGアイキャッチ生成エラー: {e}")
        return None


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
# ── note投稿ワークフロートリガー ─────────────────────────────
def trigger_note_workflow():
    """GitHub ActionsのnotePost workflowをdispatchでトリガーする"""
    if not GH_TOKEN or not GH_USER or not GH_REPO:
        log("GitHub設定不足のためnoteワークフロースキップ")
        return
    url = f"https://api.github.com/repos/{GH_USER}/{GH_REPO}/actions/workflows/note_post.yml/dispatches"
    r = requests.post(url, headers=_gh_headers(), json={"ref": "main"}, timeout=30)
    if r.status_code == 204:
        log("✓ note投稿ワークフロー起動完了（数分後にnoteに投稿されます）")
    else:
        log(f"⚠ ワークフロー起動失敗: {r.status_code} {r.text[:100]}")


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

    plan_text = gemini(f"""RayPhoneAI「{cat}」カテゴリ記事企画。JSONのみ出力:
{{"title":"タイトル（25〜40字）","keywords":"KW1 KW2 KW3","target":"ターゲット","hook":"方向性（2〜3文）","catch":"キャッチコピー（15字以内）"}}""", 400)

    try:
        meta = json.loads(re.sub(r"```json|```", "", plan_text).strip())
    except Exception:
        meta = {"title": f"{cat}×AI活用 実践{rand_num}", "target": "AI初心者", "keywords": f"{cat} AI", "hook": "AIをうまく使いたい"}
    log(f"✓ タイトル: {meta['title']}")

    # STEP 2: ブログ記事
    log("[2/5] ブログ記事を生成中（約3000字）...")
    article = strip_preamble(gemini(f"""あなたはRayphone（プロンプト設計士・商品開発15年・Claude副業月収15万達成）のブログ「RayPhoneAI」専属ライターです。

【タイトル】{meta['title']}
【カテゴリ】{cat}
【ターゲット】{meta.get('target','AI初心者のビジネスパーソン')}
【文字数】約3000字
【SEO】{meta.get('keywords', cat+' AI活用')}
【方向性】{meta.get('hook','実践的な内容で')}

【絶対禁止】# ## * ** などのマークダウン記号は一切使用禁止。見出しは■のみ使用（【】禁止）。箇条書きは「・」。URLはそのまま出力。

■構成
タイトル行
■はじめに（200字）
■見出し1〜4（各400〜600字・Claudeのプロンプト例を必ず1つ以上含める）

▼ noteで詳しく解説しています
{NOTE_URL}

■まとめ（上記URLを本文内にそのまま記載）

Rayphoneの一人称・体験談必須。# * 【】絶対禁止。合計3000字前後。""", 4000))
    log(f"✓ 記事生成完了({len(article)}字)")

    # STEP 3: アイキャッチ
    log(f"[3/5] アイキャッチを生成中... (モデル: {EYECATCH_MODEL})")
    art_id      = int(datetime.now().timestamp() * 1000)
    svg_code    = None
    eyecatch_png: bytes = b""

    # Claude API でSVGアイキャッチ生成（ダッシュボードと同方式）
    svg_code = generate_eyecatch_claude(meta['title'], cat)
    if not svg_code:
        svg_code = generate_eyecatch_svg(meta['title'], cat, art_id)
        log(f"✓ アイキャッチSVG生成完了(フォールバック {len(svg_code)}字)")
    else:
        log(f"✓ アイキャッチSVG生成完了({len(svg_code)}字)")
    eyecatch_png = b""
    # STEP 4: GitHub push
    log("[4/5] GitHubにarticles.jsonをプッシュ中...")
    art_url = f"{BLOG_URL}/?id={art_id}"
    new_art = {
        "id": art_id, "title": meta['title'], "cat": cat,
        "content": article, "svg": svg_code,
        "date": datetime.now().strftime("%Y.%m.%d"),
        "status": "published", "url": art_url,
    }

    # 既存記事を確実に取得（失敗しても空にしない）
    arts = []
    fetch_ok = False
    for attempt in range(3):
        try:
            r = requests.get(
                f"https://api.github.com/repos/{GH_USER}/{GH_REPO}/contents/articles.json",
                headers=_gh_headers(), timeout=30)
            if r.status_code == 200:
                arts = json.loads(base64.b64decode(r.json()["content"]).decode())
                fetch_ok = True
                log(f"既存記事取得: {len(arts)}件")
                break
            elif r.status_code == 404:
                log("articles.json未作成 → 新規作成")
                fetch_ok = True
                break
        except Exception as e:
            log(f"既存記事取得失敗(試行{attempt+1}): {e}")
            time.sleep(3)

    if not fetch_ok:
        log("⚠ 既存記事の取得に失敗しました。安全のため投稿を中断します。")
        return

    # 新記事を先頭に追加（同IDが既にあれば更新）
    arts = [a for a in arts if str(a.get("id","")) != str(art_id)]
    arts.insert(0, new_art)
    push_articles(arts)
    log(f"✓ ブログURL: {art_url} (合計{len(arts)}件)")

    # STEP 5: note_post.yml ワークフローをトリガー
    log("[5/5] note投稿ワークフローを起動中...")
    trigger_note_workflow()

    # カテゴリを進める
    next_idx = (cat_idx + 1) % len(CATEGORIES)
    save_cat_index(next_idx)
    log(f"次回カテゴリ: {CATEGORIES[next_idx]} (idx={next_idx})")
    log("=== 完了 ===")


print("✓ 全関数定義完了。main()を実行します", flush=True)

if __name__ == "__main__":
    main()
