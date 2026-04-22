"""
auto_post.py  ―  RayPhoneAI 自動投稿スクリプト（Playwright版・Claude記事生成対応）

フロー:
  1. 管理画面を開く
  2. パスワードでログイン & API キー類を localStorage にセット
  3. 自動入力ボタン → Claude で企画JSON生成（10秒待機）
  4. 記事生成ボタン → Claude で本文生成（最大150秒待機）
  5. noteに投稿ボタン → GitHub push + note_post.yml トリガー
"""

import os
import sys
import time
from datetime import datetime

print("=== auto_post.py 起動 ===", flush=True)
print(f"Python: {sys.version}", flush=True)

# ── 環境変数 ─────────────────────────────────────────────────
ADMIN_URL         = os.getenv("ADMIN_URL", "")
ADMIN_PASSWORD    = os.getenv("ADMIN_PASSWORD", "rayphone2025")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
GH_TOKEN          = os.getenv("GH_TOKEN", "")
GH_USER           = os.getenv("GH_USER", "")
GH_REPO           = os.getenv("GH_REPO", "")
BLOG_URL          = os.getenv("BLOG_URL", "")
NOTE_URL          = os.getenv("NOTE_URL", "")
HEADLESS          = os.getenv("HEADLESS", "true").lower() != "false"

if not ADMIN_URL and GH_USER and GH_REPO:
    ADMIN_URL = f"https://{GH_USER}.github.io/{GH_REPO}/admin.html"

print(f"ADMIN_URL: {ADMIN_URL}", flush=True)
print(f"HEADLESS: {HEADLESS}", flush=True)
print(f"CLAUDE_MODEL: {CLAUDE_MODEL}", flush=True)
print(f"ANTHROPIC_API_KEY: {'設定あり (len=' + str(len(ANTHROPIC_API_KEY)) + ', prefix=' + ANTHROPIC_API_KEY[:10] + '...)' if ANTHROPIC_API_KEY else '未設定'}", flush=True)
print(f"GEMINI_API_KEY: {'設定あり' if GEMINI_API_KEY else '未設定'}", flush=True)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def dump_art_log(page, label=""):
    """admin.html の art-log の中身を Python ログに出力（デバッグ用）"""
    try:
        txt = page.evaluate("""() => {
            var el = document.getElementById('art-log');
            return el ? el.textContent : '(art-log要素なし)';
        }""")
        log(f"─── admin.html art-log {label} ───")
        for line in (txt or "").strip().split("\n")[-30:]:
            if line.strip():
                log(f"  │ {line}")
        log(f"─── end art-log ───")
    except Exception as e:
        log(f"art-log取得エラー: {e}")


def main():
    if not ADMIN_URL:
        log("✗ ADMIN_URL または GH_USER/GH_REPO が未設定です")
        sys.exit(1)
    if not ANTHROPIC_API_KEY:
        log("✗ ANTHROPIC_API_KEY が未設定です（記事生成に必須）")
        sys.exit(1)
    if not GEMINI_API_KEY:
        log("⚠ GEMINI_API_KEY 未設定（admin.html はSVGアイキャッチなので動作は可）")

    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        # ── ブラウザ側のログ・エラーをすべてPython側に中継 ─────
        page.on("console", lambda m: log(f"[browser:{m.type}] {m.text[:300]}"))
        page.on("pageerror", lambda e: log(f"[browser:pageerror] {str(e)[:300]}"))
        page.on("requestfailed", lambda r: log(
            f"[browser:reqfail] {r.method} {r.url[:120]} → {r.failure}"
        ))
        # Anthropic API呼び出しの結果を捕捉
        def on_response(resp):
            try:
                if "api.anthropic.com" in resp.url or "generativelanguage.googleapis" in resp.url:
                    log(f"[browser:api] {resp.status} {resp.url[:120]}")
                    if resp.status >= 400:
                        try:
                            body = resp.text()[:500]
                            log(f"  │ response body: {body}")
                        except Exception:
                            pass
            except Exception:
                pass
        page.on("response", on_response)

        # ── STEP 1 ─────────────────────────────────────────────
        log(f"管理画面を開いています: {ADMIN_URL}")
        page.goto(ADMIN_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # ── STEP 2 ─────────────────────────────────────────────
        pw_gate = page.query_selector("#pw-gate")
        if pw_gate and pw_gate.is_visible():
            log("パスワードを入力中...")
            page.fill("#gate-pw", ADMIN_PASSWORD)
            page.keyboard.press("Enter")
            time.sleep(1)
            log("✓ ログイン完了")
        else:
            log("✓ 認証済み（スキップ）")

        # ── STEP 2b: APIキー類 & 設定を localStorage に投入 ────
        log("APIキーとGitHub設定をlocalStorageにセット中...")
        # JSON.stringify で安全にエスケープ
        import json as _json
        cfg_js = """(params) => {
            localStorage.setItem('rp_key',          params.geminiKey || '');
            localStorage.setItem('rp_claude_key',   params.claudeKey || '');
            localStorage.setItem('rp_claude_model', params.claudeModel || 'claude-sonnet-4-5');
            localStorage.setItem('rp_admin_auth',   params.adminPw || '');
            var cfg = {};
            try { cfg = JSON.parse(localStorage.getItem('rp_cfg') || '{}'); } catch(e) {}
            cfg.ghToken = params.ghToken || '';
            cfg.ghUser  = params.ghUser  || '';
            cfg.ghRepo  = params.ghRepo  || '';
            cfg.blogUrl = params.blogUrl || '';
            cfg.noteUrl = params.noteUrl || '';
            localStorage.setItem('rp_cfg', JSON.stringify(cfg));
            return {
                rp_key_len: (localStorage.getItem('rp_key')||'').length,
                rp_claude_key_len: (localStorage.getItem('rp_claude_key')||'').length,
                rp_claude_model: localStorage.getItem('rp_claude_model')
            };
        }"""
        params = {
            "geminiKey":   GEMINI_API_KEY,
            "claudeKey":   ANTHROPIC_API_KEY,
            "claudeModel": CLAUDE_MODEL,
            "adminPw":     ADMIN_PASSWORD,
            "ghToken":     GH_TOKEN,
            "ghUser":      GH_USER,
            "ghRepo":      GH_REPO,
            "blogUrl":     BLOG_URL,
            "noteUrl":     NOTE_URL,
        }
        ls_check = page.evaluate(cfg_js, params)
        log(f"localStorage状態: {ls_check}")

        # リロードして設定を反映
        page.reload(wait_until="networkidle", timeout=30000)
        time.sleep(2)
        page.evaluate("""() => {
            var gate = document.getElementById('pw-gate');
            if (gate) gate.style.display = 'none';
        }""")
        time.sleep(1)

        # リロード後、K.claudeKey が読めているか確認
        kcheck = page.evaluate("""() => ({
            K_claudeKey_len: (window.K && window.K.claudeKey || '').length,
            K_apiKey_len:    (window.K && window.K.apiKey    || '').length,
            model:           localStorage.getItem('rp_claude_model')
        })""")
        log(f"admin.html内部状態: {kcheck}")
        log("✓ 管理画面ロード完了")

        # ── STEP 3: 自動入力ボタン ─────────────────────────────
        log("【STEP 3】自動入力ボタンをクリック...")
        page.wait_for_selector("#art-autofill-btn", state="visible", timeout=15000)
        page.click("#art-autofill-btn")
        log("Claude応答を待機中（最大30秒）...")

        # タイトルが埋まるまでポーリング（最大30秒）
        filled = False
        for i in range(30):
            time.sleep(1)
            t = page.input_value("#art-title")
            if t and t.strip():
                log(f"✓ タイトル取得({i+1}s後): {t}")
                filled = True
                break
        if not filled:
            log("⚠ 自動入力がタイムアウト（タイトル空）")
            dump_art_log(page, "（自動入力失敗）")

        # ── STEP 4: 記事生成ボタン ─────────────────────────────
        log("【STEP 4】記事を生成するボタンをクリック...")
        page.click("#art-gen-btn")
        log("Claude本文生成を待機中（最大180秒）...")
        try:
            page.wait_for_selector("#art-out.show", timeout=180000)
            log("✓ 記事生成完了（art-out表示）")
        except PWTimeout:
            log("⚠ タイムアウト（art-out未表示）→ 続行")
            dump_art_log(page, "（記事生成失敗）")

        lt_text = page.text_content("#art-lt") or ""
        log(f"生成ステータス: {lt_text}")
        time.sleep(2)

        # ── STEP 5: note投稿ボタン ─────────────────────────────
        log("【STEP 5】noteに投稿ボタンをクリック...")
        note_btn = page.query_selector("#art-to-note-btn")
        if note_btn and note_btn.is_visible():
            # disabled の場合は押下前に状態確認
            disabled = page.evaluate("() => document.getElementById('art-to-note-btn').disabled")
            if disabled:
                log("⚠ note投稿ボタンがdisabled（記事未生成のため押下不可）")
                dump_art_log(page, "（最終状態）")
            else:
                note_btn.click()
                log("15秒待機中（GitHub push + ワークフロートリガー）...")
                time.sleep(15)
                result_text = page.text_content("#art-note-result") or ""
                log(f"✓ 結果: {result_text}")
                dump_art_log(page, "（完了後）")
        else:
            log("⚠ note投稿ボタンが見つかりません → スキップ")
            dump_art_log(page, "（ボタン未検出）")

        browser.close()

    log("=== 完了 ===")


if __name__ == "__main__":
    main()
