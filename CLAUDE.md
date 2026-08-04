# AI Daily News

## プロジェクト概要
平日の毎朝 GitHub Actions で AI ニュースを自動収集・要約し、GitHub Pages で公開。
7:45 JST に ntfy でスマホ通知。土日・日本の祝日はスキップ。
**※ 2026-06-08 から毎朝の自動実行は停止中（Gemini 有料化のため）。現在は手動起動のみ。**

## 技術構成
- **自動実行**: GitHub Actions (cron: 平日 7:30 JST) — **現在は schedule をコメントアウトして停止中・workflow_dispatch の手動起動のみ**
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

## 並行タブ（自動 worktree）運用（2026-08-04 導入）

同じフォルダで2本目の Claude Code を素の `claude` で起動すると、自動で worktree（隔離された作業コピー・`.claude/worktrees/<名前>/`）で起動する（仕組みの真実源: kyowakoku リポ `scripts/claude-wrapper.sh`／運用の詳細: kyowakoku `.claude/rules/workflow.md` §14）。このリポは `.claude/rules/` を持たない小さな構成のため、合流手順はこの CLAUDE.md に置く。

- **worktree から見える中身は「最後に push された main」**。母艦タブの未 push コミットは見えない（続きをやるなら先に母艦で push）
- **memory は見えない**（worktree は別プロジェクト扱いのため）。真実源はこの CLAUDE.md と git 管理ファイルで完結させる
- **サブエージェント等の上限は母艦タブと合算で守る**（kyowakoku 基準: サブエージェント4・重い並列監査2。WSL のメモリ枯渇防止）
- `.worktreeinclude`（git 管理外ファイルの持ち込み指定）: 持ち込み必須の git 管理外ファイルは無しと実測（2026-08-04）のため作らない
- 公開は GitHub Actions（`daily-news.yml`）が docs/ を gh-pages ブランチへ反映する方式で、**現在は手動起動（workflow_dispatch）のみ・main へ push しただけでは公開されない**。自動実行を再開した後はリモートが Actions で動きうるため、下記手順 2 の取り込みを省略しない

### 終了合図の手順（すべて worktree 内で完結・母艦の作業ツリーに触らない）
1. 通常どおり commit
2. `git fetch origin && git merge origin/main`（main の最新を取り込む。**衝突したら自己解決せずユーザーに相談**）
3. `git push origin HEAD:main`（これで main へ合流。non-fast-forward で**拒否されたら 2 からやり直す。force は使わない**）
4. worktree の削除はタブを閉じるときに Claude Code 自身が確認してくる（合流済みなら「削除」でよい）

### 母艦側の帳尻合わせ
- worktree の push 後、母艦に未 push コミットがあると main が分岐する。**マージ（`git pull --no-rebase origin main`）で取り込む**
- 残骸 worktree の掃除（母艦で）: ①先に母艦を pull ②`git log main..worktree-<名前>` で未合流コミットなしを確認 ③`git -C .claude/worktrees/<名前> status` で未コミットの作業中ファイルが無いことも確認 ④ユーザーに一言伝えてから `git worktree remove .claude/worktrees/<名前>` → `git branch -d worktree-<名前>`
