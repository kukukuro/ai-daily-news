"""
AI Daily News - ニュース収集・要約スクリプト

毎朝 RSS フィードから AI 関連ニュースを収集し、
Gemini API で要約・重要度付けして HTML を生成する。
生成後、7:45 JST まで待ってから ntfy でスマホ通知を送信する。
日本の祝日はスキップする。
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from string import Template

import feedparser
from google import genai
import jpholiday

# ============================================================
# 設定
# ============================================================

TOP_N = 5  # 出力するニュース件数

JST = timezone(timedelta(hours=9))

# 通知を送信する時刻 (JST)
NOTIFY_HOUR = 7
NOTIFY_MINUTE = 45

# RSS フィードリスト
RSS_FEEDS = [
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
    },
    {
        "name": "The Verge AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    },
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
    },
    {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    },
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
    },
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
    },
    {
        "name": "Google AI Blog",
        "url": "https://blog.google/technology/ai/rss/",
    },
    {
        "name": "Anthropic News",
        "url": "https://www.anthropic.com/rss.xml",
    },
]


# ============================================================
# 祝日判定
# ============================================================

def is_japanese_holiday() -> bool:
    """今日が日本の祝日かどうかを判定する。"""
    today = datetime.now(JST).date()
    return jpholiday.is_holiday(today)


# ============================================================
# RSS 収集
# ============================================================

def fetch_rss_articles(hours_back: int = 48) -> list[dict]:
    """各 RSS フィードから直近 hours_back 時間以内の記事を収集する。"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    articles = []

    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(
                        *entry.published_parsed[:6], tzinfo=timezone.utc
                    )
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published = datetime(
                        *entry.updated_parsed[:6], tzinfo=timezone.utc
                    )

                if published and published < cutoff:
                    continue

                summary = ""
                if hasattr(entry, "summary"):
                    summary = re.sub(r"<[^>]+>", "", entry.summary)[:500]
                elif hasattr(entry, "description"):
                    summary = re.sub(r"<[^>]+>", "", entry.description)[:500]

                articles.append(
                    {
                        "title": entry.get("title", "No Title"),
                        "link": entry.get("link", ""),
                        "source": feed_info["name"],
                        "published": published.isoformat() if published else "unknown",
                        "summary": summary,
                    }
                )
        except Exception as e:
            print(f"[WARN] {feed_info['name']} の取得に失敗: {e}", file=sys.stderr)

    print(f"[INFO] {len(articles)} 件の記事を収集しました")
    return articles


# ============================================================
# Gemini API で要約
# ============================================================

def summarize_with_gemini(articles: list[dict]) -> dict:
    """収集した記事を Gemini API に渡して、要約・重要度付けさせる。"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY が設定されていません", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"""
--- 記事 {i} ---
タイトル: {a['title']}
ソース: {a['source']}
公開日: {a['published']}
URL: {a['link']}
概要: {a['summary']}
"""

    today_str = datetime.now(JST).strftime("%Y年%m月%d日")

    prompt = f"""あなたはAI業界に精通した日本語のテックニュースキュレーターです。
以下は直近のAI関連ニュース記事の一覧です。

{articles_text}

これらの記事から、特に重要なニュースを{TOP_N}件選んでください。

■ 重要度の基準（各ニュースに独立して付与。同じランクが複数あってもよい）

A: 業界の構造が変わるレベル。
   例: Claude Opus級のメジャーリリース、GPTの世代交代、
       業界を根本から変えるような発表。
   → 年に数回あるかどうか。この日のニュースに該当するものがなければAは0件でよい。

B: 主要サービスの大きな新機能。
   例: 新モデルの一般公開、大型の機能追加、新しいプラットフォームのローンチ。

C: 注目すべき動き。
   例: 大型の資金調達、重要な業務提携、規制の導入。

D: 知っておくと良い情報。
   例: 小規模なアップデート、業界トレンドの報道。

E: 参考情報。
   例: 周辺ニュース、小ネタ。
   → 基本的にはD以上で{TOP_N}件を埋めること。Eはニュースが本当に少ない日だけ使う。

■ 各ニュースについて以下を含めてください
- 重要度（A〜E）
- 見出し（日本語で分かりやすく）
- 概要（2〜3文。何が起きたか）
- 解説（なぜ重要か、何ができるようになるか、背景情報など。一般の人にも分かりやすく）
- 元記事のURL

以下の JSON 形式で出力してください。JSON 以外のテキストは含めないでください。

{{
  "date": "{today_str}",
  "articles": [
    {{
      "importance": "B",
      "headline": "見出し",
      "summary": "概要（2〜3文）",
      "explanation": "解説（なぜ重要か、何ができるようになるか）",
      "source_name": "ソース名",
      "source_url": "URL"
    }}
  ]
}}

重要度が高い順に並べてください。
"""

    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)

    text = response.text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Gemini の応答を JSON パースできません: {e}", file=sys.stderr)
        print(f"[DEBUG] 応答テキスト:\n{text[:1000]}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] {len(result.get('articles', []))} 件のニュースを選出しました")
    return result


# ============================================================
# HTML 生成
# ============================================================

# 重要度ごとの配色
IMPORTANCE_COLORS = {
    "A": {"bg": "#ff3d3d", "text": "#fff"},
    "B": {"bg": "#ff9800", "text": "#fff"},
    "C": {"bg": "#3d8bff", "text": "#fff"},
    "D": {"bg": "#4a4d5e", "text": "#ccc"},
    "E": {"bg": "#2a2d3e", "text": "#888"},
}

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Daily News - $date</title>
  <style>
    :root {
      --bg: #0f1117;
      --card-bg: #1a1d2e;
      --accent: #6c8aff;
      --accent-dim: #3d5afe;
      --text: #e0e0e6;
      --text-muted: #8a8f9e;
      --border: #2a2d3e;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Noto Sans JP", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.8;
      padding: 0;
    }
    .header {
      background: linear-gradient(135deg, #1a1d2e 0%, #0f1117 100%);
      border-bottom: 1px solid var(--border);
      padding: 2rem 1.5rem 1.5rem;
      text-align: center;
    }
    .header h1 {
      font-size: 1.5rem;
      font-weight: 700;
      color: var(--accent);
      letter-spacing: 0.05em;
    }
    .header .date {
      color: var(--text-muted);
      font-size: 0.9rem;
      margin-top: 0.3rem;
    }
    .container {
      max-width: 740px;
      margin: 0 auto;
      padding: 1.5rem 1rem 3rem;
    }
    .article {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.2rem;
      transition: border-color 0.2s;
    }
    .article:hover { border-color: var(--accent-dim); }
    .article-meta {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.6rem;
    }
    .importance-badge {
      display: inline-block;
      font-size: 0.75rem;
      font-weight: 700;
      padding: 0.15rem 0.6rem;
      border-radius: 4px;
      letter-spacing: 0.05em;
    }
    .importance-A { background: #ff3d3d; color: #fff; }
    .importance-B { background: #ff9800; color: #fff; }
    .importance-C { background: #3d8bff; color: #fff; }
    .importance-D { background: #4a4d5e; color: #ccc; }
    .importance-E { background: #2a2d3e; color: #888; }
    .article h2 {
      font-size: 1.15rem;
      font-weight: 700;
      line-height: 1.5;
      margin-bottom: 0.6rem;
    }
    .article .summary {
      color: var(--text);
      font-size: 0.95rem;
      margin-bottom: 0.8rem;
    }
    .article .explanation {
      color: var(--text-muted);
      font-size: 0.9rem;
      background: rgba(108, 138, 255, 0.06);
      border-left: 3px solid var(--accent-dim);
      padding: 0.8rem 1rem;
      border-radius: 0 8px 8px 0;
      margin-bottom: 0.8rem;
    }
    .article .source {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .article .source a {
      color: var(--accent);
      text-decoration: none;
    }
    .article .source a:hover { text-decoration: underline; }
    .footer {
      text-align: center;
      color: var(--text-muted);
      font-size: 0.75rem;
      padding: 2rem 1rem;
      border-top: 1px solid var(--border);
    }
    .footer a { color: var(--accent); text-decoration: none; }
    .footer a:hover { text-decoration: underline; }
    @media (max-width: 600px) {
      .header { padding: 1.5rem 1rem 1rem; }
      .header h1 { font-size: 1.25rem; }
      .container { padding: 1rem 0.75rem 2rem; }
      .article { padding: 1.2rem; }
      .article h2 { font-size: 1.05rem; }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>AI Daily News</h1>
    <div class="date">$date</div>
  </div>
  <div class="container">
    $articles_html
  </div>
  <div class="footer">
    <a href="archive.html">過去のニュース</a><br><br>
    Powered by Gemini API + GitHub Actions<br>
    Generated at $generated_at
  </div>
</body>
</html>
"""

IMPORTANCE_LABELS = {
    "A": "A — 業界激震",
    "B": "B — 重要",
    "C": "C — 注目",
    "D": "D — 参考",
    "E": "E — 小ネタ",
}


def generate_html(data: dict) -> str:
    """要約データから HTML を生成する。"""
    articles_html = ""
    for article in data.get("articles", []):
        importance = article.get("importance", "D")
        badge_class = f"importance-{importance}"
        badge_label = IMPORTANCE_LABELS.get(importance, importance)

        source_link = ""
        if article.get("source_url"):
            source_link = (
                f'<a href="{article["source_url"]}" target="_blank" '
                f'rel="noopener">元記事を読む</a>'
            )

        articles_html += f"""
    <div class="article">
      <div class="article-meta">
        <span class="importance-badge {badge_class}">{badge_label}</span>
      </div>
      <h2>{article.get("headline", "")}</h2>
      <div class="summary">{article.get("summary", "")}</div>
      <div class="explanation">{article.get("explanation", "")}</div>
      <div class="source">{article.get("source_name", "")} {source_link}</div>
    </div>
"""

    generated_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    template = Template(HTML_TEMPLATE)
    return template.substitute(
        date=data.get("date", ""),
        articles_html=articles_html,
        generated_at=generated_at,
    )


# ============================================================
# アーカイブ用インデックス
# ============================================================

def update_archive_index(docs_dir: Path):
    """過去のニュースページ一覧を生成する。"""
    html_files = sorted(docs_dir.glob("????-??-??.html"), reverse=True)
    dates = [f.stem for f in html_files]

    links_html = ""
    for d in dates[:60]:
        links_html += f'    <li><a href="{d}.html">{d}</a></li>\n'

    archive_html = f"""\
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Daily News - Archive</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Noto Sans JP", sans-serif;
      background: #0f1117; color: #e0e0e6; padding: 2rem; line-height: 1.8;
    }}
    h1 {{ color: #6c8aff; text-align: center; margin-bottom: 1.5rem; }}
    ul {{ max-width: 400px; margin: 0 auto; list-style: none; padding: 0; }}
    li {{ margin-bottom: 0.5rem; }}
    a {{ color: #6c8aff; text-decoration: none; font-size: 1.1rem; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>AI Daily News Archive</h1>
  <ul>
{links_html}  </ul>
</body>
</html>
"""
    (docs_dir / "archive.html").write_text(archive_html, encoding="utf-8")


# ============================================================
# ntfy 通知
# ============================================================

def wait_until_notify_time():
    """7:45 JST まで待機する。既に過ぎていればスキップ。"""
    now = datetime.now(JST)
    target = now.replace(hour=NOTIFY_HOUR, minute=NOTIFY_MINUTE, second=0, microsecond=0)

    if now >= target:
        print("[INFO] 通知時刻を既に過ぎているため、待機せず送信します")
        return

    wait_seconds = (target - now).total_seconds()
    print(f"[INFO] 通知時刻 {NOTIFY_HOUR}:{NOTIFY_MINUTE:02d} JST まで {wait_seconds:.0f} 秒待機します")
    time.sleep(wait_seconds)


def send_notification(data: dict):
    """ntfy にプッシュ通知を送信する。"""
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print("[INFO] NTFY_TOPIC が未設定のため通知をスキップします")
        return

    pages_url = os.environ.get("PAGES_URL", "")

    # 通知本文の組み立て
    lines = []
    for article in data.get("articles", []):
        importance = article.get("importance", "D")
        headline = article.get("headline", "")
        lines.append(f"[{importance}] {headline}")

    body = "\n".join(lines)
    if pages_url:
        body += f"\n\n→ 詳細: {pages_url}"

    try:
        subprocess.run(
            [
                "curl", "-s",
                "-H", "Title: AI Daily News",
                "-H", "Tags: robot",
                "-H", "Priority: default",
                "-d", body,
                f"https://ntfy.sh/{topic}",
            ],
            check=True,
            capture_output=True,
        )
        print("[INFO] ntfy 通知を送信しました")
    except subprocess.CalledProcessError as e:
        print(f"[WARN] ntfy 通知の送信に失敗: {e}", file=sys.stderr)


# ============================================================
# メイン処理
# ============================================================

def main():
    print("[INFO] AI Daily News 生成を開始します")

    # 祝日チェック
    if is_japanese_holiday():
        today = datetime.now(JST).date()
        name = jpholiday.is_holiday_name(today)
        print(f"[INFO] 本日は祝日（{name}）のためスキップします")
        sys.exit(0)

    # 1. RSS 記事収集
    articles = fetch_rss_articles(hours_back=48)
    if not articles:
        print("[WARN] 記事が取得できませんでした。処理を中断します。")
        sys.exit(0)

    # 2. Gemini API で要約
    data = summarize_with_gemini(articles)

    # 3. HTML 生成
    html = generate_html(data)

    # 4. ファイル出力
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)

    today = datetime.now(JST).strftime("%Y-%m-%d")
    (docs_dir / f"{today}.html").write_text(html, encoding="utf-8")
    (docs_dir / "index.html").write_text(html, encoding="utf-8")
    update_archive_index(docs_dir)

    print(f"[INFO] HTML 生成完了: docs/index.html, docs/{today}.html")

    # 5. 7:45 JST まで待機してから通知
    wait_until_notify_time()
    send_notification(data)

    print("[INFO] 全処理完了")


if __name__ == "__main__":
    main()
