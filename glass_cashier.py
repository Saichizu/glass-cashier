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

# --------------------
# Item input section
# --------------------
st.subheader("Tambah Item")

item_names = [item["name"] for item in ITEMS]
selected_item = st.selectbox("Pilih Barang", item_names)
item_obj = next(item for item in ITEMS if item["name"] == selected_item)
base_price = item_obj["base_price"]

col1, col2 = st.columns(2)
width_cm = col1.number_input("Lebar (cm)", min_value=0, value=0, key="width_input")
height_cm = col2.number_input("Tinggi (cm)", min_value=0, value=0, key="height_input")

if st.button("➕ Tambah Item"):
    if width_cm > 0 and height_cm > 0:
        area_m2 = (width_cm / 100) * (height_cm / 100)
        price = int(area_m2 * base_price + SERVICE_FEE)
        st.session_state["transactions"].append({
            "item": selected_item,
            "width_cm": width_cm,
            "height_cm": height_cm,
            "area_m2": area_m2,
            "price": price,
        })
        st.success(f"Item {selected_item} ditambahkan (Rp {price:,})")
    else:
        st.error("Masukkan ukuran yang valid untuk menambahkan item.")

# --------------------
# Transaction list
# --------------------
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

    if st.button("💰 Bayar"):
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
