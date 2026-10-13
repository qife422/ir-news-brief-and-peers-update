#!/usr/bin/env python3
"""Render a validated, audience-projected IR workspace; standard library only."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from ir_workflow import build_report


LABELS = {
    "initial_baseline": "初始基线", "new_topic": "新增议题", "changed": "有变化",
    "unchanged": "无变化", "anticipated": "AI 预拟问题", "actual": "实际问题",
    "reported": "转述问题", "paraphrase": "转述问题", "confirmed": "已确认", "pending": "待核验",
    "unavailable": "证据不可用", "outside_period": "不在适用期间",
    "ready": "可准备回答", "NeedsEvidence": "缺少证据", "Draft": "Draft 草稿",
    "Reviewed": "Reviewed 已复核", "NeedsReview": "需重新复核",
    "missing_consensus": "缺少有效预期", "late_consensus": "预期快照晚于披露",
    "incomparable": "口径不可比", "zero_base": "零分母",
    "negative_base": "负基数需解释", "comparable": "口径可比",
    "radar": "投资者问题雷达", "earnings": "财报准备", "meeting": "会议准备",
    "fact": "事实", "company_position": "公司历史口径", "inference": "分析推断",
    "analysis": "分析推断", "hypothesis": "待验证假设",
}


def _text(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, dict):
        return str(value.get("text", value.get("value", "")))
    return str(value)


def _e(value: object) -> str:
    return html.escape(_text(value), quote=True)


def _label(value: object) -> str:
    return _e(LABELS.get(str(value), str(value)))


def _anchor(value: object) -> str:
    return "ref-" + hashlib.sha256(str(value).encode()).hexdigest()[:16]


def _link(url: object, text: object) -> str:
    candidate = str(url or "")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return _e(text)
    return f'<a href="{_e(candidate)}" target="_blank" rel="noopener noreferrer">{_e(text)}</a>'


def _list(items: list, empty: str = "未提供") -> str:
    return "<ul>" + "".join(f"<li>{_e(item)}</li>" for item in items) + "</ul>" if items else f'<p class="muted">{_e(empty)}</p>'


def _citations(items: list) -> str:
    return " ".join(
        f'<a class="cite" href="#{_anchor(c.get("source_id"))}">{_e(c.get("source_id"))}: {_e(c.get("locator"))}</a>'
        for c in items
    )


def _answer(answer: dict) -> str:
    statements = "".join(
        f'<p><span class="tag">{_label(s.get("kind"))}</span> {_e(s.get("text", ""))}<br>{_citations(s.get("citations", []))}</p>'
        for s in answer.get("statements", [])
    )
    review = answer.get("review") or {}
    reviewed = f'<p class="muted">复核：{_e(review.get("reviewer"))}，{_e(review.get("at"))}；{_e(review.get("scope"))}</p>' if review else ""
    return f'<div class="answer"><strong>{_label(answer.get("status"))}</strong> <span class="muted">版本 {_e(answer.get("version"))}</span>{statements}{reviewed}{_list(answer.get("gaps", []), "")}</div>'


def _topic(topic: dict) -> str:
    change = topic.get("change", {})
    priority = topic.get("priority", {})
    facts = "".join(
        f'<div class="fact"><p><span class="tag">{_label(f.get("status"))}</span> <strong>{_e(f.get("company"))}</strong> <span class="muted">{_e(f.get("period"))}</span></p><p>{_e(f.get("text", "证据缺口，暂不提供事实表述"))}</p><small>{_e(f.get("definition", ""))}</small><div>{_citations(f.get("citations", []))}</div></div>'
        for f in topic.get("facts", [])
    )
    analysis = "".join(f'<p><span class="tag">{_label(a.get("type"))}</span> {_e(a.get("text", ""))}</p>' for a in topic.get("analysis", []))
    questions = []
    for q in topic.get("questions", []):
        answers = [a for a in topic.get("answers", []) if a.get("question_id") == q.get("id")]
        questions.append(f'<details class="question" open><summary><span class="tag">{_label(q.get("origin"))}</span> {_e(q.get("text", "问题证据不足"))}</summary><p class="muted">{_label(q.get("status"))}；已确认实际提问 {_e(q.get("actual_question_count", 0))} 次</p>{_citations(q.get("citations", []))}<h4>进一步追问</h4>{_list(q.get("follow_ups", []), "未设置追问")}<h4>回答准备</h4>{"".join(_answer(a) for a in answers) or "<p class=muted>尚无回答草稿，请补充证据和适用口径。</p>"}</details>')
    needs = bool(topic.get("gaps")) or any(a.get("status") != "Reviewed" for a in topic.get("answers", []))
    state = "needs" if needs else "ready"
    return f'<article class="topic" id="{_anchor(topic.get("id"))}" data-state="{state}"><div class="topic-head"><h3>{_e(topic.get("title"))}</h3><span class="tag">{_label(change.get("status"))}</span></div><p class="muted">准备优先级 {_e(priority.get("score", "N/A"))}；实际提问 {_e(topic.get("actual_question_count", 0))} 次</p>{_list(priority.get("reasons", []), "")}{facts}{analysis}{"".join(questions)}<div class="prepare"><h4>准备动作</h4>{_list(topic.get("actions", []), "尚未指定准备动作")}<h4>证据与数据缺口</h4>{_list(topic.get("gaps", []), "本议题未记录额外缺口")}</div></article>'


def render_html(report: dict) -> str:
    metadata = report["metadata"]
    topics = report.get("topics", [])
    earnings = report.get("earnings", {})
    comparisons = earnings.get("comparisons", [])
    meetings = report.get("meeting_brief", {}).get("meetings", [])
    sources = report.get("sources", [])
    is_example = metadata.get("status") == "Example"
    banner = "Example 演示数据，不能作为正式 IR 事实或答复。" if is_example else "Draft 工作材料；事实支持力度与正式答复需 IR 审阅。"
    rows = "".join(
        "<tr>" + "".join(f"<td>{_e(c.get(k))}</td>" for k in ("company", "metric", "period", "actual", "consensus", "difference", "percentage_difference")) + f'<td>{_label(c.get("status"))}</td><td>{_e(c.get("unit"))} / {_e(c.get("currency"))}<br>{_e(c.get("accounting_basis"))}<br>{_citations(c.get("citations", []))}</td></tr>'
        for c in comparisons
    )
    table = f'<div class="table-wrap" tabindex="0" aria-label="财报比较表，可横向滚动"><table><thead><tr>{"".join(f"<th>{x}</th>" for x in ["公司", "指标", "期间", "实际值", "预期", "绝对差异", "相对差异 %", "状态", "定义与来源"])}</tr></thead><tbody>{rows}</tbody></table></div>' if rows else '<p class="empty">未提供可比的业绩与预期数据，不生成 beat 或 miss。</p>'
    meeting_html = "".join(f'<div class="meeting"><h3>{_e(m.get("title"))}</h3><p class="muted">{_e(m.get("at"))}；实际问题 {_e(m.get("actual_question_count", 0))} 次</p>{_list(m.get("questions", []), "没有可用的已确认问题")}{"".join(_answer(a) for a in m.get("answers", []))}</div>' for m in meetings) or '<p class="empty">未提供获准的真实会议记录；预拟问题不计入实际反馈。</p>'
    source_html = "".join(
        f'<div class="source" id="{_anchor(s.get("id"))}"><h3>{_e(s.get("id"))} {_link(s.get("url"), s.get("title", s.get("id")))}</h3>'
        f'<p class="muted">{_e(s.get("company"))}；版本 {_e(s.get("version"))}</p>'
        f'<p class="muted">原始发布日期 {_e(s.get("published_date_raw") or s.get("published_at"))}；精度 {_e(s.get("time_precision", "timestamp"))}'
        f'<br>版本可用边界 {_e(s.get("available_at"))}<br>获取时间 {_e(s.get("retrieved_at"))}</p>'
        f'<p class="muted">{_e(s.get("time_note", ""))}</p>'
        f'<p class="muted">指纹范围：{_e(s.get("fingerprint_scope", "由输入维护人声明；脚本未核验远程全文"))}</p></div>'
        for s in sources
    ) or '<p class="empty">没有符合本次时间和受众范围的来源。</p>'
    queue = "".join(f'<li><a href="#{_anchor(t.get("id"))}">{_e(t.get("title"))}</a>{_list(t.get("actions", []), "准备动作待指定")}</li>' for t in topics)
    safe_json = json.dumps(report, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    title = LABELS.get(metadata.get("mode"), "IR 工作准备")
    topic_html = "".join(_topic(t) for t in topics) or '<p class="empty">没有满足时间、证据与受众范围的议题，请准备获准材料。</p>'
    report_gaps_html = _list(report.get("data_gaps", []), "未记录全局数据缺口")
    earning_gaps_html = _list(earnings.get("gaps", []), "")
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><link rel="icon" href="data:,"><title>{_e(title)}</title><style>
:root{{--page:#f4f7fb;--surface:#fff;--ink:#142033;--muted:#5d6b7c;--line:#d9e1eb;--accent:#2563eb;--soft:#e9f0ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--page);color:var(--ink);font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}a{{color:var(--accent);text-underline-offset:3px}}button,input,select{{font:inherit}}button,input,select,summary,a{{scroll-margin-top:24px}}:focus-visible{{outline:3px solid #2563eb;outline-offset:3px}}.skip{{position:absolute;left:12px;top:-60px}}.skip:focus{{top:12px;background:white;padding:10px;z-index:2}}.wrap{{max-width:1240px;margin:auto;padding:28px}}header{{padding:20px 0}}h1{{font-size:30px;line-height:1.25;margin:12px 0}}h2{{font-size:22px;margin:32px 0 16px}}h3{{font-size:18px;line-height:1.4;margin:0}}h4{{font-size:14px;margin:18px 0 8px}}p{{margin:8px 0}}ul{{padding-left:22px}}li{{margin:6px 0}}.muted,small{{color:var(--muted)}}.banner{{background:#fff4d8;color:#704c00;border-left:4px solid #946200;padding:12px 16px;border-radius:4px}}.meta{{display:flex;flex-wrap:wrap;gap:8px 24px;font-size:13px}}nav{{display:flex;gap:24px;flex-wrap:wrap;margin-top:18px}}nav a{{font-weight:600}}.layout{{display:grid;grid-template-columns:minmax(0,2.4fr) minmax(230px,1fr);gap:24px}}.topic,.panel,.meeting{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:24px;margin-bottom:20px;min-width:0}}.topic-head{{display:flex;justify-content:space-between;gap:16px;align-items:start}}.tag{{display:inline-block;background:var(--soft);color:#1745a3;border-radius:5px;padding:2px 7px;font-size:12px;white-space:nowrap}}.fact{{border-left:3px solid var(--line);padding-left:14px;margin:18px 0}}.cite{{display:inline-block;font-size:12px;margin-right:10px;overflow-wrap:anywhere}}.question{{border-top:1px solid var(--line);margin-top:20px;padding-top:18px}}summary{{cursor:pointer;font-weight:600}}.answer,.prepare{{background:#eef3f9;border-radius:8px;padding:14px;margin:14px 0}}.toolbar{{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:20px 0}}.field{{display:flex;flex-direction:column;gap:5px;flex:1;min-width:160px}}label{{font-size:13px;font-weight:600}}input,select,button{{padding:9px 12px;border:1px solid #9caabd;border-radius:8px;background:white;color:var(--ink)}}button{{cursor:pointer;white-space:nowrap}}button:hover{{background:var(--soft)}}button:active{{transform:translateY(1px)}}input::placeholder{{color:#5d6b7c}}.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:10px;background:white}}table{{width:100%;border-collapse:collapse;min-width:930px}}th,td{{padding:12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}th{{background:#eef3f9;font-size:12px}}td{{font:13px/1.6 ui-monospace,Menlo,monospace}}td:first-child,td:last-child{{font-family:inherit}}.empty{{border:1px dashed var(--line);padding:22px;border-radius:10px;color:var(--muted);background:var(--surface)}}.source{{padding:18px 0;border-top:1px solid var(--line);overflow-wrap:anywhere}}.source h3{{font-size:15px}}.queue{{padding-left:20px}}footer{{border-top:1px solid var(--line);margin-top:30px;padding-top:20px;font-size:12px;overflow-wrap:anywhere}}[hidden]{{display:none!important}}
@media(max-width:767px){{.wrap{{padding:16px}}.layout{{grid-template-columns:1fr}}.topic,.panel,.meeting{{padding:18px}}h1{{font-size:25px}}.topic-head{{flex-direction:column;gap:8px}}.toolbar{{align-items:stretch}}nav{{gap:12px 18px}}}}
@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important;transition:none!important}}}}
@media print{{body{{background:white;font-size:10pt}}.wrap{{max-width:none;padding:0}}.toolbar,nav,.skip,.no-print{{display:none!important}}.layout{{display:block}}.topic,.panel,.meeting{{border-radius:0;break-inside:auto;padding:12px;margin-bottom:14px}}.question,.answer,.fact,.source{{break-inside:avoid}}table{{min-width:0;font-size:8pt}}th,td{{padding:5px}}thead{{display:table-header-group}}.table-wrap{{overflow:visible}}article[hidden]{{display:block!important}}details>*{{display:block!important}}details>summary{{display:list-item!important}}a[href^="http"]::after{{content:" (" attr(href) ")";font-size:8pt}}}}
@media print{{#count,#no-match{{display:none!important}}.question,.answer{{break-inside:auto}}.answer p{{break-inside:avoid}}h2,h3,h4,summary{{break-after:avoid}}}}
</style></head><body>
<a class="skip" href="#main">跳到报告内容</a><div class="wrap"><header>
<div class="meta"><strong>{_e(metadata.get("status"))}</strong><span>{_e(metadata.get("subject_company"))}</span><span>受众 {_e(metadata.get("audience"))}</span></div>
<h1>{_e(title)}</h1><p class="muted">把市场议题转化为有证据的问题、回答准备与后续动作。</p>
<p class="meta">截至 {_e(metadata.get("as_of"))} <span>时区 {_e(metadata.get("timezone"))}</span></p><div class="banner" role="note">{_e(banner)}</div>
<nav aria-label="报告章节"><a href="#topics">议题与问答</a><a href="#earnings">财报比较</a><a href="#meetings">会议准备</a><a href="#sources">来源台账</a></nav></header>
<main id="main"><div class="toolbar"><div class="field"><label for="query">搜索议题和问题</label><input id="query" type="search" placeholder="输入议题、公司或问题关键词"></div>
<div class="field"><label for="state">准备状态</label><select id="state"><option value="all">全部</option><option value="needs">需要准备或复核</option><option value="ready">无待复核答复</option></select></div>
<button class="no-print" id="print" type="button">打印报告</button></div>
<p id="count" class="muted" aria-live="polite">显示 {len(topics)} 个议题</p><div class="layout"><section id="topics"><h2>议题与问答</h2>{topic_html}
<p id="no-match" class="empty" hidden>没有匹配的议题，调整关键词或准备状态。</p></section><aside><h2>准备队列</h2><div class="panel"><ol class="queue">{queue}</ol></div>
<h2>本次数据缺口</h2><div class="panel">{report_gaps_html}</div></aside></div>
<section id="earnings"><h2>财报比较</h2>{table}{earning_gaps_html}</section><section id="meetings"><h2>会议准备</h2>{meeting_html}</section>
<section id="sources"><h2>来源台账</h2><p class="muted">事实通过来源 ID 和定位信息追溯。摘要需要对照链接核验，不冒充逐字引文。</p>{source_html}</section></main>
<footer>证据指纹 {_e(metadata.get("evidence_fingerprint"))}<br>内容由授权工作区筛选后生成。语义核验与正式答复接受由 IR 审阅人完成。</footer></div>
<script id="report-data" type="application/json">{safe_json}</script><script>
const q=document.getElementById('query'),s=document.getElementById('state'),articles=[...document.querySelectorAll('.topic')];
function filter(){{const term=q.value.trim().toLocaleLowerCase();let visible=0;for(const a of articles){{a.hidden=!(a.textContent.toLocaleLowerCase().includes(term)&&(s.value==='all'||a.dataset.state===s.value));if(!a.hidden)visible++;}}document.getElementById('count').textContent='显示 '+visible+' 个议题';document.getElementById('no-match').hidden=visible!==0;}}
q.addEventListener('input',filter);s.addEventListener('change',filter);document.getElementById('print').addEventListener('click',()=>window.print());
window.addEventListener('beforeprint',()=>{{for(const d of document.querySelectorAll('details')){{d.dataset.wasOpen=String(d.open);d.open=true;}}}});
window.addEventListener('afterprint',()=>{{for(const d of document.querySelectorAll('details')){{d.open=d.dataset.wasOpen==='true';}}}});
</script></body></html>'''


def render_markdown(report: dict) -> str:
    m = report["metadata"]
    lines = [f'# {LABELS.get(m.get("mode"), "IR 工作准备")}', "", f'状态：{m.get("status")}；截至：{m.get("as_of")}；受众：{m.get("audience")}', "", "Example 为演示；Draft 答复需要 IR 审阅。", ""]
    for t in report.get("topics", []):
        lines += [f'## {t["title"]}', "", f'变化：{LABELS.get(t["change"]["status"], t["change"]["status"])}；准备优先级：{t["priority"]["score"]}', ""]
        for f in t.get("facts", []):
            lines += [f'- [{f["id"]}] {f.get("text", "证据不可用")}（{f["company"]}；{f["period"]}）']
            lines += [f'  来源：{c["source_id"]}，{c["locator"]}' for c in f.get("citations", [])]
        lines += [""] + [f'{LABELS.get(a["type"], a["type"])}：{a["text"]}' for a in t.get("analysis", [])] + [""]
        for q in t.get("questions", []):
            lines += [f'### {q.get("text", "问题证据不足")}', "", f'类型：{LABELS.get(q["origin"], q["origin"])}；实际提问：{q.get("actual_question_count", 0)}', ""]
            lines += [f'- 追问：{f}' for f in q.get("follow_ups", [])]
            for a in t.get("answers", []):
                if a.get("question_id") == q.get("id"):
                    lines += ["", f'回答版本 {a["version"]}，状态 {a["status"]}']
                    for st in a.get("statements", []):
                        lines += [f'- {st["text"]}'] + [f'  来源：{c["source_id"]}，{c["locator"]}' for c in st.get("citations", [])]
                    lines += [f'- 缺口：{_text(g)}' for g in a.get("gaps", [])]
            lines += [""]
        lines += ["### 准备动作与缺口", ""] + [f'- {_text(x)}' for x in t.get("actions", []) + t.get("gaps", [])] + [""]
    lines += ["## 财报比较", ""]
    for row in report.get("earnings", {}).get("comparisons", []):
        lines += [f'- {row["company"]} {row["period"]} {row["metric"]}：实际 {_text(row.get("actual"))}，预期 {_text(row.get("consensus"))}，差异 {_text(row.get("difference"))}，相对差异 {_text(row.get("percentage_difference"))}%；{LABELS.get(row["status"], row["status"])}。']
    lines += [f'- {_text(x)}' for x in report.get("earnings", {}).get("gaps", [])]
    lines += ["", "## 会议准备", ""]
    for meeting in report.get("meeting_brief", {}).get("meetings", []):
        lines += [f'### {meeting["title"]}', "", f'时间：{meeting["at"]}；实际问题：{meeting.get("actual_question_count", 0)}', ""]
        lines += [f'- {_text(x)}' for x in meeting.get("questions", [])]
    lines += ["", "## 数据缺口", ""] + [f'- {_text(x)}' for x in report.get("data_gaps", [])]
    lines += ["", "## 来源台账", ""]
    for src in report.get("sources", []):
        lines += [f'- {src["id"]} {src.get("title", "")}：{src.get("url", "")}；版本 {src.get("version")}；原始发布日期 {src.get("published_date_raw") or src.get("published_at")}；精度 {src.get("time_precision", "timestamp")}；可用时间边界 {src.get("available_at")}.']
        lines += [f'  获取时间：{src.get("retrieved_at")}；时间说明：{src.get("time_note", "未提供补充说明")}；指纹范围：{src.get("fingerprint_scope", "由输入维护人声明；脚本未核验远程全文")}.']
    lines += ["", f'证据指纹：{m.get("evidence_fingerprint")}', ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=("radar", "earnings", "meeting"), default="radar")
    parser.add_argument("--format", choices=("html", "markdown"))
    parser.add_argument("--audience", choices=("public", "internal"))
    parser.add_argument("--as-of")
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.workspace.read_text(encoding="utf-8"))
        previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous else None
        report = build_report(data, previous=previous, mode=args.mode, audience=args.audience, as_of=args.as_of)
        fmt = args.format or ("markdown" if args.output.suffix.lower() == ".md" else "html")
        result = render_markdown(report) if fmt == "markdown" else render_html(report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(result)
    except FileExistsError:
        print("Output exists; choose a new path. No file was overwritten.", file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError):
        print("Unable to render; validate the workspace, cutoff and output path. No raw input is logged.", file=sys.stderr)
        return 1
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
