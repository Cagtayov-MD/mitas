from http.server import SimpleHTTPRequestHandler, HTTPServer


class H(SimpleHTTPRequestHandler):
    def guess_type(self, path):
        t = super().guess_type(path)
        return t + "; charset=utf-8" if t.startswith("text/") else t


HTTPServer(("127.0.0.1", 8932), H).serve_forever()
