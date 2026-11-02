"""Read a faculty time table (CSV / Excel) and pick out the rows for one course."""
from __future__ import annotations

import pandas as pd

COLUMNS = ["Faculty", "Day", "Time", "Course Code", "Course Name", "Program / Section", "Room", "Type"]
DAY_ORDER = {d: i for i, d in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])}


def load_timetable(file) -> pd.DataFrame:
    """`file` is a path or an uploaded file object (.csv, .xlsx, .xls)."""
    name = getattr(file, "name", str(file)).lower()
    df = pd.read_csv(file) if name.endswith(".csv") else pd.read_excel(file)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in ("Faculty", "Day", "Time") if c not in df.columns]
    if missing:
        raise ValueError(f"Time table is missing column(s): {', '.join(missing)}. Expected: {', '.join(COLUMNS)}")
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    return df[COLUMNS].fillna("").astype(str)


def rows_for_course(df: pd.DataFrame, faculty_names: list[str], course_code: str = "") -> list[dict]:
    """Rows for the given faculty members; if a course code is given, only that course."""
    names = [n.lower().replace("dr.", "").replace("ms.", "").replace("mr.", "").strip() for n in faculty_names]
    mask = df["Faculty"].str.lower().apply(lambda f: any(n and n in f for n in names))
    out = df[mask]
    if course_code:
        out = out[out["Course Code"].str.upper().str.contains(course_code.upper(), regex=False)]
    out = out.assign(_d=out["Day"].map(lambda d: DAY_ORDER.get(d.strip().title(), 9))).sort_values(["Faculty", "_d", "Time"])
    return out.drop(columns="_d").to_dict("records")
