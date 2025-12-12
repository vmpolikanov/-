import re
from decimal import Decimal, ROUND_HALF_UP
import pdfplumber
import pandas as pd
import streamlit as st

RUB = Decimal("0.01")

def to_decimal(s: str) -> Decimal:
    if not s or s.strip() in {"—", "-", "–"}:
        return Decimal("0")
    s = s.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return Decimal(s)
    except:
        return Decimal("0")

def find_amount(text: str, keyword: str) -> Decimal:
    for line in text.splitlines():
        if keyword.lower() in line.lower():
            nums = re.findall(r"\d[\d\s\u00a0]*,\d{2}", line)
            if nums:
                return to_decimal(nums[-1])
            return Decimal("0")
    return Decimal("0")

def read_pdf(file) -> str:
    with pdfplumber.open(file) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)

def fmt(x: Decimal) -> str:
    x = x.quantize(RUB, rounding=ROUND_HALF_UP)
    s = f"{x:.2f}"
    a, b = s.split(".")
    a = re.sub(r"(?<=\d)(?=(\d{3})+$)", " ", a)
    return f"{a},{b} ₽"

st.set_page_config(page_title="WB Налоги", layout="wide")
st.title("Расчёт суммы (п.1 + п.3 + п.4 + п.5) по отчетам WB")

files = st.file_uploader(
    "Загрузите PDF-отчеты Wildberries",
    type=["pdf"],
    accept_multiple_files=True
)

tax_rate = st.number_input(
    "Ставка налога (%)",
    min_value=0.0,
    max_value=100.0,
    value=6.0,
    step=0.5
)

if files:
    rows = []
    for f in files:
        text = read_pdf(f)

        p1 = find_amount(text, "Итого стоимость реализованного товара")
        p3 = find_amount(text, "Удержания в пользу третьих лиц")
        p4 = find_amount(text, "Компенсация ущерба")
        p5 = find_amount(text, "Прочие выплаты")

        total = (p1 + p3 + p4 + p5).quantize(RUB)

        rows.append({
            "Файл": f.name,
            "П.1": float(p1),
            "П.3": float(p3),
            "П.4": float(p4),
            "П.5": float(p5),
            "Итого": float(total),
        })

    df = pd.DataFrame(rows)

    show = df.copy()
    for c in ["П.1", "П.3", "П.4", "П.5", "Итого"]:
        show[c] = show[c].apply(lambda x: fmt(Decimal(str(x))))

    st.dataframe(show, use_container_width=True)

    grand = Decimal(str(df["Итого"].sum())).quantize(RUB)
    tax = (grand * Decimal(str(tax_rate)) / Decimal("100")).quantize(RUB)

    st.markdown(f"### Общая сумма: **{fmt(grand)}**")
    st.markdown(f"### Налог ({tax_rate}%): **{fmt(tax)}**")
