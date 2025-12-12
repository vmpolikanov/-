import re
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
import pdfplumber
import streamlit as st

# ---------- CONFIG ----------
st.set_page_config(page_title="WB Налоги", layout="wide")
RUB = Decimal("0.01")

# Денежное число WB: 1 279 714,01
MONEY_RE = re.compile(r"(?<!\d)(\d+(?:[ \u00a0]\d{3})*,\d{2})(?!\d)")

# ---------- HELPERS ----------
def to_decimal(s: str) -> Decimal:
    if not s:
        return Decimal("0")
    s = s.replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def read_pdf_text(file) -> str:
    with pdfplumber.open(file) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def fmt_rub(x: Decimal) -> str:
    x = x.quantize(RUB, rounding=ROUND_HALF_UP)
    s = f"{x:.2f}"
    whole, frac = s.split(".")
    whole = re.sub(r"(?<=\d)(?=(\d{3})+$)", " ", whole)
    return f"{whole},{frac} ₽"


def find_line_and_amount(text: str, keyword: str):
    """
    Ищем строку по ключевым словам и берём ПОСЛЕДНЕЕ денежное значение в строке
    """
    for line in text.splitlines():
        if keyword.lower() in line.lower():
            matches = MONEY_RE.findall(line)
            if not matches:
                return line, Decimal("0")

            value = to_decimal(matches[-1])

            # защита от мусора (WB суммы < 1 млрд)
            if value > Decimal("1000000000"):
                valid = [to_decimal(x) for x in matches if to_decimal(x) <= Decimal("1000000000")]
                value = min(valid) if valid else Decimal("0")

            return line, value

    return "", Decimal("0")


# ---------- UI ----------
st.title("Расчёт суммы (п.1 + п.3 + п.4 + п.5) по отчетам WB")
st.caption("Загрузите PDF-отчёты Wildberries (только .pdf, без .sig)")

files = st.file_uploader(
    "Загрузите PDF-отчеты Wildberries",
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

debug = st.checkbox("Показать отладку (какие строки найдены)", value=False)

# Ключевые строки WB
K1 = "Итого стоимость реализованного товара"
K3 = "Удержания в пользу третьих лиц"
K4 = "Компенсация ущерба"
K5 = "Прочие выплаты"

# ---------- PROCESS ----------
if files:
    rows = []
    debug_blocks = []

    for f in files:
        text = read_pdf_text(f)

        l1, p1 = find_line_and_amount(text, K1)
        l3, p3 = find_line_and_amount(text, K3)
        l4, p4 = find_line_and_amount(text, K4)
        l5, p5 = find_line_and_amount(text, K5)

        total = (p1 + p3 + p4 + p5).quantize(RUB)

        rows.append({
            "Файл": f.name,
            "П.1": float(p1),
            "П.3": float(p3),
            "П.4": float(p4),
            "П.5": float(p5),
            "Итого": float(total),
        })

        if debug:
            debug_blocks.append({
                "file": f.name,
                "p1_line": l1,
                "p1": str(p1),
                "p3_line": l3,
                "p3": str(p3),
                "p4_line": l4,
                "p4": str(p4),
                "p5_line": l5,
                "p5": str(p5),
            })

    df = pd.DataFrame(rows)

    # Красивый вывод
    pretty = df.copy()
    for c in ["П.1", "П.3", "П.4", "П.5", "Итого"]:
        pretty[c] = pretty[c].apply(lambda x: fmt_rub(Decimal(str(x))))

    st.dataframe(pretty, use_container_width=True)

    grand_total = Decimal(str(df["Итого"].sum())).quantize(RUB)
    tax = (grand_total * Decimal(str(tax_rate)) / Decimal("100")).quantize(RUB)

    st.markdown(f"### Общая сумма: **{fmt_rub(grand_total)}**")
    st.markdown(f"### Налог ({tax_rate}%): **{fmt_rub(tax)}**")

    if debug:
        st.subheader("Отладка (что именно найдено в PDF)")
        for b in debug_blocks:
            st.markdown(f"**{b['file']}**")
            st.code(
                f"""П.1 строка: {b['p1_line']}
П.1 сумма : {b['p1']}

П.3 строка: {b['p3_line']}
П.3 сумма : {b['p3']}

П.4 строка: {b['p4_line']}
П.4 сумма : {b['p4']}

П.5 строка: {b['p5_line']}
П.5 сумма : {b['p5']}
""",
                language="text",
            )
else:
    st.info("Загрузите один или несколько PDF-файлов отчётов WB")
