# -*- coding: utf-8 -*-
"""引文与自检。用法: python site/qc.py <slug> <起页> <止页> [附加页...]"""
import fitz, re, io, sys
QC = "\u201c\u201d\u2018\u2019\u300c\u300d" + '"' + "'"
slug, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
extra = [int(x) for x in sys.argv[4:]]
d = fitz.open("sources/毛选1-4卷.pdf")
def grab(a, b, ymin):
    rows = []
    for p in range(a, b + 1):
        for bl in d[p-1].get_text("blocks"):
            if bl[1] > ymin:
                rows.append((p, round(bl[1] / 5.0), bl[0], bl[4]))
    rows.sort()
    return re.sub(r"\s+", "", "".join(r[3] for r in rows))
def build(y): return grab(lo, hi, y) + "".join(grab(p, p, y) for p in extra)
SRC = [build(62), build(40)]
def norm(s, loose):
    s = re.sub("[" + re.escape(QC) + r"\s]", "", s)
    if loose:
        s = re.sub(r"[\ufe3f\ufe40\u3008\u3009\u3014\u3015\u2026\uff0c\u3002\uff1b0-9\uff10-\uff19]", "", s)
    return s
def find(q):
    for loose in (False, True):
        qn = norm(q, loose)
        for s in SRC:
            if qn in norm(s, loose):
                return "严格" if not loose else "宽松"
    return None
art = io.open("docs/篇目/%s.md" % slug, encoding="utf-8").read()
cn = lambda s: sum(1 for c in s if '\u4e00' <= c <= '\u9fff')
quotes = re.findall(r"^> ([^<\n].*)$", art, re.M)
inline = sorted(set(re.findall(r"[\u300c\u201c]([^\u300d\u201d]{8,90})[\u300d\u201d]", art)))
print("成稿汉字 %d | 引文 %d | 本站行文 %d" % (cn(art), sum(cn(q) for q in quotes), cn(art) - sum(cn(q) for q in quotes)))
bad = ln = 0
for kind, items in (("块", quotes), ("行内", inline)):
    for q in items:
        r = find(q)
        if r is None:
            bad += 1; print("  !! %s引文无出处: %s" % (kind, q[:70]))
        elif r == "宽松":
            ln += 1; print("  ~ %s宽松（需人眼）: %s" % (kind, q[:56]))
print("引文核对: 严格 %d / 宽松 %d / 无出处 %d" % (len(quotes)+len(inline)-bad-ln, ln, bad))
for b in "伟大 英明 令人震撼 醍醐灌顶 降维打击 格局 破局之道 天花板 逆袭 必读 不得不说 值得深思 精髓 真谛 底层逻辑 认知升级 要学会 关键在于 这告诉我们".split():
    for m in re.finditer(re.escape(b), art):
        print("  禁用 %s -> %s" % (b, art[max(0,m.start()-24):m.start()+24].replace("\n","")))
print("感叹号 %d | tip %d | warning %d | info %d | 金句 %d | 方法 %d | 误用 %s" % (
    art.count("\uff01"), art.count("::: tip"), art.count("::: warning"), art.count("::: info"),
    len(re.findall(r"^### \u300c", art, re.M)), len(re.findall(r"^### 方法", art, re.M)), "### 常见误用" in art))
for sec in re.split(r"^## ", art, flags=re.M)[1:]:
    print("   [%s] %d" % (sec.split("\n")[0], cn(sec)))
