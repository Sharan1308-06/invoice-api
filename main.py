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
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    invoice_no = None
    vendor = None
    date = None
    amount = None
    tax = None
    currency = None

    # ----------------------------------------
    # Invoice Number
    # ----------------------------------------

    invoice_labels = [
        "invoice no",
        "invoice number",
        "invoice #",
        "invoice id",
        "invoice",
        "inv no",
        "inv #",
        "bill no",
        "bill number",
        "reference",
        "ref no"
    ]

    for line in lines:

        lower = line.lower()

        for label in invoice_labels:

            if lower.startswith(label):

                parts = re.split(r":|#", line, maxsplit=1)

                if len(parts) > 1:
                    value = parts[1].strip()

                    if value:
                        invoice_no = value
                        break

                m = re.search(r"[A-Z]{1,6}-[A-Z0-9-]+", line)

                if m:
                    invoice_no = m.group(0)
                    break

        if invoice_no:
            break

    # fallback search anywhere
    if invoice_no is None:

        patterns = [
            r"\b[A-Z]{2,6}-\d{2,8}\b",
            r"\b[A-Z]{2,6}-[A-Z0-9-]{3,20}\b",
            r"\b\d{4}-[A-Z]{2,5}-\d+\b",
        ]

        for p in patterns:

            m = re.search(p, text)

            if m:
                invoice_no = m.group(0)
                break

    # ----------------------------------------
    # Vendor
    # ----------------------------------------

    vendor_labels = [
        "vendor",
        "seller",
        "supplier",
        "from",
        "company"
    ]

    for line in lines:

        lower = line.lower()

        for label in vendor_labels:

            if lower.startswith(label):

                parts = line.split(":", 1)

                if len(parts) > 1:
                    vendor = parts[1].strip()

                break

        if vendor:
            break

    # ----------------------------------------
    # Date
    # ----------------------------------------

    for line in lines:

        if "date" in line.lower():

            parts = line.split(":", 1)

            if len(parts) > 1:

                try:
                    dt = parser.parse(parts[1], fuzzy=True)
                    date = dt.strftime("%Y-%m-%d")
                    break
                except:
                    pass

    # ----------------------------------------
    # Amount
    # ----------------------------------------

    subtotal_labels = [
        "subtotal",
        "sub total",
        "net amount",
        "taxable value",
        "amount before tax"
    ]

    for line in lines:

        lower = line.lower()

        for label in subtotal_labels:

            if label in lower:

                m = re.search(r"([0-9][0-9,]*\.\d{2})", line)

                if m:
                    amount = parse_money(m.group(1))
                    break

        if amount is not None:
            break

    # ----------------------------------------
    # Tax
    # ----------------------------------------

    tax = None
tax_total = 0.0
found_tax = False

# Sum GST components
for line in lines:
    lower = line.lower()

    if any(label in lower for label in ["cgst", "sgst", "igst", "gst", "vat", "tax"]):

        nums = re.findall(r"([0-9][0-9,]*\.\d{2})", line)

        if nums:
            tax_total += parse_money(nums[-1])
            found_tax = True

if found_tax:
    tax = round(tax_total, 2)
    # ----------------------------------------
    # Currency
    # ----------------------------------------

    currencies = [
        "INR",
        "USD",
        "EUR",
        "GBP",
        "AED",
        "JPY",
        "AUD",
        "CAD"
    ]

    for c in currencies:

        if c in text.upper():
            currency = c
            break

    if currency is None:

        if "₹" in text or "RS." in text.upper():
            currency = "INR"

        elif "$" in text:
            currency = "USD"

    return {
        "invoice_no": invoice_no,
        "date": date,
        "vendor": vendor,
        "amount": amount,
        "tax": tax,
        "currency": currency
    }
