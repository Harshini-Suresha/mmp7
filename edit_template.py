#!/usr/bin/env python3
"""Edit the at1r bundled template: drop the Abstract section and trim the
Contact section to just the mail link, re-escaped so the JSON survives inside
the <script> tag. Run: python3 edit_template.py
"""
import json, os, re

INDEX = "/Users/harshinisuresha/Desktop/at1r-nanobody-7T83/index.html"


def ser(s):
    out = json.dumps(s, ensure_ascii=False)
    return (out.replace("<", "\\u003c").replace(">", "\\u003e")
               .replace("/", "\\u002f").replace("&", "\\u0026"))


def main():
    html = open(INDEX).read()
    start_tag = '<script type="__bundler/template">\n'
    end_tag = "\n  </script>"
    i = html.index(start_tag) + len(start_tag)
    j = html.index(end_tag, i)
    tpl = json.loads(html[i:j])

    before = tpl
    removed_abstract = "<!-- ABSTRACT -->" in tpl
    tpl = re.sub(r"<!-- ABSTRACT -->\s*<section id=\"abstract\".*?</section>\n?", "", tpl,
                 count=1, flags=re.S)
    removed_name = "[YOUR NAME]" in tpl
    tpl = re.sub(r"<p[^>]*>\[YOUR NAME\]</p>\n?", "", tpl, count=1)
    removed_gh = "[GitHub or LinkedIn link]" in tpl
    tpl = re.sub(r"<p[^>]*>\[GitHub or LinkedIn link\]</p>\n?", "", tpl, count=1)

    print("abstract removed:", removed_abstract)
    print("[YOUR NAME] removed:", removed_name)
    print("[GitHub or LinkedIn link] removed:", removed_gh)

    kept = re.findall(r"mailto:[^\"']+", tpl)
    print("mail links kept:", kept)

    new_html = html[:i] + ser(tpl) + html[j:]
    open(INDEX, "w").write(new_html)

    # verify round-trip
    ok = True if json.loads(new_html[i:new_html.index(end_tag, i)]) == tpl else False  # noqa
    for kw in ("<!-- ABSTRACT -->", "[YOUR NAME]", "[GitHub or LinkedIn link]"):
        kv = json.loads(new_html[i:new_html.index(end_tag, i)])
        if kw in kv:
            ok, print(f"WARNING {kw} still present"), None
    print("round-trip OK:", ok)


if __name__ == "__main__":
    main()