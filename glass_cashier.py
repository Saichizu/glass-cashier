import streamlit as st
import datetime
import json
from github import Github

# --- CONFIGURATION ---
GITHUB_REPO = "Saichizu/glass-cashier"

# --- ITEMS ---
ITEMS = [
    {"name": "Kaca Polos 5MM", "base_price": 190_000},
    {"name": "Kaca Reben 5MM", "base_price": 200_000},
    {"name": "Kaca Reben 3MM", "base_price": 160_000},
    {"name": "Kaca Polos 3MM", "base_price": 150_000},
    {"name": "Kaca Cermin", "base_price": 240_000},
    {"name": "Kaca Polos Utuh", "base_price": 140_000},
    {"name": "Kaca Reben Utuh", "base_price": 150_000},
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
if "transactions" not in st.session_state:
    st.session_state["transactions"] = []

if "method" not in st.session_state:
    st.session_state["method"] = None

if "owner_mode" not in st.session_state:
    st.session_state["owner_mode"] = False

if "edit_date" not in st.session_state:
    st.session_state["edit_date"] = None

# --- UI ---
st.title("Glass Cashier App")

# Item selection (base price is NOT shown)
item_names = [item["name"] for item in ITEMS]
selected_item = st.selectbox("Pilih Barang", item_names)
item_obj = next(item for item in ITEMS if item["name"] == selected_item)
base_price = item_obj["base_price"]

col1, col2 = st.columns(2)
width_cm = col1.number_input("Lebar (cm)", min_value=0, value=0)
height_cm = col2.number_input("Tinggi (cm)", min_value=0, value=0)

if width_cm > 0 and height_cm > 0:
    area_m2 = (width_cm / 100) * (height_cm / 100)
    price = int(area_m2 * base_price + SERVICE_FEE)
    st.success(f"Total Harga: Rp {price:,}")

    if st.button("Tambah ke Daftar Transaksi"):
        st.session_state["transactions"].append({
            "item": selected_item,
            "width_cm": width_cm,
            "height_cm": height_cm,
            "area_m2": area_m2,
            "price": price,
        })

# Transaction list
if st.session_state["transactions"]:
    st.subheader("Daftar Transaksi Hari Ini")
    st.table([
        {
            "Barang": t["item"],
            "Ukuran": f'{t["width_cm"]} x {t["height_cm"]} cm',
            "Luas (m2)": f'{t["area_m2"]:.2f}',
            "Harga": f'Rp {t["price"]:,}'
        }
        for t in st.session_state["transactions"]
    ])

    total_price = sum(t["price"] for t in st.session_state["transactions"])
    st.markdown(f"**Total Harga: Rp {total_price:,}**")

    method = st.radio("Pilih Metode Pembayaran", ["Cash", "Transfer"], horizontal=True)
    st.session_state["method"] = method

    pay_enabled = method is not None
    pay_btn = st.button("Bayar", disabled=not pay_enabled)
    if pay_btn and method:
        today_str = datetime.datetime.now().strftime("%d%m%y")
        filename = get_today_filename()
        transactions_today = load_transactions(filename)
        receipt_no = len(transactions_today) + 1
        receipt_code = generate_receipt_code(today_str, receipt_no)

        transaction = {
            "code": receipt_code,
            "datetime": datetime.datetime.now().isoformat(),
            "items": st.session_state["transactions"],
            "method": method,
            "total": total_price,
        }
        transactions_today.append(transaction)
        save_transactions(filename, transactions_today)
        st.success(f"Transaksi berhasil disimpan! Kode: {receipt_code}")
        st.session_state["transactions"] = []

# Finish session
if st.button("Selesaikan Sesi"):
    filename = get_today_filename()
    transactions_today = load_transactions(filename)
    by_method = {"Cash": [], "Transfer": []}
    for t in transactions_today:
        by_method[t["method"]].append(t)
    st.subheader("Ringkasan Sesi Hari Ini")
    for method, txns in by_method.items():
        st.write(f"**Transaksi {method}**")
        for t in txns:
            st.write(f"{t['code']}: Rp {t['total']:,}")
        st.write(f"Total {method}: Rp {sum(t['total'] for t in txns):,}")

    # Print-friendly summary for 76mm receipt
    summary_lines = []
    summary_lines.append("---- RINGKASAN SESI ----")
    for method, txns in by_method.items():
        summary_lines.append(f"--- {method} ---")
        for t in txns:
            summary_lines.append(f"{t['code']}: Rp {t['total']:,}")
        summary_lines.append(f"Total {method}: Rp {sum(t['total'] for t in txns):,}")
    summary_str = "\n".join(summary_lines)
    st.text_area("Struk Ringkasan (Print)", summary_str, height=180)

# View other session
st.subheader("Lihat Sesi Lain / Riwayat Transaksi")
date_str = st.date_input("Tanggal Sesi", value=datetime.datetime.now())
filename = date_str.strftime("%Y%m%d") + ".json"
if st.button("Lihat Sesi Tanggal Ini"):
    txns = load_transactions(filename)
    st.session_state["edit_date"] = filename
    st.subheader(f"Transaksi pada {date_str.strftime('%d-%m-%Y')}")
    for t in txns:
        st.write(f"{t['code']} - Rp {t['total']:,} [{t['method']}]")
    # Print session
    if st.button("Print Sesi Tanggal Ini"):
        summary_lines = []
        for t in txns:
            summary_lines.append(f"{t['code']} - Rp {t['total']:,} [{t['method']}]")
        summary_lines.append(f"Total: Rp {sum(t['total'] for t in txns):,}")
        summary_str = "\n".join(summary_lines)
        st.text_area("Struk Riwayat (Print)", summary_str, height=180)

# Owner edit privilege
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

# Refresh button
if st.button("Refresh"):
    st.experimental_rerun()
