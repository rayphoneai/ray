import { useState, useEffect, useCallback } from "react";

// ───────────────────────────────────────────────
// DATA
// ───────────────────────────────────────────────

const FONTS = [
  { value: "Noto Sans JP", label: "Noto Sans JP（ゴシック）" },
  { value: "Noto Serif JP", label: "Noto Serif JP（明朝）" },
  { value: "M PLUS 1p", label: "M PLUS 1p" },
  { value: "Zen Kaku Gothic New", label: "Zen Kaku Gothic New" },
  { value: "Zen Maru Gothic", label: "Zen Maru Gothic（丸）" },
  { value: "BIZ UDPGothic", label: "BIZ UDPGothic" },
  { value: "Klee One", label: "Klee One（手書き）" },
  { value: "DM Serif Display", label: "DM Serif Display" },
  { value: "Playfair Display", label: "Playfair Display" },
  { value: "Raleway", label: "Raleway" },
  { value: "Outfit", label: "Outfit" },
  { value: "Space Grotesk", label: "Space Grotesk" },
];

const PRESETS = {
  default: {
    name: "デフォルト",
    accentColor: "#6c63ff", headerBg: "#1a1a2e", headerText: "#ffffff",
    heroBg: "#f8f8ff", heroText: "#1a1a2e", pageBg: "#ffffff", bodyText: "#333333",
    cardBg: "#ffffff", cardBorder: "#eeeeee", pillBg: "#eeeeff", pillText: "#6c63ff",
    footerBg: "#1a1a2e", footerText: "#aaaacc",
    headingFont: "Noto Sans JP", bodyFont: "Noto Sans JP",
    headingSize: 38, bodySize: 16, lineHeight: 1.8, cardRadius: 12, pillRadius: 20,
  },
  minimal: {
    name: "ミニマル",
    accentColor: "#111111", headerBg: "#ffffff", headerText: "#111111",
    heroBg: "#fafafa", heroText: "#111111", pageBg: "#f4f4f4", bodyText: "#222222",
    cardBg: "#ffffff", cardBorder: "#e5e5e5", pillBg: "#eeeeee", pillText: "#333333",
    footerBg: "#111111", footerText: "#777777",
    headingFont: "Noto Serif JP", bodyFont: "Noto Sans JP",
    headingSize: 40, bodySize: 16, lineHeight: 1.9, cardRadius: 4, pillRadius: 4,
  },
  dark: {
    name: "ダーク",
    accentColor: "#a78bfa", headerBg: "#0a0a0a", headerText: "#e0e0e0",
    heroBg: "#111111", heroText: "#f0f0f0", pageBg: "#1a1a1a", bodyText: "#cccccc",
    cardBg: "#222222", cardBorder: "#333333", pillBg: "#2a1f4e", pillText: "#a78bfa",
    footerBg: "#0a0a0a", footerText: "#666666",
    headingFont: "Outfit", bodyFont: "Outfit",
    headingSize: 42, bodySize: 16, lineHeight: 1.75, cardRadius: 16, pillRadius: 8,
  },
  warm: {
    name: "ウォーム",
    accentColor: "#d97706", headerBg: "#3d2b1f", headerText: "#fef3c7",
    heroBg: "#fffbf0", heroText: "#3d2b1f", pageBg: "#fdf8f0", bodyText: "#3d2b1f",
    cardBg: "#fffbf0", cardBorder: "#e7d5b3", pillBg: "#fef3c7", pillText: "#b45309",
    footerBg: "#3d2b1f", footerText: "#fcd34d",
    headingFont: "Noto Serif JP", bodyFont: "Noto Sans JP",
    headingSize: 36, bodySize: 16, lineHeight: 1.85, cardRadius: 8, pillRadius: 20,
  },
  tech: {
    name: "テック",
    accentColor: "#06b6d4", headerBg: "#0f172a", headerText: "#e2e8f0",
    heroBg: "#f0f9ff", heroText: "#0f172a", pageBg: "#ffffff", bodyText: "#1e293b",
    cardBg: "#ffffff", cardBorder: "#e2e8f0", pillBg: "#ecfeff", pillText: "#0891b2",
    footerBg: "#0f172a", footerText: "#64748b",
    headingFont: "Space Grotesk", bodyFont: "Space Grotesk",
    headingSize: 40, bodySize: 16, lineHeight: 1.7, cardRadius: 8, pillRadius: 6,
  },
  elegant: {
    name: "エレガント",
    accentColor: "#c084fc", headerBg: "#1a0a2e", headerText: "#f0e6ff",
    heroBg: "#fdf4ff", heroText: "#1a0a2e", pageBg: "#ffffff", bodyText: "#2d1b4e",
    cardBg: "#ffffff", cardBorder: "#e9d5ff", pillBg: "#f3e8ff", pillText: "#7e22ce",
    footerBg: "#1a0a2e", footerText: "#c084fc",
    headingFont: "Playfair Display", bodyFont: "Noto Sans JP",
    headingSize: 38, bodySize: 16, lineHeight: 1.85, cardRadius: 16, pillRadius: 20,
  },
};

const DEFAULTS = {
  ...PRESETS.default,
  logoText: "RayPhoneAI",
  navItems: "Claude活用,士業向け,商品開発×AI,副業,プロンプト集",
  stickyHeader: true,
  heroHeadline: "AIを使いたいが\n何から始めれば\nいいかわからない\n方へ。",
  heroSubtext: "商品開発15年×Claude副業月収15万を達成したプロンプト設計士が、現場で本当に使えるAI活用法と業務時短術を届けます。",
  heroCta1: "Claude活用", heroCta2: "士業向け", heroCta3: "商品開発×AI", heroCta4: "副業×AI",
  pillStyle: "filled",
  cardShadow: "subtle", cardHover: "lift",
  alertText: "NEW　税理士・社労士向けClaude活用プロンプト集20本、販売開始しました。→ 2,480円",
  alertVisible: true,
  footerTagline: "プロンプト設計士 Rayphone の公式ブログ",
  footerCopy: "© 2025 RayPhoneAI. All rights reserved.",
  customCss: "",
};

// ───────────────────────────────────────────────
// SIDEBAR UI COMPONENTS
// ───────────────────────────────────────────────

function SLabel({ children }) {
  return (
    <div style={{ fontSize: 10, color: "#888", marginBottom: 5, textTransform: "uppercase", letterSpacing: "0.06em" }}>
      {children}
    </div>
  );
}

function Divider({ label }) {
  return (
    <div style={{ margin: "18px 0 12px", borderTop: "1px solid #2a2a3e", paddingTop: 12, fontSize: 11, color: "#666", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em" }}>
      {label}
    </div>
  );
}

function ColorRow({ label, value, onChange }) {
  return (
    <div style={{ marginBottom: 13 }}>
      <SLabel>{label}</SLabel>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input
          type="color"
          value={value}
          onChange={e => onChange(e.target.value)}
          style={{ width: 36, height: 28, border: "none", background: "none", cursor: "pointer", borderRadius: 4, flexShrink: 0 }}
        />
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          style={{ flex: 1, background: "#2a2a3e", color: "#eee", border: "1px solid #444", borderRadius: 5, padding: "4px 8px", fontSize: 12, fontFamily: "monospace" }}
        />
        <div style={{ width: 22, height: 22, borderRadius: 4, background: value, border: "1px solid #555", flexShrink: 0 }} />
      </div>
    </div>
  );
}

function SelectRow({ label, value, options, onChange }) {
  return (
    <div style={{ marginBottom: 13 }}>
      <SLabel>{label}</SLabel>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{ width: "100%", background: "#2a2a3e", color: "#eee", border: "1px solid #444", borderRadius: 5, padding: "6px 8px", fontSize: 13 }}
      >
        {options.map(o => (
          <option key={o.value || o} value={o.value || o}>{o.label || o}</option>
        ))}
      </select>
    </div>
  );
}

function RangeRow({ label, value, min, max, step = 1, unit = "", onChange }) {
  return (
    <div style={{ marginBottom: 13 }}>
      <SLabel>{label}</SLabel>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <input
          type="range" min={min} max={max} step={step} value={value}
          onChange={e => onChange(parseFloat(e.target.value))}
          style={{ flex: 1 }}
        />
        <span style={{ fontSize: 12, color: "#bbb", minWidth: 44, textAlign: "right", fontFamily: "monospace" }}>
          {value}{unit}
        </span>
      </div>
    </div>
  );
}

function ToggleRow({ label, value, onChange }) {
  return (
    <div style={{ marginBottom: 13, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <span style={{ fontSize: 12, color: "#bbb" }}>{label}</span>
      <div
        onClick={() => onChange(!value)}
        style={{ width: 40, height: 22, borderRadius: 11, background: value ? "#6c63ff" : "#444", cursor: "pointer", position: "relative", transition: "background 0.2s", flexShrink: 0 }}
      >
        <div style={{ position: "absolute", top: 2, left: value ? 20 : 2, width: 18, height: 18, borderRadius: 9, background: "#fff", transition: "left 0.2s", boxShadow: "0 1px 3px rgba(0,0,0,0.3)" }} />
      </div>
    </div>
  );
}

function TextRow({ label, value, onChange, multiline, rows = 3 }) {
  const base = { width: "100%", background: "#2a2a3e", color: "#eee", border: "1px solid #444", borderRadius: 5, padding: "6px 8px", fontSize: 12, boxSizing: "border-box" };
  return (
    <div style={{ marginBottom: 13 }}>
      <SLabel>{label}</SLabel>
      {multiline
        ? <textarea value={value} onChange={e => onChange(e.target.value)} rows={rows} style={{ ...base, resize: "vertical" }} />
        : <input type="text" value={value} onChange={e => onChange(e.target.value)} style={base} />
      }
    </div>
  );
}

// ───────────────────────────────────────────────
// SECTION PANELS
// ───────────────────────────────────────────────

function ColorsPanel({ s, u }) {
  return (
    <div>
      <Divider label="グローバル" />
      <ColorRow label="アクセントカラー" value={s.accentColor} onChange={v => u("accentColor", v)} />
      <Divider label="ヘッダー" />
      <ColorRow label="背景" value={s.headerBg} onChange={v => u("headerBg", v)} />
      <ColorRow label="テキスト / ロゴ" value={s.headerText} onChange={v => u("headerText", v)} />
      <Divider label="ヒーローセクション" />
      <ColorRow label="背景" value={s.heroBg} onChange={v => u("heroBg", v)} />
      <ColorRow label="テキスト" value={s.heroText} onChange={v => u("heroText", v)} />
      <Divider label="本文エリア" />
      <ColorRow label="ページ背景" value={s.pageBg} onChange={v => u("pageBg", v)} />
      <ColorRow label="本文テキスト" value={s.bodyText} onChange={v => u("bodyText", v)} />
      <Divider label="カード・タグ" />
      <ColorRow label="カード背景" value={s.cardBg} onChange={v => u("cardBg", v)} />
      <ColorRow label="カードボーダー" value={s.cardBorder} onChange={v => u("cardBorder", v)} />
      <ColorRow label="タグ背景" value={s.pillBg} onChange={v => u("pillBg", v)} />
      <ColorRow label="タグテキスト" value={s.pillText} onChange={v => u("pillText", v)} />
      <Divider label="フッター" />
      <ColorRow label="背景" value={s.footerBg} onChange={v => u("footerBg", v)} />
      <ColorRow label="テキスト" value={s.footerText} onChange={v => u("footerText", v)} />
    </div>
  );
}

function TypographyPanel({ s, u }) {
  return (
    <div>
      <SelectRow label="見出しフォント" value={s.headingFont} options={FONTS} onChange={v => u("headingFont", v)} />
      <SelectRow label="本文フォント" value={s.bodyFont} options={FONTS} onChange={v => u("bodyFont", v)} />
      <RangeRow label="見出しサイズ" value={s.headingSize} min={22} max={72} unit="px" onChange={v => u("headingSize", v)} />
      <RangeRow label="本文サイズ" value={s.bodySize} min={12} max={22} unit="px" onChange={v => u("bodySize", v)} />
      <RangeRow label="行間" value={s.lineHeight} min={1.4} max={2.2} step={0.05} unit="x" onChange={v => u("lineHeight", parseFloat(v.toFixed(2)))} />
      <div style={{ marginTop: 10, padding: "10px", background: "#1a1a2e", borderRadius: 6 }}>
        <div style={{ fontSize: 10, color: "#666", marginBottom: 6 }}>プレビュー（見出しフォント）</div>
        <div style={{ fontFamily: `'${s.headingFont}', sans-serif`, fontSize: 20, color: "#ddd", lineHeight: 1.3 }}>
          AIを使いたいが
        </div>
        <div style={{ fontFamily: `'${s.bodyFont}', sans-serif`, fontSize: 12, color: "#888", lineHeight: s.lineHeight, marginTop: 6 }}>
          本文フォント ({s.bodyFont}) のサンプルテキストです。
        </div>
      </div>
    </div>
  );
}

function HeaderPanel({ s, u }) {
  return (
    <div>
      <TextRow label="ロゴテキスト" value={s.logoText} onChange={v => u("logoText", v)} />
      <TextRow label="ナビゲーション項目（カンマ区切り）" value={s.navItems} onChange={v => u("navItems", v)} />
      <ToggleRow label="スティッキーヘッダー（スクロール固定）" value={s.stickyHeader} onChange={v => u("stickyHeader", v)} />
      <Divider label="お知らせバー" />
      <ToggleRow label="お知らせバーを表示" value={s.alertVisible} onChange={v => u("alertVisible", v)} />
      <TextRow label="お知らせテキスト" value={s.alertText} onChange={v => u("alertText", v)} multiline rows={2} />
    </div>
  );
}

function HeroPanel({ s, u }) {
  return (
    <div>
      <TextRow label="メインコピー（改行は\\nまたはEnter）" value={s.heroHeadline} onChange={v => u("heroHeadline", v)} multiline rows={4} />
      <TextRow label="サブコピー" value={s.heroSubtext} onChange={v => u("heroSubtext", v)} multiline rows={3} />
      <Divider label="CTAボタン（最大4つ）" />
      <TextRow label="ボタン1" value={s.heroCta1} onChange={v => u("heroCta1", v)} />
      <TextRow label="ボタン2" value={s.heroCta2} onChange={v => u("heroCta2", v)} />
      <TextRow label="ボタン3" value={s.heroCta3} onChange={v => u("heroCta3", v)} />
      <TextRow label="ボタン4" value={s.heroCta4} onChange={v => u("heroCta4", v)} />
      <SelectRow
        label="ボタンスタイル"
        value={s.pillStyle}
        options={[{ value: "filled", label: "塗りつぶし" }, { value: "outline", label: "アウトライン" }]}
        onChange={v => u("pillStyle", v)}
      />
    </div>
  );
}

function CardsPanel({ s, u }) {
  return (
    <div>
      <RangeRow label="カード角丸" value={s.cardRadius} min={0} max={32} unit="px" onChange={v => u("cardRadius", v)} />
      <RangeRow label="タグ角丸" value={s.pillRadius} min={0} max={24} unit="px" onChange={v => u("pillRadius", v)} />
      <SelectRow
        label="カードシャドウ"
        value={s.cardShadow}
        options={[{ value: "none", label: "なし" }, { value: "subtle", label: "控えめ" }, { value: "strong", label: "強め" }]}
        onChange={v => u("cardShadow", v)}
      />
      <SelectRow
        label="ホバーエフェクト"
        value={s.cardHover}
        options={[
          { value: "none", label: "なし" },
          { value: "lift", label: "浮き上がり" },
          { value: "glow", label: "グロー" },
          { value: "border", label: "ボーダー強調" },
        ]}
        onChange={v => u("cardHover", v)}
      />
    </div>
  );
}

function FooterPanel({ s, u }) {
  return (
    <div>
      <TextRow label="タグライン" value={s.footerTagline} onChange={v => u("footerTagline", v)} />
      <TextRow label="コピーライト" value={s.footerCopy} onChange={v => u("footerCopy", v)} />
    </div>
  );
}

function CSSPanel({ s, u }) {
  return (
    <div>
      <SLabel>カスタムCSS（theme.cssの末尾に追加されます）</SLabel>
      <textarea
        value={s.customCss}
        onChange={e => u("customCss", e.target.value)}
        placeholder={`.my-element {\n  color: red;\n  font-size: 18px;\n}`}
        rows={12}
        style={{
          width: "100%", background: "#0f0f1e", color: "#a8e6cf", border: "1px solid #444",
          borderRadius: 6, padding: "10px", fontSize: 11, fontFamily: "monospace",
          boxSizing: "border-box", resize: "vertical", lineHeight: 1.6,
        }}
      />
    </div>
  );
}

// ───────────────────────────────────────────────
// SITE PREVIEW
// ───────────────────────────────────────────────

function SitePreview({ s }) {
  const articles = [
    { cat: "Claude活用", title: "税理士がClaude活用で業務を30%削減できた3つのプロンプト", date: "2025.01.15" },
    { cat: "士業向け", title: "社労士向けClaude完全ガイド：就業規則作成を自動化する方法", date: "2025.01.12" },
    { cat: "副業×AI", title: "Claude副業で月収15万達成：プロンプト設計士になるまでの道のり", date: "2025.01.10" },
    { cat: "商品開発×AI", title: "商品開発担当者のためのClaude活用：企画書を10分で生成する方法", date: "2025.01.08" },
  ];

  const nav = s.navItems ? s.navItems.split(",").map(n => n.trim()).filter(Boolean) : [];
  const cardShadow = s.cardShadow === "none" ? "none" : s.cardShadow === "subtle" ? "0 2px 10px rgba(0,0,0,0.07)" : "0 4px 24px rgba(0,0,0,0.14)";
  const ctaBg = s.pillStyle === "filled" ? s.accentColor : "transparent";
  const ctaColor = s.pillStyle === "filled" ? "#ffffff" : s.accentColor;
  const ctaBorder = `2px solid ${s.accentColor}`;
  const accent33 = s.accentColor + "33";
  const accent55 = s.accentColor + "55";

  return (
    <div style={{ fontFamily: `'${s.bodyFont}', 'Noto Sans JP', sans-serif`, background: s.pageBg, color: s.bodyText, fontSize: s.bodySize }}>

      {/* Header */}
      <header style={{ background: s.headerBg, padding: "0 24px", height: 54, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ color: s.headerText, fontFamily: `'${s.headingFont}', sans-serif`, fontWeight: 800, fontSize: 18, letterSpacing: "-0.03em" }}>
          {s.logoText}
        </span>
        <div style={{ display: "flex", gap: 18, alignItems: "center" }}>
          {nav.map(n => (
            <span key={n} style={{ color: s.headerText, fontSize: 12, opacity: 0.82, cursor: "pointer" }}>{n}</span>
          ))}
        </div>
      </header>

      {/* Alert bar */}
      {s.alertVisible && (
        <div style={{ background: s.accentColor, color: "#fff", padding: "7px 20px", fontSize: 12, textAlign: "center" }}>
          {s.alertText}
        </div>
      )}

      {/* Hero */}
      <section style={{ background: s.heroBg, padding: "60px 32px", textAlign: "center" }}>
        <h1 style={{
          fontFamily: `'${s.headingFont}', sans-serif`, fontSize: s.headingSize, fontWeight: 800,
          color: s.heroText, lineHeight: 1.25, marginBottom: 22, whiteSpace: "pre-line",
          letterSpacing: "-0.03em",
        }}>
          {s.heroHeadline}
        </h1>
        <p style={{ color: s.heroText, opacity: 0.65, fontSize: Math.max(s.bodySize - 1, 13), maxWidth: 520, margin: "0 auto 32px", lineHeight: s.lineHeight }}>
          {s.heroSubtext}
        </p>
        <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
          {[s.heroCta1, s.heroCta2, s.heroCta3, s.heroCta4].filter(Boolean).map(cta => (
            <button key={cta} style={{
              padding: "9px 20px", borderRadius: s.pillRadius, border: ctaBorder,
              background: ctaBg, color: ctaColor, cursor: "pointer", fontSize: 13,
              fontFamily: "inherit", fontWeight: 600,
            }}>{cta}</button>
          ))}
        </div>
      </section>

      {/* Featured articles */}
      <section style={{ padding: "40px 24px 10px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 20 }}>
          <h2 style={{ fontFamily: `'${s.headingFont}', sans-serif`, fontSize: 14, fontWeight: 700, color: s.bodyText, letterSpacing: "0.1em" }}>FEATURED</h2>
          <span style={{ fontSize: 12, color: s.accentColor, cursor: "pointer" }}>すべて見る →</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          {articles.slice(0, 3).map(a => (
            <div key={a.title} style={{ background: s.cardBg, border: `1px solid ${s.cardBorder}`, borderRadius: s.cardRadius, overflow: "hidden", cursor: "pointer", boxShadow: cardShadow }}>
              <div style={{ height: 96, background: `linear-gradient(135deg, ${accent33}, ${accent55})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24, opacity: 0.7 }}>
                📝
              </div>
              <div style={{ padding: "12px 14px" }}>
                <span style={{ fontSize: 10, padding: "3px 9px", borderRadius: s.pillRadius, background: s.pillBg, color: s.pillText, display: "inline-block", marginBottom: 8, fontWeight: 600 }}>
                  {a.cat}
                </span>
                <p style={{ fontSize: 12, color: s.bodyText, margin: "0 0 8px", lineHeight: 1.5, fontWeight: 500 }}>{a.title}</p>
                <span style={{ fontSize: 11, color: "#999" }}>{a.date}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Latest articles */}
      <section style={{ padding: "30px 24px" }}>
        <h2 style={{ fontFamily: `'${s.headingFont}', sans-serif`, fontSize: 14, fontWeight: 700, color: s.bodyText, letterSpacing: "0.1em", marginBottom: 16 }}>LATEST ARTICLES</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {articles.map(a => (
            <div key={a.title} style={{
              display: "flex", gap: 14, alignItems: "flex-start",
              padding: "12px 14px", background: s.cardBg, border: `1px solid ${s.cardBorder}`,
              borderRadius: Math.min(s.cardRadius, 10), cursor: "pointer", boxShadow: cardShadow,
            }}>
              <div style={{ width: 72, height: 52, background: `linear-gradient(135deg, ${accent33}, ${accent55})`, borderRadius: 6, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>📝</div>
              <div style={{ flex: 1 }}>
                <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: s.pillRadius, background: s.pillBg, color: s.pillText, display: "inline-block", marginBottom: 5 }}>{a.cat}</span>
                <p style={{ fontSize: 12, color: s.bodyText, margin: "0 0 4px", fontWeight: 500, lineHeight: 1.4 }}>{a.title}</p>
                <span style={{ fontSize: 10, color: "#999" }}>{a.date}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Note CTA sidebar-style strip */}
      <section style={{ margin: "0 24px 30px", padding: "20px 24px", background: `linear-gradient(135deg, ${accent33}, ${accent55})`, borderRadius: s.cardRadius, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontFamily: `'${s.headingFont}', sans-serif`, fontWeight: 700, fontSize: 14, color: s.bodyText, marginBottom: 4 }}>{s.logoText}<br/>プロンプト集</div>
          <div style={{ fontSize: 11, color: s.bodyText, opacity: 0.7 }}>現場で即使えるAI活用プロンプト集を販売中。</div>
        </div>
        <button style={{ padding: "8px 16px", borderRadius: s.pillRadius, background: s.accentColor, color: "#fff", border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
          note で購入
        </button>
      </section>

      {/* Footer */}
      <footer style={{ background: s.footerBg, padding: "36px 28px", color: s.footerText }}>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 28, marginBottom: 28 }}>
          <div>
            <div style={{ fontFamily: `'${s.headingFont}', sans-serif`, fontWeight: 800, fontSize: 17, marginBottom: 8 }}>{s.logoText}</div>
            <div style={{ fontSize: 11, opacity: 0.6, marginBottom: 8 }}>{s.footerTagline}</div>
            <p style={{ fontSize: 11, opacity: 0.55, lineHeight: 1.7 }}>商品開発15年×Claude副業のプロンプト設計士Rayphoneが運営するAI活用メディア。</p>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, marginBottom: 10, opacity: 0.45, textTransform: "uppercase", letterSpacing: "0.06em" }}>記事カテゴリ</div>
            {["Claude活用Tips", "士業向けAI活用", "商品開発×AI", "副業×AI"].map(c => (
              <div key={c} style={{ fontSize: 11, marginBottom: 7, opacity: 0.65, cursor: "pointer" }}>{c}</div>
            ))}
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, marginBottom: 10, opacity: 0.45, textTransform: "uppercase", letterSpacing: "0.06em" }}>SNS・リンク</div>
            {["X (@rayphone_prompt)", "note", "プロフィール", "お問い合わせ"].map(c => (
              <div key={c} style={{ fontSize: 11, marginBottom: 7, opacity: 0.65, cursor: "pointer" }}>{c}</div>
            ))}
          </div>
        </div>
        <div style={{ borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: 18, fontSize: 11, opacity: 0.4, textAlign: "center" }}>
          {s.footerCopy} &nbsp;|&nbsp; Powered by Claude × Rayphone
        </div>
      </footer>
    </div>
  );
}

// ───────────────────────────────────────────────
// CSS GENERATOR
// ───────────────────────────────────────────────

function generateCSS(s) {
  const allFonts = [...new Set([s.headingFont, s.bodyFont])];
  const fontQuery = allFonts.map(f => `family=${f.replace(/ /g, "+")}:wght@400;500;700;800`).join("&");

  const cardShadowCSS =
    s.cardShadow === "none" ? "none" :
    s.cardShadow === "subtle" ? "0 2px 10px rgba(0,0,0,0.07)" :
    "0 4px 24px rgba(0,0,0,0.14)";

  const hoverCSS =
    s.cardHover === "lift" ? "transform: translateY(-4px) !important; box-shadow: 0 8px 28px rgba(0,0,0,0.14) !important;" :
    s.cardHover === "glow" ? `box-shadow: 0 0 24px ${s.accentColor}50 !important;` :
    s.cardHover === "border" ? `outline: 2px solid ${s.accentColor} !important;` :
    "";

  return `/* ============================================================
   RayPhoneAI Theme CSS
   Generated by Design Manager
   Date: ${new Date().toLocaleString("ja-JP")}
   ============================================================ */

@import url('https://fonts.googleapis.com/css2?${fontQuery}&display=swap');

/* ── CSS カスタムプロパティ ───────────────────── */
:root {
  --ray-accent:        ${s.accentColor};
  --ray-header-bg:     ${s.headerBg};
  --ray-header-text:   ${s.headerText};
  --ray-hero-bg:       ${s.heroBg};
  --ray-hero-text:     ${s.heroText};
  --ray-page-bg:       ${s.pageBg};
  --ray-body-text:     ${s.bodyText};
  --ray-card-bg:       ${s.cardBg};
  --ray-card-border:   ${s.cardBorder};
  --ray-pill-bg:       ${s.pillBg};
  --ray-pill-text:     ${s.pillText};
  --ray-footer-bg:     ${s.footerBg};
  --ray-footer-text:   ${s.footerText};
  --ray-heading-font:  '${s.headingFont}', 'Noto Sans JP', sans-serif;
  --ray-body-font:     '${s.bodyFont}', 'Noto Sans JP', sans-serif;
  --ray-heading-size:  ${s.headingSize}px;
  --ray-body-size:     ${s.bodySize}px;
  --ray-line-height:   ${s.lineHeight};
  --ray-card-radius:   ${s.cardRadius}px;
  --ray-pill-radius:   ${s.pillRadius}px;
}

/* ── ベース ──────────────────────────────────── */
body {
  background-color: var(--ray-page-bg) !important;
  color: var(--ray-body-text) !important;
  font-family: var(--ray-body-font) !important;
  font-size: var(--ray-body-size) !important;
  line-height: var(--ray-line-height) !important;
}

h1, h2, h3, h4, h5 {
  font-family: var(--ray-heading-font) !important;
}

h1 { font-size: var(--ray-heading-size) !important; }

a { color: var(--ray-accent) !important; }

/* ── ヘッダー ────────────────────────────────── */
header, nav, .header, [class*="header-"] {
  background-color: var(--ray-header-bg) !important;
  color: var(--ray-header-text) !important;
  ${s.stickyHeader ? "position: sticky !important;\n  top: 0 !important;\n  z-index: 100 !important;" : ""}
}

header a, nav a, .header a {
  color: var(--ray-header-text) !important;
}

.logo, [class*="logo"], [class*="brand"] {
  font-family: var(--ray-heading-font) !important;
  color: var(--ray-header-text) !important;
}

/* ── お知らせバー ─────────────────────────────── */
.announcement, .alert-bar, [class*="announce"], [class*="notice"] {
  background-color: var(--ray-accent) !important;
  color: #ffffff !important;
}

/* ── ヒーローセクション ───────────────────────── */
.hero, [class*="hero"] {
  background-color: var(--ray-hero-bg) !important;
  color: var(--ray-hero-text) !important;
}

.hero h1, .hero h2, .hero .headline, [class*="hero"] h1 {
  font-family: var(--ray-heading-font) !important;
  font-size: var(--ray-heading-size) !important;
  color: var(--ray-hero-text) !important;
}

/* ── カテゴリタグ / ピル ──────────────────────── */
.tag, .pill, .badge, .category-tag, [class*="-tag"], [class*="-pill"], [class*="-badge"], [class*="category"] {
  background-color: var(--ray-pill-bg) !important;
  color: var(--ray-pill-text) !important;
  border-radius: var(--ray-pill-radius) !important;
  ${s.pillStyle === "outline" ? "background-color: transparent !important;\n  border: 1.5px solid var(--ray-pill-text) !important;" : ""}
}

/* ── ボタン ───────────────────────────────────── */
button[class*="primary"], .btn-primary, .cta-btn, [class*="button-primary"] {
  background-color: var(--ray-accent) !important;
  border-color: var(--ray-accent) !important;
  color: #ffffff !important;
}

/* ── カード ───────────────────────────────────── */
.card, .article-card, .post-card, [class*="-card"] {
  background-color: var(--ray-card-bg) !important;
  border-color: var(--ray-card-border) !important;
  border-radius: var(--ray-card-radius) !important;
  box-shadow: ${cardShadowCSS} !important;
  transition: transform 0.2s ease, box-shadow 0.2s ease, outline 0.2s ease !important;
}

.card:hover, .article-card:hover, .post-card:hover, [class*="-card"]:hover {
  ${hoverCSS}
}

/* ── フッター ────────────────────────────────── */
footer, .footer, [class*="footer"] {
  background-color: var(--ray-footer-bg) !important;
  color: var(--ray-footer-text) !important;
}

footer a, .footer a {
  color: var(--ray-footer-text) !important;
  opacity: 0.8;
}
${s.customCss ? `\n/* ── カスタムCSS ─────────────────────────────── */\n${s.customCss}\n` : ""}
/* ============================================================ */
`;
}

// ───────────────────────────────────────────────
// MAIN APP
// ───────────────────────────────────────────────

const SECTIONS = [
  { id: "colors",  label: "🎨  カラースキーム", Panel: ColorsPanel },
  { id: "typo",    label: "✍️  タイポグラフィ", Panel: TypographyPanel },
  { id: "header",  label: "📌  ヘッダー",       Panel: HeaderPanel },
  { id: "hero",    label: "⭐  ヒーロー",        Panel: HeroPanel },
  { id: "cards",   label: "📄  記事カード",      Panel: CardsPanel },
  { id: "footer",  label: "🔗  フッター",        Panel: FooterPanel },
  { id: "css",     label: "💻  カスタムCSS",     Panel: CSSPanel },
];

export default function DesignManager() {
  const [s, setS] = useState(() => {
    try {
      const saved = localStorage.getItem("rayphone_dm_settings");
      return saved ? { ...DEFAULTS, ...JSON.parse(saved) } : { ...DEFAULTS };
    } catch { return { ...DEFAULTS }; }
  });

  const [activeSection, setActiveSection] = useState("colors");
  const [mode, setMode] = useState("desktop");
  const [token, setToken] = useState(() => localStorage.getItem("rayphone_dm_token") || "");
  const [status, setStatus] = useState(null);
  const [pushing, setPushing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  const u = useCallback((key, val) => {
    setS(prev => {
      const next = { ...prev, [key]: val };
      try { localStorage.setItem("rayphone_dm_settings", JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  useEffect(() => {
    try { localStorage.setItem("rayphone_dm_token", token); } catch {}
  }, [token]);

  const applyPreset = (key) => {
    const next = { ...s, ...PRESETS[key] };
    setS(next);
    try { localStorage.setItem("rayphone_dm_settings", JSON.stringify(next)); } catch {}
    setStatus({ type: "info", msg: `✓ プリセット「${PRESETS[key].name}」を適用しました` });
    setTimeout(() => setStatus(null), 2000);
  };

  const copyCSS = async () => {
    try {
      await navigator.clipboard.writeText(generateCSS(s));
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    } catch {
      setStatus({ type: "error", msg: "コピーに失敗しました" });
    }
  };

  const pushToGitHub = async () => {
    if (!token.trim()) {
      setStatus({ type: "error", msg: "GitHub Tokenを入力してください" });
      return;
    }
    setPushing(true);
    setStatus({ type: "info", msg: "⏳ GitHubに接続中..." });
    try {
      const css = generateCSS(s);
      const owner = "rayphoneai", repo = "ray", path = "theme.css";
      let sha = null;
      try {
        const r = await fetch(`https://api.github.com/repos/${owner}/${repo}/contents/${path}`, {
          headers: { Authorization: `token ${token}`, Accept: "application/vnd.github+json" },
        });
        if (r.ok) sha = (await r.json()).sha;
      } catch {}

      const encoded = btoa(unescape(encodeURIComponent(css)));
      const body = {
        message: `[Design Manager] テーマ更新 ${new Date().toLocaleString("ja-JP")}`,
        content: encoded,
        ...(sha ? { sha } : {}),
      };
      const r = await fetch(`https://api.github.com/repos/${owner}/${repo}/contents/${path}`, {
        method: "PUT",
        headers: { Authorization: `token ${token}`, "Content-Type": "application/json", Accept: "application/vnd.github+json" },
        body: JSON.stringify(body),
      });
      if (r.ok) {
        setStatus({ type: "success", msg: "✓ theme.css をGitHubに反映しました！\n\nあとはindex.htmlに以下を追加:\n<link rel=\"stylesheet\" href=\"./theme.css\">" });
      } else {
        const e = await r.json();
        setStatus({ type: "error", msg: `エラー: ${e.message}` });
      }
    } catch (e) {
      setStatus({ type: "error", msg: `通信エラー: ${e.message}` });
    } finally {
      setPushing(false);
    }
  };

  const resetSettings = () => {
    setS({ ...DEFAULTS });
    try { localStorage.removeItem("rayphone_dm_settings"); } catch {}
  };

  const statusColors = {
    success: { bg: "#064e3b", text: "#6ee7b7" },
    error:   { bg: "#7f1d1d", text: "#fca5a5" },
    info:    { bg: "#1e3a5f", text: "#93c5fd" },
  };

  const previewMaxW = mode === "mobile" ? 390 : mode === "tablet" ? 768 : "100%";

  return (
    <div style={{ display: "flex", minHeight: 740, background: "#e8e8f0", fontFamily: "system-ui, -apple-system, sans-serif" }}>

      {/* ═══════════════════════════════════════ SIDEBAR */}
      <aside style={{ width: 290, background: "#12121f", display: "flex", flexDirection: "column", flexShrink: 0, overflow: "hidden" }}>

        {/* Title bar */}
        <div style={{ padding: "14px 16px", background: "#0a0a16", borderBottom: "1px solid #252535" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 30, height: 30, borderRadius: 8, background: "linear-gradient(135deg, #6c63ff, #a78bfa)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15 }}>🎨</div>
            <div>
              <div style={{ fontWeight: 800, fontSize: 14, color: "#fff", letterSpacing: "-0.03em" }}>Design Manager</div>
              <div style={{ fontSize: 10, color: "#555" }}>RayPhoneAI テーマ設定</div>
            </div>
          </div>
        </div>

        {/* Preset themes */}
        <div style={{ padding: "12px 14px", borderBottom: "1px solid #252535" }}>
          <div style={{ fontSize: 10, color: "#666", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.06em" }}>テーマプリセット</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
            {Object.entries(PRESETS).map(([key, p]) => (
              <button
                key={key}
                onClick={() => applyPreset(key)}
                style={{ padding: "7px 4px", borderRadius: 7, border: "1px solid #333", background: p.headerBg, color: p.headerText, cursor: "pointer", fontSize: 10, textAlign: "center", overflow: "hidden", transition: "opacity 0.15s" }}
                title={p.name}
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>

        {/* Section accordion */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {SECTIONS.map(({ id, label, Panel }) => (
            <div key={id} style={{ borderBottom: "1px solid #1c1c2a" }}>
              <button
                onClick={() => setActiveSection(activeSection === id ? null : id)}
                style={{
                  width: "100%", padding: "11px 16px", background: activeSection === id ? "#1e1e38" : "transparent",
                  color: activeSection === id ? "#fff" : "#888", border: "none", cursor: "pointer",
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  fontSize: 13, textAlign: "left",
                  borderLeft: `3px solid ${activeSection === id ? "#6c63ff" : "transparent"}`,
                  transition: "all 0.15s",
                }}
              >
                <span>{label}</span>
                <span style={{ fontSize: 9, opacity: 0.5 }}>{activeSection === id ? "▲" : "▼"}</span>
              </button>
              {activeSection === id && (
                <div style={{ padding: "14px 16px 8px", background: "#18182a" }}>
                  <Panel s={s} u={u} />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Export panel */}
        <div style={{ padding: "14px 14px", background: "#0a0a16", borderTop: "1px solid #252535", flexShrink: 0 }}>
          <div style={{ fontSize: 10, color: "#555", marginBottom: 9, textTransform: "uppercase", letterSpacing: "0.06em" }}>エクスポート / 反映</div>

          <button
            onClick={copyCSS}
            style={{
              width: "100%", padding: "9px 12px", marginBottom: 8, borderRadius: 7,
              background: copied ? "#059669" : "#6c63ff", color: "#fff", border: "none",
              cursor: "pointer", fontSize: 13, fontWeight: 700, transition: "background 0.25s",
            }}
          >
            {copied ? "✓ コピーしました！" : "📋 CSSをコピー"}
          </button>

          <div style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>GitHub Token（repo 権限）</div>
          <input
            type="password" value={token} onChange={e => setToken(e.target.value)}
            placeholder="ghp_xxxxxxxxxxxx"
            style={{ width: "100%", padding: "6px 10px", borderRadius: 6, border: "1px solid #333", background: "#1e1e30", color: "#ddd", fontSize: 12, marginBottom: 8, boxSizing: "border-box" }}
          />

          <button
            onClick={pushToGitHub}
            disabled={pushing}
            style={{
              width: "100%", padding: "9px 12px", borderRadius: 7,
              background: pushing ? "#333" : "#059669", color: pushing ? "#666" : "#fff",
              border: "none", cursor: pushing ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 700,
            }}
          >
            {pushing ? "⏳ 反映中..." : "🚀 GitHubに反映"}
          </button>

          {status && (
            <div style={{
              marginTop: 8, fontSize: 11, padding: "9px 10px", borderRadius: 6, whiteSpace: "pre-line",
              background: (statusColors[status.type] || statusColors.info).bg,
              color: (statusColors[status.type] || statusColors.info).text,
              lineHeight: 1.55,
            }}>
              {status.msg}
            </div>
          )}

          <button
            onClick={() => setShowHelp(!showHelp)}
            style={{ width: "100%", padding: "7px", marginTop: 8, borderRadius: 6, border: "1px solid #2a2a3e", background: "transparent", color: "#555", cursor: "pointer", fontSize: 11 }}
          >
            {showHelp ? "▲ 使い方を閉じる" : "❓ 使い方"}
          </button>

          {showHelp && (
            <div style={{ marginTop: 7, fontSize: 10.5, color: "#888", lineHeight: 1.7, background: "#16162a", padding: 10, borderRadius: 6, borderLeft: "3px solid #6c63ff" }}>
              <strong style={{ color: "#aaa" }}>【手順】</strong><br />
              1. 左パネルでデザインを設定<br />
              2.「CSSをコピー」→ <code style={{ color: "#7dd3fc" }}>theme.css</code> として保存<br />
              3. GitHubにアップロード<br />
              &nbsp;&nbsp; または「GitHubに反映」で自動プッシュ<br />
              4. <code style={{ color: "#7dd3fc" }}>index.html</code> の <code>&lt;head&gt;</code> 内に追加:<br />
              <code style={{ color: "#a8e6cf", fontSize: 10 }}>&lt;link rel="stylesheet" href="./theme.css"&gt;</code>
            </div>
          )}
        </div>
      </aside>

      {/* ═══════════════════════════════════════ PREVIEW */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>

        {/* Toolbar */}
        <div style={{ padding: "10px 20px", background: "#fff", borderBottom: "1px solid #e5e5e5", display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: "#333", marginRight: 4 }}>ライブプレビュー</span>
          {[
            { id: "desktop", label: "🖥 PC" },
            { id: "tablet",  label: "⬜ タブレット" },
            { id: "mobile",  label: "📱 SP" },
          ].map(m => (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              style={{
                padding: "5px 14px", borderRadius: 6, fontSize: 12, cursor: "pointer",
                border: `1px solid ${mode === m.id ? "#6c63ff" : "#ddd"}`,
                background: mode === m.id ? "#6c63ff" : "#f9f9f9",
                color: mode === m.id ? "#fff" : "#666", fontWeight: mode === m.id ? 600 : 400,
              }}
            >
              {m.label}
            </button>
          ))}
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 11, color: "#bbb" }}>設定は自動保存</span>
            <button
              onClick={resetSettings}
              style={{ padding: "5px 12px", borderRadius: 6, fontSize: 11, border: "1px solid #e0e0e0", background: "#fff", color: "#999", cursor: "pointer" }}
            >
              リセット
            </button>
          </div>
        </div>

        {/* Preview frame */}
        <div style={{ flex: 1, overflowY: "auto", padding: 24, background: "#dde0ea" }}>
          <div style={{
            maxWidth: previewMaxW,
            margin: "0 auto",
            boxShadow: "0 10px 50px rgba(0,0,0,0.2)",
            borderRadius: 10,
            overflow: "hidden",
            transition: "max-width 0.3s ease",
          }}>
            <SitePreview s={s} />
          </div>
          {mode !== "desktop" && (
            <div style={{ textAlign: "center", marginTop: 12, fontSize: 11, color: "#aaa" }}>
              {mode === "mobile" ? "390px（iPhone 14）" : "768px（iPad）"}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
