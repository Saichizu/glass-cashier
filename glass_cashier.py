import streamlit as st
import datetime
import json
from github import Github

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

# --- SESSION STATE ---
if "keranjang" not in st.session_state:
    st.session_state["keranjang"] = []  # for ongoing items

if "method" not in st.session_state:
    st.session_state["method"] = None

if "owner_mode" not in st.session_state:
    st.session_state["owner_mode"] = False

if "edit_date" not in st.session_state:
    st.session_state["edit_date"] = None

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
        # cek apakah barang dengan ukuran sama sudah ada
        found = False
        for item in st.session_state["keranjang"]:
            if (
                item["item"] == selected_item
                and item["width_cm"] == width_cm
                and item["height_cm"] == height_cm
            ):
                item["qty"] += qty
                item["price"] = item["qty"] * unit_price
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
                "price": unit_price * qty,
            })

# --- Keranjang (ongoing transaction) ---
if st.session_state["keranjang"]:
    st.subheader("🛒 Keranjang")
    st.table([
        {
            "Barang": t["item"],
            "Ukuran": f'{t["width_cm"]} x {t["height_cm"]} cm',
            "Qty": t["qty"],
            "Harga Satuan": f'Rp {t["unit_price"]:,}',
            "Subtotal": f'Rp {t["price"]:,}',
        }
        for t in st.session_state["keranjang"]
    ])

    total_price = sum(t["price"] for t in st.session_state["keranjang"])
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

        transaction = {
            "code": receipt_code,
            "datetime": datetime.datetime.now().isoformat(),
            "items": st.session_state["keranjang"],
            "method": method,
            "total": total_price,
        }
        transactions_today.append(transaction)
        save_transactions(filename, transactions_today)
        st.success(f"Transaksi berhasil disimpan! Kode: {receipt_code}")

        # kosongkan keranjang setelah bayar
        st.session_state["keranjang"] = []

# --- Daftar Transaksi Hari Ini ---
st.subheader("📑 Daftar Transaksi Hari Ini")
filename = get_today_filename()
transactions_today = load_transactions(filename)

if transactions_today:
    for t in transactions_today:
        with st.expander(f"{t['code']} - Rp {t['total']:,} [{t['method']}]"):
            for item in t["items"]:
                # backward compatible display
                if "qty" in item:  
                    st.write(
                        f"- {item['item']} | {item['width_cm']}x{item['height_cm']} cm | "
                        f"{item['area_m2']:.2f} m² | {item['qty']} pcs | "
                        f"Rp {item['unit_price']:,} | Subtotal Rp {item['price']:,}"
                    )
                else:  # old format
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
    for method, txns in by_method.items():
        st.write(f"**Transaksi {method}**")
        for t in txns:
            st.write(f"{t['code']}: Rp {t['total']:,}")
        st.write(f"Total {method}: Rp {sum(t['total'] for t in txns):,}")

    summary_lines = []
    summary_lines.append("---- RINGKASAN SESI ----")
    for method, txns in by_method.items():
        summary_lines.append(f"--- {method} ---")
        for t in txns:
            summary_lines.append(f"{t['code']}: Rp {t['total']:,}")
        summary_lines.append(f"Total {method}: Rp {sum(t['total'] for t in txns):,}")
    summary_str = "\n".join(summary_lines)
    st.text_area("Struk Ringkasan (Print)", summary_str, height=180)

# --- View other session ---
st.subheader("📂 Lihat Sesi Lain / Riwayat Transaksi")
date_str = st.date_input("Tanggal Sesi", value=datetime.datetime.now())
filename = date_str.strftime("%Y%m%d") + ".json"
if st.button("Lihat Sesi Tanggal Ini"):
    txns = load_transactions(filename)
    st.session_state["edit_date"] = filename
    st.subheader(f"Transaksi pada {date_str.strftime('%d-%m-%Y')}")
    for t in txns:
        st.write(f"{t['code']} - Rp {t['total']:,} [{t['method']}]")
    if st.button("Print Sesi Tanggal Ini"):
        summary_lines = []
        for t in txns:
            summary_lines.append(f"{t['code']} - Rp {t['total']:,} [{t['method']}]")
        summary_lines.append(f"Total: Rp {sum(t['total'] for t in txns):,}")
        summary_str = "\n".join(summary_lines)
        st.text_area("Struk Riwayat (Print)", summary_str, height=180)

# --- Owner edit privilege ---
if st.button("Edit (Owner Only)"):
    passcode = st.text_input("Masukkan Kode Owner", type="password")
    if passcode == OWNER_PASSCODE:
        st.session_state["owner_mode"] = True
        st.success("Owner mode aktif.")
    else:
        st.error("Kode salah.")

if st.session_state["owner_mode"]:
    st.subheader("Edit Transaksi")
    edit_filename = st.session_state.get("edit_date") or get_today_filename()
    txns = load_transactions(edit_filename)
    for idx, t in enumerate(txns):
        st.write(f"{t['code']} - Rp {t['total']:,}")
        if st.button(f"Hapus {t['code']}", key=f"del_{t['code']}_{edit_filename}"):
            txns.pop(idx)
            save_transactions(edit_filename, txns)
            st.success(f"Transaksi {t['code']} dihapus.")
            st.experimental_rerun()

# --- Refresh button ---
if st.button("Refresh"):
    st.experimental_rerun()
