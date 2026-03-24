# AI Daily News

## プロジェクト概要
平日の毎朝 GitHub Actions で AI ニュースを自動収集・要約し、GitHub Pages で公開。
7:45 JST に ntfy でスマホ通知。土日・日本の祝日はスキップ。

## 技術構成
- **自動実行**: GitHub Actions (cron: 平日 7:30 JST)
- **ニュース収集**: Python + feedparser (RSS)
- **要約**: Google Gemini API (gemini-2.0-flash, 無料枠)
- **祝日判定**: jpholiday
- **公開**: GitHub Pages (docs/ ディレクトリ)
- **通知**: ntfy (7:45 JST)

## ディレクトリ構成
```
.github/workflows/daily-news.yml  # GitHub Actions ワークフロー
scripts/fetch_and_summarize.py     # メインスクリプト
docs/index.html                    # 最新ニュース（GitHub Pages）
docs/YYYY-MM-DD.html              # 日付別アーカイブ
docs/archive.html                  # アーカイブ一覧
```

## 重要度システム
各ニュースに A〜E の重要度を独立付与（同ランク複数可）。
- A: 業界激震（年数回レベル）
- B: 主要サービスの大きな新機能
- C: 注目すべき動き
- D: 知っておくと良い
- E: 参考情報（ニュース不足の日のみ）
基本は D 以上で 5 件。

## 開発ルール
- RSS フィードの追加・変更 → `RSS_FEEDS` リスト
- HTML テンプレート → `HTML_TEMPLATE` 変数内（外部ファイル化しない）
- Gemini モデル変更 → `summarize_with_gemini()` 内の `GenerativeModel()`
- 出力件数 → `TOP_N`
- 通知時刻 → `NOTIFY_HOUR`, `NOTIFY_MINUTE`

## Secrets（GitHub に登録が必要）
- `GEMINI_API_KEY`: Google Gemini API キー
- `NTFY_TOPIC`: ntfy のトピック名
- `PAGES_URL`: GitHub Pages の URL
