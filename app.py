"""Course File Generator – Streamlit interface.

Run locally:   streamlit run app.py
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from generator import build_course_file
from generator import ai
from generator.builder import default_status
from generator.syllabus_pdf import find_course_text, pdf_text
from generator.timetable import load_timetable, rows_for_course

ROOT = Path(__file__).parent
STATIC = json.loads((ROOT / "data" / "static_text.json").read_text(encoding="utf-8"))
COURSE_DIR = ROOT / "data" / "courses"

st.set_page_config(page_title="Course File Generator", page_icon="📘", layout="wide")


# ------------------------------------------------------------------ helpers
def records_editor(label: str, records: list[dict], key: str, columns: list[str] | None = None, height: int | None = None):
    """Editable table for a list of flat dicts."""
    df = pd.DataFrame(records, columns=columns) if columns else pd.DataFrame(records)
    df = df.astype(str)
    kw = {"height": height} if height else {}
    out = st.data_editor(df, num_rows="dynamic", width="stretch", key=key, **kw)
    return out.fillna("").to_dict("records")


def lines(label: str, items: list[str], key: str, height: int = 110) -> list[str]:
    txt = st.text_area(label, "\n".join(items), key=key, height=height)
    return [x.strip() for x in txt.split("\n") if x.strip()]


def matrix_editor(mx: dict, key: str) -> dict:
    df = pd.DataFrame([[r["values"].get(c, "") for c in mx["cols"]] for r in mx["rows"]],
                      index=[r["co"] for r in mx["rows"]], columns=mx["cols"]).astype(str)
    out = st.data_editor(df, width="stretch", key=key).fillna("")
    return {"cols": mx["cols"], "rows": [{"co": i, "values": {c: v for c, v in row.items() if v}} for i, row in out.iterrows()]}


def load_course(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ sidebar: choose the course
st.sidebar.title("📘 Course File Generator")
source = st.sidebar.radio("Start from", ["Saved course", "Upload course JSON", "Syllabus PDF (AI extraction)"])

if source == "Saved course":
    files = sorted(COURSE_DIR.glob("*.json"))
    pick = st.sidebar.selectbox("Course", files, format_func=lambda p: p.stem) if files else None
    if pick and st.sidebar.button("Load course", type="primary"):
        st.session_state.course = load_course(pick)
        st.session_state.pop("timetable_rows", None)
elif source == "Upload course JSON":
    up = st.sidebar.file_uploader("Course JSON", type="json")
    if up and st.sidebar.button("Load course", type="primary"):
        st.session_state.course = json.load(up)
else:
    pdf = st.sidebar.file_uploader("Syllabus PDF (single course or whole program)", type="pdf")
    code = st.sidebar.text_input("Course code (to find it in a program syllabus)")
    template = st.sidebar.selectbox("Copy institutional/format fields from", sorted(COURSE_DIR.glob("*.json")),
                                    format_func=lambda p: p.stem)
    if pdf and st.sidebar.button("Extract with Claude", type="primary"):
        with st.spinner("Reading the syllabus and extracting the course…"):
            try:
                text = find_course_text(pdf_text(pdf), code) if code else pdf_text(pdf)
                got = ai.extract_course_from_syllabus(text, code)
                base = load_course(template)           # inherit layout fields; faculty then edits them
                base["meta"].update({k: v for k, v in got.get("meta", {}).items() if v})
                base["theory"].update({k: v for k, v in got.get("theory", {}).items() if v})
                base["lab"] = None
                base["assignments"], base["end_term"] = [], None
                st.session_state.course = base
                st.sidebar.success("Extracted. Review every tab before generating.")
            except Exception as e:  # noqa: BLE001
                st.sidebar.error(str(e))

course = st.session_state.get("course")
if not course:
    st.title("Course File Generator")
    st.info("Choose a course in the sidebar and press **Load course** to begin.")
    st.stop()

m, th = course["meta"], course["theory"]
lab = course.get("lab")
st.title(f"{m['course_name']}  ({m['course_code']})")

tabs = st.tabs(["1 · Course details", "2 · Outcomes & syllabus", "3 · Lesson plan & mappings",
                "4 · Time table", "5 · Assignments & exam (AI)", "6 · Generate"])

# ------------------------------------------------------------------ 1 · details
with tabs[0]:
    c1, c2 = st.columns(2)
    for col, keys in ((c1, ["course_name", "course_code", "programs", "program_line", "ncrf_level", "session"]),
                      (c2, ["coordinator", "hod", "ltpc", "theory_ltpc", "lab_ltpc", "session_short"])):
        with col:
            for k in keys:
                m[k] = st.text_input(k.replace("_", " ").title(), m.get(k, ""), key=f"m_{k}")
    m["dept_key"] = st.selectbox("Department", list(STATIC["departments"]), index=list(STATIC["departments"]).index(m["dept_key"]),
                                 format_func=lambda k: STATIC["departments"][k]["name"])
    m["program_families"] = st.multiselect("Program families (selects PEOs/PSOs to print)", list(STATIC["peos"]), default=m["program_families"])
    m["theory_faculty"] = lines("Theory faculty (one per line)", m["theory_faculty"], "tf", 70)
    m["lab_faculty"] = lines("Lab faculty (one per line)", m["lab_faculty"], "lf", 70)
    for k in ("course_type", "course_nature", "prerequisites", "assumed_knowledge", "following_courses"):
        m[k] = st.text_input(k.replace("_", " ").title(), m.get(k, ""), key=f"m_{k}")

# ------------------------------------------------------------------ 2 · outcomes & syllabus
with tabs[1]:
    st.subheader("Theory course outcomes")
    th["objective"] = st.text_area("Course objective", th["objective"], height=90)
    th["cos"] = records_editor("COs", th["cos"], "cos_th", ["id", "text", "mapping"])
    th["relevance"] = st.text_area("Relevance of the course", th["relevance"], height=150)
    syl = th["syllabus"]
    st.subheader("Syllabus")
    syl["sections"] = records_editor("Sections", syl["sections"], "syl_sec", ["section", "weightage", "text"])
    th["topic_layout"] = records_editor("Topic layout", th["topic_layout"], "layout", ["section", "topics", "L", "T", "P"])
    b1, b2 = st.columns(2)
    with b1:
        syl["text_books"] = lines("Text books", syl.get("text_books", []), "tb")
        syl["online_content"] = lines("Online content", syl.get("online_content", []), "oc")
        syl["linkedin"] = lines("LinkedIn Learning", syl.get("linkedin", []), "li")
    with b2:
        syl["reference_books"] = lines("Reference books", syl.get("reference_books", []), "rb")
        syl["nptel"] = lines("NPTEL / MOOCs", syl.get("nptel", []), "np")
    if lab:
        st.subheader("Lab course outcomes")
        lab["objective"] = st.text_area("Lab objective", lab["objective"], height=80)
        lab["cos"] = records_editor("Lab COs", lab["cos"], "cos_lab", ["id", "text", "mapping"])
        lab["relevance"] = st.text_area("Relevance of the lab", lab["relevance"], height=120)
        lab["experiments"] = lines("List of experiments / assignments", lab.get("experiments", []), "exps", 160)

# ------------------------------------------------------------------ 3 · lesson plan & mappings
with tabs[2]:
    cols = ["no", "topic", "co", "bt", "pedagogy", "ict", "ai"]
    st.subheader("Theory lesson plan")
    th["lesson_plan"] = records_editor("Lesson plan", th["lesson_plan"], "lp_th", cols)
    st.subheader("CO–PO/PSO mapping (theory)")
    th["co_po"] = matrix_editor(th["co_po"], "copo_th")
    st.subheader("CO–KSA mapping (theory)")
    th["co_ksa"] = records_editor("CO-KSA", th["co_ksa"], "ksa_th", ["co", "wk", "sk", "ak", "sdg", "ethics", "skill", "nsqf"])
    if lab:
        st.subheader("Lab lesson plan")
        lab["lesson_plan"] = records_editor("Lab plan", lab["lesson_plan"], "lp_lab", cols)
        st.subheader("CO–PO/PSO mapping (lab)")
        lab["co_po"] = matrix_editor(lab["co_po"], "copo_lab")
        st.subheader("CO–KSA mapping (lab)")
        lab["co_ksa"] = records_editor("Lab CO-KSA", lab["co_ksa"], "ksa_lab", ["co", "wk", "sk", "ak", "sdg", "ethics", "skill", "nsqf"])
    st.subheader("CO targets")
    ct = course["co_targets"]
    ct["dated"] = st.text_input("Dated", ct.get("dated", ""))
    ct["note"] = st.text_area("Note on revision of targets", ct.get("note", ""), height=70)
    ct["targets"] = [{"co": r["co"], "target": r["target"]} for r in records_editor("Targets", ct["targets"], "targets", ["co", "target"])]

# ------------------------------------------------------------------ 4 · time table
with tabs[3]:
    st.write("Upload the department time table (CSV/Excel) with columns "
             "`Faculty, Day, Time, Course Code, Course Name, Program / Section, Room, Type`.")
    st.download_button("Download template CSV", (ROOT / "data" / "timetable_template.csv").read_bytes(), "timetable_template.csv")
    up = st.file_uploader("Time table", type=["csv", "xlsx", "xls"])
    if up:
        try:
            df = load_timetable(up)
            only_course = st.checkbox("Only rows of this course", value=True)
            rows = rows_for_course(df, m["theory_faculty"] + m["lab_faculty"], m["course_code"] if only_course else "")
            st.session_state.timetable_rows = records_editor("Rows", rows, "tt_rows")
        except Exception as e:  # noqa: BLE001
            st.error(str(e))
    if st.session_state.get("timetable_rows"):
        st.success(f"{len(st.session_state.timetable_rows)} time-table rows will be added to item 11.")

# ------------------------------------------------------------------ 5 · AI drafts
with tabs[4]:
    st.caption("Drafts come from Claude and must be reviewed by the faculty member. Needs ANTHROPIC_API_KEY.")
    a, b, c3 = st.columns(3)
    if a.button("Draft 'Relevance of the course'"):
        with st.spinner("Drafting…"):
            try:
                th["relevance"] = ai.draft_relevance(course)
                st.success("Updated in tab 2.")
            except Exception as e:  # noqa: BLE001
                st.error(str(e))
    n_ass = b.number_input("Assignments to draft", 1, 9, 3)
    if b.button("Draft assignments"):
        with st.spinner("Drafting…"):
            try:
                course["assignments"] = ai.draft_assignments(course, int(n_ass))
            except Exception as e:  # noqa: BLE001
                st.error(str(e))
    if c3.button("Draft end-term paper"):
        with st.spinner("Drafting…"):
            try:
                paper = ai.draft_end_term(course)
                base = course.get("end_term") or {"title": "End Term Examination", "semester": "", "date": "", "program": m["programs"],
                                                  "credits": m["ltpc"].split("-")[-1], "duration": "90 MINUTES", "max_marks": "50", "ksa_coverage": []}
                base["parts"] = paper["parts"]
                course["end_term"] = base
            except Exception as e:  # noqa: BLE001
                st.error(str(e))

    st.subheader("Assignments")
    for i, asg in enumerate(course.get("assignments") or []):
        with st.expander(asg["title"], expanded=False):
            asg["title"] = st.text_input("Title", asg["title"], key=f"at{i}")
            asg["learning_outcome"] = st.text_area("Learning outcome", asg["learning_outcome"], key=f"alo{i}", height=60)
            asg["questions"] = records_editor("Questions", asg["questions"], f"aq{i}", ["no", "text", "bt", "co"])
            if st.button("Draft model solutions", key=f"as{i}"):
                with st.spinner("Drafting…"):
                    try:
                        asg["solutions"] = ai.draft_solutions([{"no": q["no"], "text": q["text"]} for q in asg["questions"]], m["course_name"])
                    except Exception as e:  # noqa: BLE001
                        st.error(str(e))
            if asg.get("solutions"):
                asg["solutions"] = records_editor("Solutions", asg["solutions"], f"asol{i}", ["no", "q", "answer"])

    st.subheader("End-term paper")
    et = course.get("end_term")
    if et:
        for j, part in enumerate(et["parts"]):
            part["name"] = st.text_input("Part title", part["name"], key=f"pn{j}")
            part["questions"] = records_editor("Questions", part["questions"], f"pq{j}", ["no", "text", "marks", "co", "bt"])
        if st.button("Draft model solution of end-term"):
            with st.spinner("Drafting…"):
                try:
                    qs = [{"no": q["no"], "text": q["text"]} for p in et["parts"] for q in p["questions"]]
                    et["solutions"] = ai.draft_solutions(qs, m["course_name"])
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))
        if et.get("solutions"):
            et["solutions"] = records_editor("Model solution", et["solutions"], "etsol", ["no", "q", "answer"])

# ------------------------------------------------------------------ 6 · generate
with tabs[5]:
    tt = st.session_state.get("timetable_rows")
    status = default_status(course, STATIC, bool(tt))
    st.subheader("Contents checklist (Y/N column)")
    items = [{"No.": k, "Description": next((i["text"] for i in STATIC["checklist"] if i["kind"] == "item" and i["no"].rstrip(".") == k), ""), "Y/N": v}
             for k, v in status.items()]
    edited = st.data_editor(pd.DataFrame(items), width="stretch", hide_index=True, key="status",
                            disabled=["No.", "Description"], height=320)
    status = dict(zip(edited["No."], edited["Y/N"]))
    g1, g2 = st.columns(2)
    if g1.button("Generate course file", type="primary"):
        with st.spinner("Building the course file…"):
            data = build_course_file(course, STATIC, tt, status)
        st.session_state.docx = data
    if st.session_state.get("docx"):
        g1.download_button("⬇ Download course file (.docx)", st.session_state.docx,
                           f"Course_File_{m['course_code']}.docx",
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    g2.download_button("⬇ Save course data (.json)", json.dumps(course, ensure_ascii=False, indent=1).encode("utf-8"),
                       f"{m['course_code']}.json", "application/json",
                       help="Commit this file to data/courses/ in your GitHub repo to reuse it next semester.")
