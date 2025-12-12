import re
from decimal import Decimal, ROUND_HALF_UP

import pdfplumber
import pandas as pd
import streamlit as st


RUB = Decimal("0.01")


def to_decimal(s: str) -> Decimal:
    """'1 547 596,71' -> Decimal('1547596.71'), '—' -> 0"""
    if not s:
        return Decimal("0")
    s = s.strip()
    if s in {"—", "-", "–"}:
        return Decimal("0")
    s = s.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def read_pdf_text(file) -> str:
    """Extract text from all pages of the uploaded PDF."""
    with pdfplumber.open(file) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def fmt_rub(x: Decimal) -> str:
    x = x.quantize(RUB, rounding=ROUND_HALF_UP)
    s = f"{x:.2f}"
    whole, frac = s.split(".")
    whole = re.sub(r"(?<=\d)(?=(\d{3})+$)", " ", whole)
    return f"{whole},{frac} ₽"


def find_amount_by_keyword(text: str, keyword: str) -> Decimal:
    """
    WB reports often contain dates and report numbers on the same line.
    We search lines containing `keyword` and extract ONLY money-like numbers (with ,xx).
    Then we pick the most plausible one (shortest after cleanup) to avoid picking
    concatenations like '214 867 994 491 547 600,00'.
    """
    candidates: list[str] = []

    for line in text.splitlines():
        if keyword.lower() in line.lower():
            nums = re.findall(r"\d[\d\s\u00a0]*,\d{2}", line)
            for n in nums:
                clean = n.replace(" ", "").replace("\u00a0", "")
                # filter out unrealistically long "numbers" caused by merged tokens
                # (real WB sums are typically up to 12-13 chars like 9999999999,99)
                if len(clean) <= 13:
                    candidates.append(n)
            # if keyword line exists but has no amount, treat as 0
            if not nums and ("—" in line or "-" in line or "–" in line):
                candidates.append("0,00")

    if not candidates:
        return Decimal("0")

    # choose the "most plausible" candidate: the shortest cleaned token
    best = min(candidates, key=lambda v: len(v.replace(" ", "").replace("\u00a0", "")))
    return to_decimal(best)


# ---------- UI ----------
st.set_page_config(page_title="WB Налоги", layout="wide")
st.title("Расчёт суммы (п.1 + п.3 + п.4 + п.5) по отчетам WB")

files = st.file_uploader(
    "Загрузите PDF-отчеты Wildberries (только .pdf, не .sig)",
    type=["pdf"],
    accept_multiple_files=True,
)

tax_rate = st.number_input(
    "Ставка налога (%)",
    min_value=0.0,
    max_value=100.0,
    value=6.0,
    step=0.5,
)

if files:
    rows = []
    for f in files:
        text = read_pdf_text(f)

        # These keywords match your WB report text (see your uploaded PDF):
        p1 = find_amount_by_keyword(text, "Итого стоимость реализованного товара")
        p3 = find_amount_by_keyword(text, "Удержания в пользу третьих лиц")
        p4 = find_amount_by_keyword(text, "Компенсация ущерба")
        p5 = find_amount_by_keyword(text, "Прочие выплаты")

        total = (p1 + p3 + p4 + p5).quantize(RUB)

        rows.append(
            {
                "Файл": f.name,
                "П.1": float(p1),
                "П.3": float(p3),
                "П.4": float(p4),
                "П.5": float(p5),
                "Итого": float(total),
            }
        )

    df = pd.DataFrame(rows)

    # pretty view
    show = df.copy()
    for c in ["П.1", "П.3", "П.4", "П.5", "Итого"]:
        show[c] = show[c].apply(lambda x: fmt_rub(Decimal(str(x))))

    st.dataframe(show, use_container_width=True)

    grand_total = Decimal(str(df["Итого"].sum())).quantize(RUB)
    tax = (grand_total * Decimal(str(tax_rate)) / Decimal("100")).quantize(RUB)

    st.markdown(f"### Общая сумма: **{fmt_rub(grand_total)}**")
    st.markdown(f"### Налог ({tax_rate}%): **{fmt_rub(tax)}**")
