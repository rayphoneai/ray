"""
auto_post.py  ―  RayPhoneAI 自動投稿スクリプト（Playwright版）
管理画面を Playwright でブラウザ操作し、ダッシュボードと全く同じフローで実行します。

フロー:
  1. 管理画面を開く
  2. パスワードでログイン & Gemini APIキーをlocalStorageにセット
  3. 自動入力ボタンをクリック → 5秒待機
  4. 記事を生成するボタンをクリック → 生成完了まで待機（最大90秒）
  5. すぐに公開ボタンをクリック → 10秒待機
  6. noteに投稿ボタンをクリック → 10秒待機
  7. 完了
"""

import os
import sys
import time
from datetime import datetime

print("=== auto_post.py 起動 ===")
print(f"Python: {sys.version}")

# ── 環境変数 ─────────────────────────────────────────────────
ADMIN_URL      = os.getenv("ADMIN_URL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "rayphone2025")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GH_TOKEN       = os.getenv("GH_TOKEN", "")
GH_USER        = os.getenv("GH_USER", "")
GH_REPO        = os.getenv("GH_REPO", "")
BLOG_URL       = os.getenv("BLOG_URL", "")
NOTE_URL       = os.getenv("NOTE_URL", "")
HEADLESS       = os.getenv("HEADLESS", "true").lower() != "false"

# ADMIN_URLが未設定の場合はGH_USER/GH_REPOから推定
if not ADMIN_URL and GH_USER and GH_REPO:
    ADMIN_URL = f"https://{GH_USER}.github.io/{GH_REPO}/admin.html"

print(f"ADMIN_URL: {ADMIN_URL}")
print(f"HEADLESS: {HEADLESS}")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    if not ADMIN_URL:
        log("✗ ADMIN_URL または GH_USER/GH_REPO が未設定です")
        sys.exit(1)
    if not GEMINI_API_KEY:
        log("✗ GEMINI_API_KEY が未設定です")
        sys.exit(1)

    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        # ── STEP 1: 管理画面を開く ────────────────────────────
        log(f"管理画面を開いています: {ADMIN_URL}")
        page.goto(ADMIN_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # ── STEP 2: パスワードログイン ────────────────────────
        pw_gate = page.query_selector("#pw-gate")
        if pw_gate and pw_gate.is_visible():
            log("パスワードを入力中...")
            page.fill("#gate-pw", ADMIN_PASSWORD)
            page.keyboard.press("Enter")
            time.sleep(1)
            log("✓ ログイン完了")
        else:
            log("✓ 認証済み（スキップ）")

        # ── STEP 2b: APIキーとGitHub設定をlocalStorageにセット
        log("APIキーとGitHub設定をlocalStorageにセット中...")
        cfg_js = f"""() => {{
            localStorage.setItem('rp_key', '{GEMINI_API_KEY}');
            localStorage.setItem('rp_admin_auth', '{ADMIN_PASSWORD}');
            var cfg = {{}};
            try {{ cfg = JSON.parse(localStorage.getItem('rp_cfg') || '{{}}'); }} catch(e) {{}}
            cfg.ghToken = '{GH_TOKEN}';
            cfg.ghUser  = '{GH_USER}';
            cfg.ghRepo  = '{GH_REPO}';
            cfg.blogUrl = '{BLOG_URL}';
            cfg.noteUrl = '{NOTE_URL}';
            localStorage.setItem('rp_cfg', JSON.stringify(cfg));
        }}"""
        page.evaluate(cfg_js)

        # リロードして設定を反映
        page.reload(wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # pw-gate を確実に非表示にする
        page.evaluate("""() => {
            var gate = document.getElementById('pw-gate');
            if (gate) gate.style.display = 'none';
        }""")
        time.sleep(1)
        log("✓ 管理画面ロード完了")

        # ── STEP 3: 自動入力ボタンをクリック ─────────────────
        log("【STEP 3】自動入力ボタンをクリック...")
        page.wait_for_selector("#art-autofill-btn", state="visible", timeout=15000)
        page.click("#art-autofill-btn")
        log("5秒待機中（自動入力生成）...")
        time.sleep(5)

        title_val = page.input_value("#art-title")
        log(f"✓ タイトル確認: {title_val or '（空）'}")

        # ── STEP 4: 記事を生成するボタンをクリック ───────────
        log("【STEP 4】記事を生成するボタンをクリック...")
        page.click("#art-gen-btn")
        log("記事生成完了を待機中（最大90秒）...")
        try:
            page.wait_for_selector("#art-out.show", timeout=90000)
            log("✓ 記事生成完了（art-out表示）")
        except PWTimeout:
            log("⚠ タイムアウト（art-out未表示）→ 続行")
        lt_text = page.text_content("#art-lt") or ""
        log(f"生成ステータス: {lt_text}")
        time.sleep(2)

        # ── STEP 5: noteに投稿ボタンをクリック ───────────────
        # このボタン1つで「ブログ公開（GitHub push）＋ note_post.yml トリガー」が完結する
        log("【STEP 5】noteに投稿ボタンをクリック（ブログ公開＋note投稿ワークフロー起動）...")
        note_btn = page.query_selector("#art-to-note-btn")
        if note_btn and note_btn.is_visible():
            note_btn.click()
            log("10秒待機中（GitHub push + ワークフロートリガー）...")
            time.sleep(10)
            result_text = page.text_content("#art-note-result") or ""
            log(f"✓ 結果: {result_text}")
        else:
            log("⚠ note投稿ボタンが見つかりません → スキップ")

        browser.close()

    log("=== 完了 ===")


if __name__ == "__main__":
    main()
