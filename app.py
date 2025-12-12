import re
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
import pdfplumber
import streamlit as st

RUB = Decimal("0.01")

# Денежное число в формате WB: "1 547 596,71" или "150,00"
# Важно: не схватывает "21 486799449 1 547 596,71" целиком — возьмёт только "1 547 596,71"
MONEY_RE = re.compile(r"(?<!\d)(\d+(?:[ \u00a0]\d{3})*,\d{2})(?!\d)")


def to_decimal(s: str) -> Decimal:
    if not s:
        return Decimal("0")
    s = s.strip()
    if s in {"—", "-", "–"}:
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
    Возвращает (найденная_строка, сумма).
    Сумму берём как ПОСЛЕДНЕЕ денежное значение в строке (обычно WB ставит сумму в конце).
    """
    for line in text.splitlines():
        if keyword.lower() in line.lower():
            m = MONEY_RE.findall(line)
            if not m:
                # если WB ставит "—" вместо суммы
                if "—" in line or " - " in line or "–" in line:
                    return line, Decimal("0")
                return line, Decimal("0")

            # берём последнее денежное значение
            val = to_decimal(m[-1])

            # защита от мусора (на всякий случай): WB-суммы не бывают триллионами
            if val > Decimal("1000000000"):  # 1 млрд
                # если вдруг строка странная — попробуем выбрать самое маленькое из найденных
                vals = [to_decimal(x) for x in m]
                vals = [v for v in vals if v <= Decimal("1000000000")]
                if vals:
                    return line, min(vals)
                return line, Decimal("0")

            return line, val

    return "", Decimal("0")


# ---------------- UI ----------------
st.set_page_config(page_title="WB Налоги", layout="wide")
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

# Ключевые строки ровно как в твоём WB-PDF
K1 = "Итого стоимость реализованного товара"
K3 = "Удержания в пользу третьих лиц"
K4 = "Компенсация ущерба"
K5 = "Прочие выплаты"

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

        if debug:
            debug_blocks.append(
                {
                    "file": f.name,
                    "p1_line": l1,
                    "p3_line": l3,
                    "p4_line": l4,
                    "p5_line": l5,
                    "p1": str(p1),
                    "p3": str(p3),
