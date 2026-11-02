"""Assemble the full course file (.docx) from a course record + static institutional text.

Everything is driven by two inputs:
  * `course`  – one JSON record per course (see data/courses/CSS325B.json)
  * `static`  – institutional text that never changes (data/static_text.json)
Optional inputs: faculty timetable rows, per-item Y/N status, CO-attainment rows.
"""
from __future__ import annotations

import io
import re
from typing import Iterable

from . import helpers as h

PLACEHOLDER = "[To be attached by the course coordinator]"


# ----------------------------------------------------------------- utilities
def _clean_bullets(text: str) -> list[str]:
    return [re.sub(r"^[-•*]\s*", "", ln).strip() for ln in text.split("\n") if ln.strip()]


def _placeholder(doc, text=PLACEHOLDER):
    h.para(doc, text, italic=True, size=10)


def auto_items(course: dict, has_timetable: bool) -> set[str]:
    """Checklist items that this generator fills in automatically."""
    done = {"1", "2", "3", "4", "5", "7", "8", "9", "10", "13", "16"}
    if has_timetable:
        done.add("11")
    if course.get("assignments"):
        done.add("14") if any(a.get("solutions") for a in course["assignments"]) else None
    if course.get("end_term", {}).get("solutions"):
        done.add("17")
    return {x for x in done if x}


def default_status(course: dict, static: dict, has_timetable: bool = False) -> dict:
    auto = auto_items(course, has_timetable)
    status = {}
    for it in static["checklist"]:
        if it["kind"] != "item":
            continue
        key = it["no"].rstrip(".")
        status[key] = it.get("default") or ("Y" if key in auto else "")
    return status


# ----------------------------------------------------------------- sections
def cover(doc, m, static):
    dept = static["departments"][m["dept_key"]]["name"]
    dept = re.sub(r"\s*\(.*\)", "", dept).upper().replace(" AND ", " & ")
    for _ in range(2):
        h.para(doc, "")
    h.para(doc, "SCHOOL OF ENGINEERING", bold=True, size=18, align="center")
    h.para(doc, dept, bold=True, size=16, align="center")
    for _ in range(3):
        h.para(doc, "")
    h.para(doc, "COURSE FILE", bold=True, size=18, align="center")
    h.para(doc, "")
    h.para(doc, m["course_name"], bold=True, size=18, align="center")
    h.para(doc, f"({m['course_code']})", bold=True, size=18, align="center")
    for _ in range(3):
        h.para(doc, "")
    h.labelled(doc, "Program(s) and semester:", m["programs"], size=12)
    h.labelled(doc, "NCrF Level of Program:", m["ncrf_level"], size=12)
    h.labelled(doc, "Course Coordinator:", m["coordinator"], size=12)
    h.labelled(doc, "Session:", m["session"], size=12)
    h.page_break(doc)


def contents(doc, m, static, status):
    h.heading(doc, "COURSE FILE CONTENTS", 1, center=True)
    h.kv_table(doc, [
        ("PROGRAM & SEMESTER", m["program_line"]),
        ("COURSE CODE / COORDINATOR", f"{m['course_code']}   |   {m['coordinator'].upper()}"),
        ("COURSE NAME / THEORY FACULTY", f"{m['course_name'].upper()}   |   {', '.join(m['theory_faculty']).upper()}"),
        ("LTPC / LAB FACULTY", f"{m['ltpc']}   |   {', '.join(m['lab_faculty']).upper()}"),
    ], widths=(6.0, 11.0))
    rows, shade_rows = [], []
    for it in static["checklist"]:
        if it["kind"] == "section":
            rows.append((it["text"], "", ""))
            shade_rows.append(len(rows) - 1)
        else:
            key = it["no"].rstrip(".")
            rows.append((it["no"], it["text"], status.get(key, "")))
    tbl = h.table(doc, ["S. No.", "Description", "Y/N"], [list(r) for r in rows],
                  widths=(1.6, 13.4, 2.0), size=9, center_cols=(0, 2))
    # sub-heading rows: merge across and shade
    for idx in shade_rows:
        row = tbl.rows[idx + 1]
        merged = row.cells[0].merge(row.cells[2])
        h._write(merged, rows[idx][0], bold=True, size=9)
        h._shade(merged, h.SECTION_FILL)
    h.page_break(doc)


def curriculum(doc, m, static):
    h.heading(doc, "OUTCOME-BASED CURRICULUM", 1, center=True)
    h.heading(doc, "1. Vision and Mission of the University", 2)
    u = static["university"]
    h.labelled(doc, "Vision of MRU:", u["vision"])
    h.para(doc, "Mission of MRU", bold=True)
    h.bullets(doc, u["mission"])

    h.heading(doc, "2. Vision and Mission of the School", 2)
    s = static["school"]
    h.labelled(doc, "Vision of SoE:", s["vision"])
    h.para(doc, "Mission of SoE", bold=True)
    h.bullets(doc, s["mission"])

    h.heading(doc, "3. Vision and Mission of the Department", 2)
    keys = m.get("department_keys") or ([m["dept_key"]] + (["ME"] if "ME" in m["program_families"] else []))
    for k in dict.fromkeys(keys):
        d = static["departments"][k]
        h.para(doc, d["name"], bold=True)
        h.labelled(doc, "Vision:", d["vision"])
        h.para(doc, "Mission", bold=True)
        h.bullets(doc, d["mission"])

    h.heading(doc, "4. GAs, PEOs, POs and PSOs of the Program", 2)
    h.para(doc, "Graduate Attributes for an Engineer as per GAPC 4.0", bold=True)
    for ga in static["graduate_attributes"]:
        h.labelled(doc, f"{ga['code']}-{ga['title']}:", ga["description"], size=10)
        h.labelled(doc, f"{ga['wa_code']}:", ga["wa"], size=10)
    for fam in m["program_families"]:
        h.para(doc, f"PEOs of B Tech {fam} Program" + (" & specializations" if fam == "CSE" else ""), bold=True)
        for p in static["peos"][fam]:
            t = f"{p['code']}" + (f": {p['title']}" if p.get("title") else "")
            h.labelled(doc, t + ("." if not p.get("title") else ""), p["text"], size=10)
    h.para(doc, "Program Outcomes for an Engineering Program as per NBA", bold=True)
    for p in static["pos"]:
        h.labelled(doc, f"{p['code']}: {p['title']}:", p["text"], size=10)
    for fam in m["program_families"]:
        h.para(doc, f"Program Specific Outcomes for B Tech {fam}" + (" & all specializations" if fam == "CSE" else ""), bold=True)
        for p in static["psos"][fam]:
            h.labelled(doc, p["code"] + ":", p["text"], size=10)

    h.heading(doc, "5. Knowledge, Skill and Attitude (KSA) Profiles of Graduates of the Program", 2)
    for key, title in (("WK", "Knowledge Profile (WK)"), ("SK", "Skill Profile (SK)"), ("AK", "Attitude Profile (AK)")):
        h.para(doc, f"{title} of an Engineering Graduate", bold=True)
        for p in static["ksa"][key]:
            h.labelled(doc, f"{p['code']}-{p['title']}:", p["text"], size=10)

    h.heading(doc, "6. Academic Calendar", 2)
    _placeholder(doc, "[Attach the academic calendar of the session]")
    h.page_break(doc)


def co_targets(doc, m, ct, levels):
    h.heading(doc, "OUTCOME-BASED COURSE DESIGN", 1, center=True)
    h.para(doc, "School of Engineering", bold=True, align="center", space_after=0)
    h.para(doc, static_dept_line(m), bold=True, align="center")
    h.heading(doc, "7. Setting CO Targets", 2)
    h.labelled(doc, "Dated:", ct.get("dated", ""))
    h.labelled(doc, "Course Code:", f"{m['course_code']}     Course Name: {m['course_name']}     Session: {m['session']}")
    if ct.get("note"):
        h.para(doc, ct["note"])
    h.para(doc, "The revised CO Targets are as follows:", bold=True)
    h.table(doc, ["CO Number", f"CO Target ({m['session']})"], [[t["co"], str(t["target"])] for t in ct["targets"]],
            widths=(6, 6), center_cols=(0, 1))
    h.table(doc, ["Criterion for CO Attainment (in %) (Student Population)", "CO Attainment Level"],
            [[l["criterion"], l["level"]] for l in levels], widths=(10, 6), center_cols=(1,))
    h.para(doc, f"({m['coordinator']})                                                         ({m['hod']})", space_after=0)
    h.para(doc, "Course Coordinator                                                       HoD, CST")
    h.page_break(doc)


def static_dept_line(m):
    return "Department of Computer Science & Technology" if m["dept_key"] == "CST" else m.get("dept_name", "")


def _assessment_plan(doc, m, c, title):
    ap = c["assessment_plan"]
    h.para(doc, title, bold=True)
    h.merged_title_table(doc, [f"DEPARTMENT OF {m['dept_key']}", m["session_short"], "COURSE ASSESSMENT PLAN"])
    h.para(doc, f"Faculty Member: {', '.join(m['theory_faculty'])}     |     Course Coordinator: {m['coordinator']}", size=10)
    h.para(doc, f"Course Name: {m['course_name']}     |     Course Code: {m['course_code']}     |     Credits: {c['ltpc'].split('-')[-1]}", size=10)
    header = ["Section as per syllabus", "Course outcome", "Weightage (%)"] + [f"{t['name']}\n{t['marks']}" for t in ap["tools"]]
    rows = [[f"Section {s['section']}", s["cos"], s["weight"]] + ["√" if x else "" for x in s["covers"]] for s in ap["sections"]]
    rows.append(["TOTAL WEIGHTAGE", "", ""] + ap["total_weightage"])
    h.table(doc, header, rows, size=9, center_cols=tuple(range(2, len(header))))


def _design_common(doc, m, c, label):
    pairs = [
        ("Course Title", c["title"]),
        ("Course Code", c["code"]),
        ("LTPC", c["ltpc"]),
        ("Course type", m["course_type"]),
        ("Course Nature (NEP)", m["course_nature"]),
        ("Course Prerequisites", m["prerequisites"]),
        ("Assumed Knowledge", m["assumed_knowledge"]),
        ("Following Courses", m["following_courses"]),
        ("Course KSA Profile Elements", "\n".join(c["ksa_lines"])),
        ("Course SDGs/Ethics & Skill / NSQF levels", "\n".join(c["sdg_lines"])),
        ("Course Objective", c["objective"]),
    ]
    h.kv_table(doc, pairs, widths=(5.5, 11.5), size=9.5)
    h.table(doc, ["Course Outcome", "Mapping to Skill/Employment"],
            [[f"{x['id']}. {x['text']}", x["mapping"]] for x in c["cos"]], widths=(11, 6), size=9.5)
    h.para(doc, "Relevance of the course", bold=True)
    h.para(doc, c["relevance"], align="justify")


def _books(doc, b):
    for label, key in (("Text Books:", "text_books"), ("Reference Books:", "reference_books"),
                       ("Online Content for Additional Reading:", "online_content"),
                       ("MOOCs for Self-Learning (Optional) – NPTEL:", "nptel"),
                       ("LinkedIn Learning (Mandatory except for 1st year courses):", "linkedin")):
        if b.get(key):
            h.para(doc, label, bold=True, space_after=1)
            h.bullets(doc, [x.lstrip("- ") for x in b[key]], size=10)


def _lesson_plan(doc, rows, first_col, topic_col, ai_col):
    header = [first_col, topic_col, "Course outcome", "Blooms Taxonomy", "Innovative Pedagogy used", "ICT Tools used", ai_col]
    data = [[r["no"], r["topic"], r["co"], r["bt"], r["pedagogy"], r["ict"], r["ai"]] for r in rows]
    h.table(doc, header, data, widths=(1.2, 5.6, 2.0, 1.5, 2.2, 2.0, 2.5), size=8, center_cols=(0, 2, 3))


def _matrix(doc, mx):
    cols = mx["cols"]
    data = [[r["co"]] + [r["values"].get(c, "") for c in cols] for r in mx["rows"]]
    h.table(doc, ["CO/PO-PSO"] + cols, data, widths=[2.4] + [1.05] * len(cols), size=7.5,
            center_cols=tuple(range(1, len(cols) + 1)))


def _co_ksa(doc, rows):
    h.table(doc, ["CO", "WKs", "SKs", "AKs", "SDGs", "Ethics", "Skill Level", "NSQF Level"],
            [[r["co"], r["wk"], r["sk"], r["ak"], r["sdg"], r["ethics"], r["skill"], r["nsqf"]] for r in rows],
            size=9, center_cols=tuple(range(0, 8)))


def theory_design(doc, m, c):
    h.heading(doc, "8. Course Design of Theory Component", 2)
    h.para(doc, "a–e. KSA profile, SDGs/Ethics/Skill & NSQF levels, Course Objective, COs, Mapping, Relevance", italic=True, size=10)
    _design_common(doc, m, c, "theory")
    h.para(doc, "f. Syllabus with Text books, Reference books, Online Resources, MOOCs", bold=True)
    syl = c["syllabus"]
    h.table(doc, ["Sections", "Weightage"], [[s["section"], f"{s['weightage']}%"] for s in syl["sections"]] +
            [["TOTAL", f"{sum(int(s['weightage']) for s in syl['sections'])}%"]], widths=(6, 4), center_cols=(0, 1))
    for s in syl["sections"]:
        h.para(doc, f"Section-{s['section']}", bold=True, space_after=1)
        h.para(doc, s["text"], align="justify", size=10)
    _books(doc, syl)
    h.para(doc, "Topic/Unit/Chapter Layout", bold=True)
    tl = c["topic_layout"]
    tot = [sum(int(x[k]) for x in tl) for k in ("L", "T", "P")]
    h.table(doc, ["Section", "Topics", "L", "T", "P"],
            [[x["section"], x["topics"], x["L"], x["T"], x["P"]] for x in tl] + [["TOTAL", "", *map(str, tot)]],
            widths=(2.0, 10.0, 1.6, 1.6, 1.6), center_cols=(0, 2, 3, 4))
    h.para(doc, "g. Lesson Plan including innovative pedagogies, ICT Tools and AI Integration", bold=True)
    _lesson_plan(doc, c["lesson_plan"], "Lect No.", "Lecture Topics", "AI integration / AI tools used")
    h.para(doc, "h. CO-PO Mapping", bold=True)
    _matrix(doc, c["co_po"])
    h.para(doc, "i. CO-KSA Mapping", bold=True)
    _co_ksa(doc, c["co_ksa"])
    _assessment_plan(doc, m, c, "j. Course Assessment Plan – Theory")
    h.page_break(doc)


def lab_design(doc, m, c):
    h.heading(doc, "9. Course Design of Lab Component", 2)
    _design_common(doc, m, c, "lab")
    if c.get("experiments"):
        h.para(doc, "f. List of Experiments / Assignments and Case-based Problems", bold=True)
        h.bullets(doc, c["experiments"], size=10)
    h.para(doc, "g. Lab Text books, Reference books, Online Resources, MOOCs", bold=True)
    _books(doc, c.get("books", {}))
    h.para(doc, "h. Lesson Plan including innovative pedagogies, ICT Tools and AI Integration", bold=True)
    _lesson_plan(doc, c["lesson_plan"], "Lab Session", "Laboratory", "AI Integration / AI tools used / AI Policy")
    h.para(doc, "i. CO-PO Mapping", bold=True)
    _matrix(doc, c["co_po"])
    h.para(doc, "j. CO-KSA Mapping", bold=True)
    _co_ksa(doc, c["co_ksa"])
    _assessment_plan(doc, m, c, "k. Course Assessment Plan – Lab")
    h.para(doc, "l. List of Miniprojects", bold=True)
    _placeholder(doc, "[List mini-projects, if any]")
    h.page_break(doc)


def teaching(doc, m, timetable: Iterable[dict] | None, course):
    h.heading(doc, "OUTCOME-BASED TEACHING & LEARNING", 1, center=True)
    h.heading(doc, "10. List of Faculty Members Teaching the Course", 2)
    for label, names in (("Theory", m["theory_faculty"]), ("Lab", m["lab_faculty"])):
        for n in names:
            info = (m.get("faculty_details") or {}).get(n, {})
            h.para(doc, f"{label}: {n}", bold=True, space_after=0)
            for k in ("designation", "department", "university", "email"):
                if info.get(k):
                    h.para(doc, info[k], space_after=0)
    h.heading(doc, "11. Time Table of Faculty Members Teaching the Course", 2)
    rows = list(timetable or [])
    if rows:
        h.table(doc, ["Faculty", "Day", "Time", "Course", "Program / Section", "Room", "Type"],
                [[r.get("Faculty", ""), r.get("Day", ""), r.get("Time", ""),
                  f"{r.get('Course Code', '')} {r.get('Course Name', '')}".strip(),
                  r.get("Program / Section", ""), r.get("Room", ""), r.get("Type", "")] for r in rows],
                size=9, widths=(3.4, 2.0, 2.6, 3.6, 2.8, 1.6, 1.4))
    else:
        _placeholder(doc, "[Attach faculty time table]")
    h.heading(doc, "12. Lecture Notes and PowerPoint Handouts (10% of entire content)", 2)
    _placeholder(doc)
    h.heading(doc, "13. Tutorials / Assignments", 2)
    for a in course.get("assignments", []):
        h.para(doc, "MANAV RACHNA UNIVERSITY", bold=True, align="center", space_after=0)
        h.para(doc, "SCHOOL OF ENGINEERING", align="center", space_after=0)
        h.para(doc, f"DEPARTMENT OF {m['dept_key']}", align="center", space_after=2)
        h.para(doc, a["title"], bold=True, size=13, align="center")
        h.kv_table(doc, [(k, v) for k, v in a["header"].items()], widths=(4.5, 12.5), size=9)
        h.labelled(doc, "Learning Outcome:", a["learning_outcome"])
        h.table(doc, ["Q. No.", "Question", "BT Level", "CO"], [[q["no"], q["text"], q["bt"], q["co"]] for q in a["questions"]],
                widths=(1.5, 11.0, 1.8, 2.7), size=9.5, center_cols=(0, 2, 3))
    h.heading(doc, "14. Solution of Tutorials / Assignments (2 each)", 2)
    sols = [a for a in course.get("assignments", []) if a.get("solutions")]
    if sols:
        for a in sols:
            h.para(doc, a["title"], bold=True, size=12)
            for s in a["solutions"]:
                h.para(doc, f"{s['no']}  {s['q']}", bold=True, space_after=1)
                for ln in s["answer"].split("\n"):
                    if re.match(r"^\s*[-•*]\s+", ln):
                        h.bullets(doc, [re.sub(r"^\s*[-•*]\s+", "", ln)])
                    elif ln.strip():
                        h.para(doc, ln.strip(), align="justify")
    else:
        _placeholder(doc, "[Attach solutions of any 2 assignments]")
    h.page_break(doc)


def exam_paper(doc, m, e):
    h.heading(doc, "16. End-Term Question Paper", 2)
    h.para(doc, "MANAV RACHNA UNIVERSITY", bold=True, align="center", space_after=0)
    h.para(doc, "SCHOOL OF ENGINEERING", bold=True, align="center", space_after=0)
    h.para(doc, static_dept_line(m).upper(), bold=True, align="center", space_after=0)
    h.para(doc, f"“{e['title']}”", italic=True, align="center")
    h.kv_table(doc, [("SEMESTER", e["semester"]), ("DATE OF EXAM/SESSION", e["date"]), ("COURSE NAME", m["course_name"]),
                     ("COURSE CODE", m["course_code"]), ("PROGRAM", e["program"]), ("CREDITS", e["credits"]),
                     ("TIME DURATION", e["duration"]), ("MAX. MARKS", e["max_marks"])], widths=(6, 11), size=9.5)
    if e.get("ksa_coverage"):
        h.para(doc, "Students will be assessed in the End-Term Exam of this course on the following:", bold=True, size=10)
        h.table(doc, None, e["ksa_coverage"], size=9)
    for p in e["parts"]:
        h.para(doc, p["name"], bold=True)
        h.table(doc, ["Q.NO.", "QUESTIONS", "MARKS", "CO", "BLOOM'S LEVEL"],
                [[q["no"], q["text"], q["marks"], q["co"], q["bt"]] for q in p["questions"]],
                widths=(1.6, 10.2, 1.8, 1.6, 1.8), size=9.5, center_cols=(0, 2, 3, 4))
    h.heading(doc, "17. Model Solution of End-Term Exam", 2)
    if e.get("solutions"):
        for s in e["solutions"]:
            h.para(doc, f"{s['no']}. {s['q']}", bold=True, space_after=1)
            for ln in s["answer"].split("\n"):
                if re.match(r"^\s*[-•*]\s+", ln):
                    h.bullets(doc, [re.sub(r"^\s*[-•*]\s+", "", ln)])
                elif ln.strip():
                    h.para(doc, ln.strip(), align="justify")
    else:
        _placeholder(doc, "[Attach model solution]")


def assessment_attainment(doc, m, course, attainment):
    h.page_break(doc)
    h.heading(doc, "OUTCOME-BASED ASSESSMENT & ATTAINMENT", 1, center=True)
    items = [("18", "Question Papers / Continuous Assessment Question Sheets for all other assessment tools"),
             ("19", "Rubrics for Lab assessments, miniprojects and case studies"),
             ("20", "Note on how the course can contribute to the ePortfolio of Students"),
             ("21", "Attendance Record for theory and labs"),
             ("22", "Continuous Evaluation for all Assessments as per Course Assessment Plan from ERP"),
             ("23", "Assessment-wise Marks Uploaded on ERP with CO-PO mapping"),
             ("24", "Records of Rubrics based Evaluation of Lab Assessments"),
             ("25", "Records of Assessments based on Student ePortfolios, if included in the CAP"),
             ("26", "Minutes of Course Coordinator Level Meetings with Feedback Analysis and Action Taken Report")]
    for no, t in items:
        h.heading(doc, f"{no}. {t}", 3)
        _placeholder(doc)
    h.heading(doc, "27. CO Attainment Analysis and Action Taken (Phase 1 to Phase 3)", 3)
    if attainment:
        h.table(doc, ["CO", "CO TARGET", "CO ATTAINMENT", "GAP", "ACTION REQUIRED FOR NEXT ACADEMIC CYCLE"],
                [[r["co"], r["target"], r["attainment"], r["gap"], r.get("action", "")] for r in attainment],
                widths=(2.6, 2.2, 2.6, 1.8, 7.8), size=9.5, center_cols=(0, 1, 2, 3))
    else:
        _placeholder(doc, "[Upload the ERP marks sheet to compute CO attainment]")
    for no, t in (("28", "List of Slow, Moderate and Advanced Learners"),
                  ("29", "Action Taken to Support Slow, Moderate and Advanced Learners"),
                  ("30", "Impact Analysis Report and Action Taken for Next Academic Cycle"),
                  ("31", "Alternative Plan of Action for the Next Academic Cycle")):
        h.heading(doc, f"{no}. {t}", 3)
        _placeholder(doc)


def appendices(doc, c_theory, c_lab):
    h.page_break(doc)
    h.heading(doc, "APPENDICES", 1, center=True)
    h.heading(doc, "Appendix A – Sample hardcopies of Tutorials and Assignments", 3)
    _placeholder(doc, "[6 samples of Tutorials and 6 of Assignments: 2 each for Slow, Moderate and Advanced learners]")
    h.heading(doc, "Appendix B – Sample answer sheets of Mid-Sem and End-Term Exams", 3)
    _placeholder(doc, "[6 samples each: 2 for Slow, 2 for Moderate and 2 for Advanced learners]")
    for tag, title, key, head in (("C", "Evidence for pedagogy used", "pedagogy", "Name of Pedagogy"),
                                   ("D", "Evidence for ICT tools used", "ict", "Name of ICT Tool(s) used"),
                                   ("E", "Evidence for AI integration/AI tools used", "ai", "Name of AI integration technique/tool")):
        h.heading(doc, f"Appendix {tag} – {title}", 3)
        rows = []
        for src in (c_theory, c_lab):
            if not src:
                continue
            for r in src["lesson_plan"]:
                if r.get(key):
                    rows.append([r[key], f"{'Lecture' if src is c_theory else 'Lab session'} {r['no']}", ""])
        h.table(doc, [head, "Topic in which it was used", "Evidence"], rows or [["", "", ""]], widths=(5.5, 7.5, 4.0), size=9)


# ----------------------------------------------------------------- entry point
def build_course_file(course: dict, static: dict, timetable: Iterable[dict] | None = None,
                      status: dict | None = None, attainment: list | None = None) -> bytes:
    m = course["meta"]
    doc = h.new_document()
    status = status or default_status(course, static, bool(timetable))
    cover(doc, m, static)
    contents(doc, m, static, status)
    curriculum(doc, m, static)
    co_targets(doc, m, course["co_targets"], course["co_levels"])
    theory_design(doc, m, course["theory"])
    if course.get("lab"):
        lab_design(doc, m, course["lab"])
    teaching(doc, m, timetable, course)
    if course.get("end_term"):
        exam_paper(doc, m, course["end_term"])
    assessment_attainment(doc, m, course, attainment)
    appendices(doc, course["theory"], course.get("lab"))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
