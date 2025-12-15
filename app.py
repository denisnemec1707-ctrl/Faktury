'''
# Invoice QR Code Generator

This Streamlit application automates the process of paying invoices by extracting payment details from an uploaded invoice file (image or PDF) and generating the appropriate QR code for payment in either Slovakia or the Czech Republic.

**Functionality:**
- **File Upload:** Accepts JPG, PNG, and PDF files, with mobile camera support.
- **OCR:** Uses `pytesseract` to extract text from the invoice.
- **Intelligent Parsing:** Automatically detects and extracts IBAN, amount, currency, and variable symbol (VS) from the text.
- **Country Detection:** Identifies whether the invoice is Slovak or Czech based on the IBAN prefix ("SK" or "CZ").
- **Dual QR Code Generation:**
  - Generates **PAY by square** QR codes for Slovak invoices.
  - Generates **QR Platba** codes for Czech invoices.
- **User-Friendly Interface:** Displays extracted data in an editable form, allowing users to review and correct information before generating the QR code.

**Deployment:**
- Ready for deployment on Streamlit Community Cloud.
- Requires `tesseract-ocr` to be listed in `packages.txt`.
- All Python dependencies are in `requirements.txt`.
'''

import streamlit as st
import pytesseract
from PIL import Image
import re
import qrcode
from io import BytesIO
from pdf2image import convert_from_bytes
import pay_by_square

def process_file(uploaded_file):
    """Converts uploaded file (PDF or image) to a list of PIL Images."""
    images = []
    if uploaded_file.type == "application/pdf":
        try:
            pdf_images = convert_from_bytes(uploaded_file.read())
            images.extend(pdf_images)
        except Exception as e:
            st.error(f"Chyba pri spracovaní PDF: {e}")
    else:
        try:
            img = Image.open(uploaded_file)
            images.append(img)
        except Exception as e:
            st.error(f"Chyba pri otváraní obrázku: {e}")
    return images

def extract_text_from_image(image):
    """Extracts text from a single PIL Image using pytesseract."""
    try:
        return pytesseract.image_to_string(image, lang='slk+ces')
    except Exception as e:
        st.error(f"Chyba pri OCR spracovaní: {e}")
        return ""

def parse_text(text):
    """Parses extracted text to find IBAN, amount, currency, and variable symbol."""
    iban_match = re.search(r'(SK[0-9]{2}\s?[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}|CZ[0-9]{2}\s?[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\s?[0-9]{4})', text)
    iban = iban_match.group(1).replace(" ", "") if iban_match else ""

    # Try to find amount with EUR/CZK symbols or keywords
    amount_match = re.search(r'(\d{1,10}[,.]\d{2})\s?(EUR|€|Kč|CZK)', text, re.IGNORECASE)
    if not amount_match:
        amount_match = re.search(r'(EUR|€|Kč|CZK)\s?(\d{1,10}[,.]\d{2})', text, re.IGNORECASE)
        if amount_match:
            amount_str = amount_match.group(2)
        else:
            amount_str = ""
    else:
        amount_str = amount_match.group(1)

    amount = float(amount_str.replace(",", ".")) if amount_str else 0.0

    # Detect currency
    currency = "EUR"
    if "CZK" in text.upper() or "KČ" in text.upper() or (iban and iban.startswith("CZ")):
        currency = "CZK"

    # Find variable symbol
    vs_match = re.search(r'(VS|Variabiln[yý] symbol):?\s*(\d{1,10})', text, re.IGNORECASE)
    vs = vs_match.group(2) if vs_match else ""
    if not vs:
        # If no explicit "VS" found, look for a standalone 10-digit number
        vs_match = re.search(r'\b(\d{10})\b', text)
        vs = vs_match.group(1) if vs_match else ""

    return iban, amount, currency, vs

def generate_pay_by_square(iban, amount, currency, vs, msg):
    """Generates a PAY by square string."""
    try:
        return pay_by_square.generate(
            iban=iban,
            amount=amount,
            currency=currency,
            variable_symbol=vs,
            note=msg
        )
    except Exception as e:
        st.error(f"Chyba pri generovaní PAY by square kódu: {e}")
        return None

def generate_qr_platba(iban, amount, currency, vs, msg):
    """Generates a QR Platba string."""
    qr_string = f"SPD*1.0*ACC:{iban}*"
    if amount > 0:
        qr_string += f"AM:{amount:.2f}*"
    if currency:
        qr_string += f"CC:{currency}*"
    if msg:
        qr_string += f"MSG:{msg.upper()}*"
    if vs:
        qr_string += f"X-VS:{vs}*"
    return qr_string

# --- Streamlit UI ---
st.set_page_config(page_title="Invoice QR Generator", layout="centered")
st.title("🤖 Invoice QR Code Generator")
st.write("Nahrajte faktúru (obrázok alebo PDF) a aplikácia automaticky extrahuje platobné údaje a vygeneruje správny QR kód pre platbu na Slovensku alebo v Česku.")

uploaded_file = st.file_uploader("Vyberte súbor (JPG, PNG, PDF)", type=["jpg", "png", "pdf"])

if uploaded_file:
    st.session_state.iban = ""
    st.session_state.amount = 0.0
    st.session_state.currency = "EUR"
    st.session_state.vs = ""

    with st.spinner("Spracovávam súbor a extrahujem text...⏳"):
        images = process_file(uploaded_file)
        if images:
            full_text = ""
            for image in images:
                full_text += extract_text_from_image(image) + "\n"

            if full_text.strip():
                st.session_state.iban, st.session_state.amount, st.session_state.currency, st.session_state.vs = parse_text(full_text)
                st.success("Text extrahovaný! Skontrolujte a upravte údaje nižšie.")
            else:
                st.warning("Nepodarilo sa extrahovať žiadny text. Vyplňte údaje manuálne.")
        else:
            st.error("Nepodarilo sa spracovať súbor.")

# --- Payment Form ---

if 'iban' not in st.session_state:
    st.session_state.iban = ""
if 'amount' not in st.session_state:
    st.session_state.amount = 0.0
if 'currency' not in st.session_state:
    st.session_state.currency = "EUR"
if 'vs' not in st.session_state:
    st.session_state.vs = ""

# Determine default country from IBAN
default_country_index = 0 # Slovakia
if st.session_state.iban and st.session_state.iban.startswith("CZ"):
    default_country_index = 1 # Czech Republic

country = st.radio(
    "Krajina faktúry:",
    ('🇸🇰 Slovenská faktúra', '🇨🇿 Česká faktúra'),
    index=default_country_index
)

with st.form("payment_form"):
    iban = st.text_input("IBAN", value=st.session_state.iban)
    amount = st.number_input("Suma", value=st.session_state.amount, format="%.2f")
    currency = st.selectbox("Mena", ("EUR", "CZK"), index=0 if st.session_state.currency == "EUR" else 1)
    vs = st.text_input("Variabilný symbol (VS)", value=st.session_state.vs)
    msg = st.text_input("Správa pre príjemcu (nepovinné)")

    submitted = st.form_submit_button("🚀 Generovať QR kód")

    if submitted:
        if not iban:
            st.error("IBAN je povinný údaj.")
        else:
            qr_data = None
            if country == '🇸🇰 Slovenská faktúra':
                if not iban.startswith("SK"):
                    st.warning("Zvolili ste slovenskú faktúru, ale IBAN nevyzerá ako slovenský (nezačína na SK).")
                st.info("Generujem PAY by square QR kód...")
                qr_data = generate_pay_by_square(iban, amount, currency, vs, msg)
            elif country == '🇨🇿 Česká faktúra':
                if not iban.startswith("CZ"):
                    st.warning("Zvolili ste českú faktúru, ale IBAN nevyzerá ako český (nezačína na CZ).")
                st.info("Generujem QR Platba kód...")
                qr_data = generate_qr_platba(iban, amount, currency, vs, msg)

            if qr_data:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=10,
                    border=4,
                )
                qr.add_data(qr_data)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")

                # Convert to bytes to display in Streamlit
                buf = BytesIO()
                img.save(buf, format="PNG")
                byte_im = buf.getvalue()

                st.image(byte_im, caption="Naskenujte tento QR kód v bankovej aplikácii", width=300)
                st.success("QR kód úspešne vygenerovaný!")
            else:
                st.error("Nepodarilo sa vygenerovať QR kód. Skontrolujte zadané údaje.")
