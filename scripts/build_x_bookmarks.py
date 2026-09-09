#!/usr/bin/env python3
"""Build an Obsidian X-bookmark library from a browser-exported CSV."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

GENERATOR = "x-bookmarks-to-obsidian"

# 未显式指定 --output-folder 时使用的默认输出文件夹。
DEFAULT_OUTPUT_FOLDER = "X收藏夹"
# 历史默认值。若新位置没有收藏库、而旧位置存在托管收藏库，则自动沿用旧位置，避免重复生成。
LEGACY_OUTPUT_FOLDERS = ["03Resources"]

CATEGORY_RULES = [
    ("X 运营与增长", r"Twitter|推特|X\s*运营|涨粉|回复增长|推文|First Check"),
    ("内容与自媒体", r"内容|小红书|公众号|自媒体|选题|写作|热点|起号|个人IP"),
    ("Obsidian 与知识库", r"Obsidian|知识库|第二大脑|知识管理|笔记系统|PKM"),
    ("视频、剪辑与动效", r"视频|剪辑|动效|口播|Remotion|字幕|分镜"),
    ("AI视觉", r"AI视觉|视觉设计|网页设计|网站设计|前端设计|设计风格|图形设计|图表|封面|海报|插图|\bUI\b|\bUX\b|审美|图像生成"),
    ("商业获客与变现", r"获客|变现|商业|赚钱|客户|销售|商单|咨询|报价|收入|营销"),
    ("教程与项目", r"教程|指南|手把手|入门|实战|步骤|怎么|如何|SOP|从零|搭建|安装"),
    ("Skill 与插件", r"Skill|skills|插件|plugin|MCP"),
    ("AI Agent 与自动化", r"Agent|智能体|自动化|OpenClaw|工作流|workflow|computer-use"),
    ("AI 学习与认知", r"学习|教育|课程|大学|老师|教学|方法论|认知|Prompt|提示词"),
    ("AI 趋势与资源", r"榜单|清单|推荐|值得关注|合集|目录|排行榜|精选|资源|新闻|趋势"),
]

TAG_RULES = [
    ("AI视觉", "identity", r"AI视觉|视觉设计|网页设计|网站设计|前端设计|设计风格|图形设计|视觉|图表|封面|海报|插图|\bUI\b|\bUX\b|审美|ThreeUI|BioArt|图像生成"),
    ("X增长", "identity", r"推特|Twitter|X\s*运营|涨粉|回复增长|First Check|大V|X\s*榜单|推文"),
    ("内容运营", "identity", r"内容|小红书|公众号|自媒体|选题|写作|热点|起号|个人IP"),
    ("AI自动化", "identity", r"自动化|自动回复|工作流|workflow|效率系统|多维表|computer-use"),
    ("知识管理", "identity", r"Obsidian|知识库|第二大脑|知识管理|笔记系统|PKM"),
    ("视频创作", "identity", r"视频|剪辑|动效|口播|Remotion|字幕|分镜"),
    ("商业增长", "identity", r"获客|变现|商业|赚钱|客户|销售|商单|咨询|报价|收入|营销"),
    ("AI产品", "identity", r"产品经理|产品策略|产品发布|AI产品|FDE|App"),
    ("AI开发", "identity", r"代码|开发|GitHub|开源项目|工程师|CLI|组件"),
    ("AI科普", "identity", r"学习|教育|课程|大学|老师|教学|高频词|解释"),
    ("资源推荐", "identity", r"榜单|清单|推荐|值得关注|合集|目录|排行榜|精选|资源"),
    ("教程型", "style", r"教程|指南|手把手|入门|实战|步骤|怎么|如何|SOP|从零|精通|教你|搭建|安装|小白"),
    ("资源型", "style", r"榜单|清单|推荐|合集|目录|精选|资源"),
    ("案例型", "style", r"案例|复盘|踩坑|实践|方案|项目|做了一个|搞定了|收入"),
    ("观点型", "style", r"为什么|本质|观点|思考|意义|逻辑|判断|方法论"),
    ("Codex", "skill", r"Codex"), ("智能体", "skill", r"Agent|智能体|多智能体|OpenClaw"),
    ("技能开发", "skill", r"Skill|skills|插件|plugin|MCP"), ("网站开发", "skill", r"网站|网页|前端|落地页|ThreeUI|Sites"),
    ("提示词", "skill", r"Prompt|提示词"), ("微信生态", "skill", r"微信|weixin"),
    ("Grok实战", "skill", r"Grok|Grok Bot"), ("热点追踪", "skill", r"热点|NewsNow|趋势|新闻"),
    ("获客系统", "skill", r"获客|客户|销售线索|GEO"),
]

ALIASES = {
    "profile_url": ["profile_url", "author_profile", "user_url", "profile", "作者主页"],
    "avatar_url": ["avatar_url", "author_avatar", "avatar", "头像"],
    "author": ["author", "author_name", "display_name", "name", "作者", "作者名"],
    "handle": ["handle", "username", "screen_name", "x_id", "账号", "用户id"],
    "url": ["url", "tweet_url", "post_url", "status_url", "link", "原链接", "帖子链接"],
    "published": ["published", "date", "time", "created_at", "发布时间", "日期"],
    "text": ["text", "content", "post_text", "body", "正文", "内容"],
    "cover": ["cover", "media", "image", "image_url", "帖子图片"],
    "type": ["type", "post_type", "类型"],
    "article_title": ["article_title", "card_title", "文章标题"],
    "article_excerpt": ["article_excerpt", "excerpt", "summary", "文章摘要", "摘要"],
    "replies": ["replies", "reply_count", "回复"], "reposts": ["reposts", "retweets", "转发"],
    "likes": ["likes", "like_count", "喜欢", "点赞"], "views": ["views", "view_count", "浏览", "浏览量"],
}


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def yaml_string(value: object) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def md_escape(value: object) -> str:
    return str(value or "").replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def safe_name(value: str) -> str:
    value = re.sub(r"^@", "", value or "")
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_") or "unknown"


def metric(value: object) -> int:
    raw = clean(value).replace(",", "")
    match = re.match(r"^([0-9.]+)\s*([KMB万]?)$", raw, re.I)
    if not match:
        return 0
    factors = {"K": 1000, "M": 1_000_000, "B": 1_000_000_000, "万": 10_000, "": 1}
    return round(float(match.group(1)) * factors[match.group(2).upper()])


def status_id(url: str) -> str:
    match = re.search(r"/status/(\d+)", url)
    return match.group(1) if match else url.split("?", 1)[0]


def choose_title(text: str, article_title: str) -> str:
    raw = clean(article_title) or clean(re.sub(r"https?://\S+", "", text)) or "未命名收藏"
    if len(raw) <= 76:
        return raw
    return raw[:72].rstrip("，,；;：: ") + "…"


def classify(title: str, excerpt: str) -> str:
    full = f"{title} {excerpt}"
    for name, pattern in CATEGORY_RULES:
        if re.search(pattern, full, re.I):
            return name
    return "暂待整理"


def author_tags(text: str) -> list[str]:
    scored = []
    for index, (tag, tier, pattern) in enumerate(TAG_RULES):
        score = len(re.findall(pattern, text, re.I))
        if score:
            scored.append((tag, tier, score, index))
    by_tier = lambda tier: sorted((x for x in scored if x[1] == tier), key=lambda x: (-x[2], x[3]))
    identities, styles, skills = by_tier("identity"), by_tier("style"), by_tier("skill")
    chosen: list[str] = []
    visual = next((x for x in identities if x[0] == "AI视觉"), None)
    if visual:
        chosen.append("AI视觉")
    elif identities:
        chosen.append(identities[0][0])
    if styles:
        chosen.append(styles[0][0])
    for item in skills + identities[1:]:
        if len(chosen) >= 3:
            break
        if item[0] not in chosen:
            chosen.append(item[0])
    if not chosen:
        chosen.append("内容精选")
    return [tag[:6] for tag in chosen[:3]]


def normalized_header(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value.strip().lower())


def map_schema(headers: list[str]) -> tuple[str, dict[str, int]]:
    normalized = {normalized_header(h): i for i, h in enumerate(headers)}
    mapping: dict[str, int] = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            key = normalized_header(alias)
            if key in normalized:
                mapping[field] = normalized[key]
                break
    if "url" in mapping and "author" in mapping:
        return "named-columns", mapping
    if len(headers) >= 18 and any(h.startswith("css-") for h in headers):
        return "positional-css-export", {
            "profile_url": 0, "avatar_url": 1, "author": 2, "handle": 3, "url": 4,
            "published": 5, "text": 8, "cover": 9, "type": 10, "article_title": 11,
            "article_excerpt": 12, "replies": 13, "reposts": 14, "likes": 15, "views": 17,
        }
    raise ValueError("无法识别 CSV 字段；至少需要 url、author、handle、text，或经过验证的 CSS 列顺序。")


def row_value(row: list[str], mapping: dict[str, int], field: str) -> str:
    index = mapping.get(field, -1)
    return row[index].strip() if 0 <= index < len(row) else ""


def read_items(csv_path: Path) -> tuple[list[dict], dict]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    if not rows:
        raise ValueError("CSV 为空。")
    headers, raw_rows = rows[0], [r for r in rows[1:] if any(clean(x) for x in r)]
    mode, mapping = map_schema(headers)
    missing_urls = sum(not row_value(row, mapping, "url") for row in raw_rows)
    if raw_rows and missing_urls / len(raw_rows) > 0.05:
        raise ValueError(f"原文 URL 缺失 {missing_urls}/{len(raw_rows)}，疑似列识别错位。")
    seen: set[str] = set()
    items: list[dict] = []
    for source_index, row in enumerate(raw_rows, 1):
        url = row_value(row, mapping, "url")
        if not url:
            continue
        identity = status_id(url)
        if identity in seen:
            continue
        seen.add(identity)
        text = row_value(row, mapping, "text")
        article_title = row_value(row, mapping, "article_title") if row_value(row, mapping, "type").lower() == "article" else ""
        excerpt = clean(row_value(row, mapping, "article_excerpt") or text)[:900]
        title = choose_title(text, article_title)
        items.append({
            "source_index": source_index, "id": identity, "url": url, "title": title, "excerpt": excerpt,
            "category": classify(title, excerpt), "profile_url": row_value(row, mapping, "profile_url"),
            "avatar_url": row_value(row, mapping, "avatar_url"), "author": clean(row_value(row, mapping, "author")) or "未知作者",
            "handle": clean(row_value(row, mapping, "handle")), "published": clean(row_value(row, mapping, "published")),
            "cover": row_value(row, mapping, "cover"), "replies": metric(row_value(row, mapping, "replies")),
            "reposts": metric(row_value(row, mapping, "reposts")), "likes": metric(row_value(row, mapping, "likes")),
            "views": metric(row_value(row, mapping, "views")),
        })
    if not items:
        raise ValueError("没有识别到有效的 X 收藏链接。")
    unknown = sum(item["author"] == "未知作者" for item in items)
    if unknown / len(items) > 0.05:
        raise ValueError(f"作者字段无法识别 {unknown}/{len(items)}，请检查 CSV 列名。")
    return items, {"schema": mode, "source_rows": len(raw_rows), "unique_rows": len(items), "duplicates": len(raw_rows) - len(items)}


def managed(path: Path) -> bool:
    return not path.exists() or GENERATOR in path.read_text("utf-8", errors="ignore")[:500]


def protect_targets(paths: list[Path], update: bool) -> None:
    existing = [p for p in paths if p.exists()]
    if existing and not update:
        raise FileExistsError("输出已存在；确认更新同一收藏库后添加 --update：" + ", ".join(str(p) for p in existing))
    unmanaged = [p for p in existing if p.is_file() and not managed(p)]
    if unmanaged:
        raise FileExistsError("拒绝覆盖非本 Skill 管理的文件：" + ", ".join(str(p) for p in unmanaged))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


WORKFLOW_FIELDS = {
    "source": "X",
    "status": "未读",
    "priority": "普通",
    "next_action": "",
    "review_on": "",
    "reviewed_at": "",
    "practice_note": "",
    "outcome": "",
}


def existing_workflow(path: Path) -> dict[str, str]:
    """Keep the user's reading decisions when a managed bookmark is refreshed."""
    values = {**WORKFLOW_FIELDS, "imported_at": date.today().isoformat()}
    if not path.exists():
        return values
    text = path.read_text("utf-8", errors="ignore")
    frontmatter = text.split("---", 2)[1] if text.startswith("---") and text.count("---") >= 2 else ""
    for field in values:
        match = re.search(rf"^{re.escape(field)}:\s*(.*)$", frontmatter, re.M)
        if not match:
            continue
        raw = match.group(1).strip()
        if not raw or raw in {"null", "~"}:
            values[field] = ""
            continue
        try:
            values[field] = str(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            values[field] = raw.strip("'\"")
    return values


def yaml_list(values: list[str]) -> str:
    return "\n".join(f"  - {yaml_string(value)}" for value in values) if values else "  []"


def download_avatar(author: dict, avatars_dir: Path, rel_folder: str, enabled: bool) -> tuple[str, bool]:
    default = f"{rel_folder}/default-avatar.svg"
    if not enabled or not author["avatar_url"]:
        return default, False
    filename = safe_name(author["handle"] or author["author"]) + ".jpg"
    destination = avatars_dir / filename
    if destination.exists() and destination.stat().st_size:
        return f"{rel_folder}/{filename}", True
    try:
        request = urllib.request.Request(author["avatar_url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
        if len(data) < 100:
            raise ValueError("avatar response too small")
        destination.write_bytes(data)
        return f"{rel_folder}/{filename}", True
    except Exception:
        return default, False


def resolve_output_folder(vault: Path, name: str) -> str:
    """用户未显式指定输出文件夹时，决定放在 vault 内的哪个文件夹。

    优先使用 DEFAULT_OUTPUT_FOLDER；若该位置还没有收藏库，而某个历史默认位置下
    已存在同名托管收藏库，则沿用历史位置，避免为老用户重复生成一整套文件。
    """
    if (vault / DEFAULT_OUTPUT_FOLDER / f"{name}.md").exists():
        return DEFAULT_OUTPUT_FOLDER
    for legacy in LEGACY_OUTPUT_FOLDERS:
        if (vault / legacy / f"{name}.md").exists():
            print(
                f"[提示] {DEFAULT_OUTPUT_FOLDER}/ 下没有已有的“{name}”，"
                f"沿用旧位置 {legacy}/，避免重复生成。如要迁移，请显式传入 --output-folder {DEFAULT_OUTPUT_FOLDER}。"
            )
            return legacy
    return DEFAULT_OUTPUT_FOLDER


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--name", default="x收藏夹")
    parser.add_argument("--output-folder", default=None, help=f"vault 内的输出文件夹，默认 {DEFAULT_OUTPUT_FOLDER}")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--no-download-avatars", action="store_true")
    args = parser.parse_args()

    csv_path, vault = args.input.expanduser().resolve(), args.vault.expanduser().resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)
    if not (vault / ".obsidian").is_dir():
        raise ValueError(f"目标不是现有 Obsidian vault：{vault}")
    if "/" in args.name or "\\" in args.name:
        raise ValueError("--name 不能包含路径分隔符。")
    if args.output_folder is None:
        args.output_folder = resolve_output_folder(vault, args.name)

    items, report = read_items(csv_path)
    authors_map: dict[str, dict] = {}
    for item in items:
        key = item["handle"] or item["author"]
        authors_map.setdefault(key, {"author": item["author"], "handle": item["handle"], "profile_url": item["profile_url"], "avatar_url": item["avatar_url"], "items": []})["items"].append(item)
    authors = sorted(authors_map.values(), key=lambda x: (-len(x["items"]), x["author"]))
    report.update({"authors": len(authors), "output": str(vault / args.output_folder / f"{args.name}.md")})
    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    root = vault / args.output_folder
    records_dir, authors_dir, avatars_dir = root / f"{args.name}条目", root / f"{args.name}作者", root / f"{args.name}作者头像"
    main_md, main_base = root / f"{args.name}.md", root / f"{args.name}.base"
    author_md, author_base = root / f"{args.name}-作者索引.md", root / f"{args.name}-作者索引.base"
    workflow_md, workflow_base = root / f"{args.name.removesuffix('夹')}工作台.md", root / f"{args.name.removesuffix('夹')}工作台.base"
    protect_targets([main_md, main_base, author_md, author_base, workflow_md, workflow_base], args.update)
    for directory in (records_dir, authors_dir, avatars_dir):
        directory.mkdir(parents=True, exist_ok=True)

    default_avatar = """<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320"><rect width="320" height="320" rx="160" fill="#dbeafe"/><circle cx="160" cy="122" r="62" fill="#1d9bf0"/><path d="M55 292c10-72 49-106 105-106s95 34 105 106" fill="#1d9bf0"/></svg>"""
    write_text(avatars_dir / "default-avatar.svg", default_avatar)

    for item in items:
        target = records_dir / f"x-{safe_name(item['id'])}.md"
        workflow = existing_workflow(target)
        note = f'''---
title: {yaml_string(item["title"])}
generated_by: {GENERATOR}
platform: "X"
source: {yaml_string(workflow["source"])}
imported_at: {yaml_string(workflow["imported_at"])}
status: {yaml_string(workflow["status"])}
priority: {yaml_string(workflow["priority"])}
next_action: {yaml_string(workflow["next_action"])}
review_on: {yaml_string(workflow["review_on"])}
reviewed_at: {yaml_string(workflow["reviewed_at"])}
practice_note: {yaml_string(workflow["practice_note"])}
outcome: {yaml_string(workflow["outcome"])}
category: {yaml_string(item["category"])}
author: {yaml_string(item["author"])}
handle: {yaml_string(item["handle"])}
author_profile: {yaml_string(item["profile_url"])}
author_avatar: {yaml_string(item["avatar_url"])}
published: {yaml_string(item["published"])}
views: {item["views"]}
likes: {item["likes"]}
reposts: {item["reposts"]}
replies: {item["replies"]}
url: {yaml_string(item["url"])}
source_id: {yaml_string(item["id"])}
tags:
  - x收藏
---

# [{md_escape(item["title"])}]({item["url"]})

**{item["author"]}** {item["handle"]}

> [!quote] 原文摘要
> {item["excerpt"]}

- 分类：{item["category"]}
- 浏览：{item["views"]:,}
- 互动：回复 {item["replies"]:,} · 转发 {item["reposts"]:,} · 喜欢 {item["likes"]:,}
'''
        if target.exists() and not managed(target):
            raise FileExistsError(f"拒绝覆盖非托管条目：{target}")
        write_text(target, note)

    rel_avatar_folder = f"{args.output_folder}/{args.name}作者头像"
    avatar_results: dict[str, tuple[str, bool]] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(download_avatar, a, avatars_dir, rel_avatar_folder, not args.no_download_avatars): a for a in authors}
        for future in as_completed(futures):
            author = futures[future]
            avatar_results[author["handle"] or author["author"]] = future.result()

    for author in authors:
        safe = safe_name(author["handle"] or author["author"])
        target = authors_dir / f"{safe}.md"
        pinned = bool(re.search(r"^pinned:\s*true\s*$", target.read_text("utf-8", errors="ignore"), re.M)) if target.exists() else False
        if target.exists() and not managed(target):
            raise FileExistsError(f"拒绝覆盖非托管作者页：{target}")
        avatar_link, _ = avatar_results[author["handle"] or author["author"]]
        tags = author_tags(" ".join(f"{x['title']} {x['excerpt']}" for x in author["items"]))
        categories = list(dict.fromkeys(x["category"] for x in author["items"]))
        total_views = sum(x["views"] for x in author["items"])
        articles = []
        for item in sorted(author["items"], key=lambda x: -x["views"]):
            articles.extend([f"### [{md_escape(item['title'])}]({item['url']})", f"- {item['category']} · 浏览 {item['views']:,}", ""])
        note = f'''---
title: {yaml_string(author["author"])}
generated_by: {GENERATOR}
author: {yaml_string(author["author"])}
handle: {yaml_string(author["handle"])}
profile_url: {yaml_string(author["profile_url"])}
avatar: {yaml_string(f"[[{avatar_link}]]")}
article_count: {len(author["items"])}
total_views: {total_views}
pinned: {str(pinned).lower()}
categories:
{yaml_list(categories)}
author_tags:
{yaml_list(tags)}
tag_basis: "根据已收藏文章提炼"
tags:
  - x收藏作者
---

# {author["author"]}

![[{avatar_link}|100]]

[打开 {author["handle"] or author["author"]} 的 X 主页]({author["profile_url"]})

共收藏 **{len(author["items"])}** 篇 · 累计浏览 **{total_views:,}**

## 收藏文章

{chr(10).join(articles)}
'''
        write_text(target, note)

    category_counts = Counter(x["category"] for x in items)
    base = f'''# generated_by: {GENERATOR}
filters:
  and:
    - 'file.inFolder("{args.output_folder}/{args.name}条目")'
    - 'file.hasTag("x收藏")'
formulas:
  标题链接: 'link(url, title)'
  总互动: 'replies + reposts + likes'
properties:
  formula.标题链接:
    displayName: "标题"
  category:
    displayName: "能做什么"
  author:
    displayName: "作者"
  handle:
    displayName: "账号"
  views:
    displayName: "浏览"
  formula.总互动:
    displayName: "总互动"
views:
  - type: table
    name: "全部收藏"
    order: [formula.标题链接, category, author, views, formula.总互动, published]
    sort:
      - property: category
        direction: ASC
      - property: views
        direction: DESC
  - type: table
    name: "按用途"
    groupBy:
      property: category
      direction: ASC
    order: [formula.标题链接, author, views, likes, published]
  - type: table
    name: "高热收藏"
    filters:
      and:
        - 'views >= 10000'
    order: [formula.标题链接, category, author, views, formula.总互动]
'''
    if not (args.update and main_base.exists()):
        write_text(main_base, base)

    stats = "\n".join(f"| {name} | {count} |" for name, count in category_counts.most_common())
    main_note = f'''---
title: {args.name}
generated_by: {GENERATOR}
tags: [X, 收藏夹, 资源整理]
---

# {args.name}

> [!summary] 整理结果
> 原表共 **{report["source_rows"]}** 条，去重 **{report["duplicates"]}** 条，保留 **{report["unique_rows"]}** 条。
> 标题均可直接打开原 X 帖子。
> [[{args.name.removesuffix('夹')}工作台|进入内容管道]] · [[{args.name}-作者索引|按作者浏览]]

## 全部收藏

![[{args.name}.base#全部收藏]]

## 用途统计

| 能做什么 | 数量 |
| --- | ---: |
{stats}

## 快速入口

- [[{args.name.removesuffix('夹')}工作台|处理未读、学习与实践]]
- [[{args.name}.base#按用途|按用途浏览]]
- [[{args.name}.base#高热收藏|查看高热收藏]]
- [[{args.name}-作者索引|查看作者卡片库]]
'''
    if not (args.update and main_md.exists()):
        write_text(main_md, main_note)

    author_base_text = f'''# generated_by: {GENERATOR}
filters:
  and:
    - 'file.inFolder("{args.output_folder}/{args.name}作者")'
    - 'file.hasTag("x收藏作者")'
properties:
  avatar: {{displayName: "头像"}}
  author: {{displayName: "作者"}}
  handle: {{displayName: "账号"}}
  article_count: {{displayName: "已收录"}}
  author_tags: {{displayName: "精准标签"}}
  pinned: {{displayName: "置顶"}}
views:
  - type: cards
    name: "全部作者"
    order: [avatar, author, handle, article_count, author_tags, pinned]
    sort:
      - property: pinned
        direction: DESC
      - property: article_count
        direction: DESC
  - type: cards
    name: "高频收藏"
    filters:
      and:
        - 'article_count >= 2'
    order: [avatar, author, handle, article_count, author_tags, pinned]
    sort:
      - property: pinned
        direction: DESC
      - property: article_count
        direction: DESC
  - type: cards
    name: "已置顶"
    filters:
      and:
        - 'pinned == true'
    order: [avatar, author, handle, article_count, author_tags]
  - type: table
    name: "作者清单"
    order: [pinned, avatar, author, handle, article_count, author_tags, total_views, profile_url]
    sort:
      - property: pinned
        direction: DESC
      - property: article_count
        direction: DESC
'''
    if not (args.update and author_base.exists()):
        write_text(author_base, author_base_text)

    template = (Path(__file__).resolve().parent.parent / "assets" / "author-index-template.md").read_text("utf-8")
    author_index = (template.replace("__TITLE__", args.name).replace("__COUNT__", str(len(authors)))
                    .replace("__MAIN_INDEX__", args.name).replace("__SOURCE_FOLDER__", f"{args.output_folder}/{args.name}作者")
                    .replace("__AUTHOR_BASE__", f"{args.name}-作者索引.base"))
    if not (args.update and author_md.exists()):
        write_text(author_md, author_index)

    workflow_replacements = {
        "__NAME__": args.name,
        "__WORKFLOW_NAME__": args.name.removesuffix("夹") + "工作台",
        "__RECORDS_FOLDER__": f"{args.output_folder}/{args.name}条目",
        "__TODAY__": date.today().isoformat(),
    }
    if not workflow_base.exists():
        workflow_base_text = (Path(__file__).resolve().parent.parent / "assets" / "workflow-template.base").read_text("utf-8")
        for old, new in workflow_replacements.items():
            workflow_base_text = workflow_base_text.replace(old, new)
        write_text(workflow_base, workflow_base_text)
    if not workflow_md.exists():
        workflow_note = (Path(__file__).resolve().parent.parent / "assets" / "workflow-template.md").read_text("utf-8")
        for old, new in workflow_replacements.items():
            workflow_note = workflow_note.replace(old, new)
        write_text(workflow_md, workflow_note)

    downloaded = sum(ok for _, ok in avatar_results.values())
    dataview = (vault / ".obsidian/plugins/dataview").is_dir()
    report.update({"avatars_downloaded": downloaded, "avatar_fallbacks": len(authors) - downloaded, "dataview_available": dataview,
                   "main_index": str(main_md), "author_index": str(author_md)})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1)
