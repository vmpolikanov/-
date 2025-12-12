import streamlit as st
import pdfplumber
import re
import pandas as pd

st.set_page_config(page_title="WB отчёты", layout="wide")

st.title("Расчёт суммы (п.1 + п.3 + п.4 + п.5) по отчётам WB")
st.caption("Загрузите PDF-отчёты Wildberries (только .pdf, без .sig)")

# ---------- helpers ----------

def parse_money(text: str) -> float:
    """
    Преобразует строку вида:
    1 279 714,01
    56 157,57
    в float
    """
    if not text:
        return 0.0
    text = text.replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except:
        return 0.0


def extract_value(lines, keywords):
    """
    Ищет строку по ключевым словам и вытаскивает число
    """
    for line in lines:
        if any(k.lower() in line.lower() for k in keywords):
            match = re.search(r"([\d\s]+,\d{2})", line)
            if match:
                return parse_money(match.group(1))
    return 0.0


def parse_pdf(file):
    p1 = p3 = p4 = p5 = 0.0

    with pdfplumber.open(file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    lines = text.split("\n")

    # ⚠️ Ключевые формулировки WB (проверены на реальных отчётах)
    p1 = extract_value(lines, [
        "стоимость реализованного товара",
    ])

    p3 = extract_value(lines, [
        "вознаграждение вайлдберриз",
    ])

    p4 = extract_value(lines, [
        "возврат товаров",
    ])

    p5 = extract_value(lines, [
        "корректировка",
        "удержание",
    ])

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

    st.dataframe(
        df,
        use_container_width=True
    )

    grand_total = df["Итого"].sum()
    tax_value = grand_total * tax_rate / 100

    st.markdown(f"### Общая сумма: **{grand_total:,.2f} ₽**")
    st.markdown(f"### Налог ({tax_rate:.1f}%): **{tax_value:,.2f} ₽**")

else:
    st.info("Загрузите один или несколько PDF-файлов отчётов WB")
