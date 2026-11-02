"""Claude-powered drafting. Every function returns data that a faculty member reviews before it is used.

The API key is read from st.secrets["ANTHROPIC_API_KEY"] (Streamlit Cloud) or the ANTHROPIC_API_KEY env var.
"""
from __future__ import annotations

import json
import os
import re

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

SYSTEM = ("You are an academic assistant for an engineering university department. You write accurate, concise "
          "course-file content aligned to Outcome Based Education: every question carries a Course Outcome (CO) and "
          "a Bloom's Taxonomy level (BT1-BT6). Reply with JSON only, no prose, no code fences.")

COURSE_SCHEMA_HINT = """{
 "meta": {"course_name":"", "course_code":"", "ltpc":"L-T-P-C", "theory_ltpc":"", "lab_ltpc":"", "prerequisites":"", "assumed_knowledge":"", "following_courses":""},
 "theory": {"title":"", "code":"", "ltpc":"", "objective":"",
   "cos":[{"id":"CODE.1","text":"","mapping":"Skill Development | Employment and Skill Development | Entrepreneurship"}],
   "syllabus":{"sections":[{"section":"A","weightage":25,"text":""}],"text_books":[],"reference_books":[],"online_content":[],"nptel":[],"linkedin":[]},
   "topic_layout":[{"section":"A","topics":"","L":0,"T":0,"P":0}]}
}"""


def _client():
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets["ANTHROPIC_API_KEY"]
        except Exception:
            key = None
    if not key:
        raise RuntimeError("No ANTHROPIC_API_KEY found. Add it to .streamlit/secrets.toml or the app's Secrets settings.")
    return anthropic.Anthropic(api_key=key)


def ask_json(prompt: str, max_tokens: int = 6000):
    msg = _client().messages.create(model=MODEL, max_tokens=max_tokens, system=SYSTEM,
                                    messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


def extract_course_from_syllabus(syllabus_text: str, course_code: str = ""):
    """Syllabus text -> the 'meta' + 'theory' parts of a course record (review before use)."""
    return ask_json(f"Extract the course {course_code} from this syllabus text into JSON exactly in this shape "
                    f"(leave unknown fields as empty strings/lists; do not invent content):\n{COURSE_SCHEMA_HINT}\n\n"
                    f"SYLLABUS TEXT:\n{syllabus_text}", max_tokens=8000)


def draft_relevance(course: dict) -> str:
    c = course["theory"]
    out = ask_json("Write the 'Relevance of the course' paragraph (120-170 words, plain prose) for this course. "
                   'Return {"relevance": "..."}.\n' + json.dumps({"title": c["title"], "objective": c["objective"],
                                                                 "cos": [x["text"] for x in c["cos"]]}))
    return out["relevance"]


def draft_assignments(course: dict, n: int = 3, per_assignment: int = 5) -> list[dict]:
    """New assignments in the course-file format (questions tagged with CO and BT)."""
    c = course["theory"]
    out = ask_json(f"Create {n} assignments with {per_assignment} questions each for this course, covering all four "
                   "syllabus sections and every CO. Return a JSON list of "
                   '{"title":"Assignment 1","learning_outcome":"","questions":[{"no":"Q1","text":"","bt":"BT2","co":"CO1"}]}.\n'
                   + json.dumps({"title": c["title"], "cos": c["cos"], "syllabus": c["syllabus"]["sections"]}), max_tokens=7000)
    for a in out:
        a["header"] = {"Program / Semester": course["meta"]["program_line"], "Course Code": course["meta"]["course_code"],
                       "Course Name": course["meta"]["course_name"]}
    return out


def draft_end_term(course: dict) -> dict:
    """End-term paper: Part A (25 marks) and Part B (25 marks), with CO and BT per question."""
    c = course["theory"]
    return ask_json("Create a 50-mark end-term paper: PART – A (25 Marks) with 5 short-answer questions and PART – B "
                    "(25 Marks) with 5 questions of 5 marks. Cover all COs, mixed BT levels. Return JSON "
                    '{"parts":[{"name":"PART – A (25 Marks)","questions":[{"no":"Q1","text":"","marks":"5","co":"CO1","bt":"BT2"}]}]}.\n'
                    + json.dumps({"title": c["title"], "cos": c["cos"], "syllabus": c["syllabus"]["sections"]}), max_tokens=5000)


def draft_solutions(questions: list[dict], context: str) -> list[dict]:
    """Model answers for a list of {no, text} questions. Answers use '- ' for bullet lines."""
    return ask_json("Write concise model answers (marking-scheme style, 3-6 lines each). Return JSON list of "
                    '{"no":"","q":"","answer":""}.\nCOURSE: ' + context + "\nQUESTIONS:\n" + json.dumps(questions), max_tokens=7000)
