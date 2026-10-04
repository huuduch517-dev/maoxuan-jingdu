# -*- coding: utf-8 -*-
"""构建并发布到 GitHub Pages。用法：python site/deploy.py ["提交说明"]

做三件事：
1. 按 pages 模式重建 site/pages/（首页带完整文档头）
2. 提交到 main
3. 用 git subtree 把 site/pages/ 推到 gh-pages 分支

注意：本机 git 配了 http.proxy=127.0.0.1:7897，代理不在跑时推送会失败，
所以每条 git 命令都带 -c http.proxy= -c https.proxy= 临时绕开（不动全局配置）。
"""
import os, subprocess, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIT = ["git", "-c", "http.proxy=", "-c", "https.proxy="]
URL = "https://huuduch517-dev.github.io/maoxuan-jingdu/"


def run(cmd, **kw):
    print("  $", " ".join(cmd[:3]) + (" …" if len(cmd) > 3 else ""))
    return subprocess.run(cmd, cwd=ROOT, **kw)


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else \
        "更新站点 " + datetime.date.today().isoformat()

    print("1／3 构建")
    if run([sys.executable, "site/render.py", "pages"]).returncode:
        sys.exit("构建失败")

    print("2／3 提交 main")
    run(GIT + ["add", "-A"])
    r = run(GIT + ["commit", "-q", "-m", msg])
    if r.returncode:
        print("  （没有改动可提交）")
    if run(GIT + ["push", "origin", "main"]).returncode:
        sys.exit("推送 main 失败——检查代理是否在跑")

    print("3／3 发布 gh-pages")
    if run(GIT + ["subtree", "push", "--prefix", "site/pages", "origin", "gh-pages"]).returncode:
        print("  subtree 推送失败，改用强制覆盖")
        run(GIT + ["push", "origin",
                   "`" + "git subtree split --prefix site/pages main`" + ":gh-pages", "--force"])

    print("\n完成 →", URL)
    print("（GitHub Pages 构建约需一分钟）")


if __name__ == "__main__":
    main()
