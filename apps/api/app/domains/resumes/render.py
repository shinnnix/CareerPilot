"""Deterministic rendering of a resume workspace for export and preview text."""

from html import escape

from app.domains.resumes.parser import entry_text
from app.domains.resumes.schemas import ResumeHead, ResumeSection

TEMPLATE_LABELS = {
    "classic": "经典简约",
    "modern": "现代商务",
    "elegant": "雅致居中",
    "compact": "紧凑黑白",
}


def to_markdown(*, title: str, head: ResumeHead, sections: list[ResumeSection]) -> str:
    lines: list[str] = [f"# {head.name or title}"]
    contact = _contact_line(head)
    if head.target_title:
        lines.append(f"**目标岗位**：{head.target_title}")
    if contact:
        lines.append(contact)
    for section in sections:
        if not section.entries:
            continue
        lines.append("")
        lines.append(f"## {section.title}")
        for entry in section.entries:
            header = entry_text(entry)
            if header:
                period = f"（{entry.period}）" if entry.period else ""
                lines.append(f"**{header}**{period}")
            for bullet in entry.bullets:
                lines.append(f"- {bullet}")
    return "\n".join(lines).strip() + "\n"


def to_html(*, title: str, head: ResumeHead, sections: list[ResumeSection]) -> str:
    blocks: list[str] = []
    blocks.append(f"<h1>{escape(head.name or title)}</h1>")
    if head.target_title:
        blocks.append(f'<p class="target">{escape(head.target_title)}</p>')
    contact = _contact_line(head)
    if contact:
        blocks.append(f'<p class="contact">{escape(contact)}</p>')
    for section in sections:
        if not section.entries:
            continue
        blocks.append(f"<h2>{escape(section.title)}</h2>")
        for entry in section.entries:
            header = entry_text(entry)
            if header:
                period = (
                    f'<span class="period">{escape(entry.period)}</span>'
                    if entry.period
                    else ""
                )
                blocks.append(f'<div class="entry"><strong>{escape(header)}</strong>{period}</div>')
            if entry.bullets:
                items = "".join(f"<li>{escape(bullet)}</li>" for bullet in entry.bullets)
                blocks.append(f"<ul>{items}</ul>")
    body = "\n".join(blocks)
    return (
        "<!doctype html>"
        '<html lang="zh-CN"><head><meta charset="utf-8" />'
        f"<title>{escape(head.name or title)}</title>"
        "<style>"
        "body{font-family:'PingFang SC','Microsoft YaHei',system-ui,sans-serif;"
        "max-width:760px;margin:40px auto;padding:0 24px;color:#17201b;line-height:1.7}"
        "h1{margin:0 0 6px;font-size:30px}h2{margin:26px 0 10px;font-size:17px;"
        "border-bottom:1px solid #dfe4dc;padding-bottom:6px}"
        ".contact{color:#657069}.period{float:right;color:#657069}"
        "ul{margin:6px 0 0;padding-left:20px}li{margin:3px 0}"
        "</style></head><body>"
        f"{body}"
        "</body></html>"
    )


def _contact_line(head: ResumeHead) -> str:
    parts = [
        head.phone or "",
        head.email or "",
        head.city or "",
        *[link.url for link in head.links],
    ]
    return " · ".join(part for part in parts if part)
