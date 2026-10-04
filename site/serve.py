# -*- coding: utf-8 -*-
"""本地预览服务器。

必须自己写一个：python -m http.server 不给 text/html 发 charset=utf-8，
中文会整页乱码；而发布成 Artifact 时骨架会注入 charset，所以产物里不加 meta。
用法：python site/serve.py [端口]
"""
import os, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def guess_type(self, path):
        t = super().guess_type(path)
        if t in ("text/html", "text/css", "application/javascript", "text/javascript"):
            return t + "; charset=utf-8"
        return t

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    print("毛选精读 → http://localhost:%d" % port)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
