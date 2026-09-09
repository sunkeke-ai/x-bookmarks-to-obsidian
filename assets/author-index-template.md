---
title: __TITLE__ · 作者索引
generated_by: x-bookmarks-to-obsidian
tags:
  - X
  - 收藏夹
  - 作者
---

# __TITLE__ · 作者索引

> [!summary] 共 **__COUNT__** 位作者
> 每张卡片显示头像、作者名、收录篇数，以及从收藏文章中提炼的精准标签。
> 点击右上角星标即可置顶；已置顶作者会自动排在第一排。
> [[__MAIN_INDEX__|返回主收藏夹]]

## 全部作者

```dataviewjs
const sourceFolder = "__SOURCE_FOLDER__";
const root = dv.container;
const styleId = "x-bookmark-author-cards-v1";

if (!document.getElementById(styleId)) {
  const style = document.createElement("style");
  style.id = styleId;
  style.textContent = `
    .x-author-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0 16px;color:var(--text-muted);font-size:13px}
    .x-author-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
    .x-author-card{position:relative;min-width:0;min-height:154px;padding:18px 16px 14px;border:1px solid rgba(96,165,250,.34);border-radius:15px;background:linear-gradient(145deg,#092a4a 0%,#0b365e 58%,#0b2848 100%);box-shadow:0 5px 16px rgba(8,28,51,.16);color:#f8fbff;display:flex;flex-direction:column;overflow:hidden}
    .x-author-card.is-pinned{border-color:rgba(217,178,88,.7);box-shadow:0 5px 18px rgba(217,178,88,.16)}
    .x-author-top{display:flex;align-items:center;gap:11px;padding-right:28px;min-width:0}
    .x-author-avatar{display:block!important;width:58px!important;height:58px!important;min-width:58px!important;max-width:58px!important;min-height:58px!important;max-height:58px!important;flex:0 0 58px!important;aspect-ratio:1/1!important;border-radius:999px!important;clip-path:circle(50% at 50% 50%);object-fit:cover!important;object-position:center!important;border:2px solid #38bdf8!important;background:#dbeafe;padding:0!important;margin:0!important}
    .x-author-identity{min-width:0;line-height:1.2}
    .x-author-name{font-size:15px;font-weight:750;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#fff}
    .x-author-handle{margin-top:4px;font-size:10px;color:#93c5fd;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .x-author-count{margin-top:7px;font-size:11px;color:#dbeafe}
    .x-author-tags{display:flex;flex-wrap:wrap;gap:6px;margin:13px 0 12px}
    .x-author-tag{padding:3px 9px;border:1px solid #60a5fa;border-radius:999px;background:rgba(37,99,235,.24);font-size:11px;line-height:1.25;color:#eef6ff;white-space:nowrap}
    .x-author-open{appearance:none!important;-webkit-appearance:none!important;margin-top:auto!important;align-self:flex-start!important;border:0!important;border-radius:0!important;background:transparent!important;background-color:transparent!important;box-shadow:none!important;padding:0!important;color:#7dd3fc!important;font-size:11px!important;font-weight:650!important;line-height:1.4!important;cursor:pointer}
    .x-author-open:hover{color:#fff!important;text-decoration:underline}
    .x-author-pin{appearance:none!important;-webkit-appearance:none!important;position:absolute!important;right:12px!important;top:10px!important;width:26px!important;height:26px!important;min-width:0!important;min-height:0!important;border:0!important;border-radius:0!important;background:transparent!important;background-color:transparent!important;box-shadow:none!important;color:rgba(148,163,184,.66)!important;font-size:24px!important;line-height:26px!important;text-align:center!important;cursor:pointer;padding:0!important;margin:0!important}
    .x-author-pin:hover{transform:translateY(-1px);color:#fbbf24!important;text-shadow:0 0 8px rgba(251,191,36,.45)}
    .x-author-pin[aria-pressed="true"]{background:transparent!important;border:0!important;color:#fbbf24!important;text-shadow:0 0 8px rgba(251,191,36,.38)}
    @media(max-width:1000px){.x-author-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
    @media(max-width:760px){.x-author-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @media(max-width:480px){.x-author-grid{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);
}

let authors = dv.pages(`"${sourceFolder}"`).where(p => p.file.tags?.includes("#x收藏作者")).array();
const isTrue = value => value === true || value === "true";
const countOf = p => Number(p.article_count || 0);
const avatarPath = value => {
  if (!value) return "";
  if (typeof value === "object" && value.path) return value.path;
  return String(value).replace(/^\[\[/, "").replace(/\]\]$/, "").split("|")[0];
};
const resourceUrl = value => {
  const file = app.vault.getAbstractFileByPath(avatarPath(value));
  return file ? app.vault.getResourcePath(file) : "";
};
const sortedAuthors = () => [...authors].sort((a,b) =>
  Number(isTrue(b.pinned))-Number(isTrue(a.pinned)) || countOf(b)-countOf(a) ||
  String(a.author||a.file.name).localeCompare(String(b.author||b.file.name),"zh-CN")
);

function render() {
  root.empty();
  const pinnedCount = authors.filter(p => isTrue(p.pinned)).length;
  const toolbar = root.createDiv({cls:"x-author-toolbar"});
  toolbar.createSpan({text:`${authors.length} 位作者 · ${pinnedCount} 位已置顶`});
  toolbar.createSpan({text:"点击 ☆ 置顶到第一排"});
  const grid = root.createDiv({cls:"x-author-grid"});
  for (const author of sortedAuthors()) {
    const pinned = isTrue(author.pinned);
    const card = grid.createDiv({cls:`x-author-card${pinned ? " is-pinned" : ""}`});
    const pin = card.createEl("button",{cls:"x-author-pin",text:pinned?"★":"☆",attr:{"aria-label":pinned?"取消置顶":"置顶作者","aria-pressed":String(pinned),title:pinned?"取消置顶":"置顶作者"}});
    pin.addEventListener("click",async event=>{
      event.stopPropagation();
      const file=app.vault.getAbstractFileByPath(author.file.path);
      const next=!isTrue(author.pinned);
      await app.fileManager.processFrontMatter(file,fm=>{fm.pinned=next;});
      author.pinned=next;
      render();
    });
    const top=card.createDiv({cls:"x-author-top"});
    const img=top.createEl("img",{cls:"x-author-avatar",attr:{src:resourceUrl(author.avatar),alt:`${author.author||author.file.name} 的头像`}});
    img.addEventListener("error",()=>{img.style.visibility="hidden";});
    const identity=top.createDiv({cls:"x-author-identity"});
    identity.createDiv({cls:"x-author-name",text:String(author.author||author.file.name)});
    identity.createDiv({cls:"x-author-handle",text:String(author.handle||"")});
    identity.createDiv({cls:"x-author-count",text:`📚 已收录 ${countOf(author)} 篇`});
    const tags=card.createDiv({cls:"x-author-tags"});
    for(const tag of Array.from(author.author_tags||[]).slice(0,3)) tags.createSpan({cls:"x-author-tag",text:String(tag).slice(0,6)});
    const open=card.createEl("button",{cls:"x-author-open",text:"查看全部文章 →"});
    open.addEventListener("click",event=>{event.stopPropagation();app.workspace.openLinkText(author.file.path,dv.current().file.path,false);});
  }
}
render();
```

## 其他视图

- [[__AUTHOR_BASE__#全部作者|Base 数据库]]
- [[__AUTHOR_BASE__#高频收藏|高频收藏作者]]
- [[__AUTHOR_BASE__#已置顶|已置顶作者]]
- [[__AUTHOR_BASE__#作者清单|作者清单]]
