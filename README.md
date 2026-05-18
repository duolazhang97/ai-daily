# AI Daily News 🤖

每日 AI 资讯自动聚合站。从 Hacker News / Reddit 抓取新闻，DeepSeek 筛选翻译，生成静态 HTML，通过 GitHub Actions + Cloudflare Pages 全自动部署。

## 部署步骤（全程 15 分钟，无需写代码）

### 1. 注册账号（5 分钟）

| 平台 | 操作 |
|------|------|
| [GitHub](https://github.com) | 注册账号 |
| [Cloudflare](https://cloudflare.com) | 注册账号（选 Free 套餐） |
| [DeepSeek](https://platform.deepseek.com) | 注册 → API Keys → 创建 key，复制保存 |

### 2. 创建 GitHub 仓库（2 分钟）

1. 在 GitHub 点 **New Repository**
2. 名称填 `ai-daily`，选 Public
3. **不要勾** "Add a README file"（我们要推自己的代码）

### 3. 上传代码（3 分钟）

```bash
cd ai-daily
git init
git add .
git commit -m "init: AI Daily News"
git remote add origin https://github.com/你的用户名/ai-daily.git
git push -u origin main
```

### 4. 设置 Secret（1 分钟）

1. 仓库页面 → Settings → Secrets and variables → Actions
2. 点 **New repository secret**
3. Name: `DEEPSEEK_API_KEY`，Value: 粘贴你的 DeepSeek API key

### 5. 部署到 Cloudflare Pages（3 分钟）

1. Cloudflare Dashboard → Workers & Pages → Pages → **Connect to Git**
2. 选 GitHub → 选 `ai-daily` 仓库 → Begin setup
3. **Build settings 全部留空**（我们是纯静态 HTML，不需要构建）
4. Build output directory 不填 → Save and Deploy

### 6. 绑定域名（可选，1 分钟）

Cloudflare Pages → 你的项目 → Custom domains → 添加你的域名。

---

## 手动试跑

第一次部署后不会自动触发，先手动跑一次看看效果：

1. GitHub 仓库 → Actions → AI Daily News → **Run workflow**
2. 等 2-3 分钟跑完
3. 打开 `https://你的项目名.pages.dev` 就能看到效果

之后每天北京时间早上 6-7 点自动更新。

## 自定义

修改 `main.py` 里的配置：

```python
MAX_NEWS = 20          # 每天展示多少条
AI_KEYWORDS = [...]    # AI 相关关键词，用于过滤 HN
SOURCES = [...]        # 新闻源配置
```

## 成本

| 项目 | 费用 |
|------|------|
| GitHub | 免费 |
| Cloudflare Pages | 免费 |
| DeepSeek API | ~$0.5-2/月（每天一次调用） |
| 域名（可选） | ~$10/年 |

**月成本 ≤ $2**
