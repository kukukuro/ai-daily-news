# AI Daily News

毎朝 7:30 (JST) に AI 関連ニュースを自動収集・要約し、GitHub Pages で公開。
7:45 にスマホへプッシュ通知を送信するシステム。
土日・日本の祝日は自動スキップ。

## 仕組み

```
GitHub Actions (平日 7:30 JST に自動実行)
  → Python が RSS フィードを巡回し記事収集
  → Gemini API で要約・重要度 (A〜E) 付け
  → HTML を生成 → GitHub Pages にデプロイ
  → 7:45 JST まで待機 → ntfy でスマホに通知
```

## 重要度の基準

| ランク | 意味 | 例 |
|--------|------|----|
| A | 業界激震 | Claude Opus 級のメジャーリリース、GPT 世代交代 |
| B | 重要 | 新モデル公開、大型機能追加 |
| C | 注目 | 大型資金調達、重要な提携、規制導入 |
| D | 参考 | 小規模アップデート、業界トレンド |
| E | 小ネタ | 周辺ニュース（ニュースが少ない日のみ） |

## セットアップ手順

### 1. Gemini API キーの取得

1. [Google AI Studio](https://aistudio.google.com/apikey) にアクセス
2. Google アカウントでログイン
3. 「API キーを作成」をクリック
4. 表示されたキーを控えておく

> 無料枠: 1 日 1,500 リクエスト。1 日 1 回なので余裕です。

### 2. ntfy アプリのセットアップ（スマホ通知）

1. スマホに ntfy アプリをインストール
   - [iOS (App Store)](https://apps.apple.com/app/ntfy/id1625396347)
   - [Android (Google Play)](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
2. アプリを開き、右下の「+」ボタンをタップ
3. トピック名を入力（例: `ai-news-gunji-2026`）
   - 推測されにくい名前にすること（これがセキュリティになる）
4. 「Subscribe」をタップ

### 3. GitHub リポジトリの作成

```bash
# WSL2 環境で実行
cd ~/projects
# このフォルダを配置した後
cd ai-daily-news
git init
git add .
git commit -m "初回セットアップ"
git remote add origin git@github.com:mtinlet001-arch/ai-daily-news.git
git push -u origin main
```

### 4. GitHub Secrets の登録

リポジトリの Settings → Secrets and variables → Actions で以下を登録:

| Name | 値 |
|------|-----|
| `GEMINI_API_KEY` | 手順 1 で取得した API キー |
| `NTFY_TOPIC` | 手順 2 で設定したトピック名 |
| `PAGES_URL` | `https://mtinlet001-arch.github.io/ai-daily-news/` |

### 5. GitHub Pages の有効化

1. Settings → Pages を開く
2. Source を **GitHub Actions** に設定

### 6. 動作確認（手動実行）

1. Actions タブを開く
2. 「Daily AI News」を選択
3. 「Run workflow」をクリック
4. 実行完了後、Pages の URL にアクセスして確認
5. スマホに ntfy 通知が届いていることを確認

## 日常の使い方

- 平日の朝、スマホに通知が届く
- 通知をタップ → ブラウザで詳細を読む
- または直接 URL をブックマークして開く
- 過去のニュースはページ下部の「過去のニュース」リンクから

### スマホのホーム画面に追加（おすすめ）

- **iPhone**: Safari で URL を開く → 共有ボタン → 「ホーム画面に追加」
- **Android**: Chrome で URL を開く → メニュー → 「ホーム画面に追加」

## カスタマイズ

### ニュースソースの追加・変更

`scripts/fetch_and_summarize.py` の `RSS_FEEDS` リストを編集。

### 表示件数の変更

同ファイルの `TOP_N` を変更（デフォルト: 5）。

### 通知時刻の変更

同ファイルの `NOTIFY_HOUR`, `NOTIFY_MINUTE` を変更。

### 生成時刻の変更

`.github/workflows/daily-news.yml` の cron 式を変更。
時刻は UTC で指定（JST から 9 時間引く）。

```yaml
# 例: 毎朝 8:00 JST = 23:00 UTC (前日)
- cron: '0 23 * * 0-4'
```

## トラブルシューティング

### Actions が動かない

- Settings → Actions → General で「Allow all actions」が有効か確認
- Secrets が正しく登録されているか確認

### ページが更新されない

- Actions タブで最新のログを確認
- Pages の Source が「GitHub Actions」になっているか確認

### 通知が届かない

- ntfy アプリでトピック名が Secrets と一致しているか確認
- アプリの通知権限がオンになっているか確認
- Actions のログで ntfy 送信ステップのエラーを確認

### 祝日にスキップされない

- `jpholiday` ライブラリは天皇誕生日等の振替休日にも対応しています
- 特殊な休日（年末年始の会社休日など）はカバーしません
