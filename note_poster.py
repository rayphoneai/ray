"""
note_poster.py — RayPhoneAI 自動投稿スクリプト
================================================
使い方:
  python note_poster.py post --title "タイトル" --body "本文" --svg eyecatch.svg
  python note_poster.py test        # 接続テスト
  python note_poster.py server      # 管理画面連携サーバー起動

必要なライブラリ:
  pip install playwright python-dotenv flask flask-cors
  playwright install chromium
"""

import os, sys, json, time, base64, argparse, tempfile, threading
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

NOTE_EMAIL    = os.getenv("NOTE_EMAIL", "")
NOTE_PASSWORD = os.getenv("NOTE_PASSWORD", "")
HEADLESS      = os.getenv("HEADLESS", "false").lower() == "true"
PORT          = int(os.getenv("PORT", "8765"))


# =========================================================
# PLAYWRIGHT 投稿ロジック
# =========================================================
def post_to_note(title: str, body: str, svg_code: str = None,
                 publish: bool = False, blog_url: str = "") -> dict:
    """
    noteに記事を投稿する。
    publish=False → 下書き保存
    publish=True  → 公開
    戻り値: {"ok": bool, "url": str, "message": str}
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return {"ok": False, "url": "", "message": "playwright が未インストールです。pip install playwright && playwright install chromium を実行してください。"}

    if not NOTE_EMAIL or not NOTE_PASSWORD:
        return {"ok": False, "url": "", "message": ".env に NOTE_EMAIL と NOTE_PASSWORD が設定されていません。"}

    svg_path = None
    png_path = None
    tmp_file = None
    card_url = blog_url.strip() if blog_url else ""

    # SVGデータの受信確認
    svg_len = len(svg_code) if svg_code else 0
    # <svg タグを正規化（前後の空白や余分な文字を除去）
    if svg_code:
        svg_idx = svg_code.find('<svg')
        if svg_idx > 0:
            print(f"  SVG前に{svg_idx}字の余分な文字を除去します")
            svg_code = svg_code[svg_idx:]
        elif svg_idx < 0:
            print(f"  警告: SVGデータに<svgタグが見つかりません")
    has_svg = bool(svg_code and '<svg' in svg_code)
    print(f"  ★ SVGデータ確認: {svg_len}字 → 正規化後has_svg: {has_svg}")

    try:
        # SVGを一時ファイルとして保存 & 事前にPNG変換（メインブラウザセッション外で実行）
        if svg_code and '<svg' in svg_code:
            tmp_file = tempfile.NamedTemporaryFile(suffix=".svg", delete=False, mode='w', encoding='utf-8')
            tmp_file.write(svg_code)
            tmp_file.close()
            svg_path = tmp_file.name
            print(f"  SVG一時ファイル作成: {svg_path}")

            # PNG変換: メインセッション前に完全別プロセスで実行（タブ干渉を防ぐ）
            png_path = svg_path.replace(".svg", ".png")
            try:
                with sync_playwright() as pw_pre:
                    b_pre = pw_pre.chromium.launch(headless=True)
                    p_pre = b_pre.new_page()
                    p_pre.set_viewport_size({"width": 1280, "height": 670})
                    svg_html = "<!DOCTYPE html><html><body style='margin:0;padding:0;background:#fff;'>{}</body></html>".format(svg_code)
                    p_pre.set_content(svg_html, wait_until="networkidle")
                    time.sleep(0.5)
                    p_pre.screenshot(path=png_path, clip={"x":0,"y":0,"width":1280,"height":670})
                    b_pre.close()
                print(f"  SVG→PNG変換完了（事前）: {Path(png_path).name}")
            except Exception as e:
                print(f"  PNG変換失敗（SVGをそのまま使用）: {e}")
                png_path = None

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=HEADLESS,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 1000},
                locale="ja-JP"
            )
            page = ctx.new_page()
            page.set_default_timeout(20000)

            # ---- ログイン ----
            print("[1/6] noteにログイン中...")
            page.goto("https://note.com/login", wait_until="networkidle")
            time.sleep(3)

            try:
                # メール欄に入力
                email_input = page.locator('input[type="email"], input[name="email"], input').first
                email_input.wait_for(state="visible", timeout=10000)
                email_input.click()
                time.sleep(0.5)
                email_input.fill(NOTE_EMAIL)
                print(f"  メール入力完了: {NOTE_EMAIL[:6]}...")
                time.sleep(0.8)

                # パスワード入力
                pass_input = page.locator('input[type="password"]').first
                pass_input.wait_for(state="visible", timeout=5000)
                pass_input.click()
                time.sleep(0.3)
                pass_input.fill(NOTE_PASSWORD)
                print("  パスワード入力完了")
                time.sleep(1)

                # スクリーンショット（入力確認用）
                page.screenshot(path="debug_before_submit.png")
                print("  送信前スクリーンショット保存: debug_before_submit.png")

                # 送信：複数の方法を試す
                submitted = False
                # 1. ボタンクリックを最初に試す
                for sel in ['button[type="submit"]', 'button:has-text("ログイン")', 'button:has-text("次へ")', 'input[type="submit"]']:
                    try:
                        b = page.locator(sel).first
                        if b.is_visible(timeout=2000):
                            b.click()
                            print(f"  ボタンクリック: {sel}")
                            submitted = True
                            break
                    except Exception:
                        continue
                # 2. ボタンが見つからなければEnterで送信
                if not submitted:
                    pass_input.press("Enter")
                    print("  Enterキーで送信")
                time.sleep(3)

                # ログインページから離脱するまで最大40秒待機
                for i in range(40):
                    time.sleep(1)
                    cur = page.url
                    if "/login" not in cur:
                        print(f"  ✓ ログイン成功: {cur}")
                        break
                    print(f"  待機 {i+1}秒... {cur}")
                    # 15秒後にまだログインページなら再度ボタンクリック
                    if i == 14:
                        print("  再送信を試みます...")
                        for sel in ['button[type="submit"]', 'button:has-text("ログイン")', 'button:has-text("次へ")']:
                            try:
                                b = page.locator(sel).first
                                if b.is_visible(timeout=1000):
                                    b.click()
                                    print(f"  クリック: {sel}")
                                    break
                            except Exception:
                                continue
                else:
                    page.screenshot(path="debug_login_fail.png")
                    browser.close()
                    return {"ok": False, "url": "", "message": "ログイン失敗。debug_login_fail.png を確認してください。パスワードが正しいか確認してください。"}

            except Exception as e:
                page.screenshot(path="debug_login_error.png")
                browser.close()
                return {"ok": False, "url": "", "message": f"ログインエラー: {str(e)}"}

            time.sleep(2)

            # ---- 新規記事作成ページへ ----
            print("[2/6] 新規記事作成ページを開いています...")
            page.goto("https://note.com/notes/new", wait_until="networkidle")
            time.sleep(3)

            if "/login" in page.url:
                browser.close()
                return {"ok": False, "url": "", "message": "セッションエラー。ログイン後に記事ページへアクセスできませんでした。"}

            print(f"  エディタURL: {page.url}")

            # ---- タイトル入力 ----
            print("[3/6] タイトルを入力中...")
            try:
                title_sel = page.locator(".m-editor-title, [placeholder*='タイトル'], h1[contenteditable]").first
                title_sel.click()
                time.sleep(0.3)
                page.keyboard.press("Control+A")
                page.keyboard.type(title, delay=30)
            except Exception as e:
                print(f"  タイトル入力の代替手段を試みます: {e}")
                page.keyboard.press("Tab")
                page.keyboard.type(title, delay=30)

            # ---- 本文入力 ----
            print("[4/6] 本文を入力中...")

            # blog_urlパラメータを最優先、なければbodyから正規表現で抽出
            import re as _re
            card_url = blog_url.strip() if blog_url else ""
            if not card_url:
                m = _re.search(r'(?:▼\s*ブログ記事はこちら\s*\n)(https?://\S+)', body)
                if m:
                    card_url = m.group(1).strip()
            if card_url:
                print(f"  ブログURL確認: {card_url}")
            else:
                print(f"  ブログURL: 未取得（bodyにURLなし）")

            try:
                body_sel = page.locator(".m-editor-body, [data-placeholder*='本文'], .ProseMirror").first
                body_sel.click()
            except Exception:
                page.keyboard.press("Tab")
            time.sleep(0.5)
            page.evaluate(f"""
                const el = document.querySelector('.m-editor-body, .ProseMirror, [data-placeholder]');
                if (el) {{
                    el.focus();
                    document.execCommand('insertText', false, {json.dumps(body)});
                }}
            """)
            time.sleep(1.5)

            # ---- 「▼ ブログ記事はこちら」の次の行をクリックしてURL入力→Enter ----
            if card_url:
                print(f"  URLをリンクカードとして挿入中: {card_url}")
                try:
                    # ▼の段落をスクロールして画面内に表示
                    page.evaluate("""
                        () => {
                            const editor = document.querySelector('.m-editor-body, .ProseMirror, [data-placeholder]');
                            if (!editor) return;
                            const paras = Array.from(editor.querySelectorAll('p, div'));
                            for (let p of paras) {
                                if (p.textContent.includes('▼') && p.textContent.includes('ブログ記事はこちら')) {
                                    p.scrollIntoView({block: 'center'});
                                    break;
                                }
                            }
                        }
                    """)
                    time.sleep(1)

                    # ▼の次の段落の座標を取得
                    coords = page.evaluate("""
                        () => {
                            const editor = document.querySelector('.m-editor-body, .ProseMirror, [data-placeholder]');
                            if (!editor) return null;
                            const paras = Array.from(editor.querySelectorAll('p, div'));
                            for (let i = 0; i < paras.length; i++) {
                                if (paras[i].textContent.includes('▼') && paras[i].textContent.includes('ブログ記事はこちら')) {
                                    const next = paras[i+1];
                                    if (next) {
                                        const rect = next.getBoundingClientRect();
                                        return {x: rect.x + 10, y: rect.y + rect.height/2};
                                    }
                                }
                            }
                            return null;
                        }
                    """)

                    if coords and 0 < coords['y'] < 950:
                        print(f"  ▼次行クリック: x={coords['x']:.0f} y={coords['y']:.0f}")
                        page.mouse.click(coords['x'], coords['y'])
                        time.sleep(0.5)
                        # 行を全選択して上書き（既存テキストがあれば消す）
                        page.keyboard.press("Home")
                        page.keyboard.press("Shift+End")
                        time.sleep(0.2)
                        # URLを入力してEnter（noteが自動でカード変換）
                        page.keyboard.type(card_url, delay=20)
                        page.keyboard.press("Enter")
                        time.sleep(3)
                        print(f"  ✓ URLリンク挿入完了: {card_url}")
                    else:
                        print(f"  ▼が画面内に見つからず（coords={coords}）→ 末尾に追記")
                        page.evaluate("""
                            const el = document.querySelector('.m-editor-body, .ProseMirror, [data-placeholder]');
                            if (el) { el.focus();
                                const r = document.createRange();
                                r.selectNodeContents(el); r.collapse(false);
                                const s = window.getSelection();
                                s.removeAllRanges(); s.addRange(r); }
                        """)
                        page.keyboard.press("Enter")
                        page.keyboard.type(card_url, delay=20)
                        page.keyboard.press("Enter")
                        time.sleep(3)
                        print(f"  ✓ URL末尾追記完了")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  URL挿入エラー: {e}")

            # ---- アイキャッチ画像アップロード ----
            if svg_path and Path(svg_path).exists():
                print("[5/6] アイキャッチをアップロード中...")
                try:
                    # 事前変換済みPNGを使用（メインセッション内では別タブを開かない）
                    upload_file = png_path if png_path and Path(png_path).exists() else svg_path
                    print(f"  アップロードファイル: {Path(upload_file).name}")

                    # ページのビューポートを再設定（タブ操作後に縮小している場合の対策）
                    page.set_viewport_size({"width": 1280, "height": 1000})
                    page.bring_to_front()
                    time.sleep(1)

                    # スクリーンショットでDOM確認
                    page.screenshot(path="debug_editor.png")

                    # ページ上の全ボタン情報を取得
                    buttons_info = page.evaluate("""
                        () => {
                            const els = document.querySelectorAll('button, label[for], [role="button"]');
                            return Array.from(els).map(e => ({
                                tag: e.tagName,
                                text: e.textContent.trim().slice(0,30),
                                cls: e.className.slice(0,80),
                                y: e.getBoundingClientRect().top,
                                x: e.getBoundingClientRect().left,
                                w: e.getBoundingClientRect().width,
                                h: e.getBoundingClientRect().height
                            })).filter(e => e.w > 0 && e.h > 0);
                        }
                    """)
                    print(f"  ページ上の要素数: {len(buttons_info)}")
                    # y座標が低いもの（画面上部）を表示
                    for b in sorted(buttons_info, key=lambda x: x["y"])[:20]:
                        print(f"    y={b['y']:.0f} [{b['tag']}] {b['text']!r} cls={b['cls'][:50]}")

                    # STEP1: アイキャッチボタンをクリック
                    # スクリーンショットで判明: y=-4010の sc-131cded0 がアイキャッチボタン（画面外上部）
                    # bg-tranのボタンは本文挿入メニューなので使わない
                    print("  STEP1: アイキャッチボタンをクリック...")
                    icon_clicked = False

                    # ページ最上部にスクロール
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(1)

                    # sc-131cded0 クラスのボタン（アイキャッチエリアのボタン）
                    eyecatch_btn = page.locator('button[class*="sc-131cded0"]').first
                    if eyecatch_btn.count() > 0:
                        try:
                            eyecatch_btn.scroll_into_view_if_needed()
                            time.sleep(0.5)
                            eyecatch_btn.click()
                            time.sleep(2)
                            print("  ✓ アイキャッチボタンクリック（sc-131cded0）")
                            icon_clicked = True
                        except Exception as e:
                            print(f"  sc-131cded0クリックエラー: {e}")

                    if not icon_clicked:
                        try:
                            page.evaluate("""
                                const btn = document.querySelector('button[class*="sc-131cded0"]');
                                if(btn){ btn.scrollIntoView(); btn.click(); }
                            """)
                            time.sleep(2)
                            print("  ✓ アイキャッチボタンJS経由クリック")
                            icon_clicked = True
                        except Exception as e:
                            print(f"  JSクリックエラー: {e}")

                    # STEP1後のスクリーンショット
                    page.screenshot(path="debug_after_eyecatch_click.png")

                    # STEP2: 「画像をアップロード」クリック → ファイル選択 → 「保存」クリック
                    # スクリーンショットで判明: アイキャッチボタン後に
                    #「画像をアップロード」「記事にあう画像を選ぶ」「Adobe Express〜」のメニューが出る
                    print("  STEP2: 「画像をアップロード」をクリック...")
                    time.sleep(1)
                    uploaded = False

                    try:
                        with page.expect_file_chooser(timeout=15000) as fc_info:
                            for sel2 in [
                                'button:has-text("画像をアップロード")',
                                'div:has-text("画像をアップロード")',
                                'li:has-text("画像をアップロード")',
                            ]:
                                try:
                                    b2 = page.locator(sel2).first
                                    if b2.count() > 0 and b2.is_visible(timeout=2000):
                                        b2.click()
                                        print(f"  ✓ 「画像をアップロード」クリック: {sel2}")
                                        break
                                except Exception:
                                    continue

                        # ファイル選択（「開く」に相当）
                        file_chooser = fc_info.value
                        file_chooser.set_files(upload_file)
                        print("  ✓ ファイル選択完了")
                        time.sleep(4)

                        # STEP3: ファイル選択後のプレビューポップアップで「保存」をクリック
                        # スクリーンショットで確認: 画像プレビュー + 右下に「キャンセル」「保存」ボタン
                        print("  STEP3: 「保存」ボタンが出るまで待機中...")
                        time.sleep(3)  # ポップアップが完全に表示されるまで待つ
                        page.screenshot(path="debug_after_file_select.png")

                        save_clicked = False
                        # 最大10秒間「保存」ボタンを探す
                        # ※ has-text("保存")は「下書き保存」にも一致するため完全一致で探す
                        for attempt in range(10):
                            try:
                                # 完全一致: text="保存" のボタンのみ
                                b3 = page.get_by_role("button", name="保存", exact=True).first
                                if b3.count() > 0 and b3.is_visible(timeout=1000):
                                    b3.click()
                                    print(f"  ✓ 「保存」クリック（完全一致）")
                                    save_clicked = True
                                    time.sleep(2)
                                    break
                            except Exception:
                                pass
                            if not save_clicked:
                                print(f"  保存ボタン待機 {attempt+1}秒...")
                                time.sleep(1)

                        if not save_clicked:
                            print("  「保存」ボタンが見つかりません。Enterキーで試みます")
                            page.keyboard.press("Enter")
                            time.sleep(2)

                        uploaded = True
                        print("  ✓ アイキャッチのアップロード完了")
                        print("  アップロード処理完了を5秒待機中...")
                        time.sleep(5)

                    except Exception as e:
                        print(f"  アップロードエラー: {e}")
                        page.screenshot(path="debug_upload_error.png")

                    if not uploaded:
                        print("  アイキャッチのアップロードに失敗しました（本文は保存されます）")

                except Exception as e:
                    print(f"  アイキャッチエラー: {e}")
            else:
                print("[5/6] アイキャッチなし（スキップ）")

            # ---- 公開 or 下書き保存 ----
            print(f"[6/6] {'公開' if publish else '下書き保存'}中...")
            result_url = ""

            try:
                if publish:
                    # まずページ上部にスクロール
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(1)
                    # 「公開に進む」ボタンをクリック
                    pub_btn_clicked = False
                    for sel in [
                        'button:has-text("公開に進む")',
                        'button:has-text("公開設定")',
                        'button:has-text("公開する")',
                    ]:
                        try:
                            b = page.locator(sel).first
                            if b.count() > 0 and b.is_visible(timeout=2000):
                                b.click()
                                time.sleep(2)
                                print(f"  クリック: {sel}")
                                pub_btn_clicked = True
                                break
                        except Exception:
                            continue

                    if pub_btn_clicked:
                        # 確認ダイアログの「公開する」をクリック
                        for sel2 in [
                            'button:has-text("公開する")',
                            'button:has-text("投稿する")',
                            'button:has-text("公開")',
                        ]:
                            try:
                                b2 = page.locator(sel2).last
                                if b2.count() > 0 and b2.is_visible(timeout=3000):
                                    b2.click()
                                    print(f"  確認クリック: {sel2}")
                                    time.sleep(3)
                                    break
                            except Exception:
                                continue

                    try:
                        page.wait_for_url("**/n/**", timeout=15000)
                    except Exception:
                        pass
                    result_url = page.url
                    print(f"  公開後URL: {result_url}")
                else:
                    # 下書き保存：ページ上部にスクロールしてからボタンを探す
                    saved = False
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(1)
                    selectors = [
                        'button:has-text("下書き保存")',
                        'button:has-text("下書き")',
                        '[data-testid="draft-save"]',
                        'button[aria-label*="下書き"]',
                    ]
                    for sel in selectors:
                        try:
                            btn = page.locator(sel).first
                            if btn.count() > 0 and btn.is_visible(timeout=2000):
                                btn.scroll_into_view_if_needed()
                                time.sleep(0.3)
                                btn.click()
                                time.sleep(2)
                                print(f"  下書き保存ボタンをクリック: {sel}")
                                saved = True
                                break
                        except Exception:
                            continue

                    if not saved:
                        print("  ボタンが見つからないためCtrl+Sで保存を試みます")
                        page.keyboard.press("Control+s")
                        time.sleep(3)

                    result_url = page.url
                    print(f"  保存後URL: {result_url}")

            except PWTimeout:
                result_url = page.url
                print("  タイムアウト（処理は完了している可能性あり）")

            time.sleep(1)
            browser.close()

            status = "公開完了" if publish else "下書き保存完了"
            print(f"\n✓ {status}！")
            if result_url and "note.com" in result_url:
                print(f"  URL: {result_url}")

            return {"ok": True, "url": result_url, "message": status}

    except Exception as e:
        msg = f"エラー: {str(e)}"
        print(f"\n✗ {msg}")
        return {"ok": False, "url": "", "message": msg}

    finally:
        if tmp_file and Path(tmp_file.name).exists():
            try:
                os.unlink(tmp_file.name)
            except Exception:
                pass
        if png_path and Path(png_path).exists():
            try:
                os.unlink(png_path)
            except Exception:
                pass


# =========================================================
# 接続テスト
# =========================================================
def run_test():
    print("=" * 50)
    print("RayPhoneAI note 接続テスト")
    print("=" * 50)
    print(f"EMAIL   : {NOTE_EMAIL[:4]}...{NOTE_EMAIL[-8:] if len(NOTE_EMAIL) > 12 else '(未設定)'}")
    print(f"PASSWORD: {'設定済み' if NOTE_PASSWORD else '未設定'}")
    print(f"HEADLESS: {HEADLESS}")
    print()

    if not NOTE_EMAIL or not NOTE_PASSWORD:
        print("✗ .env ファイルに認証情報が設定されていません。")
        print("  .env ファイルを作成して以下を記入してください：")
        print("  NOTE_EMAIL=your@email.com")
        print("  NOTE_PASSWORD=your_password")
        return

    result = post_to_note(
        title="【テスト投稿】RayPhoneAI 接続テスト",
        body="これはRayPhoneAI管理画面からの接続テスト投稿です。公開されません。",
        publish=False
    )
    print()
    print("結果:", "✓ 成功" if result["ok"] else "✗ 失敗")
    print("メッセージ:", result["message"])
    if result["url"]:
        print("URL:", result["url"])


# =========================================================
# Flask ローカルサーバー（管理画面から呼び出す）
# =========================================================
def run_server():
    try:
        from flask import Flask, request, jsonify
        from flask_cors import CORS
    except ImportError:
        print("flask と flask-cors が必要です。")
        print("pip install flask flask-cors")
        return

    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}},
         supports_credentials=False,
         allow_headers=["Content-Type", "Authorization", "Accept"],
         methods=["GET", "POST", "OPTIONS"])

    @app.after_request
    def after_request(response):
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,Accept")
        response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        return response

    # 2重投稿防止ロック（タイムアウト付き）
    posting_lock = threading.Lock()
    is_posting = [False]
    posting_started_at = [0]
    POSTING_TIMEOUT = 300  # 5分で自動リセット

    @app.route("/health", methods=["GET"])
    def health():
        # タイムアウトしたロックを自動解除
        import time as t2
        if is_posting[0] and posting_started_at[0] and (t2.time() - posting_started_at[0]) > POSTING_TIMEOUT:
            is_posting[0] = False
            print("  ロックタイムアウト → 自動解除")
        return jsonify({
            "ok": True,
            "message": "RayPhoneAI Poster Server 起動中",
            "email_set": bool(NOTE_EMAIL),
            "password_set": bool(NOTE_PASSWORD),
            "is_posting": is_posting[0]
        })

    @app.route("/reset", methods=["POST"])
    def reset_lock():
        is_posting[0] = False
        posting_started_at[0] = 0
        return jsonify({"ok": True, "message": "ロックをリセットしました"})

    @app.route("/post", methods=["POST"])
    def post():
        import time as t3
        # タイムアウト確認
        if is_posting[0] and posting_started_at[0] and (t3.time() - posting_started_at[0]) > POSTING_TIMEOUT:
            is_posting[0] = False
        # 2重実行防止
        if is_posting[0]:
            return jsonify({"ok": False, "message": "すでに投稿処理中です。完了までお待ちください。"}), 429

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "message": "リクエストデータがありません"}), 400

        title    = data.get("title", "")
        body     = data.get("body", "")
        svg      = data.get("svg", "")
        publish  = data.get("publish", False)
        blog_url = data.get("blog_url", "")
        art_id   = data.get("art_id", "")
        # art_idがあれば ?id= を付けて記事固有URLにする
        if art_id and blog_url:
            blog_url = blog_url.rstrip('/') + '/?id=' + art_id
        print(f"  受信blog_url: {repr(blog_url)}")

        print(f"  受信データ確認: title={title[:20]}... svg={len(svg)}字 body={len(body)}字")

        if not title:
            return jsonify({"ok": False, "message": "タイトルが空です"}), 400

        is_posting[0] = True
        posting_started_at[0] = __import__('time').time()
        result_container = [None]

        def worker():
            try:
                result_container[0] = post_to_note(title, body, svg, publish, blog_url)
            finally:
                is_posting[0] = False

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=180)

        if result_container[0] is None:
            is_posting[0] = False
            return jsonify({"ok": False, "message": "タイムアウト（処理が長すぎます）"}), 504

        return jsonify(result_container[0])

    @app.route("/post_x", methods=["POST"])
    def post_x_route():
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "message": "データなし"}), 400
        tweet = data.get("tweet", "")
        if not tweet:
            return jsonify({"ok": False, "message": "ツイート文字列が空です"}), 400
        print(f"\n[/post_x] 受信: {tweet[:60]}...")
        result = post_to_x(tweet)
        return jsonify(result)


    print("RayPhoneAI Poster Server")
    print("=" * 50)
    print(f"サーバー起動中: http://localhost:{PORT}")
    print("管理画面からの投稿リクエストを待機しています...")
    print("停止するには Ctrl+C を押してください")
    print()
    app.run(host="127.0.0.1", port=PORT, debug=False)


# =========================================================
# X (Twitter) 自動投稿
# =========================================================
X_USERNAME = os.getenv("X_USERNAME", "")
X_PASSWORD = os.getenv("X_PASSWORD", "")

def post_to_x(tweet_text: str) -> dict:
    """XにPlaywrightでツイートを投稿する（専用プロフィール方式）"""
    print(f"\n[X投稿] 開始: {tweet_text[:40]}...")

    from pathlib import Path as _Path
    import json as _json

    # 専用Xプロフィールディレクトリ
    x_profile_dir = os.path.expandvars(r"C:\Users\jyuma\x_profile")

    # プロフィールが存在しない場合は案内して終了
    if not os.path.exists(x_profile_dir):
        msg = (
            f"Xプロフィールが未作成です。以下の手順で初回セットアップしてください：\n"
            f"1. Chromeを全て閉じる\n"
            f"2. コマンドプロンプトで実行:\n"
            f'   chrome.exe --user-data-dir="{x_profile_dir}" --no-first-run\n'
            f"3. 開いたChromeでx.comにログイン\n"
            f"4. Chromeを閉じる\n"
            f"5. 再度記事生成を実行"
        )
        print(f"  [X] {msg}")
        return {"ok": False, "message": msg}

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            print(f"  [X] 専用プロフィールで起動: {x_profile_dir}")
            ctx = pw.chromium.launch_persistent_context(
                user_data_dir=x_profile_dir,
                channel="chrome",
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-sandbox",
                ],
                viewport={"width": 1280, "height": 800},
                ignore_default_args=["--enable-automation"],
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            # X.comにアクセス
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            print(f"  [X] URL: {page.url}")

            # ログイン確認
            if "login" in page.url or "i/flow" in page.url or "signout" in page.url:
                page.screenshot(path="debug_x_not_logged_in.png")
                ctx.close()
                return {
                    "ok": False,
                    "message": (
                        "Xプロフィールでログインが切れています。\n"
                        f'chrome.exe --user-data-dir="{x_profile_dir}" --no-first-run\n'
                        "で開いてx.comに再ログインしてください。"
                    )
                }

            print(f"  [X] ログイン確認OK")

            # 作成ボタンをクリック
            for sel in [
                '[data-testid="SideNav_NewTweet_Button"]',
                'a[href="/compose/post"]',
                '[aria-label="ポストを作成"]',
                '[aria-label="Create post"]',
            ]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        time.sleep(2)
                        print(f"  [X] 作成ボタンクリック: {sel}")
                        break
                except Exception:
                    continue

            # テキストエリアに入力
            # 。で必ず終わるよう句点を探す（Xは280文字制限）
            _url_part = "\n\n" + card_url if card_url else ""
            _max_body = 275 - len(_url_part)
            _pos = tweet_text.rfind("。", 0, _max_body)
            if _pos > 0:
                _body = tweet_text[:_pos + 1]
            else:
                for _e in ["！", "？"]:
                    _p = tweet_text.rfind(_e, 0, _max_body)
                    if _p > 0:
                        _body = tweet_text[:_p + 1]
                        break
                else:
                    _body = tweet_text[:_max_body].rstrip()
            tweet_text_trimmed = _body + _url_part
            editor_typed = False
            for sel in [
                '[data-testid="tweetTextarea_0"]',
                'div[role="textbox"][aria-multiline="true"]',
                '[data-testid="tweetTextarea_0RichTextInputContainer"] div[contenteditable="true"]',
            ]:
                try:
                    editor = page.locator(sel).first
                    if editor.is_visible(timeout=5000):
                        editor.click()
                        time.sleep(0.8)
                        editor.type(tweet_text_trimmed, delay=25)
                        time.sleep(1.5)
                        editor_typed = True
                        print(f"  [X] テキスト入力完了 ({len(tweet_text_trimmed)}文字)")
                        break
                except Exception:
                    continue

            if not editor_typed:
                page.screenshot(path="debug_x_post.png")
                ctx.close()
                return {"ok": False, "message": "テキストエリアが見つかりません"}

            page.screenshot(path="debug_x_before_post.png")

            # 投稿ボタンクリック
            posted = False
            for sel in [
                '[data-testid="tweetButton"]',
                '[data-testid="tweetButtonInline"]',
                'button:has-text("ポストする")',
                'button:has-text("Post")',
            ]:
                try:
                    btn = page.locator(sel).last
                    if btn.is_visible(timeout=3000):
                        btn.scroll_into_view_if_needed()
                        time.sleep(0.3)
                        btn.click()
                        time.sleep(3)
                        print(f"  [X] 投稿ボタンクリック: {sel}")
                        posted = True
                        break
                except Exception:
                    continue

            if not posted:
                # ボタン一覧をログ出力
                for b in page.locator('button').all()[:15]:
                    try:
                        tid = b.get_attribute('data-testid') or ''
                        txt = (b.inner_text() or '')[:20]
                        if tid or txt:
                            print(f"    testid={tid} text={repr(txt)}")
                    except Exception:
                        pass
                page.screenshot(path="debug_x_post.png")
                ctx.close()
                return {"ok": False, "message": "投稿ボタンが見つかりません。debug_x_post.pngを確認してください"}

            ctx.close()
            print(f"  [X] ✓ 投稿完了")
            return {"ok": True, "message": "X投稿完了"}

    except Exception as e:
        print(f"  [X] エラー: {e}")
        return {"ok": False, "message": f"X投稿エラー: {str(e)}"}



    import subprocess as _sp
    import json as _json
    from pathlib import Path as _Path

    # Chromeのユーザーデータディレクトリを検索
    chrome_profiles = [
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data"),
    ]
    user_data_dir = None
    for p in chrome_profiles:
        if os.path.exists(p):
            user_data_dir = p
            print(f"  [X] ブラウザプロフィール: {p}")
            break

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:

            if user_data_dir:
                # 実際のChromeプロフィールを使用（ログイン状態を引き継ぐ）
                print("  [X] Chromeプロフィールで起動中...")
                ctx = pw.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    channel="chrome",
                    headless=False,  # プロフィール使用時は必ずheadless=False
                    args=["--disable-blink-features=AutomationControlled", "--profile-directory=Default"],
                    viewport={"width": 1280, "height": 800},
                )
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
            else:
                # Chromeが見つからない場合はCookieファイルを試す
                cookie_file = _Path(__file__).parent / "x_cookies.json"
                browser = pw.chromium.launch(
                    headless=HEADLESS,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                ctx2 = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = ctx2.new_page()
                if cookie_file.exists():
                    try:
                        ctx2.add_cookies(_json.loads(cookie_file.read_text(encoding="utf-8")))
                    except Exception:
                        pass

            # X.comにアクセス
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            print(f"  [X] URL: {page.url}")

            # ログイン確認
            if "login" in page.url or "i/flow" in page.url:
                page.screenshot(path="debug_x_not_logged_in.png")
                try:
                    ctx.close() if user_data_dir else None
                except Exception:
                    pass
                return {
                    "ok": False,
                    "message": "Xにログインしていません。まずChromeでx.comにログインしてください。その後再試行してください。"
                }

            print(f"  [X] ログイン確認OK")

            # ツイート作成ボタンをクリック
            compose_clicked = False
            for sel in [
                '[data-testid="SideNav_NewTweet_Button"]',
                'a[href="/compose/post"]',
                '[aria-label="ポストを作成"]',
                '[aria-label="Create post"]',
            ]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=3000):
                        btn.click()
                        time.sleep(2)
                        compose_clicked = True
                        print(f"  [X] 作成ボタンクリック: {sel}")
                        break
                except Exception:
                    continue

            # テキストエリアに入力
            # 。で必ず終わるよう句点を探す（Xは280文字制限）
            _url_part = "\n\n" + card_url if card_url else ""
            _max_body = 275 - len(_url_part)
            _pos = tweet_text.rfind("。", 0, _max_body)
            if _pos > 0:
                _body = tweet_text[:_pos + 1]
            else:
                for _e in ["！", "？"]:
                    _p = tweet_text.rfind(_e, 0, _max_body)
                    if _p > 0:
                        _body = tweet_text[:_p + 1]
                        break
                else:
                    _body = tweet_text[:_max_body].rstrip()
            tweet_text_trimmed = _body + _url_part
            editor_typed = False
            for sel in [
                '[data-testid="tweetTextarea_0"]',
                '[data-testid="tweetTextarea_0RichTextInputContainer"]',
                'div[role="textbox"][aria-multiline="true"]',
            ]:
                try:
                    editor = page.locator(sel).first
                    if editor.is_visible(timeout=5000):
                        editor.click()
                        time.sleep(0.5)
                        editor.type(tweet_text_trimmed, delay=20)
                        time.sleep(1)
                        editor_typed = True
                        print(f"  [X] テキスト入力完了 ({len(tweet_text_trimmed)}文字): {sel}")
                        break
                except Exception:
                    continue

            if not editor_typed:
                page.screenshot(path="debug_x_post.png")
                try:
                    ctx.close() if user_data_dir else None
                except Exception:
                    pass
                return {"ok": False, "message": "テキストエリアが見つかりません。debug_x_post.pngを確認してください"}

            page.screenshot(path="debug_x_before_post.png")
            time.sleep(1)

            # 投稿ボタンクリック
            posted = False
            for sel in [
                '[data-testid="tweetButton"]',
                '[data-testid="tweetButtonInline"]',
                'button:has-text("ポストする")',
                'button:has-text("Post")',
            ]:
                try:
                    btn = page.locator(sel).last
                    if btn.is_visible(timeout=3000):
                        btn.scroll_into_view_if_needed()
                        time.sleep(0.3)
                        btn.click()
                        time.sleep(3)
                        print(f"  [X] 投稿ボタンクリック: {sel}")
                        posted = True
                        break
                except Exception:
                    continue

            if not posted:
                btns = page.locator('button').all()
                print(f"  [X] ボタン一覧:")
                for b in btns[:15]:
                    try:
                        tid = b.get_attribute('data-testid') or ''
                        txt = (b.inner_text() or '')[:20]
                        if tid or txt:
                            print(f"    testid={tid} text={repr(txt)}")
                    except Exception:
                        pass
                page.screenshot(path="debug_x_post.png")
                try:
                    ctx.close() if user_data_dir else None
                except Exception:
                    pass
                return {"ok": False, "message": "投稿ボタンが見つかりません。debug_x_post.pngを確認してください"}

            print(f"  [X] ✓ 投稿完了")
            time.sleep(1)
            try:
                ctx.close() if user_data_dir else None
            except Exception:
                pass
            return {"ok": True, "message": "X投稿完了"}

    except Exception as e:
        print(f"  [X] エラー: {e}")
        return {"ok": False, "message": f"X投稿エラー: {str(e)}"}



    import json as _json
    from pathlib import Path as _Path
    cookie_file = _Path(__file__).parent / "x_cookies.json"

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=HEADLESS, args=["--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = ctx.new_page()

            # ---------- Cookie読み込み（保存済みの場合） ----------
            if cookie_file.exists():
                try:
                    cookies = _json.loads(cookie_file.read_text(encoding="utf-8"))
                    ctx.add_cookies(cookies)
                    print(f"  [X] Cookie読み込み: {len(cookies)}件")
                except Exception as e:
                    print(f"  [X] Cookie読み込みエラー: {e}")

            # ---------- ホームへアクセス ----------
            page.goto("https://x.com/home", wait_until="domcontentloaded")
            time.sleep(3)

            # ログイン済みか確認（URLだけでなく要素でも確認）
            is_logged_in = False
            try:
                # ログイン済みなら「ポストする」ボタンや作成ボタンが存在する
                compose_btn = page.locator('[data-testid="SideNav_NewTweet_Button"]')
                if compose_btn.is_visible(timeout=5000):
                    is_logged_in = True
            except Exception:
                pass

            if not is_logged_in:
                print("  [X] 未ログイン検出 → ログインフロー開始")
                # 古いCookieを削除
                import json as _json2
                if cookie_file.exists():
                    cookie_file.unlink()
                    print("  [X] 古いCookieを削除")

                page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
                time.sleep(4)

                # ユーザー名入力（人間らしくゆっくり入力）
                try:
                    user_input = page.locator('input[autocomplete="username"]')
                    user_input.wait_for(state="visible", timeout=20000)
                    user_input.click()
                    time.sleep(0.5)
                    for ch in X_USERNAME:
                        page.keyboard.type(ch, delay=80)
                    time.sleep(1)
                    print("  [X] ユーザー名入力完了")
                except Exception as e:
                    page.screenshot(path="debug_x_login.png")
                    browser.close()
                    return {"ok": False, "message": f"ユーザー名入力失敗: {e}"}

                # 「次へ」ボタンクリック
                try:
                    for sel in ['[data-testid="LoginForm_Forward_Button"]', 'button:has-text("次へ")', 'button:has-text("Next")']:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=3000):
                            btn.click()
                            print(f"  [X] 「次へ」クリック: {sel}")
                            break
                    time.sleep(3)
                except Exception as e:
                    page.screenshot(path="debug_x_login.png")
                    browser.close()
                    return {"ok": False, "message": f"「次へ」クリック失敗: {e}"}

                # 追加確認（電話番号/ユーザー名確認画面）
                try:
                    verify = page.locator('input[data-testid="ocfEnterTextTextInput"]')
                    if verify.is_visible(timeout=4000):
                        verify.fill(X_USERNAME.replace("@", ""))
                        time.sleep(0.5)
                        for sel in ['[data-testid="ocfEnterTextNextButton"]', 'button:has-text("次へ")']:
                            btn = page.locator(sel).first
                            if btn.is_visible(timeout=2000):
                                btn.click()
                                break
                        print("  [X] 追加確認完了")
                        time.sleep(3)
                except Exception:
                    pass

                # パスワード入力
                pw_filled = False
                for sel in ['input[name="password"]', 'input[type="password"]', 'input[autocomplete="current-password"]']:
                    try:
                        pw_input = page.locator(sel).first
                        pw_input.wait_for(state="visible", timeout=10000)
                        pw_input.click()
                        time.sleep(0.5)
                        for ch in X_PASSWORD:
                            page.keyboard.type(ch, delay=60)
                        time.sleep(0.5)
                        print(f"  [X] パスワード入力完了: {sel}")
                        pw_filled = True
                        break
                    except Exception:
                        continue

                if not pw_filled:
                    page.screenshot(path="debug_x_login.png")
                    browser.close()
                    return {"ok": False, "message": "パスワード入力欄が見つかりません。debug_x_login.pngを確認してください"}

                # 「ログイン」ボタンクリック
                for sel in ['[data-testid="LoginForm_Login_Button"]', 'button:has-text("ログイン")', 'button:has-text("Log in")']:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=3000):
                            btn.click()
                            print(f"  [X] ログインボタンクリック: {sel}")
                            break
                    except Exception:
                        continue
                time.sleep(5)

                # ログイン確認
                if "login" in page.url or "i/flow" in page.url:
                    page.screenshot(path="debug_x_login.png")
                    browser.close()
                    return {"ok": False, "message": f"Xログイン失敗。debug_x_login.pngを確認。URL: {page.url}"}

                # Cookie保存
                cookies = ctx.cookies()
                cookie_file.write_text(_json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  [X] ログイン成功・Cookie保存: {len(cookies)}件 → {cookie_file}")

            else:
                print(f"  [X] ログイン済み確認: {page.url}")
                time.sleep(1)

            # ---------- ツイート投稿 ----------
            # ホームに確実に移動
            try:
                page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)
            except Exception as e:
                print(f"  [X] ホーム遷移エラー: {e}")
                browser.close()
                return {"ok": False, "message": f"ホーム遷移失敗: {e}"}

            print(f"  [X] ホームURL: {page.url}")

            # 投稿エリアをクリック
            editor_clicked = False
            for sel in ['[data-testid="tweetTextarea_0"]', '[placeholder="いまどうしてる？"]', 'div[role="textbox"]']:
                try:
                    editor = page.locator(sel).first
                    if editor.is_visible(timeout=5000):
                        editor.click()
                        time.sleep(0.5)
                        editor_clicked = True
                        print(f"  [X] エディタクリック: {sel}")
                        break
                except Exception:
                    continue

            if not editor_clicked:
                # 作成ボタンから開く
                for sel in ['[data-testid="SideNav_NewTweet_Button"]', 'a[href="/compose/post"]']:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=3000):
                            btn.click()
                            time.sleep(2)
                            break
                    except Exception:
                        continue
                try:
                    page.locator('[data-testid="tweetTextarea_0"]').first.click()
                    time.sleep(0.5)
                except Exception:
                    pass

            # テキスト入力（280文字制限を考慮）
            # 。で必ず終わるよう句点を探す（Xは280文字制限）
            _url_part = "\n\n" + card_url if card_url else ""
            _max_body = 275 - len(_url_part)
            _pos = tweet_text.rfind("。", 0, _max_body)
            if _pos > 0:
                _body = tweet_text[:_pos + 1]
            else:
                for _e in ["！", "？"]:
                    _p = tweet_text.rfind(_e, 0, _max_body)
                    if _p > 0:
                        _body = tweet_text[:_p + 1]
                        break
                else:
                    _body = tweet_text[:_max_body].rstrip()
            tweet_text_trimmed = _body + _url_part
            # エディタに確実にフォーカスを当ててから入力
            try:
                editor_el = page.locator('[data-testid="tweetTextarea_0"]').first
                if editor_el.is_visible(timeout=3000):
                    editor_el.click()
                    time.sleep(0.5)
                    editor_el.type(tweet_text_trimmed, delay=20)
                else:
                    raise Exception("editor not visible")
            except Exception:
                # フォールバック: キーボード入力
                for ch in tweet_text_trimmed:
                    page.keyboard.type(ch, delay=20)
            time.sleep(1.5)
            print(f"  [X] テキスト入力完了 ({len(tweet_text_trimmed)}文字)")

            # 投稿前スクリーンショット（デバッグ用）
            page.screenshot(path="debug_x_before_post.png")

            # 投稿ボタンクリック（複数のセレクタを試す）
            posted = False
            for sel in [
                '[data-testid="tweetButton"]',
                '[data-testid="tweetButtonInline"]',
                'button[data-testid="tweetButton"]',
                'div[data-testid="tweetButton"]',
                'button:has-text("ポストする")',
                'button:has-text("Post")',
                'button:has-text("ポスト")',
                '[role="button"]:has-text("ポストする")',
            ]:
                try:
                    btn = page.locator(sel).last  # lastを使う（モーダル内のボタン）
                    if btn.is_visible(timeout=2000):
                        btn.scroll_into_view_if_needed()
                        time.sleep(0.3)
                        btn.click()
                        time.sleep(3)
                        print(f"  [X] 投稿ボタンクリック: {sel}")
                        posted = True
                        break
                except Exception:
                    continue

            if not posted:
                # 全ボタンのtestIdを列挙してログに出す
                btns = page.locator('button').all()
                print(f"  [X] ページ上のボタン一覧 ({len(btns)}個):")
                for b in btns[:20]:
                    try:
                        tid = b.get_attribute('data-testid') or ''
                        txt = (b.inner_text() or '')[:20]
                        if tid or txt:
                            print(f"    testid={tid} text={repr(txt)}")
                    except Exception:
                        pass
                page.screenshot(path="debug_x_post.png")
                browser.close()
                return {"ok": False, "message": "投稿ボタンが見つかりません。debug_x_post.pngを確認してください"}


            # Cookie再保存（更新分）
            cookies = ctx.cookies()
            cookie_file.write_text(_json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")

            browser.close()
            print(f"  [X] ✓ 投稿完了")
            return {"ok": True, "message": "X投稿完了"}

    except Exception as e:
        print(f"  [X] エラー: {e}")
        return {"ok": False, "message": f"X投稿エラー: {str(e)}"}


# =========================================================
# CLI エントリーポイント
# =========================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RayPhoneAI note 自動投稿ツール")
    subparsers = parser.add_subparsers(dest="command")

    # post コマンド
    post_parser = subparsers.add_parser("post", help="記事を投稿する")
    post_parser.add_argument("--title",   required=True, help="記事タイトル")
    post_parser.add_argument("--body",    required=True, help="本文テキスト")
    post_parser.add_argument("--svg",     default=None,  help="SVGファイルパス（アイキャッチ）")
    post_parser.add_argument("--publish", action="store_true", help="公開する（省略時は下書き）")

    # test コマンド
    subparsers.add_parser("test", help="接続テスト")

    # server コマンド
    subparsers.add_parser("server", help="管理画面連携サーバー起動")

    args = parser.parse_args()

    if args.command == "post":
        svg_code = None
        if args.svg and Path(args.svg).exists():
            with open(args.svg, "r", encoding="utf-8") as f:
                svg_code = f.read()
        result = post_to_note(args.title, args.body, svg_code, args.publish)
        sys.exit(0 if result["ok"] else 1)

    elif args.command == "test":
        run_test()

    elif args.command == "server":
        run_server()

    else:
        parser.print_help()
