import streamlit as st
from datetime import datetime

# Initialize session states
if "keranjang" not in st.session_state:
    st.session_state.keranjang = []

if "transaksi" not in st.session_state:
    st.session_state.transaksi = {}

# Input untuk menambahkan item ke keranjang
st.header("Tambah Item ke Keranjang")
with st.form("form_item"):
    nama_item = st.text_input("Nama Item")
    jumlah = st.number_input("Jumlah", min_value=1, step=1)
    harga = st.number_input("Harga Satuan", min_value=0.0, step=100.0, format="%.2f")
    submitted = st.form_submit_button("Tambahkan")

    if submitted and nama_item and harga > 0:
        st.session_state.keranjang.append({
            "nama": nama_item,
            "jumlah": jumlah,
            "harga": harga,
            "total": jumlah * harga
        })
        st.success(f"{nama_item} ditambahkan ke keranjang!")

# ========================
# KERANJANG (Ongoing Transaction)
# ========================
st.header("🛒 Keranjang (Ongoing Transaction)")
if st.session_state.keranjang:
    total_bayar = sum(item["total"] for item in st.session_state.keranjang)

    for i, item in enumerate(st.session_state.keranjang):
        st.write(f"{item['nama']} - {item['jumlah']} x {item['harga']:.2f} = {item['total']:.2f}")

    st.write(f"**Total: {total_bayar:.2f}**")

    if st.button("💰 Bayar"):
        # Generate kode transaksi
        kode_transaksi = datetime.now().strftime("%Y%m%d%H%M%S")
        st.session_state.transaksi[kode_transaksi] = {
            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "items": st.session_state.keranjang.copy()
        }
        st.success(f"Transaksi {kode_transaksi} berhasil disimpan!")

        # Kosongkan keranjang setelah bayar
        st.session_state.keranjang = []
else:
    st.info("Keranjang kosong, tambahkan item terlebih dahulu.")

# ========================
# DAFTAR TRANSAKSI HARI INI
# ========================
st.header("📜 Daftar Transaksi Hari Ini")
if st.session_state.transaksi:
    for kode, data in st.session_state.transaksi.items():
        with st.expander(f"Transaksi {kode} - {data['waktu']}"):
            for item in data["items"]:
                st.write(f"{item['nama']} - {item['jumlah']} x {item['harga']:.2f} = {item['total']:.2f}")
else:
    st.info("Belum ada transaksi hari ini.")
