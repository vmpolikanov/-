import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="WB отчёты", layout="wide")

st.title("Расчёт суммы (п.1 + п.3 + п.4 + п.5) по отчётам WB")
st.caption("Загрузите PDF-отчёты Wildberries (только .pdf, без .sig)")


# ---------- helpers ----------

def to_float(value: str) -> float:
    value = value.replace(" ", "").replace(",", ".")
    try:
        return float(value)
    except:
        return 0.0


def extract_money_from_line(line: str) -> float:
    """
    Берём ТОЛЬКО последнее денежное значение в строке
    вида 1 279 714,01
    """
    matches = re.findall(r"\d[\d\s]*,\d{2}", line)
    if not matches:
        return 0.0

    value = to_float(matches[-1])

    # защита от мусора (WB отчёты всегда < 1 млрд)
    if value > 1_000_000_000:
        return 0.0

    return value


def find_value(lines, keywords):
    for line in lines:
        if any(k.lower() in line.lower() for k in keywords):
            val = extract_money_from_line(line)
            if val > 0:
                return val
    return 0.0


def parse_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    lines = text.split("\n")

    p1 = find_value(lines, ["стоимость реализованного товара"])
    p3 = find_value(lines, ["вознаграждение вайлдберриз"])
    p4 = find_value(lines, ["возврат товаров"])
    p5 = find_value(lines, ["корректировка", "удержание"])

    total = p1 + p3 + p4 + p5

    return p1, p3, p4, p5, total


# ---------- UI ----------

files = st.file_uploader(
    "Загрузите PDF-отчёты",
    type=["pdf"],
    accept_multiple_files=True
)

tax_rate = st.number_input(
    "Ставка налога (%)",
    min_value=0.0,
    max_value=100.0,
    value=6.0,
    step=0.1
)

if files:
    rows = []

    for f in files:
        p1, p3, p4, p5, total = parse_pdf(f)

        rows.append({
            "Файл": f.name,
            "П.1": round(p1, 2),
            "П.3": round(p3, 2),
            "П.4": round(p4, 2),
            "П.5": round(p5, 2),
            "Итого": round(total, 2),
        })

    df = pd.DataFrame(rows)

    st.dataframe(df, use_container_width=True)

    grand_total = df["Итого"].sum()
    tax_value = grand_total * tax_rate / 100

    st.markdown(f"### Общая сумма: **{grand_total:,.2f} ₽**")
    st.markdown(f"### Налог ({tax_rate:.1f}%): **{tax_value:,.2f} ₽**")

else:
    st.info("Загрузите один или несколько PDF-файлов отчётов WB")
