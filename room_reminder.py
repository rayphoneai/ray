#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
楽天ROOM 投稿リマインダー（GitHub Actions 版）

旧構成（ローカル Windows タスク schedule.py mail / OneDrive\\デスクトップ\\files）が
作業フォルダごと消失して停止したため、GitHub Actions + Gmail SMTP に移植したもの。

- 1 日 3 回（08:00 / 11:30 / 21:00 JST）に、自分宛へ HTML リマインドメールを送る
- 商品は room_products.json から日付 + スロットで決定的にローテーション
- メール本文・ボタン類は旧メールと同一レイアウト
- 送信は Gmail SMTP（アプリパスワード）。GitHub Secrets で認証情報を渡す

env:
  GMAIL_ADDRESS        送信元 Gmail（既定 jyumaru.shidou@gmail.com）
  GMAIL_APP_PASSWORD   Gmail アプリパスワード（必須・Secrets）
  MAIL_TO              宛先（既定 = GMAIL_ADDRESS）
  SLOT                 '08:00' / '11:30' / '21:00' を明示指定（手動テスト用・任意）
"""

import os
import sys
import json
import smtplib
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from urllib.parse import quote

JST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_PATH = os.path.join(HERE, "room_products.json")

SLOTS = ["08:00", "11:30", "21:00"]

# 「投稿済みにする」ボタンの定型本文（旧メールと同一）
DONE_BODY = "このまま送信すると投稿済みになります（本文は編集不要）。"


def pick_slot():
    """現在時刻（JST）またはSLOT環境変数からスロットを決定。"""
    override = (os.environ.get("SLOT") or "").strip()
    if override in SLOTS:
        return override
    now = datetime.now(JST)
    hm = now.hour * 60 + now.minute
    # しきい値で最寄りスロットに割り当て（手動実行でも破綻しないように）
    if hm < 10 * 60:          # 〜10:00 → 朝枠
        return "08:00"
    if hm < 16 * 60:          # 〜16:00 → 昼枠
        return "11:30"
    return "21:00"            # それ以降 → 夜枠


def pick_product(products, slot):
    """日付 + スロットで決定的に1商品を選ぶ（毎回違う・全商品を巡回）。"""
    slot_idx = SLOTS.index(slot)
    day_ordinal = datetime.now(JST).date().toordinal()
    idx = (day_ordinal * len(SLOTS) + slot_idx) % len(products)
    return products[idx]


def build_html(slot, p):
    done_subject = quote(f"[ROOM-DONE] {p['id']}")
    done_body = quote(DONE_BODY)
    mailto = f"mailto:jyumaru.shidou@gmail.com?subject={done_subject}&amp;body={done_body}"
    return f"""<div style="font-family:-apple-system,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#1a1a1a;">
  <p style="color:#888;font-size:13px;margin:0 0 4px;">楽天ROOM 投稿リマインド｜{slot}</p>
  <h2 style="font-size:18px;margin:0 0 16px;">{p['title']}</h2>

  <p style="font-size:13px;color:#555;margin:0 0 6px;">▼ 紹介文（長押しで全選択 → コピー）</p>
  <div style="background:#f4f6f8;border:1px solid #e0e4e8;border-radius:10px;padding:14px;font-size:15px;line-height:1.7;white-space:normal;">{p['intro']}<br><br>{p['hashtags']}</div>

  <div style="margin:22px 0 8px;">
    <a href="{p['url']}" style="display:inline-block;padding:14px 20px;margin:6px 0;border-radius:10px;text-decoration:none;font-weight:bold;font-size:16px;background:#bf0000;color:#fff;">▶ 商品ページを開く</a>
  </div>
  <p style="font-size:13px;color:#666;margin:0 0 18px;">
    開いたページで「共有」→「楽天ROOM（コレ！）」を選び、上の紹介文を貼り付けて投稿してください。
  </p>

  <div style="margin:0 0 18px;">
    <a href="https://room.rakuten.co.jp/" style="display:inline-block;padding:14px 20px;margin:6px 0;border-radius:10px;text-decoration:none;font-weight:bold;font-size:16px;background:#fff;color:#bf0000;border:2px solid #bf0000;">楽天ROOMアプリを開く</a>
  </div>

  <div style="border-top:1px solid #eee;padding-top:16px;">
    <p style="font-size:13px;color:#555;margin:0 0 6px;">投稿が終わったら↓を押して、開いたメールをそのまま送信</p>
    <a href="{mailto}" style="display:inline-block;padding:14px 20px;margin:6px 0;border-radius:10px;text-decoration:none;font-weight:bold;font-size:16px;background:#0a7d33;color:#fff;">✅ 投稿済みにする</a>
  </div>
</div>
"""


def build_text(slot, p):
    return (
        f"■ 今出す商品\n{p['title']}\n\n"
        f"■ 紹介文（コピーして貼り付け）\n{p['intro']}\n\n{p['hashtags']}\n\n"
        f"■ 商品ページ（タップ→共有→ROOMでコレ！）\n{p['url']}\n\n"
        f"■ 楽天ROOMアプリ\nhttps://room.rakuten.co.jp/\n"
    )


def main():
    addr = os.environ.get("GMAIL_ADDRESS", "jyumaru.shidou@gmail.com").strip()
    app_pw = (os.environ.get("GMAIL_APP_PASSWORD") or "").replace(" ", "").strip()
    mail_to = os.environ.get("MAIL_TO", addr).strip()

    if not app_pw:
        print("ERROR: GMAIL_APP_PASSWORD is not set", file=sys.stderr)
        sys.exit(1)

    with open(PRODUCTS_PATH, encoding="utf-8") as f:
        products = json.load(f)
    if not products:
        print("ERROR: room_products.json is empty", file=sys.stderr)
        sys.exit(1)

    slot = pick_slot()
    p = pick_product(products, slot)

    msg = EmailMessage()
    msg["Subject"] = f"【ROOM投稿 {slot}】{p['title'][:50]}"
    msg["From"] = addr
    msg["To"] = mail_to
    msg.set_content(build_text(slot, p))
    msg.add_alternative(build_html(slot, p), subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(addr, app_pw)
        s.send_message(msg)

    print(f"OK: sent slot={slot} id={p['id']} title={p['title'][:30]}")


if __name__ == "__main__":
    main()
