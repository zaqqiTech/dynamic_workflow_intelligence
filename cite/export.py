import json, re, unicodedata
lib = json.load(open("cite/library.json", encoding="utf-8"))
TY = {"article-journal": "JOUR", "book": "BOOK", "chapter": "CHAP", "paper-conference": "CONF", "report": "RPRT", "webpage": "ELEC"}
BT = {"article-journal": "article", "book": "book", "chapter": "incollection", "paper-conference": "inproceedings", "report": "techreport", "webpage": "misc"}

def name(a): return a["literal"] if "literal" in a else (f'{a.get("non-dropping-particle","")+" " if a.get("non-dropping-particle") else ""}{a["family"]}, {a["given"]}')
def pages(p): return p.split("-", 1) if p and "-" in p else (p, None)

ris = []
for i, it in enumerate(lib, 1):
    r = [f"TY  - {TY[it['type']]}"]
    r += [f"AU  - {name(a)}" for a in it.get("author", [])]
    r.append(f"TI  - {it['title']}")
    if it.get("container-title"): r.append(f"T2  - {it['container-title']}")
    if it.get("container-title-short"): r.append(f"J2  - {it['container-title-short']}")
    if it.get("collection-title"): r.append(f"T3  - {it['collection-title']}")
    y = it["issued"]["date-parts"][0][0]; r.append(f"PY  - {y}")
    for k, tag in (("volume", "VL"), ("issue", "IS"), ("publisher", "PB"), ("publisher-place", "CY"), ("DOI", "DO"), ("URL", "UR"), ("number", "M1")):
        if it.get(k): r.append(f"{tag}  - {it[k]}")
    sp, ep = pages(it.get("page"))
    if sp: r.append(f"SP  - {sp}")
    if ep: r.append(f"EP  - {ep}")
    r.append(f"N1  - Cited as [{i}] in the DWI manuscript")
    r.append("ER  - ")
    ris.append("\n".join(r))
open("cite/DWI_references.ris", "w", encoding="utf-8").write("\n\n".join(ris) + "\n")

def key(it, i):
    a = it.get("author", [{}])[0]
    fam = a.get("family") or a.get("literal", "ref").split()[0]
    fam = unicodedata.normalize("NFKD", fam).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z]", "", fam) + str(it["issued"]["date-parts"][0][0]) + f"_{i}"
bib = []
for i, it in enumerate(lib, 1):
    f = {"title": "{" + it["title"] + "}", "year": str(it["issued"]["date-parts"][0][0])}
    auth = " and ".join("{" + a["literal"] + "}" if "literal" in a else name(a) for a in it.get("author", []))
    if auth: f["author"] = auth
    ct = it.get("container-title")
    if ct: f[{"article-journal": "journal", "chapter": "booktitle", "paper-conference": "booktitle"}.get(it["type"], "howpublished")] = ct
    for k, b in (("volume", "volume"), ("issue", "number"), ("publisher", "publisher"), ("publisher-place", "address"),
                 ("DOI", "doi"), ("URL", "url"), ("collection-title", "series")):
        if it.get(k): f[b] = it[k]
    if it.get("page"): f["pages"] = it["page"].replace("-", "--")
    if it["type"] == "report" and it.get("publisher"): f["institution"] = f.pop("publisher")
    bib.append(f"@{BT[it['type']]}{{{key(it, i)},\n" + ",\n".join(f"  {k} = {{{v}}}" for k, v in f.items()) + "\n}")
open("cite/DWI_references.bib", "w", encoding="utf-8").write("\n\n".join(bib) + "\n")
print(len(ris), "RIS records;", len(bib), "BibTeX entries")
