# -*- coding: utf-8 -*-
"""毛选精读 · 页面输出（导师模式）。

用法：
    python site/render.py          → site/out/   首页是裸片段，供 Artifact 包骨架
    python site/render.py pages    → site/pages/ 首页是完整文档，供 GitHub Pages

两种目标对首页的要求正好相反：Artifact 会把 index.html 塞进它自己的 <head>/<body>
骨架（并注入 charset），所以首页不能自带文档头；GitHub Pages 原样提供文件，
所以首页必须自带。其余页面在两种模式下都是完整文档。
"""
import os, io, re, json, sys, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import (ROOT, OUT, ART, TOTAL, SECS, extract, build_source_html,
                   md_to_html, parse_md, split_sections, split_h3, load_shapes,
                   doubts_of, quotes_of, esc, inline)

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = len(sys.argv) > 1 and sys.argv[1] == "pages"
if PAGES:
    OUT = os.path.join(HERE, "pages")
os.makedirs(os.path.join(OUT, "a"), exist_ok=True)
for f in ("app.css", "app.js"):
    io.open(os.path.join(OUT, f), "w", encoding="utf-8").write(
        io.open(os.path.join(HERE, f), encoding="utf-8").read())

SHAPES, MOVES = load_shapes()
SH = {d["id"]: d for d in SHAPES}
MV = {d["id"]: d for d in MOVES}

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Noto+Serif+SC:wght@400;700&family=Noto+Sans+SC:wght@500'
         '&family=Spectral:ital,wght@0,400;0,600;1,400&display=swap">')

# 只有 index.html 会被 Artifact 的骨架包起来（它注入 charset / viewport）。
# 其余页面是「supporting files」，原样输出——必须自带完整文档头，
# 否则浏览器按 quirks 模式渲染，中文还会乱码。
def HEAD(title, up, standalone=True):
    h = "<title>%s</title>%s<link rel=\"stylesheet\" href=\"%sapp.css\">" % (title, FONTS, up)
    if not standalone:
        return h + "\n"
    return ('<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '%s\n</head>\n<body>\n' % h)

FOOT_HTML = "\n</body>\n</html>\n"

def bar(up, extra=""):
    return ('<header class="bar"><div class="bar-in">'
            '<a class="home" href="%sindex.html"><span class="hm">毛选</span>精读</a>'
            '<nav class="chips">%s'
            '<a class="cb" href="%sshapes.html">形状库</a>'
            '<a class="cb" href="%squotes.html">金句</a>'
            '<a class="cb" href="%sdoubts.html">存疑</a>'
            '</nav></div><div class="prog" id="prog"></div></header>' % (up, extra, up, up, up))

VOL = {"1": "一", "2": "二", "3": "三", "4": "四"}
LEGEND = ('<div class="key"><span class="kt">可信度</span>'
          '<span class="k1">原文</span><span class="k2">题解注释</span>'
          '<span class="k3">学界看法</span><span class="k4">本站判断</span></div>')

# ------------------------------------------------------------------ 收集
arts = []
for aid, slug, lo, hi, bookpg in ART:
    path = os.path.join(ROOT, "docs/篇目/%s.md" % slug)
    if not os.path.exists(path):
        print("  跳过（尚无解读）:", slug); continue
    fm, md = parse_md(path)
    title, date, headnote, body, notes = extract(lo, hi)
    srchtml, srcdata, nunits = build_source_html(body, notes)
    arts.append(dict(id=aid, slug=slug, fm=fm, md=md, sections=split_sections(md),
                     title=title, date=date, headnote=headnote, srchtml=srchtml,
                     srcdata=srcdata, notes=notes, bookpg=bookpg, nunits=nunits,
                     doubts=doubts_of(md), quotes=quotes_of(md)))
arts.sort(key=lambda a: (str(a["fm"].get("volume")), str(a["fm"].get("date"))))
AIDX = {a["id"]: a for a in arts}


def notes_block(a):
    if not a["notes"]:
        return ""
    items, cur = [], ""
    for _, t in a["notes"]:
        if re.match(r"^[〔︿]?\s*\d", t):
            if cur: items.append(cur)
            cur = t
        else:
            cur += t
    if cur: items.append(cur)
    return ('<details class="notesrc"><summary>原书注释 %d 条</summary>%s'
            '<p class="prov">录自《毛泽东选集》第%s卷，人民出版社 1991 年第二版，第 %s 页。逐字抽自原书，未作改动。</p></details>'
            % (len(items), "".join("<p>%s</p>" % esc(x) for x in items),
               VOL.get(str(a["fm"].get("volume")), ""), a["bookpg"]))


def try_box(key, label, prompt, cta="先写下我的答案"):
    return ('<div class="try" data-k="%s" data-l="%s"><div class="tq">%s</div>'
            '<div class="tslot"></div><button class="tbtn" type="button">%s</button></div>'
            % (key, esc(label), prompt, cta))


def shape_quiz(a):
    """文本细读之前的形状设问。"""
    mine = a["fm"].get("shapes") or []
    if isinstance(mine, str): mine = [mine]
    opts = "".join('<li><b>%s</b>——%s</li>' % (esc(d["id"]), esc(d.get("rule", ""))) for d in SHAPES)
    ans = ""
    for sid in mine:
        d = SH.get(sid)
        if not d: continue
        exs = [e for e in d.get("examples", []) if a["fm"].get("title", "").replace("，", "") in e.replace("，", "")]
        ans += ('<div class="ansd"><b class="moss">%s</b><p>%s</p>%s</div>'
                % (esc(sid), esc(d.get("how", "")),
                   ("<p class='exh'>本篇的落点：%s</p>" % "；".join(esc(e.split("：", 1)[-1]) for e in exs)) if exs else ""))
    if not mine:
        ans = '<div class="ansd"><p>这一篇看不出上面任何一种形状——他不是在对付一个反对意见，而是在给一份已经定下的事规定做法。<b>看不出形状也是一种答案</b>，不要硬套。</p></div>'
    return ('<section class="quiz" id="quiz"><div class="qlab">停一下 · 先答再往下读</div>'
            '<p class="qask">这一篇对付反对意见用的是哪一种形状？</p>'
            '<ol class="qopt">%s</ol>%s'
            '<details class="rev"><summary>看本站的判断</summary>%s'
            '<p class="how">怎么看出来的：先找出他有没有接下对方的标准（接下了 → 抢前提），'
            '再看他有没有说"情况变了"（有 → 改事实基础），'
            '最后看他是不是没拆对方的做法而只是加了人（是 → 加一层）。'
            '<a href="../shapes.html">三种形状的完整说明 ›</a></p></details></section>'
            % (opts, try_box(a["id"] + ":shape", "论证形状设问", "你的判断是哪一种？为什么。", "先写我的判断"), ans))


def questions_block(a, qs_md):
    items = re.findall(r"^\d+\.\s+(.*)$", qs_md, re.M)
    lis = ""
    for n, q in enumerate(items, 1):
        lis += ('<li><div class="qn">%d</div><div class="qb"><p>%s</p>%s</div></li>'
                % (n, inline(q), try_box("%s:q%d" % (a["id"], n), "第 %d 问" % n, "", "写下我的答案")))
    return ('<section class="sec ask" id="s0b"><div class="sh"><span class="sn">先答</span>'
            '<h2>三个问题</h2></div>'
            '<p class="lede">这三个问题必须回到原文才能答。<b>现在答，不要往下看</b>——'
            '读完解读再答，答案已经在你脑子里了，问了等于没问。答不出来也写一句"答不出，卡在哪"。</p>'
            '<ol class="qlist">%s</ol></section>' % lis)


def apply_section(a, md):
    """现实应用：每个情境先让读者写，再展开推演。"""
    out = []
    for h3, body in split_h3(md):
        if h3:
            out.append("<h3>%s</h3>" % inline(h3))
        chunks = re.split(r"^(\*\*情境[^*]*\*\*)\s*$", body, flags=re.M)
        out.append(md_to_html(chunks[0]))
        it = iter(chunks[1:])
        for n, (titl, rest) in enumerate(zip(it, it), 1):
            name = titl.strip("*")
            key = "%s:apply%d" % (a["id"], abs(hash(name)) % 9999)
            out.append('<div class="case"><div class="ch">%s</div>%s'
                       '<details class="rev"><summary>展开本站的推演</summary>%s</details></div>'
                       % (esc(name),
                          try_box(key, name, "按这一篇的思路，你的第一步做什么？写一句就行。", "先写我的第一步"),
                          md_to_html(rest)))
    return "\n".join(out)


def recap(a):
    mine_s = a["fm"].get("shapes") or []
    mine_m = a["fm"].get("moves") or []
    if isinstance(mine_s, str): mine_s = [mine_s]
    if isinstance(mine_m, str): mine_m = [mine_m]
    def chip(x, cls):
        return '<a class="mc %s" href="../shapes.html#%s">%s</a>' % (cls, x, esc(x))
    if not (mine_s or mine_m):
        return ""
    return ('<section class="sec recap"><div class="sh"><span class="sn">带走</span>'
            '<h2>这一篇练过的</h2></div>'
            '<p class="lede">解读本身不用记。下一篇你会再碰到下面这些——到时候先自己试，再看本站怎么说。</p>'
            '<div class="mcs">%s%s</div></section>'
            % ("".join(chip(x, "sh") for x in mine_s), "".join(chip(x, "mv") for x in mine_m)))


# ------------------------------------------------------------------ 单篇
for a in arts:
    fm, sec = a["fm"], dict(a["sections"])
    meta = ['<span class="vol">卷%s</span>' % VOL.get(str(fm.get("volume")), ""),
            '<span class="num">%s</span>' % fm.get("date", ""),
            '<span>%s</span>' % fm.get("genre", ""),
            '<span>原文 <b class="num">%s</b> 字</span>' % fm.get("wordcount_source", "")]
    meta += ['<span class="th">%s</span>' % t for t in (fm.get("themes") or [])]
    pre = ""
    if fm.get("prerequisite"):
        names = fm["prerequisite"] if isinstance(fm["prerequisite"], list) else [fm["prerequisite"]]
        links = []
        for n in names:
            hit = [x for x in arts if (x["fm"].get("title", "").replace("，", "") == n.replace("，", "")
                                       or x["slug"] == n)]
            links.append('<a href="%s.html">%s</a>' % (hit[0]["id"], n) if hit else esc(n))
        pre = '<div class="prereq"><b>建议先读</b>%s</div>' % " · ".join(links)

    # 检验与延伸拆开：三个问题提前，其余留在末尾
    qs_md, rest_md = "", []
    for h3, b in split_h3(sec.get("检验与延伸", "")):
        if h3 == "三个问题":
            qs_md = b
        elif h3:
            rest_md.append("### " + h3 + "\n" + b)
        else:
            rest_md.append(b)

    nav = ['<li><a href="#s0">原文</a></li>', '<li><a href="#s0b">三个问题</a></li>',
           '<li><a href="#quiz">论证形状</a></li>']
    body = []
    for idx, name in enumerate(SECS, 1):
        if name not in sec:
            continue
        sid = "s%d" % idx
        nav.append('<li><a href="#%s">%s</a></li>' % (sid, name))
        inner = (apply_section(a, sec[name]) if name == "现实应用"
                 else md_to_html("\n".join(rest_md)) if name == "检验与延伸"
                 else md_to_html(sec[name]))
        extra = ""
        if name == "检验与延伸":
            extra = '<p class="backq">「三个问题」在原文之后，<a href="#s0b">回去对一下你写的答案</a>。</p>'
        body.append('<section class="sec" id="%s"><div class="sh"><span class="sn num">%d</span>'
                    '<h2>%s</h2><button class="anb" data-a="%s" data-l="%s" type="button">写点什么</button></div>'
                    '%s%s</section>' % (sid, idx, esc(name), sid, esc(name), extra, inner))
        if name == "写作现场":
            body.append(shape_quiz(a))
    nav.append('<li><a href="#s7">我的感悟</a></li>')
    navhtml = "".join(nav)

    page = HEAD(esc(fm.get("title", a["slug"])) + " · 毛选精读", "../")
    page += bar("../", '<button class="cb d" id="dj" type="button">存疑</button>'
                       '<button class="cb n" id="nj" type="button">批注</button>')
    page += """
<div class="shell"><div class="grid"><article>
<header class="mast">
 <div class="rail">卷%s</div>
 <p class="eyebrow">原文 ＋ 史实层 ＋ 应用层</p>
 <h1>%s</h1>
 <div class="meta">%s</div>
 %s%s
 %s
</header>
<nav class="tocm"><div class="tt">这一篇怎么读</div><ol>%s</ol>
<p class="tn">顺序是有意的：<b>先读原文，再答三问，再猜形状</b>，然后才看解读。</p></nav>

<section class="sec src" id="s0"><div class="sh"><span class="sn">原</span><h2>原文</h2>
<button class="anb" data-a="s0" data-l="原文（整篇）" type="button">写点什么</button></div>
<div class="srcwrap">
 <div class="srchead"><b>%s</b> <span class="num">%s</span>%s
 <span class="dim">全文按原文分节，共 %d 节。解读里的「第 X 段／节」都可以点开回看。</span></div>
 %s
 %s
</div></section>
%s
%s
%s
<section class="sec" id="s7"><div class="sh"><span class="sn">你</span><h2>我的感悟</h2></div>
<p id="nstat" class="dim">正在连接批注存储……</p>
<div id="nall" class="nwrap"></div><div id="ngen"></div></section>
<footer class="foot"><div class="tags">%s</div>
<div>三轮制产出：考证 → 写作 → 对抗性质检。引文逐字核对；凡非原文、非题解注释的断言，都标为本站判断。</div></footer>
</article>
<nav class="toc"><div class="tt">目录</div><ol>%s</ol>%s</nav>
</div></div>
<script>var SRC=%s;var AID="%s";</script>
<script src="../app.js"></script>
""" % (VOL.get(str(fm.get("volume")), ""), esc(fm.get("title", a["slug"])), "".join(meta), pre,
       ('<p class="lede">%s</p>' % esc(a["headnote"])) if a["headnote"] else "",
       LEGEND, navhtml,
       esc(a["title"]), esc(a["date"]),
       ('<br>＊ ' + esc(a["headnote"]) + "<br>") if a["headnote"] else "<br>",
       a["nunits"], a["srchtml"], notes_block(a),
       questions_block(a, qs_md) if qs_md else "",
       "\n".join(body), recap(a),
       "".join('<span>%s</span>' % t for t in (fm.get("applies_to") or [])),
       navhtml, LEGEND,
       json.dumps(a["srcdata"], ensure_ascii=False), a["id"])
    io.open(os.path.join(OUT, "a", a["id"] + ".html"), "w", encoding="utf-8").write(page + FOOT_HTML)

# ------------------------------------------------------------------ 形状库
def shape_card(d, cls, kind):
    rows = ""
    for k, lab in [("rule", "一句话"), ("how", "怎么做"), ("cost", "代价"), ("far", "换个地方怎么用")]:
        if d.get(k):
            rows += '<div class="row"><dt>%s</dt><dd>%s</dd></div>' % (lab, esc(d[k]))
    ex = "".join("<li>%s</li>" % esc(e) for e in d.get("examples", []))
    return ('<section class="shc %s" id="%s"><div class="shh"><span class="tag">%s</span>'
            '<h3>%s</h3></div><dl>%s</dl>'
            '<div class="exs"><span class="exl">本站实例</span><ul>%s</ul></div></section>'
            % (cls, d["id"], kind, esc(d["id"]), rows, ex))

sp = HEAD("论证形状库 · 毛选精读", "") + bar("") + """
<div class="shell"><article>
<header class="mast"><p class="eyebrow">这个站真正的产出</p><h1>论证形状库</h1>
<p class="lede">解读本身不用记。<b>形状和读法要带走</b>——它们让你以后不靠这个站也能读。
每条都挂了本站实例；<b>没有实例的不许进库</b>。新增门槛：换一本书、换一场争论还用得上，或在本项目里已出现三次以上。</p></header>
<h2 class="plain"><span class="moss">三种论证形状</span>　他怎么对付一个反对意见</h2>
<p class="lede sm">读任何说服型文本，第一个动作就是判断它用的是哪一种。三种都不是，也是一种答案——不要硬套。</p>
%s
<h2 class="plain"><span class="moss">七条读法</span>　从文本里把东西读出来的具体动作</h2>
%s
</article></div>""" % ("".join(shape_card(d, "sh", "形状") for d in SHAPES),
                       "".join(shape_card(d, "mv", "读法") for d in MOVES))
io.open(os.path.join(OUT, "shapes.html"), "w", encoding="utf-8").write(sp + FOOT_HTML)

# ------------------------------------------------------------------ 首页
cards = []
for a in arts:
    fm = a["fm"]
    shs = fm.get("shapes") or []
    if isinstance(shs, str): shs = [shs]
    cards.append('<a class="card" href="a/%s.html"><span class="cv">卷%s</span>'
                 '<span class="yr num">%s</span><b>%s</b><p>%s</p>'
                 '<div class="tg">%s</div></a>'
                 % (a["id"], VOL.get(str(fm.get("volume")), ""), fm.get("date", ""),
                    esc(fm.get("title", a["slug"])), esc((a["headnote"] or "")[:62]),
                    "".join('<span class="moss">%s</span>' % esc(x) for x in shs)
                    + "".join('<span>%s</span>' % t for t in (fm.get("themes") or [])[:2])))
PATHS = [("先建立思维底座", "认识论与方法在先，后面所有篇目都要回到这里",
          ["反对本本主义", "实践论", "矛盾论", "改造我们的学习", "关于领导方法的若干问题"]),
         ("管理与组织", "带团队、开会、定决议、让指令落地",
          ["必须注意经济工作", "关心群众生活，注意工作方法", "关于领导方法的若干问题",
           "关于健全党委制", "党委会的工作方法"]),
         ("长期判断力", "看不到结果时靠什么维持判断",
          ["中国的红色政权为什么能够存在？", "星星之火，可以燎原", "论持久战", "愚公移山"])]
have = {a["fm"].get("title"): a["id"] for a in arts}
plist = "".join(
    '<div class="path"><b>%s</b><p>%s</p><div class="pl">%s</div></div>'
    % (name, why, " · ".join(
        '<a href="a/%s.html">%s</a>' % (have[t], t) if t in have else '<span class="todo">%s</span>' % t
        for t in items))
    for name, why, items in PATHS)
ndoubt = sum(len(a["doubts"]) for a in arts)
nquote = sum(len(a["quotes"]) for a in arts)
idx = HEAD("毛选精读", "", standalone=PAGES) + bar("") + """
<div class="shell"><article class="wide">
<header class="mast hero">
 <p class="eyebrow">原文 ＋ 史实层 ＋ 应用层　／　导师模式</p>
 <h1>毛选<span class="thin">精读</span></h1>
 <p class="lede big">把《毛泽东选集》四卷中的三十七篇，逐篇做成原文与解读并列的读本。
 <b>这个站的职能是训练，不是讲解</b>——每篇先让你读原文、答三问、判断他用的是哪一种论证形状，然后才展开解读。</p>
 %s
</header>
<div class="stats">
 <div class="st"><b class="num">%d<span class="of">／%d</span></b><span>已完成篇目</span></div>
 <div class="st"><b class="num">%d</b><span>论证形状 ＋ 读法</span></div>
 <div class="st"><b class="num">%d</b><span>存疑待核</span></div>
 <div class="st"><b class="num">%d</b><span>金句已解剖</span></div>
</div>
<h2 class="plain">三条读法</h2><div class="paths">%s</div>
<h2 class="plain">已完成的篇目</h2><div class="cards">%s</div>
<h2 class="plain">这个站是怎么做的</h2>
<div class="how4">
 <div><b>先问后讲</b><p>每篇在解读之前先问你一句——这一篇用的是哪种论证形状。答完再看本站的判断，并且给出"怎么看出来的"。</p></div>
 <div><b>三轮制</b><p>考证（只查不写）→ 写作 → 对抗性质检。三轮分开跑，考证轮不写解读，才不会为了让解读顺畅而扭曲史实。</p></div>
 <div><b>可信度四级</b><p>原文 ／ 题解注释 ／ 学界看法 ／ 本站判断。最后一级用虚线框，那是最该被你质疑的部分。</p></div>
 <div><b>输出你自己来</b><p>三个问题和每个现实情境，都先让你写下自己的答案，再展开本站的推演作对照。</p></div>
</div>
</article></div>""" % (LEGEND, len(arts), TOTAL, len(SHAPES) + len(MOVES), ndoubt, nquote, plist, "".join(cards))
io.open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(idx + (FOOT_HTML if PAGES else ""))

# ------------------------------------------------------------------ 存疑 / 金句
blocks = "".join(
    '<section class="dgroup"><h3><a href="a/%s.html">%s</a><span class="cnt num">%d 处</span></h3>'
    '<ul>%s</ul></section>'
    % (a["id"], esc(a["fm"].get("title", a["slug"])), len(a["doubts"]),
       "".join("<li>%s</li>" % esc(x) for x in a["doubts"])) for a in arts)
io.open(os.path.join(OUT, "doubts.html"), "w", encoding="utf-8").write(
    HEAD("存疑索引 · 毛选精读", "") + bar("") + """
<div class="shell"><article>
<header class="mast"><p class="eyebrow">诚实度仪表盘</p><h1>存疑索引</h1>
<p class="lede">全站标为「本站判断 ／ 存疑」的地方汇总在这里，共 <b class="num">%d</b> 处。
每一条都是写作时本来可以顺手编过去、却没有编的地方。这一页同时是人工核对的工作清单——核实一条，就从这里少一条。</p></header>
%s</article></div>""" % (ndoubt, blocks) + FOOT_HTML)

qcards = []
for a in arts:
    for text, f in a["quotes"]:
        rows = ""
        for k in ["出处", "当时指什么", "它成立的前提", "常见误读", "还剩下什么"]:
            if k in f:
                cls = " mis" if k == "常见误读" else (" left" if k == "还剩下什么" else "")
                rows += '<div class="row%s"><dt>%s</dt><dd>%s</dd></div>' % (
                    cls, k, re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(f[k])))
        qcards.append('<details class="qc"><summary><span class="qt">%s</span>'
                      '<span class="qs">%s　<span class="num">%s</span></span></summary><dl>%s</dl>'
                      '<a class="more" href="a/%s.html">回到原篇 ›</a></details>'
                      % (esc(text), esc(a["fm"].get("title", "")), a["fm"].get("date", ""), rows, a["id"]))
io.open(os.path.join(OUT, "quotes.html"), "w", encoding="utf-8").write(
    HEAD("金句库 · 毛选精读", "") + bar("") + """
<div class="shell"><article>
<header class="mast"><p class="eyebrow">剥掉历史条件之后</p><h1>金句库</h1>
<p class="lede">共 <b class="num">%d</b> 条。默认只显示原句，点开才展开解剖。
请特别注意每条里的<span class="hl-mis">常见误读</span>和<b>还剩下什么</b>两行——
后者是剥掉具体历史条件后真正可迁移的那一点点内核，多数比口号小得多。</p></header>
%s</article></div>""" % (nquote, "".join(qcards)) + FOOT_HTML)

print("生成完毕：%d 篇 ／ 形状 %d ＋ 读法 %d ／ 存疑 %d ／ 金句 %d"
      % (len(arts), len(SHAPES), len(MOVES), ndoubt, nquote))
for a in arts:
    sh = a["fm"].get("shapes") or []
    print("  %s %-14s 原文 %2d 节 · 形状 %s" % (a["id"], a["slug"], a["nunits"], sh))
