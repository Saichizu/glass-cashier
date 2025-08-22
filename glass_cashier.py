import streamlit as st
import datetime
import json
import math
from github import Github
from io import BytesIO
from reportlab.pdfgen import canvas

# --- CONFIGURATION ---
GITHUB_REPO = "Saichizu/glass-cashier"
SHOP_NAME = "GLASS CASHIER"  # shown at top of receipt

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

# --- HELPERS ---
def rupiah(n):
    try:
        return f"Rp {int(n):,}".replace(",", ".")
    except Exception:
        return f"Rp {n}"

def mm_to_pt(mm):
    # 1 inch = 25.4 mm, 1 inch = 72 pt
    return mm * 72.0 / 25.4

def safe_item_fields(item):
    """Return tuple (name, w_cm, h_cm, qty, unit_price, subtotal, area_m2)
    using safe defaults to support older transaction shapes."""
    name = item.get("item") or item.get("name") or "Item"
    w = item.get("width_cm", 0)
    h = item.get("height_cm", 0)
    qty = int(item.get("qty", 1))
    unit_price = int(item.get("unit_price", 0))
    subtotal = int(item.get("price", unit_price * qty))
    area_m2 = float(item.get("area_m2", (w/100.0)*(h/100.0) if (w and h) else 0))
    return name, w, h, qty, unit_price, subtotal, area_m2

# --- GITHUB UTILS ---
def get_github_client():
    github_token = st.secrets.get("GITHUB_TOKEN", None)
    if not github_token or not isinstance(github_token, str) or not github_token.strip():
        st.error("GITHUB_TOKEN not found or empty in Streamlit secrets. Please set your token in app settings.")
        raise ValueError("Missing or empty GITHUB_TOKEN in Streamlit secrets.")
    return Github(github_token)

def get_today_filename():
    today = datetime.datetime.now().strftime("%Y%m%d")
    return f"{today}.json"

def load_transactions(filename):
    try:
        g = get_github_client()
        repo = g.get_repo(GITHUB_REPO)
        file_content = repo.get_contents(filename).decoded_content.decode()
        return json.loads(file_content)
    except Exception:
        return []

def save_transactions(filename, data):
    try:
        g = get_github_client()
        repo = g.get_repo(GITHUB_REPO)
        try:
            file = repo.get_contents(filename)
            repo.update_file(filename, "Update transactions", json.dumps(data, indent=2), file.sha)
        except Exception:
            repo.create_file(filename, "Create transactions", json.dumps(data, indent=2))
    except Exception as e:
        st.error(f"Gagal menyimpan transaksi: {e}")

def generate_receipt_code(date_str, count):
    return f"GL{date_str}-{count:03d}"

# --- PDF UTILS ---
def create_receipt_pdf(transaction):
    # --- Set up your margins ---
    margin_left = 20   # left margin
    margin_right = 20  # right margin
    margin_top = 16    # top margin
    margin_bottom = 16 # bottom margin

    width_pt = mm_to_pt(76)
    line_h = 12
    header_lines = 6
    footer_lines = 6
    item_lines_per = 2
    items_count = len(transaction.get("items", []))
    est_lines = header_lines + footer_lines + (items_count * item_lines_per)

    # Calculate PDF height with bottom margin
    height_pt = est_lines * line_h + margin_top + margin_bottom

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width_pt, height_pt))
    y = height_pt - margin_top  # Start below the top margin

    # Header
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width_pt/2, y, SHOP_NAME)
    y -= line_h

    c.setFont("Helvetica", 8)
    code = transaction.get("code", "GL-XXXXXX")
    c.drawString(margin_left, y, f"Kode: {code}")
    y -= line_h

    tstr = transaction.get("datetime", "")[:16]
    if not tstr:
        tstr = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    else:
        try:
            dt = datetime.datetime.fromisoformat(transaction["datetime"])
            tstr = dt.strftime("%d-%m-%Y %H:%M")
        except Exception:
            pass
    c.drawString(margin_left, y, f"Tanggal: {tstr}")
    y -= line_h

    c.line(margin_left, y, width_pt - margin_right, y)
    y -= line_h

    # Items
    c.setFont("Helvetica", 8)
    for it in transaction.get("items", []):
        name, w, h, qty, unit_price, subtotal, area_m2 = safe_item_fields(it)
        c.drawString(margin_left, y, f"{name}  {w:.2f}x{h:.2f} cm")
        c.drawRightString(width_pt - margin_right, y, rupiah(subtotal))
        y -= line_h

        c.drawString(margin_left, y, f"{qty} × {rupiah(unit_price)} = {rupiah(unit_price * qty)}")
        y -= line_h

        # Page break logic, but unlikely needed for short receipts

    # Footer
    c.line(margin_left, y, width_pt - margin_right, y)
    y -= line_h

    total_qty = int(transaction.get("total_qty", sum(safe_item_fields(i)[3] for i in transaction.get("items", []))))
    total_sum = int(transaction.get("total", sum(safe_item_fields(i)[5] for i in transaction.get("items", []))))
    method = transaction.get("method", "-")

    c.drawString(margin_left, y, "Total Qty:")
    c.drawRightString(width_pt - margin_right, y, str(total_qty))
    y -= line_h

    c.drawString(margin_left, y, "Total:")
    c.drawRightString(width_pt - margin_right, y, rupiah(total_sum))
    y -= line_h

    c.drawString(margin_left, y, "Metode:")
    c.drawRightString(width_pt - margin_right, y, method)
    y -= line_h

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def create_summary_pdf(title, lines):
    margin_left = 20
    margin_right = 20
    margin_top = 16
    margin_bottom = 16

    width_pt = mm_to_pt(76)
    line_h = 12
    header_lines = 2
    footer_lines = 1
    est_lines = header_lines + footer_lines + len(lines)
    height_pt = est_lines * line_h + margin_top + margin_bottom

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width_pt, height_pt))
    y = height_pt - margin_top

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width_pt/2, y, title)
    y -= line_h * 2
    c.setFont("Helvetica", 8)
    for line in lines:
        c.drawString(margin_left, y, line)
        y -= line_h
        if y < (margin_left + 3*line_h):
            c.showPage()
            height_pt = 40*line_h + margin_top + margin_bottom
            c.setPageSize((width_pt, height_pt))
            y = height_pt - margin_top
            c.setFont("Helvetica", 8)

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
st.title("GLASS CASHIER")

# Item selection
st.subheader("Tambah ke Keranjang")
item_names = [item["name"] for item in ITEMS]
selected_item = st.selectbox("Pilih Barang", item_names)
item_obj = next(item for item in ITEMS if item["name"] == selected_item)
base_price = item_obj["base_price"]

# PATCH: qty on same row as width and height
col1, col2, col3 = st.columns(3)
width_cm = col1.number_input("Lebar (cm)", min_value=0.0, value=st.session_state.get("width_cm", 0.0), step=0.1, format="%.2f", key="width_cm")
height_cm = col2.number_input("Tinggi (cm)", min_value=0.0, value=st.session_state.get("height_cm", 0.0), step=0.1, format="%.2f", key="height_cm")
qty = col3.number_input("Jumlah", min_value=1, value=st.session_state.get("qty", 1), key="qty")

add_col, clear_col = st.columns([2, 1])

def clear_inputs():
    st.session_state["width_cm"] = 0.0
    st.session_state["height_cm"] = 0.0
    st.session_state["qty"] = 1

with add_col:
    add_clicked = st.button("➕ Tambah ke Keranjang")
with clear_col:
    st.button("🧹 Clear Tambah ke Keranjang", on_click=clear_inputs)

if width_cm > 0 and height_cm > 0:
    area_m2 = (width_cm / 100) * (height_cm / 100)
    unit_price = int(area_m2 * base_price + SERVICE_FEE)
    st.success(f"Harga per item: {rupiah(unit_price)}")

    if add_clicked:
        found = False
        for item in st.session_state["keranjang"]:
            if (
                item.get("item") == selected_item
                and float(item.get("width_cm", 0)) == float(width_cm)
                and float(item.get("height_cm", 0)) == float(height_cm)
            ):
                item["qty"] = int(item.get("qty", 1)) + qty
                raw_subtotal = item["qty"] * unit_price
                item["unit_price"] = unit_price
                item["price"] = math.ceil(raw_subtotal / 1000) * 1000
                found = True
                break

        if not found:
            st.session_state["keranjang"].append({
                "item": selected_item,
                "width_cm": float(width_cm),
                "height_cm": float(height_cm),
                "area_m2": area_m2,
                "unit_price": unit_price,
                "qty": int(qty),
                "price": math.ceil((unit_price * qty) / 1000) * 1000,
            })

# --- Keranjang (ongoing transaction) ---
if st.session_state["keranjang"]:
    st.subheader("🛒 Keranjang")
    total_qty = 0
    total_price = 0
    items_to_remove = []

    for idx, t in enumerate(st.session_state["keranjang"]):
        name, w, h, qty, unit_p, subtotal, _ = safe_item_fields(t)
        col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 1, 2, 3, 1])
        with col1:
            st.write(name)
        with col2:
            st.write(f"{w:.2f} x {h:.2f} cm")
        with col3:
            st.write(f"{qty}")
        with col4:
            st.write(f"{rupiah(unit_p)}")
        with col5:
            st.write(f"{rupiah(subtotal)}")
        with col6:
            if st.button("❌", key=f"remove_{idx}"):
                items_to_remove.append(idx)

        total_qty += qty
        total_price += subtotal

    for idx in sorted(items_to_remove, reverse=True):
        st.session_state["keranjang"].pop(idx)

    st.markdown(f"**Total Qty: {total_qty} pcs**")
    st.markdown(f"**Total Keranjang: {rupiah(total_price)}**")

    method = st.radio("Pilih Metode Pembayaran", ["Cash", "Transfer"], horizontal=True)
    st.session_state["method"] = method

    pay_enabled = method is not None

    def bayar_action():
        today_str = datetime.datetime.now().strftime("%d%m%y")
        filename = get_today_filename()
        transactions_today = load_transactions(filename)
        receipt_no = len(transactions_today) + 1
        receipt_code = generate_receipt_code(today_str, receipt_no)

        total_qty = sum(safe_item_fields(t)[3] for t in st.session_state["keranjang"])
        total_price = sum(safe_item_fields(t)[5] for t in st.session_state["keranjang"])

        transaction = {
            "code": receipt_code,
            "datetime": datetime.datetime.now().isoformat(),
            "items": st.session_state["keranjang"],
            "method": method,
            "total_qty": int(total_qty),
            "total": int(total_price),
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
        st.session_state["width_cm"] = 0.0
        st.session_state["height_cm"] = 0.0
        st.session_state["qty"] = 1

    st.button("💳 Bayar", disabled=not pay_enabled, on_click=bayar_action)

# --- Daftar Transaksi Hari Ini ---
st.subheader("📑 Daftar Transaksi Hari Ini")
filename = get_today_filename()
transactions_today = load_transactions(filename)

if transactions_today:
    for t in transactions_today:
        qty_display = t.get("total_qty", sum(safe_item_fields(i)[3] for i in t.get("items", [])))
        total_display = t.get("total", sum(safe_item_fields(i)[5] for i in t.get("items", [])))
        method_display = t.get("method", "-")
        with st.expander(f"{t.get('code','(tanpa kode)')} - {rupiah(total_display)} [{qty_display} pcs, {method_display}]"):
            for item in t.get("items", []):
                name, w, h, qty, unit_p, subtotal, area_m2 = safe_item_fields(item)
                st.write(
                    f"- {name} | {w:.2f}x{h:.2f} cm | {area_m2:.2f} m² | {qty} pcs | "
                    f"{rupiah(unit_p)} | Subtotal {rupiah(subtotal)}"
                )
else:
    st.info("Belum ada transaksi hari ini.")

# --- Finish session ---
if st.button("Selesaikan Sesi"):
    by_method = {"Cash": [], "Transfer": []}
    for t in transactions_today:
        by_method[t.get("method", "-")].append(t)

    st.subheader("Ringkasan Sesi Hari Ini")
    summary_lines = []
    for method, txns in by_method.items():
        st.write(f"**Transaksi {method}**")
        for t in txns:
            qty_display = t.get("total_qty", sum(safe_item_fields(i)[3] for i in t.get("items", [])))
            st.write(f"{t.get('code','(tanpa kode)')}: {rupiah(t.get('total', 0))} ({qty_display} pcs)")
        total_m = sum(t.get('total', 0) for t in txns)
        st.write(f"Total {method}: {rupiah(total_m)}")
        summary_lines.append(f"{method}: {rupiah(total_m)}")

    summary_str = "\n".join(summary_lines)
    st.text_area("Struk Ringkasan", summary_str, height=180)

    pdf = create_summary_pdf("Ringkasan Sesi", summary_lines)
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
                    file_name=f"reprint_{st.session_state['last_receipt'].get('code','no_code')}.pdf",
                    mime="application/pdf"
                )
        else:
            st.error("Kode salah. Tidak bisa reprint.")
else:
    st.info("Belum ada struk terakhir untuk di-reprint.")

# --- Refresh button ---
if st.button("Refresh"):
    st.experimental_rerun()
