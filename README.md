# Course File Generator

Streamlit app that builds a complete **Course File (.docx)** for any course, following the department's sample
course file (cover page, contents checklist, outcome-based curriculum, course design, teaching & learning,
end-term paper, assessment/attainment sections and appendices A–E).

## What is automated

| Part of the course file | Source |
|---|---|
| Vision/Mission, GAs, PEOs, POs, PSOs, KSA profiles | `data/static_text.json` (written once) |
| Cover page, contents checklist, CO targets, course design tables, lesson plan, CO-PO / CO-KSA, assessment plan | `data/courses/<CODE>.json` (one record per course) |
| Faculty time table (item 11) | uploaded CSV/Excel → `generator/timetable.py` |
| Relevance, assignments, end-term paper, model solutions | drafted by Claude (`generator/ai.py`), reviewed by faculty |
| Course record from a syllabus PDF | `generator/syllabus_pdf.py` + Claude extraction |
| Appendix C/D/E evidence tables | built from the lesson plan (pedagogy / ICT / AI columns) |
| Attendance, marks, answer-sheet samples, minutes | placeholders – attach manually (next phase: ERP marks → CO attainment) |

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add your Anthropic API key (needed only for AI features)
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)

1. Push this folder to a GitHub repo.
2. share.streamlit.io → *New app* → pick the repo, main file `app.py`.
3. App settings → *Secrets* → add `ANTHROPIC_API_KEY`.

## Add a new course

* **Fastest:** sidebar → *Syllabus PDF (AI extraction)* → upload PDF, enter the course code → review/edit each tab.
* **Or** copy `data/courses/CSS325B.json`, edit it, and load it with *Saved course*.
* After editing, tab 6 → **Save course data (.json)** and commit it to `data/courses/` to reuse it next semester.

## Time table format

`Faculty, Day, Time, Course Code, Course Name, Program / Section, Room, Type` – see `data/timetable_template.csv`.

## Layout

```
app.py                     Streamlit interface (6 tabs)
generator/builder.py       builds the .docx, one function per section
generator/helpers.py       python-docx table/format helpers
generator/timetable.py     time-table reader
generator/syllabus_pdf.py  PDF → text
generator/ai.py            Claude drafting / extraction
data/static_text.json      institutional text + contents checklist
data/courses/              one JSON per course
```
