"""
note_post.py — RayPhoneAI note記事ジェネレータ（v5.0 Discord通知方式）

【v5.0 変更点 — note.com自動操作の全廃】
旧(v4.0): Playwright + Cookie注入で note.com を直接自動操作して投稿していた。
          → note.com の DOM 変更のたびにセレクタが壊れて投稿失敗（タイトル欄・
            アイキャッチ・公開確認ボタンが掴めない）。さらに「非公式ツールによる
            直接自動投稿」はアカウント停止リスクの根本原因でもある。
新(v5.0): note.com を一切自動操作しない。祠堂じゅまる(post_article.py)と同方式。
          記事生成(Gemini) → アイキャッチ生成(Gemini) → Discord に通知。
          → 人間が note を開いてコピペで手動投稿する（通知＝人間レビューゲート）。

【廃止したもの】
- Playwright / Chromium / cookie注入 / NOTE_EMAIL / NOTE_PASSWORD / NOTE_COOKIES_B64
- GitHub への articles.json / cat_index.txt 永続化（GH_TOKEN系）
- 投稿済みフラグ・当日二重投稿ガード・初期化モード（手動投稿なので不要）

【維持したもの】
- RayPhoneAI のペルソナ・カテゴリ・記事生成プロンプト（Gemini）
- アイキャッチ画像生成（Gemini / gemini-2.5-flash-image）
- カテゴリは日付順(ordinal)でローテーション（状態ファイル不要・ステートレス）
"""
import sys
print("=== note_post.py 起動（v5.0 Discord通知方式） ===", flush=True)
print(f"Python: {sys.version}", flush=True)

try:
    import os, io, json, time, base64, re, requests, traceback
    from datetime import date, datetime
    print("✓ 基本ライブラリ読み込み完了", flush=True)
except Exception as e:
    print(f"✗ ライブラリ読み込みエラー: {e}", flush=True)
    sys.exit(1)

# ── 環境変数 ────────────────────────────────────────────────
print("環境変数を読み込み中...", flush=True)
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL         = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_HASHTAG_MODEL = os.getenv("GEMINI_HASHTAG_MODEL", "gemini-2.5-flash-lite")
EYECATCH_MODEL       = os.getenv("EYECATCH_MODEL", "gemini-2.5-flash-image")
DISCORD_WEBHOOK_URL  = os.getenv("DISCORD_WEBHOOK_URL", "")
# note の新規下書きを開く URL（投稿アカウントにログインした状態で開くこと）
NOTE_NEW_URL         = os.getenv("NOTE_NEW_URL", "https://note.com/new")

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


def pick_category() -> str:
    """日付(序数)でカテゴリをローテーション。状態ファイル不要のステートレス方式。"""
    return CATEGORIES[date.today().toordinal() % len(CATEGORIES)]


# ── Gemini API ──────────────────────────────────────────────
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


_CLAUDE_SYS = (
    "あなたは日本語ブログ記事のプロフェッショナルライターです。以下を厳守してください:\n"
    "・「はい」「承知しました」などの前置き・承諾文は絶対に出力しない\n"
    "・# ## ### などのマークダウン見出しを出力しない（見出しは ■ を使う）\n"
    "・**太字** *斜体* ``` などのマークダウン装飾を一切使わない\n"
    "・箇条書きは - * ではなく「・」を使う\n"
    "・指定された本文のみを出力する（メタ的な説明・補足を書かない）"
)


def gemini_text(prompt, max_tokens=3500, temperature=0.8, model=None):
    """Gemini テキスト生成。旧 claude() 互換（関数名のみ変更）。"""
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


# ── アイキャッチ画像生成（Gemini）────────────────────────────
def generate_eyecatch_image(title: str, cat: str) -> bytes | None:
    """note アイキャッチを Gemini で生成し、1280x670(≒3:2)の PNG bytes を返す。
    生成に失敗した場合は None（記事の通知は止めない）。"""
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

    raw = None
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
                    raw = base64.b64decode(part["inlineData"]["data"])
                    break
            if raw is None:
                log(f"note: 画像データが見つかりません: {str(data)[:200]}")
                return None
        elif "imagen" in model:
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model}:generateImages?key={GEMINI_API_KEY}")
            body = {
                "prompt": {"text": prompt},
                "imageGenerationConfig": {"aspectRatio": "16:9", "numberOfImages": 1}
            }
            r = requests.post(url, json=body, timeout=60)
            r.raise_for_status()
            data = r.json()
            images = data.get("images", [])
            if not images:
                log(f"note: Imagen応答に画像なし: {str(data)[:200]}")
                return None
            raw = base64.b64decode(images[0]["bytesBase64Encoded"])
        else:
            log(f"note: 未知のモデル: {model}")
            return None
    except Exception as e:
        log(f"note: 画像生成エラー ({model}): {e}")
        return None

    # ── note アイキャッチ向けに 1280x670 へ整形（best-effort）──
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img = ImageOps.fit(img, (1280, 670), method=Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception as e:
        log(f"note: アイキャッチ整形スキップ（元画像を使用）: {e}")
        return raw


# ── タイトルサニタイズ ──────────────────────────────────────
def sanitize_title(title: str) -> str:
    """note タイトルから先頭の括弧装飾（【深堀り】[保存版]『初心者向け』★決定★等）を除去。
    観測データ: 装飾系を外したらスキ数が増えたため除去方針。"""
    if not title:
        return ""
    t = title.strip()
    pattern = r'^\s*[【\[『「★☆\*][^】\]』」★☆\*]{1,15}[】\]』」★☆\*]\s*[:：\-―ー\s]*'
    for _ in range(3):
        new_t = re.sub(pattern, '', t)
        if new_t == t:
            break
        t = new_t
    t = t.lstrip('・-—:： 　')
    return t.strip()


# ── 記事生成（Gemini）───────────────────────────────────────
def generate_note_article(category: str) -> tuple[str, str]:
    """指定カテゴリで note 記事のタイトルと本文を生成する。
    Returns: (title, body)。title は sanitize_title 済み。"""
    log(f"記事生成開始: カテゴリ={category}")

    title_prompt = f"""カテゴリ「{category}」の note 記事タイトルを1つだけ出力してください。

【厳守事項】
・25〜32字以内
・読者(個人事業主・クリエイター・ライター)が「自分のことだ」と感じる具体性
・実用的・行動につながる表現
・煽り表現禁止(絶対・必ず・全員・100%・誰でも・神・最強・革命)
・先頭に【】[]『』★☆等の括弧装飾を絶対に使わない(【深堀り】【完全版】【保存版】等)
・「:」「|」「→」等の記号使用は最小限
・タイトル本文のみ1行で出力(説明・前置き・引用符・番号付け禁止)"""

    title_raw = gemini_text(title_prompt, max_tokens=200, temperature=0.9)
    title = title_raw.split('\n')[0].strip().strip('"').strip("'")
    title = sanitize_title(title)
    if not title or len(title) < 5:
        title = f"{category}の現場ノウハウを共有します"
    log(f"✓ タイトル: {title}")

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

    body = gemini_text(body_prompt, max_tokens=4000, temperature=0.85)
    log(f"✓ 本文生成完了({len(body)}字)")

    return title, body


def generate_hashtags(title: str, category: str, body: str) -> list[str]:
    """記事に合うハッシュタグを5個生成。失敗時はカテゴリベースのフォールバック。"""
    try:
        hashtag_text = gemini_text(
            f"以下のnote記事に合うハッシュタグを5個生成してください。\n"
            f"タイトル：{title}\nカテゴリ：{category}\n"
            f"本文抜粋：{body[:300]}\n\n"
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
        return tags
    cat_tag = "#" + category.replace(" ", "").replace("xAI", "AI活用")
    return [cat_tag, "#AI活用", "#Claude", "#副業", "#プロンプト設計"]


# ── Discord通知（じゅまる方式：スマホで“タイトル→本文→タグ”をコピペ投稿）──
def _post_text(text: str):
    r = requests.post(DISCORD_WEBHOOK_URL, json={"content": text}, timeout=30)
    r.raise_for_status()


def notify_discord(title: str, body: str, hashtags: list[str], eyecatch_png: bytes):
    """生成した記事を Discord に4分割で送る。人間がコピペして note に手動投稿する。"""
    today = date.today().strftime("%Y-%m-%d")
    hashtag_line = " ".join(hashtags)

    # 1. 下書きURL＋アイキャッチ画像＋ガイド
    head = (
        f"【note下書き｜RayPhoneAI】{today}\n"
        f"▼タップで新規下書きを開く\n{NOTE_NEW_URL}\n\n"
        f"この後 “タイトル → 本文 → ハッシュタグ” の順で送ります。\n"
        f"各メッセージを長押しコピー → 下書きに貼り付けてください。\n"
        f"※ note.com の RayPhoneAI アカウントにログインした状態で開くこと。"
    )
    if eyecatch_png:
        files = {"file": ("eyecatch.png", eyecatch_png, "image/png")}
        r = requests.post(DISCORD_WEBHOOK_URL, data={"content": head}, files=files, timeout=30)
    else:
        r = requests.post(DISCORD_WEBHOOK_URL,
                          json={"content": head + "\n（※画像生成に失敗：画像なし）"}, timeout=30)
    r.raise_for_status()
    log("✓ Discord通知（1/4 URL＋画像）")

    # 2. タイトル（中身だけ＝コピーがクリーン）
    _post_text(title)
    log("✓ Discord通知（2/4 タイトル）")

    # 3. 本文（Discordの1900字制限で分割）
    MAX = 1900
    if len(body) <= MAX:
        _post_text(body)
    else:
        rest = body
        while rest:
            _post_text(rest[:MAX])
            rest = rest[MAX:]
    log("✓ Discord通知（3/4 本文）")

    # 4. ハッシュタグ
    if hashtag_line:
        _post_text(hashtag_line)
    log("✓ Discord通知（4/4 ハッシュタグ）")


# ── メイン ──────────────────────────────────────────────────
def main():
    log("=== note記事生成開始（v5.0 Discord通知方式） ===")
    log(f"使用モデル: 本文={GEMINI_MODEL} / ハッシュタグ={GEMINI_HASHTAG_MODEL} / 画像={EYECATCH_MODEL}")

    if not GEMINI_API_KEY:
        log("✗ GEMINI_API_KEY 未設定のため中止")
        sys.exit(1)
    if not DISCORD_WEBHOOK_URL:
        log("✗ DISCORD_WEBHOOK_URL 未設定のため中止")
        sys.exit(1)

    category = pick_category()
    log(f"今回のカテゴリ: {category}")

    # 記事生成
    try:
        title, body = generate_note_article(category)
    except Exception as e:
        log(f"✗ 記事生成エラー: {e}")
        log(traceback.format_exc()[:500])
        sys.exit(1)

    title = sanitize_title(title)
    log(f"投稿予定タイトル: {title}")
    log(f"本文: {len(body)}字")

    # ハッシュタグ
    hashtags = generate_hashtags(title, category, body)
    log(f"ハッシュタグ: {' '.join(hashtags)}")

    # アイキャッチ
    eyecatch_png = b""
    try:
        png_bytes = generate_eyecatch_image(title, category)
        if png_bytes:
            eyecatch_png = png_bytes
            log(f"✓ アイキャッチ生成完了({len(png_bytes)//1024}KB)")
        else:
            log("アイキャッチ生成失敗 → 画像なしで続行")
    except Exception as e:
        log(f"アイキャッチ生成エラー(なしで続行): {e}")

    # Discord通知
    try:
        notify_discord(title, body, hashtags, eyecatch_png)
    except Exception as e:
        log(f"✗ Discord通知エラー: {e}")
        log(traceback.format_exc()[:500])
        sys.exit(1)

    log("=== 完了（Discordで内容を確認 → note へ手動投稿してください） ===")


print("✓ note_post.py 読み込み完了", flush=True)

if __name__ == "__main__":
    main()
