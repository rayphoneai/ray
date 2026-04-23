"""
auto_post.py  ―  RayPhoneAI 自動投稿スクリプト（Playwright版）
管理画面を Playwright でブラウザ操作し、ダッシュボードと全く同じフローで実行します。

フロー:
  1. 管理画面を開く
  2. パスワードでログイン & API キーを localStorage にセット
  3. 自動入力ボタンをクリック → タイトルが埋まるまで待機（最大60秒）
  4. 記事を生成するボタンをクリック → 生成完了まで待機（最大240秒）
  5. note に投稿ボタンをクリック → GitHub push + workflow dispatch 完了待機
  6. 完了

前回までのバグ修正:
  - autoFill 後の固定 time.sleep(5) を wait_for_function に置き換え
    （タイトル空のまま次に進んで alert 連鎖で沈黙していた問題）
  - 記事生成タイムアウトを 90 秒 → 240 秒に延長
  - タイトル空なら即 abort（無意味な長時間待機を避ける）
  - dialog / console.error / pageerror をログに出力
  - タイトル空の時に出る alert を自動 accept（進行をブロックしないため）
"""

import os
import sys
import time
from datetime import datetime

print("=== auto_post.py 起動 ===")
print(f"Python: {sys.version}")

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

# ADMIN_URL が未設定の場合は GH_USER/GH_REPO から推定
if not ADMIN_URL and GH_USER and GH_REPO:
    ADMIN_URL = f"https://{GH_USER}.github.io/{GH_REPO}/admin.html"

print(f"ADMIN_URL: {ADMIN_URL}")
print(f"HEADLESS: {HEADLESS}")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def dump_art_log(page):
    """admin.html 側の art-log パネルを読み出して出力（失敗デバッグ用）"""
    try:
        txt = page.text_content("#art-log") or ""
        if txt.strip():
            log("---- art-log ----")
            for line in txt.splitlines():
                if line.strip():
                    log("  " + line)
            log("-----------------")
    except Exception as e:
        log(f"(art-log 取得失敗: {e})")


def main():
    if not ADMIN_URL:
        log("✗ ADMIN_URL または GH_USER/GH_REPO が未設定です")
        sys.exit(1)
    if not ANTHROPIC_API_KEY:
        log("✗ ANTHROPIC_API_KEY が未設定です（記事生成に必須）")
        sys.exit(1)
    if not GEMINI_API_KEY:
        log("⚠ GEMINI_API_KEY 未設定（アイキャッチは admin.html 側で SVG 生成されるため動作は可）")

    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        # ── dialog / console / pageerror ハンドラ ─────────────
        # alert が出ても進行をブロックしないように自動 accept
        def _on_dialog(dialog):
            log(f"⚠ ダイアログ検出({dialog.type}): {dialog.message}")
            try:
                dialog.accept()
            except Exception:
                pass

        def _on_console(msg):
            try:
                if msg.type in ("error", "warning"):
                    log(f"[console.{msg.type}] {msg.text}")
            except Exception:
                pass

        def _on_pageerror(err):
            log(f"[pageerror] {err}")

        page.on("dialog", _on_dialog)
        page.on("console", _on_console)
        page.on("pageerror", _on_pageerror)

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

        # ── STEP 2b: API キーと GitHub 設定を localStorage にセット
        log("API キーと GitHub 設定を localStorage にセット中...")
        cfg_js = f"""() => {{
            localStorage.setItem('rp_key', '{GEMINI_API_KEY}');
            localStorage.setItem('rp_claude_key', '{ANTHROPIC_API_KEY}');
            localStorage.setItem('rp_claude_model', '{CLAUDE_MODEL}');
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
        log("タイトルが埋まるのを待機中（最大60秒）...")
        try:
            page.wait_for_function(
                "() => { var el = document.getElementById('art-title');"
                " return !!(el && el.value && el.value.trim().length > 0); }",
                timeout=60000,
            )
            title_val = page.input_value("#art-title")
            log(f"✓ タイトル: {title_val}")
        except PWTimeout:
            log("✗ autoFill が60秒以内に完了しませんでした → 中断")
            dump_art_log(page)
            browser.close()
            sys.exit(1)

        # ── STEP 4: 記事を生成するボタンをクリック ───────────
        log("【STEP 4】記事を生成するボタンをクリック...")
        page.click("#art-gen-btn")
        log("記事生成完了を待機中（最大240秒）...")
        try:
            page.wait_for_selector("#art-out.show", timeout=240000)
            log("✓ 記事生成完了（art-out 表示）")
        except PWTimeout:
            log("✗ 記事生成タイムアウト（art-out 未表示）")
            dump_art_log(page)
            browser.close()
            sys.exit(1)

        lt_text = page.text_content("#art-lt") or ""
        log(f"生成ステータス: {lt_text}")
        time.sleep(2)

        # ── STEP 5: note に投稿ボタンをクリック ───────────────
        # このボタン1つで「ブログ公開（GitHub push）＋ note_post.yml トリガー」が完結する
        log("【STEP 5】note に投稿ボタンをクリック（ブログ公開＋note 投稿ワークフロー起動）...")
        try:
            page.wait_for_selector("#art-to-note-btn", state="visible", timeout=10000)
            page.click("#art-to-note-btn")
            log("20秒待機中（GitHub push + workflow dispatch）...")
            # 段階的に結果表示を監視
            result_text = ""
            for i in range(20):
                time.sleep(1)
                result_text = page.text_content("#art-note-result") or ""
                if "ワークフロー起動完了" in result_text or "✅" in result_text or "⚠" in result_text:
                    break
            log(f"✓ 結果: {result_text or '（結果未取得）'}")
        except PWTimeout:
            log("⚠ note 投稿ボタンが表示されませんでした → スキップ")
            dump_art_log(page)

        browser.close()

    log("=== 完了 ===")


if __name__ == "__main__":
    main()
