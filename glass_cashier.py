import streamlit as st
import datetime
import json
import math
from github import Github
from io import BytesIO
from reportlab.pdfgen import canvas
from zoneinfo import ZoneInfo

# --- GITHUB TOKEN (Safe Fetch) ---
def get_github_token():
    token = st.secrets.get("GITHUB_TOKEN", "").strip()
    if not token:
        st.warning("⚠️ GITHUB_TOKEN not found. Please check Streamlit secrets.")
        return None
    return token

# --- CONFIGURATION ---
GITHUB_REPO = "Saichizu/glass-cashier"
SHOP_NAME = "Glass Cashier App"  # shown at top of receipt

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
    return mm * 72.0 / 25.4

def safe_item_fields(item):
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
    token = get_github_token()
    if not token:
        raise RuntimeError("GitHub token is missing or invalid.")
    return Github(token)

def get_today_filename():
    today = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
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

def delete_transaction(filename, code_to_delete):
    try:
        g = get_github_client()
        repo = g.get_repo(GITHUB_REPO)
        file = repo.get_contents(filename)
        transactions = json.loads(file.decoded_content.decode())
        new_transactions = [t for t in transactions if t.get("code") != code_to_delete]
        repo.update_file(
            path=filename,
            message=f"Delete transaction {code_to_delete}",
            content=json.dumps(new_transactions, indent=2),
            sha=file.sha
        )
        return True
    except Exception as e:
        st.error(f"Gagal menghapus transaksi: {e}")
        return False

def generate_receipt_code(date_str, count):
    return f"GL{date_str}-{count:03d}"

def list_session_files():
    try:
        g = get_github_client()
        repo = g.get_repo(GITHUB_REPO)
        files = repo.get_contents("")
        session_files = [f.name for f in files if f.name.endswith(".json") and f.name[:8].isdigit()]
        session_files.sort(reverse=True)
        return session_files
    except Exception as e:
        st.error(f"Gagal mengambil daftar sesi: {e}")
        return []

def create_receipt_pdf(transaction):
    margin_left = 20
    margin_right = 20
    margin_top = 16
    margin_bottom = 16

    width_pt = mm_to_pt(76)
    line_h = 12
    header_lines = 6
    footer_lines = 6
    item_lines_per = 2
    items_count = len(transaction.get("items", []))
    est_lines = header_lines + footer_lines + (items_count * item_lines_per)
    height_pt = est_lines * line_h + margin_top + margin_bottom

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width_pt, height_pt))
    y = height_pt - margin_top

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width_pt/2, y, SHOP_NAME)
    y -= line_h

    c.setFont("Helvetica", 8)
    code = transaction.get("code", "GL-XXXXXX")
    c.drawString(margin_left, y, f"Kode: {code}")
    y -= line_h

    tstr = transaction.get("datetime", "")[:16]
    if not tstr:
        tstr = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%d-%m-%Y %H:%M")
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

    c.setFont("Helvetica", 8)
    for it in transaction.get("items", []):
        name, w, h, qty, unit_price, subtotal, area_m2 = safe_item_fields(it)
        c.drawString(margin_left, y, f"{name}  {w:.2f}x{h:.2f} cm")
        c.drawRightString(width_pt - margin_right, y, rupiah(subtotal))
        y -= line_h

        c.drawString(margin_left, y, f"{qty} × {rupiah(unit_price)} = {rupiah(unit_price * qty)}")
        y -= line_h

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
if "last_receipt_pdf" not in st.session_state:
    st.session_state["last_receipt_pdf"] = None
if "reprint_passcode" not in st.session_state:
    st.session_state["reprint_passcode"] = ""
if "just_paid" not in st.session_state:
    st.session_state["just_paid"] = False

# --- SAFE RESET for widget values ---
def safe_reset():
    # Only reset widget state if just_paid and before widgets are rendered
    if st.session_state.get("just_paid"):
        st.session_state["keranjang"] = []
        st.session_state["width_cm"] = 0.0
        st.session_state["height_cm"] = 0.0
        st.session_state["qty"] = 1
        st.session_state["just_paid"] = False

safe_reset()

st.title("Sistem Penjualan Kaca")
col1, col2 = st.columns(2)

with col1:
    if st.button("Refresh"):
        st.rerun()

with col2:
    if st.button("🔑 Cek Koneksi Jika Daftar Transaksi tidak Muncul"):
        try:
            g = get_github_client()
            user = g.get_user().login
            st.success("Tersambung")
        except Exception as e:
            st.error(f"Gagal Koneksi [Laporkan ke Gerald]: {e}")



# --- Item selection
st.subheader("Tambah ke Keranjang")
item_names = [item["name"] for item in ITEMS]
selected_item = st.selectbox("Pilih Barang", item_names)
item_obj = next(item for item in ITEMS if item["name"] == selected_item)
base_price = item_obj["base_price"]

col1, col2, col3 = st.columns(3)
width_cm = col1.number_input("Lebar (cm)", min_value=0.0, value=st.session_state.get("width_cm", 0.0), step=0.1, format="%.2f", key="width_cm")
height_cm = col2.number_input("Tinggi (cm)", min_value=0.0, value=st.session_state.get("height_cm", 0.0), step=0.1, format="%.2f", key="height_cm")
qty = col3.number_input("Jumlah", min_value=1, value=st.session_state.get("qty", 1), key="qty")

def clear_inputs():
    st.session_state["width_cm"] = 0.0
    st.session_state["height_cm"] = 0.0
    st.session_state["qty"] = 1

add_col, clear_col = st.columns([2, 1])
with add_col:
    add_clicked = st.button("➕ Tambah ke Keranjang")
with clear_col:
    st.button("🧹 Bersihkan", on_click=clear_inputs)

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
    col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 1, 2, 3, 1])
    with col1: st.markdown("**Item**")
    with col2: st.markdown("**Ukuran)**")
    with col3: st.markdown("**Qty**")
    with col4: st.markdown("**Harga Satuan**")
    with col5: st.markdown("**Subtotal**")
    with col6: st.markdown("**Hapus**")

    total_qty = 0
    total_price = 0
    items_to_remove = []
    for idx, t in enumerate(st.session_state["keranjang"]):
        name, w, h, qty, unit_p, subtotal, _ = safe_item_fields(t)
        col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 1, 2, 3, 1])
        with col1: st.write(name)
        with col2: st.write(f"{w:.2f} x {h:.2f} cm")
        with col3: st.write(f"{qty}")
        with col4: st.write(f"{rupiah(unit_p)}")
        with col5: st.write(f"{rupiah(subtotal)}")
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

    # BAYAR BUTTON
    if st.button("💳 Bayar", disabled=not pay_enabled):
        today_str = datetime.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%d%m%y")
        filename = get_today_filename()
        transactions_today = load_transactions(filename)
        receipt_no = len(transactions_today) + 1
        receipt_code = generate_receipt_code(today_str, receipt_no)
        total_qty = sum(safe_item_fields(t)[3] for t in st.session_state["keranjang"])
        total_price = sum(safe_item_fields(t)[5] for t in st.session_state["keranjang"])
        transaction = {
            "code": receipt_code,
            "datetime": datetime.datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "items": st.session_state["keranjang"],
            "method": method,
            "total_qty": int(total_qty),
            "total": int(total_price),
        }
        transactions_today.append(transaction)
        save_transactions(filename, transactions_today)
        st.success(f"Transaksi berhasil disimpan! Kode: {receipt_code}")
        pdf = create_receipt_pdf(transaction)
        st.session_state["last_receipt"] = transaction
        st.session_state["last_receipt_pdf"] = pdf
        st.download_button(
            label="⬇️ Download Receipt PDF",
            data=pdf,
            file_name=f"{receipt_code}.pdf",
            mime="application/pdf"
        )
        st.session_state["just_paid"] = True

# --- Daftar Transaksi Hari Ini ---
st.subheader("📑 Daftar Transaksi Hari Ini")
filename = get_today_filename()
transactions_today = load_transactions(filename)

# 🔄 Sort so latest transactions appear first
transactions_today = sorted(
    transactions_today,
    key=lambda x: x.get("timestamp", ""),
    reverse=True
)

if transactions_today:
    for i, t in enumerate(transactions_today):
        qty_display = t.get("total_qty", sum(safe_item_fields(it)[3] for it in t.get("items", [])))
        total_display = t.get("total", sum(safe_item_fields(it)[5] for it in t.get("items", [])))
        method_display = t.get("method", "-")
        with st.expander(f"{t.get('code','(tanpa kode)')} - {rupiah(total_display)} [{qty_display} pcs, {method_display}]"):
            col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 1, 2, 3, 1])
            with col1: st.markdown("**Item**")
            with col2: st.markdown("**Ukuran**")
            with col3: st.markdown("**Qty**")
            with col4: st.markdown("**Harga Satuan**")
            with col5: st.markdown("**Subtotal**")
            with col6: st.markdown("")
            for item in t.get("items", []):
                name, w, h, qty, unit_p, subtotal, area_m2 = safe_item_fields(item)
                col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 1, 2, 3, 1])
                with col1: st.write(name)
                with col2: st.write(f"{w:.2f} x {h:.2f} cm")
                with col3: st.write(f"{qty}")
                with col4: st.write(f"{rupiah(unit_p)}")
                with col5: st.write(f"{rupiah(subtotal)}")
                with col6: st.write("")
            
            passcode = st.text_input(
                f"Masukkan Kode Owner untuk Aksi [{t.get('code','no_code')}]",
                type="password",
                key=f"owner_passcode_{i}"
            )
            if passcode:
                if passcode == OWNER_PASSCODE:
                    col_reprint, col_delete = st.columns(2)
                    with col_reprint:
                        if st.button(f"Reprint Struk [{t.get('code','no_code')}]", key=f"reprint_btn_{i}"):
                            pdf = create_receipt_pdf(t)
                            st.download_button(
                                label=f"⬇️ Download Reprint PDF [{t.get('code','no_code')}]",
                                data=pdf,
                                file_name=f"reprint_{t.get('code','no_code')}.pdf",
                                mime="application/pdf"
                            )
                    with col_delete:
                        if st.button(f"🗑️ Hapus Nota [{t.get('code','no_code')}]", key=f"delete_btn_{i}"):
                            if delete_transaction(filename, t.get("code")):
                                st.success(f"Nota {t.get('code')} berhasil dihapus.")
                                st.rerun()
                else:
                    st.error("Kode salah. Tidak bisa melakukan aksi owner.")
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
            qty_display = t.get("total_qty", sum(safe_item_fields(it)[3] for it in t.get("items", [])))
            st.write(f"{t.get('code','(tanpa kode)')}: {rupiah(t.get('total', 0))} ({qty_display} pcs)")
        total_m = sum(t.get('total', 0) for t in txns)
        st.write(f"Total {method}: {rupiah(total_m)}")
        summary_lines.append(f"{method}: {rupiah(total_m)}")
    summary_str = "\n".join(summary_lines)
    st.text_area("Struk Ringkasan", summary_str, height=180)
    pdf = create_summary_pdf("Ringkasan Sesi", summary_lines)
    st.download_button("⬇️ Download Ringkasan PDF", pdf, file_name="summary.pdf", mime="application/pdf")

# --- RIWAYAT SESI HARIAN (Moved to very bottom) ---
st.subheader("📅 Riwayat Sesi Harian")
session_files = list_session_files()
if session_files:
    sesi_label = [f"Sesi {f[:4]}-{f[4:6]}-{f[6:8]}" for f in session_files]
    selected_idx = st.selectbox("Pilih Sesi", range(len(session_files)), format_func=lambda x: sesi_label[x])
    selected_file = session_files[selected_idx]

    st.info(f"Menampilkan transaksi dari sesi: **{sesi_label[selected_idx]}**")
    transactions = load_transactions(selected_file)
    if transactions:
        for i, t in enumerate(transactions):
            qty_display = t.get("total_qty", sum(safe_item_fields(it)[3] for it in t.get("items", [])))
            total_display = t.get("total", sum(safe_item_fields(it)[5] for it in t.get("items", [])))
            method_display = t.get("method", "-")
            with st.expander(f"{t.get('code','(tanpa kode)')} - {rupiah(total_display)} [{qty_display} pcs, {method_display}]"):
                col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 1, 2, 3, 1])
                with col1: st.markdown("**Item**")
                with col2: st.markdown("**Ukuran**")
                with col3: st.markdown("**Qty**")
                with col4: st.markdown("**Harga Satuan**")
                with col5: st.markdown("**Subtotal**")
                with col6: st.markdown("")
                for item in t.get("items", []):
                    name, w, h, qty, unit_p, subtotal, area_m2 = safe_item_fields(item)
                    col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 1, 2, 3, 1])
                    with col1: st.write(name)
                    with col2: st.write(f"{w:.2f} x {h:.2f} cm")
                    with col3: st.write(f"{qty}")
                    with col4: st.write(f"{rupiah(unit_p)}")
                    with col5: st.write(f"{rupiah(subtotal)}")
                    with col6: st.write("")
                # Reprint for session transactions
                passcode = st.text_input(f"Masukkan Kode Owner untuk Reprint [{t.get('code','no_code')}] (Riwayat)", type="password", key=f"riwayat_reprint_passcode_{i}")
                if passcode:
                    if passcode == OWNER_PASSCODE:
                        if st.button(f"Reprint Struk [{t.get('code','no_code')}] (Riwayat)", key=f"riwayat_reprint_btn_{i}"):
                            pdf = create_receipt_pdf(t)
                            st.download_button(
                                label=f"⬇️ Download Reprint PDF [{t.get('code','no_code')}]",
                                data=pdf,
                                file_name=f"reprint_{t.get('code','no_code')}.pdf",
                                mime="application/pdf"
                            )
                    else:
                        st.error("Kode salah. Tidak bisa reprint.")
    else:
        st.info("Tidak ada transaksi pada sesi ini.")
else:
    st.info("Belum ada sesi harian yang tercatat.")
