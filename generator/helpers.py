"""Small python-docx helpers: fonts, shaded header cells, bordered tables."""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

FONT = "Times New Roman"
HEADER_FILL = "D9E2F3"   # light blue header cells
SECTION_FILL = "F2F2F2"  # grey sub-heading rows


def new_document() -> Document:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.0)
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    st.paragraph_format.space_after = Pt(4)
    for name, size in (("Heading 1", 15), ("Heading 2", 13), ("Heading 3", 12)):
        h = doc.styles[name]
        h.font.name = FONT
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.color.rgb = RGBColor(0, 0, 0)
        h.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        h.paragraph_format.space_before = Pt(10)
        h.paragraph_format.space_after = Pt(6)
    return doc


def para(doc, text="", bold=False, italic=False, size=None, align=None, space_after=None, style=None):
    p = doc.add_paragraph(style=style)
    if text:
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        if size:
            r.font.size = Pt(size)
    if align == "center":
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "justify":
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if space_after is not None:
        p.paragraph_format.space_after = Pt(space_after)
    return p


def labelled(doc, label, text, size=None):
    """'Label: text' with the label in bold."""
    p = doc.add_paragraph()
    r = p.add_run(label + " ")
    r.bold = True
    r2 = p.add_run(text)
    if size:
        r.font.size = r2.font.size = Pt(size)
    return p


def bullets(doc, items, size=None):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        r = p.add_run(it)
        if size:
            r.font.size = Pt(size)


def heading(doc, text, level=1, center=False):
    h = doc.add_heading(text, level=level)
    if center:
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return h


def page_break(doc):
    doc.add_page_break()


def _shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:shd")):
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def _write(cell, text, bold=False, size=9.5, align=None):
    cell.text = ""
    lines = str(text if text is not None else "").split("\n")
    for i, line in enumerate(lines):
        p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run(line)
        r.bold = bold
        r.font.size = Pt(size)
        if align == "center":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def table(doc, header, rows, widths=None, size=9.5, center_cols=(), header_fill=HEADER_FILL):
    """Bordered table. `header` may be None. `widths` in cm."""
    ncols = len(header) if header else len(rows[0])
    t = doc.add_table(rows=0, cols=ncols)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    if header:
        cells = t.add_row().cells
        for i, h in enumerate(header):
            _write(cells[i], h, bold=True, size=size, align="center")
            _shade(cells[i], header_fill)
        _repeat_header(t.rows[0])
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            _write(cells[i], v, size=size, align="center" if i in center_cols else None)
    _apply_widths(t, widths or [17.0 / ncols] * ncols)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def _apply_widths(t, widths):
    """Fixed layout + grid + cell widths so Word and LibreOffice both respect them."""
    tblPr = t._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    for i, w in enumerate(widths):
        t.columns[i].width = Cm(w)
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)


def kv_table(doc, pairs, widths=(5.0, 12.0), size=10, label_fill=HEADER_FILL):
    """Two-column key/value table (course-info tables, assignment headers)."""
    t = doc.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for k, v in pairs:
        c = t.add_row().cells
        _write(c[0], k, bold=True, size=size)
        _shade(c[0], label_fill)
        _write(c[1], v, size=size)
    _apply_widths(t, list(widths))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def merged_title_table(doc, title_lines, size=10):
    """Single-cell banner table used on the assessment-plan sheets."""
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _write(t.rows[0].cells[0], "\n".join(title_lines), bold=True, size=size, align="center")
    _shade(t.rows[0].cells[0], HEADER_FILL)
    _apply_widths(t, [17.0])
    return t


def _repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def set_landscape(section):
    from docx.enum.section import WD_ORIENT
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Cm(29.7), Cm(21.0)


def set_portrait(section):
    from docx.enum.section import WD_ORIENT
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width, section.page_height = Cm(21.0), Cm(29.7)
