import re
from datetime import datetime

from dateutil import parser
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceRequest(BaseModel):
    invoice_text: str


def extract_money(value):
    if value is None:
        return None

    value = value.replace(",", "")
    value = re.sub(r"[^\d.]", "", value)

    try:
        return float(value)
    except:
        return None


@app.get("/")
def root():
    return {"status": "running"}


@app.post("/extract")
def extract(req: InvoiceRequest):

    text = req.invoice_text

    invoice_no = None
    date = None
    vendor = None
    amount = None
    tax = None

    # Invoice Number
    m = re.search(r"Invoice\s*No[:\-]?\s*(.+)", text, re.I)
    if m:
        invoice_no = m.group(1).strip()

    # Vendor
    m = re.search(r"Vendor[:\-]?\s*(.+)", text, re.I)
    if m:
        vendor = m.group(1).strip()

    # Date
    m = re.search(r"Date[:\-]?\s*(.+)", text, re.I)
    if m:
        try:
            d = parser.parse(m.group(1).strip(), dayfirst=True)
            date = d.strftime("%Y-%m-%d")
        except:
            pass

    # Subtotal / Amount
    m = re.search(
        r"(Subtotal|Amount)\s*[:\-]?\s*(.+)",
        text,
        re.I,
    )
    if m:
        amount = extract_money(m.group(2))

    # GST / Tax
    m = re.search(
        r"(GST|Tax).*?[:\-]?\s*(.+)",
        text,
        re.I,
    )
    if m:
        tax = extract_money(m.group(2))

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": "INR",
    }