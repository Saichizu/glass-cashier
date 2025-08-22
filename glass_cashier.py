import streamlit as st
import datetime
import json
import math
from github import Github
from io import BytesIO
from reportlab.pdfgen import canvas

# --- CONFIGURATION ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = "Saichizu/glass-cashier"

# --- ITEMS ---
ITEMS = [
    {"name": "Kaca Polos 5MM", "base_price": 190000},
    {"name": "Kaca Reben 5MM", "base_price": 200000},
    {"name": "Kaca Reben 3MM", "base_price": 160000},
    {"name": "Kaca Polos 3MM", "base_price": 150000},
    {"name": "Kaca Cermin", "base_price": 240000},
    {"name": "Kaca Polos Utuh", "base_price": 140000},
    {"name": "Kaca Reben Utuh", "base_price": 150000},
]

SERVICE_FEE = 500
OWNER_PASSCODE = "901012"

# --- GITHUB UTILS ---
def get_github_client():
    return Github(GITHUB_TOKEN)

def get_today_filename():
    today = datetime.datetime.now().strftime("%Y%m%d")
    return f"{today}.json"

def load_transactions(filename):
    g = get_github_client()
    repo = g.get_repo(GITHUB_REPO)
    try:
        file_content = repo.get_contents(filename).decoded_content.decode()
        return json.loads(file_content)
    except Exception:
        return []

def save_transactions(filename, data):
    g = get_github_client()
    repo = g.get_repo(GITHUB_REPO)
    try:
        file = repo.get_contents(filename)
        repo.update_file(filename, "Update transactions", json.dumps(data, indent=2), file.sha)
    except Exception:
        repo.create_file(filename, "Create transactions", json.dumps(data, indent=2))

def generate_receipt_code(date_str, count):
    return f"GL{date_str}-{count:03d}"

# --- PDF UTILS ---
def create_receipt_pdf(transaction):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(220, 600))  # narrow width for thermal-like receipt
    y = 570

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(110, y, "Glass Cashier App")
    y -= 15
    c.setFont("Helvetica", 8)
    c.drawCentredString(110, y, transaction["datetime"][:19])

    y -= 20
    c.setFont("Helvetica", 9)
    for item in transaction["items"]:
        line = f"{item['item']} {item['width_cm']}x{item['height_cm']} x{item['qty']}"
        c.drawString(10, y, line)
        c.drawRightString(210, y, f"Rp {item['price']:,}")
        y -= 15

    y -= 5
    c.line(10, y, 210, y)
    y -= 15
    c.drawString(10, y, "Total Qty")
    c.drawRightString(210, y, str(transaction["total_qty"]))
    y -= 15
    c.drawString(10, y, "Total")
    c.drawRightString(210, y, f"Rp {transaction['total']:,}")
    y -= 15
    c.drawString(10, y, "Metode")
    c.drawRightString(210, y, transaction["method"])

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- SESSION STATE ---
if "keranjang" not in st.session_state:
    st.session_state["keranjang"] = []
if "method" not in st.session_state:
    st.session_state["method"] = None
if "owner_mode" not in st.session_state:
    st.session_state["owner_mode"] = False
if "edit_date" not in st.session_state:
    st.session_state["edit_date"] = None
if "last_receipt" not in st.session_state:
    st.session_state["last_receipt"] = None

# --- UI ---
st.title("Glass Cashier App")

# Item selection
st.subheader("Tambah ke Keranjang")
item_names = [item["name"] for item in ITEMS]
selected_item = st.selectbox("Pilih Barang", item_names)
item_obj = next(item for item in ITEMS if item["name"] == selected_item)
base_price = item_obj["base_price"]

col1, col2 = st.columns(2)
width_cm = col1.number_input("Lebar (cm)", min_value=0, value=0)
height_cm = col2.number_input("Tinggi (cm)", min_value=0, value=0)

if width_cm > 0 and height_cm > 0:
    area_m2 = (width_cm / 100) * (height_cm / 100)
    unit_price = int(area_m2 * base_price + SERVICE_FEE)
    st.success(f"Harga per item: Rp {unit_price:,}")

    qty = st.number_input("Jumlah", min_value=1, value=1)

    if st.button("➕ Tambah ke Keranjang"):
        found = False
        for item in st.session_state["keranjang"]:
            if (
                item["item"] == selected_item
                and item["width_cm"] == width_cm
                and item["height_cm"] == height_cm
            ):
                item["qty"] += qty
                raw_subtotal = item["qty"] * unit_price
                item["price"] = math.ceil(raw_subtotal / 1000) * 1000
                found = True
                break

        if not found:
            st.session_state["keranjang"].append({
                "item": selected_item,
                "width_cm": width_cm,
                "height_cm": height_cm,
                "area_m2": area_m2,
                "unit_price": unit_price,
                "qty": qty,
                "price": math.ceil((unit_price * qty) / 1000) * 1000,
            })

# --- Keranjang (ongoing transaction) ---
if st.session_state["keranjang"]:
    st.subheader("🛒 Keranjang")
    total_qty = 0
    total_price = 0
    items_to_remove = []

    for idx, t in enumerate(st.session_state["keranjang"]):
        col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 1, 2, 3, 1])
        with col1:
            st.write(t["item"])
        with col2:
            st.write(f"{t['width_cm']} x {t['height_cm']} cm")
        with col3:
            st.write(f"{t['qty']}")
        with col4:
            st.write(f"Rp {t['unit_price']:,}")
        with col5:
            st.write(f"Rp {t['price']:,}")
        with col6:
            if st.button("❌", key=f"remove_{idx}"):
                items_to_remove.append(idx)

        total_qty += t["qty"]
        total_price += t["price"]

    for idx in sorted(items_to_remove, reverse=True):
        st.session_state["keranjang"].pop(idx)

    st.markdown(f"**Total Qty: {total_qty} pcs**")
    st.markdown(f"**Total Keranjang: Rp {total_price:,}**")

    method = st.radio("Pilih Metode Pembayaran", ["Cash", "Transfer"], horizontal=True)
    st.session_state["method"] = method

    pay_enabled = method is not None
    if st.button("💳 Bayar", disabled=not pay_enabled):
        today_str = datetime.datetime.now().strftime("%d%m%y")
        filename = get_today_filename()
        transactions_today = load_transactions(filename)
        receipt_no = len(transactions_today) + 1
        receipt_code = generate_receipt_code(today_str, receipt_no)

        total_qty = sum(t["qty"] for t in st.session_state["keranjang"])
        total_price = sum(t["price"] for t in st.session_state["keranjang"])

        transaction = {
            "code": receipt_code,
            "datetime": datetime.datetime.now().isoformat(),
            "items": st.session_state["keranjang"],
            "method": method,
            "total_qty": total_qty,
            "total": total_price,
        }
        transactions_today.append(transaction)
        save_transactions(filename, transactions_today)
        st.success(f"Transaksi berhasil disimpan! Kode: {receipt_code}")

        # PDF receipt download
        pdf = create_receipt_pdf(transaction)
        st.download_button(
            label="⬇️ Download Receipt PDF",
            data=pdf,
            file_name=f"{receipt_code}.pdf",
            mime="application/pdf"
        )

        st.session_state["last_receipt"] = transaction
        st.session_state["keranjang"] = []

# --- Daftar Transaksi Hari Ini ---
st.subheader("📑 Daftar Transaksi Hari Ini")
filename = get_today_filename()
transactions_today = load_transactions(filename)

if transactions_today:
    for t in transactions_today:
        qty_display = t.get("total_qty", sum(i.get("qty", 1) for i in t["items"]))
        with st.expander(f"{t['code']} - Rp {t['total']:,} [{qty_display} pcs, {t['method']}]"):
            for item in t["items"]:
                if "qty" in item:
                    st.write(
                        f"- {item['item']} | {item['width_cm']}x{item['height_cm']} cm | "
                        f"{item['area_m2']:.2f} m² | {item['qty']} pcs | "
                        f"Rp {item['unit_price']:,} | Subtotal Rp {item['price']:,}"
                    )
                else:
                    st.write(
                        f"- {item['item']} | {item['width_cm']}x{item['height_cm']} cm | "
                        f"{item['area_m2']:.2f} m² | Rp {item['price']:,}"
                    )
else:
    st.info("Belum ada transaksi hari ini.")

# --- Finish session ---
if st.button("Selesaikan Sesi"):
    by_method = {"Cash": [], "Transfer": []}
    for t in transactions_today:
        by_method[t["method"]].append(t)

    st.subheader("Ringkasan Sesi Hari Ini")
    summary_lines = []
    for method, txns in by_method.items():
        st.write(f"**Transaksi {method}**")
        for t in txns:
            qty_display = t.get("total_qty", sum(i.get("qty", 1) for i in t["items"]))
            st.write(f"{t['code']}: Rp {t['total']:,} ({qty_display} pcs)")
        total_m = sum(t['total'] for t in txns)
        st.write(f"Total {method}: Rp {total_m:,}")
        summary_lines.append(f"{method}: Rp {total_m:,}")

    summary_str = "\n".join(summary_lines)
    st.text_area("Struk Ringkasan", summary_str, height=180)

    pdf = BytesIO()
    c = canvas.Canvas(pdf, pagesize=(220, 600))
    y = 570
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(110, y, "Ringkasan Sesi")
    y -= 20
    c.setFont("Helvetica", 8)
    for line in summary_lines:
        c.drawString(10, y, line)
        y -= 15
    c.showPage()
    c.save()
    pdf.seek(0)

    st.download_button("⬇️ Download Ringkasan PDF", pdf, file_name="summary.pdf", mime="application/pdf")

# --- Reprint function (Owner Only) ---
st.subheader("🔁 Reprint Struk")
if st.session_state.get("last_receipt"):
    passcode = st.text_input("Masukkan Kode Owner untuk Reprint", type="password")
    if passcode:
        if passcode == OWNER_PASSCODE:
            if st.button("Reprint"):
                pdf = create_receipt_pdf(st.session_state["last_receipt"])
                st.download_button(
                    label="⬇️ Download Reprint PDF",
                    data=pdf,
                    file_name=f"reprint_{st.session_state['last_receipt']['code']}.pdf",
                    mime="application/pdf"
                )
        else:
            st.error("Kode salah. Tidak bisa reprint.")
else:
    st.info("Belum ada struk terakhir untuk di-reprint.")

# --- Refresh button ---
if st.button("Refresh"):
    st.experimental_rerun()
