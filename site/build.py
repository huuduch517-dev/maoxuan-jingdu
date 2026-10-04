# -*- coding: utf-8 -*-
"""毛选精读 · 站点生成器（核心）

输入：docs/篇目/<slug>.md（解读）+ sources/毛选1-4卷.pdf（原文）+ data/shapes.yaml
输出：site/out/ 下的静态页面（由 render.py 写出）

加一篇新文章：跑完三轮产出 docs/篇目/<slug>.md，在 ART 里加一行，重跑 render.py。
原文、存疑索引、金句库、形状库、进度数字全部自动更新。
"""
import fitz, re, io, os, json, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# id, slug, PDF 起止页, 书内页码
ART = [
    ("a01", "反对本本主义", 123, 132, "109–118"),
    ("a03", "必须注意经济工作", 133, 140, "119–125"),
    ("a04", "关心群众生活注意工作方法", 150, 155, "136–141"),
    ("a05", "论反对日本帝国主义的策略", 156, 183, "142–169"),
    ("a02", "关于领导方法的若干问题", 934, 939, "897–902"),
]
TOTAL = 37

NOTE_OPEN = "〈〔︿"
NOTE_CLOSE = "〉〕﹀"
NOTE_RE = "[" + NOTE_OPEN + NOTE_CLOSE + r"]\s*\d+\s*[" + NOTE_OPEN + NOTE_CLOSE + "]"
CN = "一二三四五六七八九十"
SECS = ["写作现场", "文本细读", "金句解剖", "方法提炼", "现实应用", "检验与延伸"]


# ---------------------------------------------------------------- 原文抽取
def extract(lo, hi):
    """按字号分层：标题 / 日期 / 题解 / 小标题 / 正文 / 篇末注释。

    坑一：PyMuPDF 返回的块序不保证是阅读顺序，必须自己按 页→行→x 排。
    坑二：同一视觉行内的块要按 x 排（纵坐标按 5pt 分桶），否则注号会插进词中间。
    坑三：不能靠「注释」二字判断篇末注释起点，要靠字号。
    坑四：小标题可能跨多行，必须合并连续的标题块。
    坑五：正文左边界逐页不同，首行缩进要跟本页的左边界比。
    """
    d = fitz.open(os.path.join(ROOT, "sources/毛选1-4卷.pdf"))
    rows = []
    for p in range(lo, hi + 1):
        for bl in d[p - 1].get_text("dict")["blocks"]:
            if bl.get("type") != 0 or bl["bbox"][1] <= 62:
                continue
            spans = [sp for ln in bl["lines"] for sp in ln["spans"]]
            if not spans:
                continue
            size = round(sum(s["size"] for s in spans) / len(spans), 1)
            txt = re.sub(r"\s+", "", "".join(s["text"] for s in spans))
            if txt:
                rows.append((p, bl["bbox"][1], bl["bbox"][0], size, txt))
    d.close()
    rows.sort(key=lambda r: (r[0], round(r[1] / 5.0), r[2]))

    base = {}
    for p, y, x, size, t in rows:
        if 8 <= size <= 10.5:
            base[p] = min(base.get(p, 9999), x)

    title = date = ""
    headnote, notes, body = [], [], []
    for p, y, x, size, t in rows:
        if size >= 15 and not title:
            title = t
            continue
        if not date and re.fullmatch(r"（一九[^）]*）", t):
            date = t
            continue
        if t == "注释":
            continue
        if size <= 7.2:
            if t.startswith("*") or t.startswith("＊"):
                headnote.append(t.lstrip("*＊"))
            else:
                notes.append((size, t))
            continue
        if 10.8 <= size <= 14.5:
            body.append(("h", t, False))
        else:
            body.append(("p", t, (x - base.get(p, x)) > 12))
    return title, date, " ".join(headnote), body, notes


def build_source_html(body, notes):
    """合成段落 → 分节。三级：原文小标题 → （一）（二）编号 → 自然段（首行缩进）。"""
    paras, buf, hbuf = [], "", ""
    for kind, t, indent in body:
        if kind == "h":
            if buf:
                paras.append(("p", buf)); buf = ""
            hbuf += t
            continue
        if hbuf:
            paras.append(("h", hbuf)); hbuf = ""
        if indent and buf:
            paras.append(("p", buf)); buf = ""
        buf += t
    if hbuf:
        paras.append(("h", hbuf))
    if buf:
        paras.append(("p", buf))

    has_head = any(k == "h" for k, _ in paras)
    units = []
    if has_head:
        for kind, t in paras:
            if kind == "h":
                m = re.match(r"^([一二三四五六七八九十]+)(.*)$", t)
                units.append([m.group(1) if m else "", m.group(2) if m else t, ""])
            elif units:
                units[-1][2] += t
            else:
                units.append(["", "", t])
    else:
        whole = "".join(t for _, t in paras)
        parts = re.split(r"（([一二三四五六七八九十]+)）", whole)
        if len(parts) > 5:
            it = iter(parts[1:])
            for lab, seg in zip(it, it):
                units.append([lab, "", seg])
        else:
            for i, (_, t) in enumerate(paras):
                units.append([CN[i] if i < len(CN) else "", "", t])

    out, data = [], {}
    for i, (lab, head, txt) in enumerate(units, 1):
        clean = re.sub(NOTE_RE, "", txt)
        clean = re.sub("[" + NOTE_OPEN + NOTE_CLOSE + "]", "", clean)
        data[str(i)] = clean
        num = lab or CN[i - 1] if i <= 10 else str(i)
        label = html.escape(head) if head else ""
        esc_txt = html.escape(txt)
        esc_txt = re.sub("[" + NOTE_OPEN + r"]\s*(\d+)\s*[" + NOTE_CLOSE + "]",
                         r'<sup class="nt">\1</sup>', esc_txt)
        out.append(
            '<section class="op" id="p%d"><div class="opn"><span class="num">%s</span>%s</div>'
            '<p>%s</p>'
            '<button class="anb" data-a="p%d" data-l="原文第%s节" type="button">写点什么</button></section>'
            % (i, num, ('<span class="opt">%s</span>' % label) if label else "", esc_txt, i, num))
    return "\n".join(out), data, len(units)


# ---------------------------------------------------------------- Markdown
def esc(s):
    return html.escape(s, quote=False)


def inline(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"第([一二三四五六七八九十]+)([段节])",
               r'<button class="pr" data-p="\1">第\1\2</button>', s)
    return s


def cite_level(cite):
    """引文的可信度级别：原文 / 题解注释。"""
    if re.search(r"注[〔〈︿]|题解|出版说明|校订表", cite):
        return ("zhu", "题解注释")
    return ("yuan", "原文")


def md_to_html(md, lift_qs=False):
    lines = md.split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("::: "):
            kind = ln[4:].strip().split()[0]
            cls, lbl = {"tip": ("mine obs", "本站判断 ／ 一个细节"),
                        "warning": ("mine", "本站判断 ／ 存疑"),
                        "info": ("acad", "学界看法")}.get(kind, ("mine", "本站判断"))
            inner, i, depth = [], i + 1, 1
            while i < len(lines):
                if lines[i].startswith("::: "):
                    depth += 1
                elif lines[i].strip() == ":::":
                    depth -= 1
                    if depth == 0:
                        break
                inner.append(lines[i]); i += 1
            out.append('<aside class="lv %s"><span class="lvb">%s</span>%s</aside>'
                       % (cls, lbl, md_to_html("\n".join(inner))))
            i += 1
            continue
        if ln.startswith("### "):
            t = ln[4:].strip()
            cls = ' class="gemh"' if t.startswith("「") else ""
            out.append("<h3%s>%s</h3>" % (cls, inline(t)))
            i += 1; continue
        if ln.startswith("## ") or ln.startswith("# ") or ln.startswith("#### "):
            i += 1; continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                head = "".join("<th>%s</th>" % inline(c) for c in rows[0])
                body = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r)
                               for r in rows[1:])
                out.append('<div class="tw"><table><thead><tr>%s</tr></thead>'
                           '<tbody>%s</tbody></table></div>' % (head, body))
            continue
        if ln.startswith("> "):
            q, cite = [], ""
            while i < len(lines) and lines[i].startswith(">"):
                t = lines[i][1:].strip()
                m = re.match(r"<cite>(.*)</cite>", t)
                if m:
                    cite = m.group(1)
                elif t:
                    q.append(t)
                i += 1
            k, name = cite_level(cite) if cite else ("yuan", "原文")
            out.append('<figure class="lv %s q"><span class="lvb">%s</span>'
                       '<blockquote>%s</blockquote>%s</figure>'
                       % (k, name, inline(" ".join(q)),
                          ('<figcaption>%s</figcaption>' % inline(cite)) if cite else ""))
            continue
        if re.match(r"^\d+\. ", ln):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                items.append(inline(re.sub(r"^\d+\. ", "", lines[i]))); i += 1
            out.append('<ol class="qs">%s</ol>' % "".join("<li>%s</li>" % x for x in items))
            continue
        if ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(inline(lines[i][2:])); i += 1
            rows = []
            for x in items:
                m = re.match(r"<strong>(.+?)</strong>[：:](.*)$", x)
                if m:
                    k = m.group(1)
                    cls = " mis" if "误读" in k else (" left" if "还剩下" in k else "")
                    rows.append('<div class="row%s"><dt>%s</dt><dd>%s</dd></div>'
                                % (cls, k, m.group(2)))
                else:
                    rows.append('<div class="row"><dd>%s</dd></div>' % x)
            out.append("<dl>%s</dl>" % "".join(rows))
            continue
        if ln.strip():
            out.append("<p>%s</p>" % inline(ln.strip()))
        i += 1
    return "\n".join(out)


# ---------------------------------------------------------------- 文件解析
def parse_md(path):
    raw = io.open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    fm = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            v = v.strip()
            if v.startswith("["):
                v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
            fm[k.strip()] = v
    return fm, m.group(2)


def split_sections(md):
    """把六节切开，返回有序 [(节名, 该节 markdown)]。"""
    out, cur, buf = [], None, []
    for ln in md.split("\n"):
        m = re.match(r"^## (.+)$", ln)
        if m:
            if cur:
                out.append((cur, "\n".join(buf)))
            cur, buf = m.group(1).strip(), []
        elif cur:
            buf.append(ln)
    if cur:
        out.append((cur, "\n".join(buf)))
    return out


def split_h3(md):
    """把一节按三级标题切开。"""
    out, cur, buf = [], None, []
    for ln in md.split("\n"):
        m = re.match(r"^### (.+)$", ln)
        if m:
            if cur is not None:
                out.append((cur, "\n".join(buf)))
            cur, buf = m.group(1).strip(), []
        else:
            if cur is None:
                cur, buf = "", [ln]
            else:
                buf.append(ln)
    if cur is not None:
        out.append((cur, "\n".join(buf)))
    return out


def load_shapes():
    """极简 YAML 读取，只认本项目 data/shapes.yaml 的结构（两组、每组若干条、条内标量 + examples 列表）。"""
    txt = io.open(os.path.join(ROOT, "data/shapes.yaml"), encoding="utf-8").read()
    groups, g, cur, last = {}, None, None, None
    for raw in txt.splitlines():
        if re.match(r"^(shapes|moves):(\s|#|$)", raw):
            g = raw.split(":")[0]; groups[g] = []; cur = last = None
            continue
        if g is None or not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^\s*-\s+id:\s*(.+)$", raw)
        if m:
            cur = {"id": m.group(1).strip(), "examples": []}
            groups[g].append(cur); last = None
            continue
        if cur is None:
            continue
        m = re.match(r"^\s{6,}-\s+(.+)$", raw)          # examples 的条目
        if m and last == "examples":
            cur["examples"].append(m.group(1).strip()); continue
        m = re.match(r"^\s{4}(\w+):\s*(.*)$", raw)       # 字段
        if m:
            k, v = m.group(1), m.group(2).strip()
            last = k
            if k != "examples":
                cur[k] = "" if v == "|" else v
            continue
        if last and last != "examples":                   # 块标量续行
            cur[last] = (cur.get(last, "") + " " + raw.strip()).strip()
    return groups.get("shapes", []), groups.get("moves", [])


def doubts_of(md):
    return [re.sub(r"\*\*|`", "", m.group(2)).strip().replace("\n", " ")
            for m in re.finditer(r"::: warning(.*?)\n(.*?)\n:::", md, re.S)]


def quotes_of(md):
    out = []
    for m in re.finditer(r"^### 「(.+?)」\n(.*?)(?=\n### |\n## |\Z)", md, re.M | re.S):
        fields = {}
        for f in re.finditer(r"- \*\*(.+?)\*\*：(.*)", m.group(2)):
            fields[f.group(1)] = f.group(2).strip()
        if fields:
            out.append((m.group(1), fields))
    return out
