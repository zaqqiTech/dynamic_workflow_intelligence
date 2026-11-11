"""Turn citation placeholders in a .docx into Mendeley-style citation fields.

Placeholders written by the build script:
  ⟦C4–6,21⟧   a citation of references 4, 5, 6 and 21 (one run)
  ⟦BIB0⟧ / ⟦BIB1⟧   start / end of the reference list
Each citation becomes  { ADDIN CSL_CITATION {json} }  with the CSL-JSON of every cited item embedded,
the format written by the Mendeley Desktop Word plugin (and read by Mendeley Cite's legacy-citation
conversion and by Zotero). The reference list becomes  { ADDIN Mendeley Bibliography CSL_BIBLIOGRAPHY }.
The citation style (IEEE) is recorded as a custom document property, as the plugin does.
"""
import json, os, re, shutil, sys, uuid, zipfile
from xml.sax.saxutils import escape

NS = uuid.UUID("6f1c3a52-2b1e-4c0e-9a77-3d2f0d8f4b10")
STYLE = "http://www.zotero.org/styles/ieee"


def parse_nums(s):
    out = []
    for part in re.split(r"\s*,\s*", s):
        m = re.match(r"(\d+)\s*[–-]\s*(\d+)$", part)
        if m:
            out += list(range(int(m.group(1)), int(m.group(2)) + 1))
        else:
            out.append(int(part))
    return out


def ieee_label(nums):
    """IEEE style: [1]; [7], [8]; [4]–[6]; [4]–[6], [21]."""
    nums = sorted(set(nums))
    groups, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        if j - i >= 2:
            groups.append(f"[{nums[i]}]–[{nums[j]}]")
        else:
            groups += [f"[{n}]" for n in nums[i:j + 1]]
        i = j + 1
    return ", ".join(groups)


def mendeley_item(lib, n, k):
    item = dict(lib[n - 1])
    item["id"] = f"ITEM-{k}"
    item["author"] = [dict({"dropping-particle": "", "non-dropping-particle": "", "parse-names": False, "suffix": ""}, **a)
                      if "family" in a else a for a in item.get("author", [])]
    doc_uuid = uuid.uuid5(NS, f"ref-{n}")
    return {"id": f"ITEM-{k}", "itemData": item, "uris": [f"http://www.mendeley.com/documents/?uuid={doc_uuid}"]}


def citation_json(lib, nums, cid):
    label = ieee_label(nums)
    return {
        "citationID": f"MENDELEY_CITATION_{uuid.uuid5(NS, f'cit-{cid}')}",
        "citationItems": [mendeley_item(lib, n, k + 1) for k, n in enumerate(sorted(set(nums)))],
        "mendeley": {"formattedCitation": label, "plainTextFormattedCitation": label,
                     "previouslyFormattedCitation": label},
        "properties": {"noteIndex": 0},
        "schema": "https://github.com/citation-style-language/schema/raw/master/csl-citation.json",
    }, label


def field(instr, result_run):
    return ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve">{escape(instr)}</w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            f'{result_run}'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>')


def add_custom_props(tmp):
    """Record the citation style as Mendeley's plugin does (docProps/custom.xml)."""
    props = {"Mendeley Citation Style_1": STYLE, "Mendeley Recent Style Id 0_1": STYLE,
             "Mendeley Recent Style Name 0_1": "IEEE"}
    items = "".join(
        f'<property fmtid="{{D5CDD505-2E9C-101B-9397-08002B2CF9AE}}" pid="{i + 2}" name="{escape(k)}">'
        f'<vt:lpwstr>{escape(v)}</vt:lpwstr></property>' for i, (k, v) in enumerate(props.items()))
    open(os.path.join(tmp, "docProps", "custom.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">' + items + '</Properties>')
    ct = os.path.join(tmp, "[Content_Types].xml")
    x = open(ct, encoding="utf-8").read()
    if "/docProps/custom.xml" not in x:
        x = x.replace("</Types>", '<Override PartName="/docProps/custom.xml" '
                      'ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml"/></Types>')
        open(ct, "w", encoding="utf-8").write(x)
    rels = os.path.join(tmp, "_rels", ".rels")
    x = open(rels, encoding="utf-8").read()
    if "docProps/custom.xml" not in x:
        x = x.replace("</Relationships>", '<Relationship Id="rIdCustomProps" '
                      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/custom-properties" '
                      'Target="docProps/custom.xml"/></Relationships>')
        open(rels, "w", encoding="utf-8").write(x)


def convert(docx_in, docx_out, lib_json):
    lib = json.load(open(lib_json, encoding="utf-8"))
    tmp = docx_out + ".d"
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(docx_in) as z:
        z.extractall(tmp)
    path = os.path.join(tmp, "word", "document.xml")
    xml = open(path, encoding="utf-8").read()
    counter = {"n": 0}
    cited = set()

    def sub_cit(mo):
        rpr = re.search(r"<w:rPr>.*?</w:rPr>", mo.group(0), re.S)
        rpr = rpr.group(0) if rpr else ""
        nums = parse_nums(mo.group(1))
        cited.update(nums)
        counter["n"] += 1
        data, label = citation_json(lib, nums, counter["n"])
        instr = "ADDIN CSL_CITATION " + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return field(instr, f'<w:r>{rpr}<w:t xml:space="preserve">{escape(label)}</w:t></w:r>')

    xml = re.sub(r"<w:r>(?:(?!</w:r>).)*?⟦C([0-9–,\- ]+)⟧(?:(?!</w:r>).)*?</w:r>", sub_cit, xml, flags=re.S)
    bib_begin = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                 '<w:r><w:instrText xml:space="preserve">ADDIN Mendeley Bibliography CSL_BIBLIOGRAPHY </w:instrText></w:r>'
                 '<w:r><w:fldChar w:fldCharType="separate"/></w:r>')
    xml, nb0 = re.subn(r"<w:r>(?:(?!</w:r>).)*?⟦BIB0⟧(?:(?!</w:r>).)*?</w:r>", bib_begin, xml, flags=re.S)
    xml, nb1 = re.subn(r"<w:r>(?:(?!</w:r>).)*?⟦BIB1⟧(?:(?!</w:r>).)*?</w:r>",
                       '<w:r><w:fldChar w:fldCharType="end"/></w:r>', xml, flags=re.S)
    assert "⟦C" not in xml and "⟦BIB" not in xml, "unreplaced citation placeholder"
    assert nb0 == 1 and nb1 == 1, "bibliography markers missing"
    missing = set(range(1, len(lib) + 1)) - cited
    assert not missing, f"references never cited: {sorted(missing)}"
    open(path, "w", encoding="utf-8").write(xml)
    add_custom_props(tmp)
    if os.path.exists(docx_out):
        os.remove(docx_out)
    with zipfile.ZipFile(docx_out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(tmp):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, tmp))
    shutil.rmtree(tmp)
    print(f"{counter['n']} citation fields, {len(cited)} distinct references, bibliography field added -> {docx_out}")


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
