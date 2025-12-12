import re
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd
import pdfplumber
import streamlit as st

RUB_DEC = Decimal("0.01")

def parse_rub_amount(s: str) -> Decimal:
    if not s:
        return Decimal("0")
    s = s.strip()
    if s in {"—", "-", "–"}:
        return Decimal("0")
    s = s.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        return Decimal(s)
    except:
        return Decimal("0")

def extract_point_amount(text: str, point: int) -> Decimal:
    pattern = rf"(?m)^\\s*{point}\\.(?!\\d).*?$"
    m = re.search(pattern, text)
    if not m:
        return Decimal("0")
    line = m.group(0)
    nums = re.findall(r"\\d[\\d\\s\u00a0]*,\\d{{2}}", line)
    if not nums:
        return Decimal("0")
    return parse_rub_amount(nums[-1])

def read_pdf_text(file):
    with pdfplumber.open(file) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)

def rub_fmt(x: Decimal) -> str:
    q = x.quantize(RUB_DEC, rounding=ROUND_HALF_UP)
    s = f"{q:.2f}"
    whole, frac = s.split(".")
    whole = re.sub(r"(?<=\\d)(?=(\\d{3})+$)", " ", whole)
    return f"{whole},{frac} ₽"

st.set_page_config(page_title="WB налоги", layout="wide")
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
        text = read_pdf_text(f)
        a1 = extract_point_amount(text, 1)
        a3 = extract_point_amount(text, 3)
        a4 = extract_point_amount(text, 4)
        a5 = extract_point_amount(text, 5)
        total = (a1 + a3 + a4 + a5).quantize(RUB_DEC)

        rows.append({
            "Файл": f.name,
            "П.1": float(a1),
            "П.3": float(a3),
            "П.4": float(a4),
            "П.5": float(a5),
            "Итого": float(total)
        })

    df = pd.DataFrame(rows)

    show = df.copy()
    for c in ["П.1", "П.3", "П.4", "П.5", "Итого"]:
        show[c] = show[c].apply(lambda x: rub_fmt(Decimal(str(x))))

    st.dataframe(show, use_container_width=True)

    grand_total = Decimal(str(df["Итого"].sum())).quantize(RUB_DEC)
    st.markdown(f"### Общая сумма: **{rub_fmt(grand_total)}**")

    tax = (grand_total * Decimal(str(tax_rate)) / Decimal("100")).quantize(RUB_DEC)
    st.markdown(f"### Налог ({tax_rate}%): **{rub_fmt(tax)}**")
