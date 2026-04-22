# Claude 記事生成 移行完全版 — 変更サマリ

## 方針
- **記事テキスト生成** → Claude API（`claude-sonnet-4-5` デフォルト）
- **アイキャッチ画像** → Gemini のまま（note側 `gemini-2.5-flash-image` / blog側 静的SVGテンプレート）
- 既存 `gemini()` 関数・呼び出し側コードは可能な限り温存

---

## 変更ファイル一覧（4ファイル）

| ファイル | 配置先 | 主な変更 |
|---|---|---|
| `admin.html` | リポジトリルート | Claude APIキー入力追加・`claudeCall()`を実際のClaude呼出しに差替 |
| `auto_post.py` | リポジトリルート | `ANTHROPIC_API_KEY`/`CLAUDE_MODEL` 環境変数対応・localStorage注入 |
| `note_post.py` | リポジトリルート | `claude()` 関数追加・テキスト生成2箇所をClaudeに切替（画像は非変更） |
| `auto_post.yml` | `.github/workflows/` | env に `ANTHROPIC_API_KEY` / `CLAUDE_MODEL` 追加 |
| `note_post.yml` | `.github/workflows/` | env に `ANTHROPIC_API_KEY` / `CLAUDE_MODEL` 追加 |

---

## 導入手順

### 1. Anthropic APIキー取得
https://console.anthropic.com/ → Settings → API Keys → Create Key
→ 発行された `sk-ant-...` をコピー

### 2. GitHub Secrets 追加
リポジトリ `rayphoneai/ray` → Settings → Secrets and variables → Actions
- **New repository secret**
  - Name: `ANTHROPIC_API_KEY`
  - Value: `sk-ant-...`

### 3. （任意）モデル切替用 Variable 追加
同画面の **Variables** タブ:
- Name: `CLAUDE_MODEL`
- Value: `claude-sonnet-4-5`（または `claude-opus-4-7` / `claude-haiku-4-5`）
- 未設定時はスクリプト側デフォルト `claude-sonnet-4-5` が使用されます。

### 4. ファイル配置
```
ray/
├── admin.html          ← 置換
├── auto_post.py        ← 置換
├── note_post.py        ← 置換
└── .github/workflows/
    ├── auto_post.yml   ← 置換
    └── note_post.yml   ← 置換
```

### 5. 管理画面でClaudeキー登録（手動操作の場合）
- admin.html を開く → 設定 → Claude API Key を入力 → 保存
- GitHub Actions 自動実行時は `auto_post.py` が localStorage に自動注入するため入力不要

---

## 動作確認

### A. Anthropic API 単体確認（ローカル）
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python3 -c "
import requests
r = requests.post(
    'https://api.anthropic.com/v1/messages',
    headers={
        'x-api-key':  '$ANTHROPIC_API_KEY',
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json',
    },
    json={
        'model': 'claude-sonnet-4-5',
        'max_tokens': 1024,
        'messages': [{'role':'user','content':'テストです。「OK」とだけ返してください。'}]
    }, timeout=30
)
print(r.status_code, r.json()['content'][0]['text'][:80])
"
```
→ `200 OK` などが返れば成功。

### B. GitHub Actions 手動実行
Actions タブ → `ブログ自動投稿` → Run workflow
→ ログに以下が出ることを確認：
- ✗ が出ず完走すればOK
- 従来の `Gemini API呼び出し中...` ではなく、記事生成部分でClaudeが動いている
- アイキャッチは引き続きGeminiで生成される（note側）

### C. 管理画面から手動実行
admin.html → 記事生成 → ログ欄に `Claude API呼び出し中...` が出る

---

## ロールバック

いずれかの問題が起きた場合：
1. 4ファイルを git で revert
2. GitHub Secrets の `ANTHROPIC_API_KEY` は削除不要（未使用になるだけ）

---

## モデル別コスト目安（2025年基準・参考）

| モデル | 入力 (/1M tok) | 出力 (/1M tok) | 推奨用途 |
|---|---|---|---|
| `claude-haiku-4-5` | $1 | $5 | 高速・低コスト重視 |
| `claude-sonnet-4-5` | $3 | $15 | バランス（**デフォルト**） |
| `claude-opus-4-7` | $15 | $75 | 最高品質 |

1記事（約3000字出力≒4500トークン）あたり:
- Sonnet 4.5: 約 **$0.07〜0.10**
- Opus 4.7: 約 **$0.35〜0.50**
- Haiku 4.5: 約 **$0.03**

1日3回×30日 = 90記事/月:
- Sonnet 4.5: 約 **$6〜9/月**
- Haiku 4.5: 約 **$3/月**

（料金は変動するため最新情報は console.anthropic.com で確認してください）

---

## 注意点

1. **admin.html のアイキャッチは従来通りSVG**。note側だけGemini画像生成を使います。もし blog 側もGemini画像化したい場合は別途要相談。
2. `note_post.py` の `gemini()` 関数定義は残存させています（`generate_eyecatch_image()` では使っていませんが、将来の画像生成用リトライ等で流用可能）。
3. `anthropic-dangerous-direct-browser-access: true` ヘッダは admin.html がブラウザから直接Claude APIを叩くために必要。APIキーはPlaywright経由でlocalStorageに注入されるため、**キーが公開されるのはGitHub Actionsランナー上のヘッドレスブラウザ内のみ**。ユーザーがブラウザで admin.html を開く場合も同一PC上にしか残らないため実運用上は問題ありません。
