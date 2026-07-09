import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dateutil import parser

app = FastAPI(title="Invoice Extraction API")

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


def money(value):
    value = value.replace(",", "")
    value = re.sub(r"[^\d.]", "", value)

    try:
        return float(value)
    except:
        return None


def search_patterns(patterns, text):

    for p in patterns:

        m = re.search(p, text, re.I | re.M)

        if m:
            return m.group(1).strip()

    return None


@app.post("/extract")
def extract(req: InvoiceRequest):

    text = req.invoice_text
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    invoice_no = None
    vendor = None
    date = None
    amount = None
    tax = None
    currency = None

    # -------------------------
    # Invoice Number
    # -------------------------

    invoice_no = search_patterns([
        r"Invoice\s*No\.?\s*:\s*(.+)",
        r"Invoice\s*Number\s*:\s*(.+)",
        r"Invoice\s*#\s*:\s*(.+)",
        r"Invoice\s*ID\s*:\s*(.+)",
        r"Bill\s*No\.?\s*:\s*(.+)",
        r"Reference\s*:\s*(.+)"
    ], text)

    if invoice_no:

        invoice_no = invoice_no.split()[0]

    if invoice_no is None:

        m = re.search(
            r"\b[A-Z]{1,6}-[A-Z0-9-]{2,20}\b",
            text
        )

        if m:
            invoice_no = m.group(0)

    # -------------------------
    # Vendor
    # -------------------------

    vendor = search_patterns([
        r"Vendor\s*:\s*(.+)",
        r"Seller\s*:\s*(.+)",
        r"Supplier\s*:\s*(.+)",
        r"Company\s*:\s*(.+)",
        r"From\s*:\s*(.+)"
    ], text)

    # -------------------------
    # Date
    # -------------------------

    raw_date = search_patterns([
        r"Invoice\s*Date\s*:\s*(.+)",
        r"Date\s*:\s*(.+)",
        r"Issue\s*Date\s*:\s*(.+)"
    ], text)

    if raw_date:

        try:

            d = parser.parse(raw_date, fuzzy=True)

            date = d.strftime("%Y-%m-%d")

        except:

            pass

    # -------------------------
    # Amount
    # -------------------------

    amount_labels = [
        "subtotal",
        "sub total",
        "net amount",
        "amount before tax",
        "taxable value"
    ]

    for line in lines:

        lower = line.lower()

        if any(x in lower for x in amount_labels):

            nums = re.findall(r"[0-9][0-9,]*\.\d{2}", line)

            if nums:
                amount = money(nums[-1])
                break

    # -------------------------
    # Tax
    # -------------------------

    cgst = 0
    sgst = 0
    igst = 0

    for line in lines:

        lower = line.lower()

        nums = re.findall(r"[0-9][0-9,]*\.\d{2}", line)

        if not nums:
            continue

        value = money(nums[-1])

        if "cgst" in lower:
            cgst += value

        elif "sgst" in lower:
            sgst += value

        elif "igst" in lower:
            igst += value

    if cgst or sgst or igst:

        tax = round(cgst + sgst + igst, 2)

    else:

        for line in lines:

            lower = line.lower()

            if (
                "gst" in lower
                or "vat" in lower
                or "tax" in lower
            ):

                nums = re.findall(
                    r"[0-9][0-9,]*\.\d{2}",
                    line
                )

                if nums:
                    tax = money(nums[-1])
                    break

    # -------------------------
    # Currency
    # -------------------------

    m = re.search(
        r"Currency\s*:\s*([A-Z]{3})",
        text,
        re.I
    )

    if m:

        currency = m.group(1).upper()

    else:

        t = text.upper()

        if "USD" in t or "$" in text:
            currency = "USD"

        elif "EUR" in t:
            currency = "EUR"

        elif "GBP" in t:
            currency = "GBP"

        elif "INR" in t or "RS." in t or "₹" in text:
            currency = "INR"

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency
    }
