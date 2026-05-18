#!/usr/bin/env python3
"""AI Daily News — 自动聚合 AI 资讯，LLM 翻译摘要，生成静态 HTML"""

import os
import json
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import requests
from openai import OpenAI

# ── 配置 ──────────────────────────────────────────────
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
DEEPSEEK_BASE = "https://api.deepseek.com"
OUTPUT_FILE = "index.html"
MAX_NEWS = 20  # 最终展示的新闻数
LOCAL_TZ = timezone(timedelta(hours=8))  # Asia/Shanghai

# ── 新闻源 ────────────────────────────────────────────
SOURCES = [
    # Hacker News top stories
    {
        "name": "Hacker News",
        "type": "hn",
    },
    # Reddit AI subreddits
    {
        "name": "Reddit",
        "type": "reddit",
        "subreddits": ["artificial", "MachineLearning", "LocalLLaMA", "ChatGPT"],
    },
]

# AI 关键词，用于预过滤 HN 标题
AI_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "openai", "gemini", "deepseek",
    "anthropic", "llama", "mistral", "transformer", "diffusion",
    "neural", "deepmind", "copilot", "codex", "langchain", "rag",
    "agent", "chatgpt", "grok", "xai", "stable diffusion",
    "midjourney", "sora", "runway", "hugging face", "qwen",
    "fine-tun", "inference", "gpu", "nvidia", "token",
    "multimodal", "embedding", "vector", "prompt",
    "machine learning", "deep learning", "generative",
    "robot", "autonomous", "benchmark",
]


# ── 新闻抓取 ──────────────────────────────────────────
def fetch_hn_top():
    """抓取 Hacker News 头条，AI 关键词预过滤"""
    resp = requests.get(
        "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15
    )
    story_ids = resp.json()[:80]  # 取前 80 条

    candidates = []
    for sid in story_ids:
        try:
            item = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                timeout=10,
            ).json()
            title = (item.get("title") or "").lower()
            # 预过滤：标题含 AI 关键词
            if any(kw in title for kw in AI_KEYWORDS):
                candidates.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                        "source": "HN",
                        "score": item.get("score", 0),
                        "time": item.get("time", 0),  # Unix timestamp
                    }
                )
            if len(candidates) >= 30:
                break
        except Exception:
            continue
    return candidates


def fetch_reddit(subreddits):
    """抓取 Reddit 多个 subreddit 热门"""
    candidates = []
    headers = {"User-Agent": "AI-Daily-Bot/1.0"}
    for sub in subreddits:
        try:
            resp = requests.get(
                f"https://www.reddit.com/r/{sub}/hot.json?limit=15",
                headers=headers,
                timeout=15,
            )
            posts = resp.json()["data"]["children"]
            for p in posts:
                data = p["data"]
                # 跳过置顶、广告
                if data.get("stickied") or data.get("promoted"):
                    continue
                candidates.append(
                    {
                        "title": data["title"],
                        "url": f"https://www.reddit.com{data['permalink']}",
                        "source": f"r/{sub}",
                        "score": data.get("score", 0),
                        "time": data.get("created_utc", 0),
                    }
                )
        except Exception:
            continue
    return candidates


def fetch_all_news():
    """聚合所有新闻源，去重排序"""
    all_candidates = []
    for src in SOURCES:
        if src["type"] == "hn":
            all_candidates.extend(fetch_hn_top())
        elif src["type"] == "reddit":
            all_candidates.extend(fetch_reddit(src["subreddits"]))

    # 按分数排序，取高分部分
    all_candidates.sort(key=lambda x: x["score"], reverse=True)
    # URL 去重
    seen = set()
    unique = []
    for c in all_candidates:
        if c["url"] not in seen:
            seen.add(c["url"])
            unique.append(c)
    return unique[:60]  # 送 LLM 前取 60 条候选


# ── LLM 处理 ──────────────────────────────────────────
def process_with_llm(articles):
    """用 DeepSeek 批量过滤 + 翻译 + 摘要"""
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE)

    # 构造 prompt
    articles_text = ""
    for i, a in enumerate(articles):
        articles_text += f"[{i}] {a['title']} | 来源:{a['source']}\n"

    prompt = f"""你是 AI 资讯编辑。从以下候选文章列表中，选出{MAX_NEWS}篇最重要的 AI/科技新闻。

要求：
1. 过滤掉与 AI/大模型/科技无关的
2. 优先选重大新闻（新品发布、论文突破、大厂动态、开源项目）
3. 来源尽量多样化
4. 为每篇生成：中文摘要（≤35字，信息密度高）+ 保留原标题

返回纯 JSON 数组（不要 markdown 代码块），每个元素格式：
{{"id": 原文编号, "cn_summary": "中文一句话摘要", "en_title": "原标题"}}

候选列表：
{articles_text}
"""
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",  # 便宜够用
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000,
        )
        raw = resp.choices[0].message.content.strip()
        # 清理可能的 markdown 包裹
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        return result
    except Exception as e:
        print(f"LLM 处理失败: {e}")
        # 降级：直接取前 20 条，不翻译
        return [
            {
                "id": i,
                "cn_summary": a["title"][:35],
                "en_title": a["title"],
            }
            for i, a in enumerate(articles[:MAX_NEWS])
        ]


# ── HTML 生成 ─────────────────────────────────────────
def relative_time(ts):
    """Unix 时间戳 → 相对时间字符串"""
    if not ts:
        return ""
    delta = time.time() - ts
    if delta < 3600:
        return f"{int(delta // 60)}分钟前"
    elif delta < 86400:
        return f"{int(delta // 3600)}小时前"
    elif delta < 172800:
        return "昨天"
    else:
        return f"{int(delta // 86400)}天前"


def generate_html(results, articles):
    """生成最终 HTML"""
    now = datetime.now(LOCAL_TZ)
    date_str = now.strftime("%Y.%m.%d")
    iso_date = now.strftime("%Y-%m-%d")

    # 构建新闻卡片
    cards = []
    for i, r in enumerate(results):
        idx = r["id"]
        a = articles[idx] if idx < len(articles) else None
        if not a:
            continue
        num = f"{i + 1:02d}"
        t = relative_time(a.get("time", 0))
        time_tag = f'<span class="time">⏱ {t}</span>' if t else ""
        cards.append(
            f"""    <a class="item" href="{a['url']}" target="_blank" rel="noopener">
      <span class="num">{num}</span>
      <div class="content">
        <p class="cn">{r['cn_summary']}</p>
        <p class="en">{r.get('en_title', a['title'])}</p>
        <div class="info">
          <span class="source-tag">{a['source']}</span>
          {time_tag}
        </div>
      </div>
    </a>"""
        )

    # 完整 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Daily — {date_str}</title>
<meta name="description" content="每日 AI 资讯聚合，由 AI 自动生成。{iso_date} 共 {len(cards)} 条。">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><text y='28' font-size='28'>🤖</text></svg>">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0d1117;
    color: #c9d1d9;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    min-height: 100vh;
  }}
  header {{
    border-bottom: 1px solid #21262d;
    padding: 32px 24px;
    text-align: center;
  }}
  header h1 {{
    font-size: 28px;
    background: linear-gradient(90deg, #58a6ff, #3fb950, #58a6ff);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 3s linear infinite;
  }}
  @keyframes shimmer {{ to {{ background-position: 200% center; }} }}
  header p {{ color: #8b949e; margin-top: 8px; font-size: 14px; }}
  .container {{ max-width: 800px; margin: 0 auto; padding: 32px 24px; }}
  .item {{
    display: grid;
    grid-template-columns: 36px 1fr;
    gap: 14px;
    align-items: start;
    padding: 18px 20px;
    margin-bottom: 10px;
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    text-decoration: none;
    color: inherit;
    transition: border-color 0.2s, background 0.2s;
  }}
  .item:hover {{ border-color: #58a6ff; background: #1c2129; }}
  .num {{
    color: #30363d;
    font-size: 13px;
    font-weight: 700;
    font-family: 'SF Mono', 'Fira Code', monospace;
    padding-top: 2px;
  }}
  .cn {{ font-size: 15px; color: #e6edf3; line-height: 1.6; font-weight: 500; }}
  .en {{
    font-size: 12px;
    color: #8b949e;
    margin-top: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .info {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 10px;
  }}
  .source-tag {{
    font-size: 11px;
    color: #58a6ff;
    background: rgba(88,166,255,0.12);
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
    letter-spacing: 0.5px;
  }}
  .time {{
    font-size: 11px;
    color: #484f58;
  }}
  footer {{
    text-align: center;
    padding: 40px 24px;
    color: #484f58;
    font-size: 12px;
    border-top: 1px solid #21262d;
    margin-top: 40px;
  }}
  @media (max-width: 600px) {{
    .item {{ padding: 14px 16px; }}
    .container {{ padding: 16px; }}
    .cn {{ font-size: 14px; }}
  }}
</style>
</head>
<body>
<header>
  <h1>🤖 AI Daily · {date_str}</h1>
  <p>{len(cards)} 条 AI 资讯 · 由 DeepSeek 自动生成</p>
</header>
<main class="container">
{chr(10).join(cards)}
</main>
<footer>
  <p>每日自动更新 · 新闻来自 Hacker News / Reddit · AI 筛选摘要</p>
</footer>
</body>
</html>
"""
    return html


# ── 主流程 ────────────────────────────────────────────
def main():
    print("📡 正在抓取新闻...")
    articles = fetch_all_news()
    print(f"   拿到 {len(articles)} 条候选")

    if len(articles) < 5:
        print("⚠️  新闻源获取不足，请检查网络")
        return

    print("🧠 DeepSeek 正在筛选翻译...")
    results = process_with_llm(articles)
    print(f"   选出 {len(results)} 条")

    html = generate_html(results, articles)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 已生成 {OUTPUT_FILE} ({len(html)} bytes)")

    # 打印预览
    print("\n📋 今日摘要预览：")
    for i, r in enumerate(results):
        print(f"  {r['cn_summary']}")


if __name__ == "__main__":
    main()
