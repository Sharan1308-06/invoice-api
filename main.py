import re
from dateutil import parser
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Invoice Extraction API")

# -----------------------------
# Enable CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceRequest(BaseModel):
    invoice_text: str


@app.get("/")
def root():
    return {"status": "running"}


def parse_money(value):
    if value is None:
        return None

    value = value.replace(",", "")
    value = re.sub(r"[^\d.]", "", value)

    try:
        return float(value)
    except Exception:
        return None


def find_first(patterns, text):
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


@app.post("/extract")
def extract(req: InvoiceRequest):

    text = req.invoice_text

    # -----------------------------
    # Invoice Number
    # -----------------------------
    invoice_no = find_first([
        r"Invoice\s*No\.?\s*[:#-]?\s*(.+)",
        r"Invoice\s*Number\s*[:#-]?\s*(.+)",
        r"Invoice\s*#\s*[:\-]?\s*(.+)"
    ], text)

    # -----------------------------
    # Vendor
    # -----------------------------
    vendor = find_first([
        r"Vendor\s*[:\-]?\s*(.+)",
        r"Seller\s*[:\-]?\s*(.+)",
        r"Supplier\s*[:\-]?\s*(.+)"
    ], text)

    # -----------------------------
    # Date
    # -----------------------------
    raw_date = find_first([
        r"Date\s*[:\-]?\s*(.+)"
    ], text)

    date = None
    if raw_date:
        try:
            dt = parser.parse(raw_date, dayfirst=True, fuzzy=True)
            date = dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # -----------------------------
    # Amount (Subtotal)
    # -----------------------------
    amount = None

    subtotal_patterns = [
        r"Subtotal\s*[:\-]?\s*([^\n]+)",
        r"Sub\s*Total\s*[:\-]?\s*([^\n]+)",
        r"Net\s*Amount\s*[:\-]?\s*([^\n]+)",
        r"Amount\s*Before\s*Tax\s*[:\-]?\s*([^\n]+)"
    ]

    for p in subtotal_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            amount = parse_money(m.group(1))
            break

    # -----------------------------
    # Tax
    # -----------------------------
    tax = None

    tax_patterns = [
        r"GST.*?([0-9,]+\.\d{2})",
        r"VAT.*?([0-9,]+\.\d{2})",
        r"Tax.*?([0-9,]+\.\d{2})",
        r"CGST.*?([0-9,]+\.\d{2})",
        r"SGST.*?([0-9,]+\.\d{2})",
        r"IGST.*?([0-9,]+\.\d{2})"
    ]

    for p in tax_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            tax = parse_money(m.group(1))
            break

    # -----------------------------
    # Currency
    # -----------------------------
    currency = None

    m = re.search(r"Currency\s*[:\-]?\s*([A-Z]{3})", text, re.IGNORECASE)
    if m:
        currency = m.group(1).upper()

    if currency is None:
        if "USD" in text.upper():
            currency = "USD"
        elif "EUR" in text.upper():
            currency = "EUR"
        elif "GBP" in text.upper():
            currency = "GBP"
        elif "INR" in text.upper():
            currency = "INR"
        elif "RS." in text.upper() or "₹" in text:
            currency = "INR"

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency
    }
