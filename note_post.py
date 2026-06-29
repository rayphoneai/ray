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
# .strip() + BOM除去: Windows等でSecretにBOM/空白が混入してもURLを壊さない
DISCORD_WEBHOOK_URL  = os.getenv("DISCORD_WEBHOOK_URL", "").strip().lstrip("﻿").strip()
# note の新規下書きを開く URL（投稿アカウントにログインした状態で開くこと）
NOTE_NEW_URL         = os.getenv("NOTE_NEW_URL", "https://note.com/new").strip().lstrip("﻿").strip()

CATEGORIES = [
    "Claude活用Tips",
    "商品開発xAI",
    "AI執筆・自動化術",
    "副業xAI",
    "プロンプト設計術",
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
            # gemini-2.5系は出力前に「思考」トークンを消費し maxOutputTokens を食う。
            # 創作文には思考不要 & 思考分で本文が途中truncateするのを防ぐため明示OFF。
            "thinkingConfig": {"thinkingBudget": 0},
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
                if text and finish_reason == "MAX_TOKENS":
                    log(f"⚠ 出力がmaxOutputTokensで途中終了（末尾が切れている可能性）: {len(text)}字")
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


def trim_to_last_sentence(text: str) -> str:
    """maxOutputTokensで本文が途中終了したとき、末尾の中途半端な文を落として
    最後の文末（。！？や閉じ括弧）まで戻す。既に文末で終わっていれば素通し。"""
    if not text:
        return text
    t = text.rstrip()
    enders = "。．.！!？?」』）)】］"
    if t and t[-1] in enders:
        return t
    # 末尾から最も近い文末記号を探して、その直後で切る
    last = max((t.rfind(c) for c in enders), default=-1)
    if last == -1:
        return t  # 文末記号が一つも無ければ手を加えない
    return t[:last + 1].rstrip()


# ── 記事生成（Gemini）───────────────────────────────────────
def generate_note_article(category: str) -> tuple[str, str]:
    """指定カテゴリで note 記事のタイトルと本文を生成する。
    Returns: (title, body)。title は sanitize_title 済み。"""
    log(f"記事生成開始: カテゴリ={category}")

    title_prompt = f"""カテゴリ「{category}」の note 記事タイトルを1つだけ出力してください。
記事は、書き手(商品開発を15年やってきた個人事業主)が自分の実体験 ― AIをこう使った、あるいは こうしくじった ― を約1500字で正直に語る内容です。特定業種(士業など)に限定しないこと。

【厳守事項】
・20〜30字以内
・読者(個人事業主・クリエイター・ライター)が「自分のことだ」と感じる具体性
・体験談・失敗談・気づきが伝わる、地に足のついた表現(誇張しない)
・煽り表現禁止(絶対・必ず・全員・100%・誰でも・神・最強・革命)
・一人称を使う場合は「私」(「僕」「俺」は使わない)
・先頭に【】[]『』★☆等の括弧装飾を絶対に使わない(【深堀り】【完全版】【保存版】等)
・「:」「：」「|」「→」等の記号は使わない
・タイトル本文のみ1行で出力(説明・前置き・引用符・番号付け禁止)"""

    title_raw = gemini_text(title_prompt, max_tokens=200, temperature=0.9)
    title = title_raw.split('\n')[0].strip().strip('"').strip("'")
    title = sanitize_title(title)
    if not title or len(title) < 5:
        title = f"{category}で、私がつまずいて分かったこと"
    log(f"✓ タイトル: {title}")

    body_prompt = f"""タイトル: {title}
カテゴリ: {category}

あなたは Rayphone。商品開発を15年やってきた個人事業主で、いまはその現場感覚を土台に AI(Claude等)を毎日の実務で使い倒し、プロンプト設計・AI執筆・自動化を試しています。完璧な専門家ではなく、試行錯誤しながら付き合っている等身大の人です。特定の業種(士業など)に限定せず、ものづくり・商品開発の経験から見えたAIの活かし方を語ります。
読者は個人事業主・クリエイター・ライターで、AIを実務に取り入れたい層です。

上記タイトルの note 記事の本文を 1200〜1500字程度で書いてください。1500字を超えたら冗長です。情報を盛らず、短く濃く。
情報を網羅して詰め込むのではなく、あなた自身の実体験(うまくいった話、あるいは しくじった話)を1つだけ語る感覚で書きます。

■書き方
・具体的な場面から入る ― いつ、何をしようとして、どうなったか。失敗談なら、つまずいた瞬間の戸惑いや、そこで分かったことを正直に書く
・その体験から得た「使い方のコツ」を1つだけ、読者がすぐ試せる形で渡す。可能なら実際に使ったプロンプトを一例だけ載せる
・要点は1つに絞る。教科書的に並べない
・最後は、読者へのやわらかい問いかけか、本音の一言で締める
・全体に体温のある語り口。少し砕けてよい。一人称は必ず「私」(「僕」「俺」は使わない)
・字数は1500字を上限の目安に。書き終える前に長すぎないか見直し、冗長な説明は削る

■禁止事項
・# ## ### マークダウン見出し → 見出しを置くなら ■ を使う(無くてもよい)
・**太字** *斜体* ``` 等のマークダウン記号一切禁止
・箇条書きは - * ではなく「・」を使う
・「はい」「承知しました」等の前置き・承諾文禁止
・煽り表現(絶対・必ず・全員・100%・誰でも・神・最強・革命)を避ける
・「いかがでしたか」「まとめると」のような優等生的な締めを使わない
・本文のみ出力(タイトル・自己紹介・メタ説明は不要)"""

    # flashは日本語の字数指定をほぼ守れない（プロンプトで「900〜1200字」と書いても
    # 1500〜2200字に膨らむ／「縮めて」も効かない）。唯一効くのは maxOutputTokens の
    # ハード上限なので、本文だけトークン枠を絞って物理的に長さを抑える。
    # 枠切れで文が途中終了し得るため、生成後に末尾を最後の文末まで戻して整える。
    body = gemini_text(body_prompt, max_tokens=1500, temperature=0.85)
    body = trim_to_last_sentence(body)
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


# ── Discord通知（PC/スマホ両対応：コードブロックでクリーンにコピー）──────
def _post_text(text: str):
    r = requests.post(DISCORD_WEBHOOK_URL, json={"content": text}, timeout=30)
    r.raise_for_status()


def _post_code_block(text: str):
    """コードブロックで送る。
    PCのDiscordはブロック右上の「コピー」ボタンで、改行を保ったまま中身だけを
    ワンクリックでコピーできる（通常メッセージはPCだとユーザー名・時刻まで
    巻き込み、改行も崩れてベタ詰めになりやすい）。スマホは長押しコピーで従来通り。"""
    safe = text.replace("```", "ˋˋˋ")  # ブロックを壊すバッククォート3連を無害化
    _post_text("```\n" + safe + "\n```")


def _split_for_codeblock(text: str, max_inner: int = 1900) -> list[str]:
    """段落（空行）優先で max_inner 以内のチャンクに分割。
    文の途中で切らない。1段落だけで上限超のときのみ文字単位で強制分割。"""
    chunks: list[str] = []
    cur = ""
    for p in text.split("\n\n"):
        if len(p) > max_inner:                # 1段落が長すぎる → 強制分割
            if cur:
                chunks.append(cur); cur = ""
            for i in range(0, len(p), max_inner):
                chunks.append(p[i:i + max_inner])
            continue
        cand = p if not cur else cur + "\n\n" + p
        if len(cand) <= max_inner:
            cur = cand
        else:
            chunks.append(cur); cur = p
    if cur:
        chunks.append(cur)
    return chunks or [""]


def notify_discord(title: str, body: str, hashtags: list[str], eyecatch_png: bytes):
    """生成した記事を Discord に分割して送る。人間がコピペして note に手動投稿する。"""
    today = date.today().strftime("%Y-%m-%d")
    hashtag_line = " ".join(hashtags)

    # 1. 下書きURL＋アイキャッチ画像＋ガイド
    head = (
        f"【note下書き｜RayPhoneAI】{today}\n"
        f"▼タップで新規下書きを開く\n{NOTE_NEW_URL}\n\n"
        f"この後 “タイトル → 本文 → ハッシュタグ” をコードブロックで送ります。\n"
        f"PCはブロック右上のコピーボタン、スマホは長押しコピーで、\n"
        f"改行を保ったまま note に貼り付けてください。\n"
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

    # 2. タイトル（コードブロック＝コピーがクリーン）
    _post_code_block(title)
    log("✓ Discord通知（2/4 タイトル）")

    # 3. 本文（段落優先で分割し、各チャンクをコードブロックで）
    chunks = _split_for_codeblock(body, 1900)
    for ch in chunks:
        _post_code_block(ch)
    log(f"✓ Discord通知（3/4 本文 {len(chunks)}通）")

    # 4. ハッシュタグ
    if hashtag_line:
        _post_code_block(hashtag_line)
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
