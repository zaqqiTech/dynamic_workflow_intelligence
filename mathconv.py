"""Convert a small math markup to Office Math (OMML) and splice it into a .docx.

Markup (only used inside the build script, never visible to readers):
  x_{..}  x^{..}  x_{..}^{..}   sub/superscripts on the preceding atom
  @frac{a}{b}  @ceil{a}  @set{a}  @ang{a}  @paren{a}  @bars{a}
  @cases{row ;; row}   left brace + stacked rows      @lines{row ;; row}  stacked rows
  @low{base}{limit}    limit below (e.g. max over a set)
  @t{text}  upright text        @q  em space
Runs of >= 2 ASCII letters are set upright (function names, labels); single letters italic.
"""
import json, re, sys, zipfile, shutil, os
from xml.sax.saxutils import escape

OPS = set("=<>≤≥∈∉∪∩∨∧≡−+×≠→⊆≺⪯:|‖")


class P:
    def __init__(self, s):
        self.s, self.i = s, 0

    def peek(self, k=0):
        j = self.i + k
        return self.s[j] if j < len(self.s) else ""

    def group(self):
        assert self.peek() == "{", f"expected {{ at {self.i} in {self.s!r}"
        depth, j = 0, self.i
        while True:
            c = self.s[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        inner = self.s[self.i + 1:j]
        self.i = j + 1
        return inner


def split_top(s, sep=";;"):
    out, depth, cur, i = [], 0, "", 0
    while i < len(s):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
        if depth == 0 and s.startswith(sep, i):
            out.append(cur); cur = ""; i += len(sep); continue
        cur += s[i]; i += 1
    out.append(cur)
    return out


def parse(s):
    """Return list of nodes: ('t', text, upright) | ('sub',b,x) | ('sup',b,x) | ('subsup',b,x,y) |
    ('frac',a,b) | ('d',beg,end,[rows]) | ('arr',[rows]) | ('low',base,lim) | ('txt',text) | ('sp',)"""
    p = P(s)
    nodes = []
    while p.i < len(s):
        c = p.peek()
        if c == "@":
            m = re.match(r"@([a-z]+)", s[p.i:])
            cmd = m.group(1); p.i += len(m.group(0))
            if cmd == "q":
                nodes.append(("txt", "\u2003")); continue
            if cmd == "t":
                nodes.append(("txt", p.group())); continue
            if cmd == "frac":
                a = p.group(); b = p.group(); nodes.append(("frac", parse(a), parse(b))); continue
            if cmd == "low":
                a = p.group(); b = p.group(); nodes.append(("low", parse(a), parse(b))); continue
            if cmd in ("cases", "lines"):
                rows = [[parse(c.strip()) for c in split_top(r.strip(), "&&")] for r in split_top(p.group())]
                mat = ("mat", rows)
                nodes.append(("d", "{", "", [mat]) if cmd == "cases" else mat); continue
            pairs = {"ceil": ("⌈", "⌉"), "set": ("{", "}"), "ang": ("⟨", "⟩"), "paren": ("(", ")"),
                     "bars": ("|", "|"), "ho": ("(", "]")}
            beg, end = pairs[cmd]
            nodes.append(("d", beg, end, parse(p.group()))); continue
        if c in "_^":
            p.i += 1
            if p.peek() == "{":
                arg = parse(p.group())
            else:
                arg = parse(p.s[p.i]); p.i += 1
            base = nodes.pop() if nodes else ("t", "", False)
            # split a multi-char text run so that only its last atom carries the script
            if base[0] == "t" and len(base[1]) > 1:
                txt = base[1]
                m = re.search(r"([A-Za-z]{2,}|[0-9]+|.)$", txt)
                head, atom = txt[:m.start()], m.group(0)
                if head:
                    nodes.append(("t", head, False))
                base = ("t", atom, len(atom) > 1 and atom.isalpha())
            if c == "^" and base[0] == "sub":
                nodes.append(("subsup", base[1], base[2], arg)); continue
            if c == "_" and base[0] == "sup":
                nodes.append(("subsup", base[1], arg, base[2])); continue
            nodes.append(("sub" if c == "_" else "sup", [base], arg)); continue
        # plain characters: group ASCII words, numbers, single symbols
        m = re.match(r"[A-Za-z]{2,}|[0-9]+(?:\.[0-9]+)?|.", s[p.i:])
        tok = m.group(0); p.i += len(tok)
        if tok == " ":
            # drop spaces next to operators (Word spaces operators itself)
            prev = nodes[-1][1][-1:] if nodes and nodes[-1][0] == "t" and nodes[-1][1] else ""
            nxt = s[p.i:p.i + 1]
            if prev in OPS or nxt in OPS or prev == "" or prev in "([{" or nxt in ")]}," or nxt == "":
                continue
        upright = len(tok) > 1 and tok.isalpha()
        nodes.append(("t", tok, upright))
    # merge adjacent text runs with same style
    merged = []
    for n in nodes:
        if merged and n[0] == "t" and merged[-1][0] == "t" and merged[-1][2] == n[2] and not n[2]:
            merged[-1] = ("t", merged[-1][1] + n[1], False)
        else:
            merged.append(n)
    return merged


def omml(nodes, sz):
    rpr = f'<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'

    def run(text, upright=False, normal=False):
        mp = ""
        if normal:
            mp = '<m:rPr><m:nor/></m:rPr>'
        elif upright:
            mp = '<m:rPr><m:sty m:val="p"/></m:rPr>'
        return f'<m:r>{mp}{rpr}<m:t xml:space="preserve">{escape(text)}</m:t></m:r>'

    out = []
    for n in nodes:
        k = n[0]
        if k == "t":
            out.append(run(n[1], n[2]))
        elif k == "txt":
            out.append(run(n[1], normal=True))
        elif k == "sp":
            out.append(run(" "))
        elif k == "sub":
            out.append(f"<m:sSub><m:e>{omml(n[1], sz)}</m:e><m:sub>{omml(n[2], sz)}</m:sub></m:sSub>")
        elif k == "sup":
            out.append(f"<m:sSup><m:e>{omml(n[1], sz)}</m:e><m:sup>{omml(n[2], sz)}</m:sup></m:sSup>")
        elif k == "subsup":
            out.append(f"<m:sSubSup><m:e>{omml(n[1], sz)}</m:e><m:sub>{omml(n[2], sz)}</m:sub>"
                       f"<m:sup>{omml(n[3], sz)}</m:sup></m:sSubSup>")
        elif k == "frac":
            out.append(f"<m:f><m:num>{omml(n[1], sz)}</m:num><m:den>{omml(n[2], sz)}</m:den></m:f>")
        elif k == "low":
            out.append(f"<m:limLow><m:e>{omml(n[1], sz)}</m:e><m:lim>{omml(n[2], sz)}</m:lim></m:limLow>")
        elif k == "d":
            beg, end = n[1], n[2]
            body = omml(n[3], sz)
            out.append(f'<m:d><m:dPr><m:begChr m:val="{escape(beg)}"/><m:endChr m:val="{escape(end)}"/>'
                       f'<m:grow/></m:dPr><m:e>{body}</m:e></m:d>')
        elif k == "mat":
            ncol = max(len(r) for r in n[1])
            mpr = (f'<m:mPr><m:baseJc m:val="center"/><m:cGpRule m:val="3"/><m:cGp m:val="360"/>'
                   '<m:mcs>' + '<m:mc><m:mcPr><m:count m:val="1"/><m:mcJc m:val="left"/></m:mcPr></m:mc>' * ncol + '</m:mcs></m:mPr>')
            rows = "".join("<m:mr>" + "".join(f"<m:e>{omml(c, sz)}</m:e>" for c in (r + [[]] * (ncol - len(r)))) + "</m:mr>"
                           for r in n[1])
            out.append(f"<m:m>{mpr}{rows}</m:m>")
        elif k == "arr":
            rows = "".join(f"<m:e>{omml(r, sz)}</m:e>" for r in n[1])
            out.append(f"<m:eqArr><m:eqArrPr><m:baseJc m:val=\"center\"/></m:eqArrPr>{rows}</m:eqArr>")
    return "".join(out)


def to_omath(src, sz):
    return f"<m:oMath>{omml(parse(src), sz)}</m:oMath>"


def splice(docx_in, docx_out, math_json):
    maths = json.load(open(math_json, encoding="utf-8"))
    tmp = docx_out + ".d"
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(docx_in) as z:
        z.extractall(tmp)
    path = os.path.join(tmp, "word", "document.xml")
    xml = open(path, encoding="utf-8").read()
    if 'xmlns:m="' not in xml[:3000]:
        xml = xml.replace("<w:document ", '<w:document xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" ', 1)
    n_done = 0

    def sub(mo):
        nonlocal n_done
        i = int(mo.group(1)); m = maths[i]
        n_done += 1
        return to_omath(m["src"], m["size"])
    xml = re.sub(r"<w:r>(?:(?!</w:r>).)*?⟦M(\d+)⟧(?:(?!</w:r>).)*?</w:r>", sub, xml, flags=re.S)
    assert "⟦M" not in xml, "unreplaced math placeholder"
    open(path, "w", encoding="utf-8").write(xml)
    if os.path.exists(docx_out):
        os.remove(docx_out)
    with zipfile.ZipFile(docx_out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(tmp):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, tmp))
    shutil.rmtree(tmp)
    print(f"spliced {n_done} equations into {docx_out}")


if __name__ == "__main__":
    splice(sys.argv[1], sys.argv[2], sys.argv[3])
