from datetime import datetime, timedelta
import hashlib
import sqlite3
import os
import csv
from zoneinfo import ZoneInfo
from typing import Any

import jwt

from config import DATABASE_PATH
from src.database.init_database import InitDatabase
from src.utils.logger import get_logger, log_error
from src.utils.security import get_secret_key, get_algorithm

class DatabaseManager:
    """Manager untuk mengelola database dan operasi autentikasi"""

    # Konstanta
    SECRET_KEY = get_secret_key()
    ALGORITHM = get_algorithm()
    TIMEZONE = "Asia/Jakarta"
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 1
    SESSION_DURATION_MINUTES = 60
    KEY_LENGTH = 10
    FALLBACK_USER_ID = 1

    def __init__(self, db_name: str | None = None):
        self.logger = get_logger("DatabaseManager")
        self.db_name = db_name or str(DATABASE_PATH)

        if not os.path.exists(self.db_name):
            InitDatabase()

        try:
            self._ensure_transaction_schema()
        except Exception as e:
            log_error(e, context="saat memastikan skema transaksi", logger=self.logger)

    @staticmethod
    def hash_key(key: str) -> str:
        """Menghasilkan hash SHA-512 dari key"""
        pwd_hash = key
        return hashlib.sha512(pwd_hash.encode()).hexdigest()

    def _ensure_transaction_schema(self):
        """Pastikan tabel transaksi mendukung metadata penjualan modern."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transaksi'")
            if not cursor.fetchone():
                conn.close()
                return

            cursor.execute("PRAGMA table_info(transaksi)")
            columns_info = cursor.fetchall()
            columns = {row[1] for row in columns_info}

            required_columns = {
                "id_kasir": "INTEGER",
                "nama_kasir": "TEXT",
                "nama_customer": "TEXT",
                "subtotal": "INTEGER DEFAULT 0",
                "diskon_nominal": "INTEGER DEFAULT 0",
                "diskon_persen": "REAL DEFAULT 0",
                "pembulatan": "INTEGER DEFAULT 0",
                "metode_bayar": "TEXT",
                "nominal_bayar": "INTEGER DEFAULT 0",
                "nominal_kembali": "INTEGER DEFAULT 0",
                "catatan": "TEXT",
            }

            for column_name, column_type in required_columns.items():
                if column_name not in columns:
                    cursor.execute(
                        f"ALTER TABLE transaksi ADD COLUMN {column_name} {column_type}"
                    )

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer'")
            if cursor.fetchone():
                cursor.execute("SELECT id FROM customer WHERE nama = ?", ("Pelanggan Umum",))
                if not cursor.fetchone():
                    cursor.execute(
                        """
                        INSERT INTO customer (nama, nomer_hp, alamat)
                        VALUES (?, ?, ?)
                        """,
                        ("Pelanggan Umum", "", ""),
                    )

            # Migrasi trigger: ganti trigger lama agar memperhitungkan diskon & pembulatan
            cursor.execute("DROP TRIGGER IF EXISTS handle_transaksi_detail_insert")
            cursor.execute("""
                CREATE TRIGGER handle_transaksi_detail_insert
                AFTER INSERT ON transaksi_detail
                BEGIN
                    UPDATE transaksi_detail
                    SET harga = (
                        CASE 
                            WHEN NEW.jenis_produk = 'satuan' THEN
                                (SELECT harga_jual FROM produk_satuan WHERE id = NEW.id_produk)
                            WHEN NEW.jenis_produk = 'paket' THEN
                                (SELECT harga_jual FROM produk_paket WHERE id = NEW.id_produk)
                        END
                    ) WHERE id = NEW.id;

                    UPDATE transaksi 
                    SET subtotal = (
                        SELECT COALESCE(SUM(sub_total), 0) 
                        FROM transaksi_detail 
                        WHERE id_transaksi = NEW.id_transaksi
                    ),
                    total = (
                        SELECT COALESCE(SUM(sub_total), 0) 
                        FROM transaksi_detail 
                        WHERE id_transaksi = NEW.id_transaksi
                    ) - COALESCE(diskon_nominal, 0) + COALESCE(pembulatan, 0)
                    WHERE id = NEW.id_transaksi;

                    UPDATE produk_satuan SET stok = stok - NEW.jumlah 
                    WHERE id = NEW.id_produk AND NEW.jenis_produk = 'satuan';

                    UPDATE produk_satuan SET stok = stok - (
                        SELECT dp.jumlah * NEW.jumlah
                        FROM detail_paket dp
                        WHERE dp.id_paket = NEW.id_produk 
                        AND dp.id_produk = produk_satuan.id
                    ) 
                    WHERE id IN (
                        SELECT id_produk 
                        FROM detail_paket 
                        WHERE id_paket = NEW.id_produk
                    ) AND NEW.jenis_produk = 'paket';
                END;
            """)

            conn.commit()
        finally:
            conn.close()

    def register_user(self, username, key, role):
        """
        Mendaftarkan user baru ke database

        Args:
            username: Nama pengguna
            key: Kunci akses (harus 10 digit angka)
            role: Role pengguna (admin, Super_user)

        Returns:
            True jika berhasil

        Raises:
            ValueError: Jika validasi gagal atau username/key sudah terdaftar
        """
        if not key.isdigit() or len(key) != self.KEY_LENGTH:
            raise ValueError("Kunci harus Angka dan 10 Digit")

        hash_key = self.hash_key(key)

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                           INSERT INTO users (nama, hash_kunci, role)
                           VALUES (?, ?, ?)
                           ''', (username, hash_key, role))
            conn.commit()
            return True
        except sqlite3.IntegrityError as e:
            log_error(e, context="register_user (Integrity Error)", logger=self.logger)
            raise ValueError("Nama atau Kunci Sudah Terdaftar")
        except Exception as e:
            log_error(e, context="register_user", logger=self.logger)
            raise
        finally:
            conn.close()

    def get_users_for_table(self, role_filter="Semua", search_text="", limit=5, offset=0):
        """Ambil list user untuk ditabelkan."""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT id, nama, role, hash_kunci as password, '' as aksi FROM users WHERE 1=1"
        params = []
        
        if role_filter != "Semua":
            query += " AND role = ?"
            params.append(role_filter)
            
        if search_text:
            query += " AND (nama LIKE ? OR CAST(id AS TEXT) LIKE ?)"
            params.extend([f"%{search_text}%", f"%{search_text}%"])
            
        query += " ORDER BY id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        result = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return result

    def get_users_count(self, role_filter="Semua", search_text=""):
        """Hitung jumlah total baris user berdasarkan filter, untuk keperluan pagination."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        query = "SELECT COUNT(*) FROM users WHERE 1=1"
        params = []
        
        if role_filter != "Semua":
            query += " AND role = ?"
            params.append(role_filter)
            
        if search_text:
            query += " AND (nama LIKE ? OR CAST(id AS TEXT) LIKE ?)"
            params.extend([f"%{search_text}%", f"%{search_text}%"])
            
        cursor.execute(query, params)
        result = cursor.fetchone()[0]
        
        conn.close()
        return result

    def update_user(self, user_id, username, key=None, role=None):
        """Update data user, kunci/password diupdate hanya jika diberikan."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            if key and str(key).strip():
                if not str(key).isdigit() or len(str(key)) != self.KEY_LENGTH:
                    raise ValueError("Kunci harus Angka dan 10 Digit")
                hash_key = self.hash_key(str(key))
                if role:
                    cursor.execute('''
                        UPDATE users SET nama = ?, hash_kunci = ?, role = ? WHERE id = ?
                    ''', (username, hash_key, role, user_id))
                else:
                    cursor.execute('''
                        UPDATE users SET nama = ?, hash_kunci = ? WHERE id = ?
                    ''', (username, hash_key, user_id))
            else:
                if role:
                    cursor.execute('''
                        UPDATE users SET nama = ?, role = ? WHERE id = ?
                    ''', (username, role, user_id))
                else:
                    cursor.execute('''
                        UPDATE users SET nama = ? WHERE id = ?
                    ''', (username, user_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            raise ValueError("Nama atau Kunci Sudah Terdaftar")
        finally:
            conn.close()

    def delete_user(self, user_id):
        """Menghapus user dengan menjaga minimal 1 role Super_user tetap ada."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError("User tidak ditemukan")

            target_role = row[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE role = ?", ("Super_user",))
            super_user_count = cursor.fetchone()[0]

            if super_user_count == 0:
                raise ValueError("Tidak ada Super_user di database. Hapus user dibatalkan.")

            if target_role == "Super_user" and super_user_count <= 1:
                raise ValueError("Tidak dapat menghapus Super_user terakhir!")

            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()

    def verify_login(self, key):
        """
        Memverifikasi login user dengan key

        Args:
            key: Kunci akses user

        Returns:
            Tuple (bool, dict/str): (True, user_data) jika berhasil,
                                    (False, error_message) jika gagal
        """
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        hash_key = self.hash_key(key)

        cursor.execute('''
                       SELECT id, nama, hash_kunci, role, failed_attempts, locked_until
                       FROM users
                       WHERE hash_kunci = ?
                       ''', (hash_key,))

        result = cursor.fetchone()

        if not result:
            conn.close()
            return self._handle_failed_login()

        user_id, username, stored_hash, role, failed_attempts, locked_until = result

        # Cek apakah akun terkunci
        if locked_until:
            is_locked, message = self._check_account_lock(cursor, user_id, locked_until)
            if is_locked:
                conn.close()
                return False, message

        # Verifikasi hash key
        if hash_key == stored_hash:
            self._reset_failed_attempts(cursor, user_id)
            conn.commit()
            conn.close()
            return True, {"user_id": user_id, "username": username, "role": role}
        else:
            conn.close()
            return self._handle_failed_login()

    def _check_account_lock(self, cursor, user_id, locked_until):
        """
        Mengecek apakah akun masih terkunci

        Returns:
            Tuple (bool, str): (True, message) jika masih terkunci,
                              (False, None) jika sudah tidak terkunci
        """
        lock_time = datetime.fromisoformat(locked_until)

        if datetime.now() < lock_time:
            return True, f"Akun Anda Terkunci hingga {lock_time.strftime('%H:%M:%S')}"
        else:
            self._reset_failed_attempts(cursor, user_id)
            return False, None

    @staticmethod
    def _reset_failed_attempts(cursor, user_id):
        """Reset percobaan login yang gagal dan unlock akun"""
        cursor.execute('''
                       UPDATE users
                       SET locked_until    = NULL,
                           failed_attempts = 0
                       WHERE id = ?
                       ''', (user_id,))

    def _handle_failed_login(self):
        """
        Menangani percobaan login yang gagal

        Returns:
            Tuple (bool, str): (False, error_message)
        """
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        user_id = self.FALLBACK_USER_ID

        cursor.execute('''
                       SELECT failed_attempts, locked_until
                       FROM users
                       WHERE id = ?
                       ''', (user_id,))

        result = cursor.fetchone()
        failed_attempts = result[0]
        locked_until = result[1]
        failed_attempts += 1

        # Cek apakah masih terkunci
        if locked_until:
            is_locked, message = self._check_account_lock(cursor, user_id, locked_until)
            if is_locked:
                conn.close()
                return False, message
            else:
                conn.commit()
                failed_attempts = 1

        # Jika sudah mencapai batas maksimal percobaan
        if failed_attempts >= self.MAX_FAILED_ATTEMPTS:
            locked_until = datetime.now() + timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)
            cursor.execute('''
                           UPDATE users
                           SET failed_attempts = ?,
                               locked_until    = ?
                           WHERE id = ?
                           ''', (failed_attempts, locked_until.isoformat(), user_id))
            conn.commit()
            conn.close()
            return False, "Terlalu Banyak Percobaan, Akun Anda Dikunci"
        else:
            cursor.execute('''
                           UPDATE users
                           SET failed_attempts = ?
                           WHERE id = ?
                           ''', (failed_attempts, user_id))
            conn.commit()
            conn.close()
            remaining_attempts = self.MAX_FAILED_ATTEMPTS - failed_attempts
            return False, f"Key Tidak Ditemukan, Sisa Percobaan: {remaining_attempts}"

    def session_login(self, user_id, nama, role):
        """
        Membuat session login dengan JWT token

        Args:
            user_id: ID user
            nama: Nama user
            role: Role user
        """
        current_time = datetime.now(ZoneInfo(self.TIMEZONE))

        payload = {
            'userid': user_id,
            'nama': nama,
            'role': role,
            'iat': current_time.timestamp(),
            'exp': (current_time + timedelta(minutes=self.SESSION_DURATION_MINUTES)).timestamp()
        }

        token_login = jwt.encode(payload, self.SECRET_KEY, algorithm=self.ALGORITHM)

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Hapus session lama
        cursor.execute("DELETE FROM sessions")
        conn.commit()

        # Insert session baru
        cursor.execute("INSERT INTO sessions (token) VALUES (?)", (token_login,))
        conn.commit()
        conn.close()

    def verify_session(self):
        """
        Memverifikasi session yang tersimpan

        Returns:
            Tuple (bool, dict/str): (True, user_data) jika valid,
                                    (False, error_message) jika tidak valid
        """
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute("SELECT token FROM sessions WHERE id = ?", (1,))

        result = cursor.fetchone()
        conn.close()

        if not result:
            return False, "database.py : token tidak ada"

        try:
            token = result[0]

            if not self.ALGORITHM:
                raise RuntimeError("ALGORITHM belum diset di file security")

            decoded_token = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            return True, {
                "user_id": decoded_token['userid'],
                "username": decoded_token['nama'],
                "role": decoded_token['role']
            }
        except jwt.ExpiredSignatureError as e:
            log_error(e, context="verify_session (Expired)", logger=self.logger)
            return False, "token already expired"
        except jwt.InvalidTokenError as e:
            log_error(e, context="verify_session (Invalid)", logger=self.logger)
            return False, "token tidak valid"
        except Exception as e:
            msg = log_error(e, context="verify_session", logger=self.logger)
            return False, msg

    def delete_session(self):
        """Menghapus semua session dari database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM sessions")

        conn.commit()
        conn.close()

    def verify_is_valid(self, jenis, sku, nama, nama_satuan = None):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        if jenis == "satuan":
            cursor.execute("""
                SELECT 1 FROM produk_satuan WHERE nama_barang = ?
            """, (nama,))
            nama_barang = cursor.fetchone()

            cursor.execute("""
                SELECT 1 FROM produk_satuan WHERE sku = ? 
            """, (sku,))
            sku_barang = cursor.fetchone()

            conn.close()

            is_valid = not (nama_barang or sku_barang)
            return {
                "is_valid": is_valid,
                "nama_barang": nama_barang,
                "sku_barang": sku_barang
            }
        else:
            cursor.execute("""
                SELECT 1 FROM produk_paket WHERE sku = ?
            """, (sku,))

            sku_barang = cursor.fetchone()

            cursor.execute("""
                SELECT 1 FROM produk_paket WHERE nama_paket = ?
            """, (nama,))

            nama_barang = cursor.fetchone()

            cursor.execute("""
                SELECT 1 FROM produk_satuan WHERE nama_barang = ?
            """, (nama_satuan,))

            nama_produk = cursor.fetchone()

            is_valid = nama_produk and (not (sku_barang or nama_barang))
            return {
                "is_valid": is_valid,
                "sku_barang": sku_barang,
                "nama_barang": nama_barang,
                "nama_produk": not nama_produk
            }

    def insert_barang_baru_satuan(self, sku, nama, harga_jual, harga_beli, stok, tanggal):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO produk_satuan (sku, nama_barang, harga_jual, stok, tanggal)
            VALUES (?,?,?,?,?)
        """,(sku, nama, harga_jual, stok, tanggal))

        conn.commit()

        cursor.execute("""
            SELECT id FROM produk_satuan WHERE sku = ?
        """, (sku,))

        result = cursor.fetchone()
        id_barang = result[0]

        cursor.execute("""
            INSERT INTO harga_beli (id_satuan, harga)
            VALUES (?,?)
        """, (id_barang, harga_beli))

        conn.commit()
        conn.close()

    def insert_barang_baru_paket(self, nama, harga_jual, nama_barang, sku, coversion):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO produk_paket (sku, nama_paket, harga_jual) VALUES (?,?,?)
        """, (sku, nama, harga_jual))

        conn.commit()

        cursor.execute("""
            SELECT id FROM produk_satuan WHERE nama_barang = ?
        """, (nama_barang,))

        id_barang = cursor.fetchone()
        id_barang_ = id_barang[0]

        cursor.execute("""
            SELECT id FROM produk_paket WHERE sku = ?
        """, (sku,))

        id_paket = cursor.fetchone()
        id_paket_ = id_paket[0]

        cursor.execute("""
            INSERT INTO detail_paket (id_paket, id_produk, jumlah) VALUES (?,?,?)
        """, (id_paket_, id_barang_, coversion))

        conn.commit()
        conn.close()

    def get_produk_satuan(self, limit=1, offset=0):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                ps.sku,
                ps.nama_barang,
                ps.harga_jual,
                ps.stok AS stock,
                ps.tanggal AS tgl_masuk,
                hb.harga AS harga_beli
            FROM produk_satuan ps
            LEFT JOIN harga_beli hb ON ps.id = hb.id_satuan
            ORDER BY nama_barang ASC 
            LIMIT ? OFFSET ?
        """, (limit, offset))

        result = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return result

    def get_produk_paket(self, limit=1, offset=0):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                pp.sku,
                pp.nama_paket AS nama_barang,
                pp.harga_jual,
                dp.jumlah,
                ps.nama_barang AS nama
            FROM produk_paket pp
            LEFT JOIN detail_paket dp ON pp.id = dp.id_paket
            LEFT JOIN produk_satuan ps ON ps.id = dp.id_produk
            ORDER BY nama_barang ASC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        result = [dict(r) for r in cursor.fetchall()]

        for item in result:
            nama = item.get("nama")
            jumlah = item.get("jumlah")
            item["keterangan"] = f"{nama} {jumlah} pcs"

        conn.close()
        return result

    def get_rows_produk(self, index):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        if index == 0:
            cursor.execute("""
                SELECT COUNT(*) FROM produk_satuan
            """)

            result = cursor.fetchone()[0]
            return result
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM produk_paket
            """)

            result = cursor.fetchone()[0]
            return result

    def search_products(self, keyword: str, limit: int, filter_index: int = 0):
        keyword = keyword.strip()
        filter_keyword = f"%{keyword}%" if keyword else "%"

        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query_parts = []
        params = []

        if filter_index in (0, 1):
            query_parts.append(
                """
                SELECT
                    id,
                    sku,
                    nama_barang,
                    harga_jual,
                    stok,
                    'satuan' AS tipe
                FROM produk_satuan
                WHERE sku LIKE ? OR nama_barang LIKE ?
                """
            )
            params.extend([filter_keyword, filter_keyword])

        if filter_index in (0, 2):
            query_parts.append(
                """
                SELECT
                    id,
                    sku,
                    nama_paket AS nama_barang,
                    harga_jual,
                    NULL AS stok,
                    'paket' AS tipe
                FROM produk_paket
                WHERE sku LIKE ? OR nama_paket LIKE ?
                """
            )
            params.extend([filter_keyword, filter_keyword])

        if not query_parts:
            conn.close()
            return []

        final_query = " UNION ALL ".join(query_parts) + " ORDER BY nama_barang ASC, sku ASC LIMIT ?"
        params.append(limit)
        cursor.execute(final_query, params)
        result = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return result

    @staticmethod
    def _get_default_customer_name(customer_name):
        cleaned = (customer_name or "").strip()
        return cleaned or "Pelanggan Umum"

    def _get_or_create_customer_id(self, cursor, customer_name):
        final_name = self._get_default_customer_name(customer_name)
        cursor.execute("SELECT id FROM customer WHERE nama = ?", (final_name,))
        row = cursor.fetchone()
        if row:
            return row[0], final_name

        cursor.execute(
            """
            INSERT INTO customer (nama, nomer_hp, alamat)
            VALUES (?, ?, ?)
            """,
            (final_name, "", ""),
        )
        return cursor.lastrowid, final_name

    @staticmethod
    def _normalize_product_type(product_type):
        return "satuan" if str(product_type).strip().lower() == "satuan" else "paket"

    def _calculate_total_hpp(self, cursor, cart_items):
        total_hpp = 0

        for item in cart_items:
            product_id = item.get("product_id")
            qty = int(item.get("qty") or 0)
            product_type = self._normalize_product_type(item.get("tipe"))

            if not product_id or qty <= 0:
                continue

            if product_type == "satuan":
                cursor.execute(
                    "SELECT COALESCE(harga, 0) FROM harga_beli WHERE id_satuan = ?",
                    (product_id,),
                )
                row = cursor.fetchone()
                hpp = int(row[0] or 0) if row else 0
            else:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(dp.jumlah * COALESCE(hb.harga, 0)), 0)
                    FROM detail_paket dp
                    LEFT JOIN harga_beli hb ON hb.id_satuan = dp.id_produk
                    WHERE dp.id_paket = ?
                    """,
                    (product_id,),
                )
                row = cursor.fetchone()
                hpp = int(row[0] or 0) if row else 0

            total_hpp += hpp * qty

        return total_hpp

    @staticmethod
    def _generate_invoice_number(cursor, customer_id):
        """Generate nomor invoice unik: {id_customer}{YYMMDD}{urutan_hari}.
        
        Contoh: 12603241 = customer 1, tanggal 26/03/24, transaksi ke-1 hari itu.
        """
        now = datetime.now()
        date_part = now.strftime("%y%m%d")  # e.g. "260324"
        today_str = now.strftime("%Y-%m-%d")

        cursor.execute(
            "SELECT COUNT(*) FROM transaksi WHERE date(tanggal) = date(?)",
            (today_str,),
        )
        count_today = cursor.fetchone()[0]
        sequence = count_today + 1

        return f"{customer_id}{date_part}{sequence}"

    def create_sale_transaction(self, cart_items, sale_data, user_data=None):
        """Simpan penjualan dengan validasi dan update stok yang benar."""
    
        if not cart_items:
            return {"success": False, "message": "Keranjang masih kosong."}
    
        user_data = user_data or {}
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
    
        try:
            # 1. VALIDASI STOK TERLEBIH DAHULU
            for item in cart_items:
                product_id = item.get("product_id")
                qty = int(item.get("qty") or 0)
                product_type = self._normalize_product_type(item.get("tipe"))
            
                if not product_id or qty <= 0:
                    continue
            
                # Validasi produk ada
                table = "produk_satuan" if product_type == "satuan" else "produk_paket"
                cursor.execute(f"SELECT id FROM {table} WHERE id = ?", (product_id,))
                if not cursor.fetchone():
                    raise ValueError(
                        f"Produk '{item.get('nama_barang', '-')}' tidak ditemukan"
                    )
            
                # Validasi stok (hanya untuk satuan)
                if product_type == "satuan":
                    cursor.execute(
                        "SELECT stok FROM produk_satuan WHERE id = ?",
                        (product_id,)
                    )
                    row = cursor.fetchone()
                    if not row or row[0] < qty:
                        raise ValueError(
                            f"Stok '{item['nama_barang']}' tidak cukup. "
                            f"Butuh: {qty}, Ada: {row[0] if row else 0}"
                        )
        
            # 2. GET OR CREATE CUSTOMER
            customer_id, customer_name = self._get_or_create_customer_id(
                cursor, sale_data.get("customer_name")
            )
        
            # 3. GENERATE INVOICE NUMBER
            invoice_number = self._generate_invoice_number(cursor, customer_id)

            # 4. INSERT TRANSAKSI
            cursor.execute(
                """
                INSERT INTO transaksi (
                    id, id_customer, id_kasir,
                    subtotal, diskon_nominal, diskon_persen, pembulatan,
                    total, metode_bayar, nominal_bayar, nominal_kembali, catatan
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_number,
                    customer_id,
                    user_data.get("user_id"),
                    int(sale_data.get("subtotal") or 0),
                    int(sale_data.get("discount_nominal") or 0),
                    float(sale_data.get("discount_percent") or 0),
                    int(sale_data.get("rounding") or 0),
                    int(sale_data.get("total") or 0),
                    sale_data.get("payment_method"),
                    int(sale_data.get("amount_paid") or 0),
                    int(sale_data.get("change_amount") or 0),
                    (sale_data.get("notes") or "").strip(),
                ),
            )
        
            transaction_id = invoice_number
        
            # 5. INSERT DETAIL
            for item in cart_items:
                product_id = item.get("product_id")
                qty = int(item.get("qty") or 0)
                product_type = self._normalize_product_type(item.get("tipe"))
            
                if not product_id or qty <= 0:
                    continue
            
                # INSERT detail (trigger database akan otomatis mengupdate stok produk satuan / paket)
                cursor.execute(
                    """
                    INSERT INTO transaksi_detail (
                        id_transaksi, jenis_produk, id_produk, jumlah, harga
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        transaction_id,
                        product_type,
                        product_id,
                        qty,
                        int(item.get("harga_jual") or 0),
                    ),
                )
        
            # 6. HITUNG & INSERT LABA (hapus dulu jika trigger lama sempat insert)
            cursor.execute("DELETE FROM laba_transaksi WHERE id_transaksi = ?", (transaction_id,))
            total_hpp = self._calculate_total_hpp(cursor, cart_items)
            cursor.execute(
                """
                SELECT total, diskon_nominal, diskon_persen, pembulatan
                FROM transaksi
                WHERE id = ?
                """,
                (transaction_id,),
            )
            transaction_totals = cursor.fetchone() or (0, 0, 0, 0)
            total, diskon_nominal, diskon_persen, pembulatan = transaction_totals
            laba_kotor = (
                total
                - total_hpp
                - (diskon_nominal or 0)
                - (diskon_persen or 0)
                + (pembulatan or 0)
            )
            pajak = int(laba_kotor * 0.2) if laba_kotor > 0 else 0
            laba_bersih = laba_kotor - pajak
        
            cursor.execute(
                """
                INSERT INTO laba_transaksi (
                    id_transaksi, tanggal, pendapatan_kotor,
                    total_hpp, laba_kotor, pajak_20_persen, laba_bersih
                )
                SELECT id, tanggal, total, ?, ?, ?, ?
                FROM transaksi WHERE id = ?
                """,
                (total_hpp, laba_kotor, pajak, laba_bersih, transaction_id),
            )
        
            # 7. COMMIT
            conn.commit()
        
            return {
                "success": True,
                "transaction_id": transaction_id,
                "customer_name": customer_name,
                "message": "Transaksi berhasil disimpan.",
            }
        
        except (sqlite3.Error, ValueError) as error:
            conn.rollback()
            msg = log_error(error, context="create_sale_transaction", logger=self.logger)
            return {"success": False, "message": msg}
        except Exception as e:
            conn.rollback()
            msg = log_error(e, context="create_sale_transaction (Uncaught)", logger=self.logger)
            return {"success": False, "message": msg}
        finally:
            conn.close()

    def get_search_produk(self, index, keyword, limit=1, offset=0, lock=False):
        keyword = f"%{keyword}%"
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if index == 0:

            if lock:
                where = "WHERE ps.sku LIKE ?"
                params = [keyword, limit, offset]
            else:
                where = "WHERE ps.sku LIKE ? OR ps.nama_barang LIKE ?"
                params = [keyword, keyword, limit, offset]

            cursor.execute(f"""
                SELECT 
                    ps.sku,
                    ps.nama_barang,
                    ps.harga_jual,
                    ps.stok AS stock,
                    ps.tanggal AS tgl_masuk,
                    hb.harga AS harga_beli
                FROM produk_satuan ps
                LEFT JOIN harga_beli hb ON ps.id = hb.id_satuan
                {where}
                ORDER BY nama_barang ASC 
                LIMIT ? OFFSET ?
            """, params)

        else:

            if lock:
                where = "WHERE pp.sku LIKE ?"
                params = [keyword, limit, offset]
            else:
                where = "WHERE pp.sku LIKE ? OR pp.nama_paket LIKE ?"
                params = [keyword, keyword, limit, offset]

            cursor.execute(f"""
                SELECT
                    pp.sku,
                    pp.nama_paket AS nama_barang,
                    pp.harga_jual,
                    dp.jumlah,
                    ps.nama_barang AS nama
                FROM produk_paket pp
                LEFT JOIN detail_paket dp ON pp.id = dp.id_paket
                LEFT JOIN produk_satuan ps ON ps.id = dp.id_produk
                {where}
                ORDER BY nama_barang ASC
                LIMIT ? OFFSET ?
            """, params)

        result = [dict(r) for r in cursor.fetchall()]

        conn.close()
        return result

    def get_search_row(self, index, keyword):
        keyword = f"%{keyword}%"
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        if index == 0:
            cursor.execute("""
                SELECT COUNT(*) FROM produk_satuan
                WHERE sku LIKE ? OR nama_barang LIKE ?
            """, (keyword, keyword))

            result = cursor.fetchone()[0]

            conn.close()
            return result
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM produk_paket
                WHERE sku LIKE ? OR nama_paket LIKE ?
            """, (keyword, keyword))

            result = cursor.fetchone()[0]

            conn.close()
            return result

    def get_produk_for_delete(self, jenis, sku):
        """Ambil detail produk berdasarkan jenis dan SKU untuk proses hapus."""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if jenis == "satuan":
            cursor.execute("""
                SELECT
                    ps.id,
                    ps.sku,
                    ps.nama_barang,
                    ps.stok,
                    ps.harga_jual,
                    hb.harga AS harga_beli
                FROM produk_satuan ps
                LEFT JOIN harga_beli hb ON hb.id_satuan = ps.id
                WHERE ps.sku = ?
            """, (sku,))
        else:
            cursor.execute("""
                SELECT
                    pp.id,
                    pp.sku,
                    pp.nama_paket AS nama_barang,
                    pp.harga_jual,
                    dp.jumlah,
                    ps.nama_barang AS nama_satuan
                FROM produk_paket pp
                LEFT JOIN detail_paket dp ON pp.id = dp.id_paket
                LEFT JOIN produk_satuan ps ON ps.id = dp.id_produk
                WHERE pp.sku = ?
            """, (sku,))

        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if not rows:
            return None

        if jenis == "satuan":
            return rows[0]

        item = rows[0]
        nama_satuan = item.get("nama_satuan")
        jumlah = item.get("jumlah")
        item["keterangan"] = f"{nama_satuan} {jumlah} pcs" if nama_satuan and jumlah else "-"
        return item

    def update_produk(self, jenis, sku_lama, data_baru):
        """Update produk satuan/paket berdasarkan SKU lama dengan validasi unik."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        result = {
            "updated": False,
            "error": "",
        }

        try:
            if jenis == "satuan":
                cursor.execute("SELECT id FROM produk_satuan WHERE sku = ?", (sku_lama,))
                row = cursor.fetchone()
                if not row:
                    result["error"] = "Produk tidak ditemukan"
                    conn.rollback()
                    return result

                id_satuan = row[0]

                cursor.execute(
                    "SELECT 1 FROM produk_satuan WHERE nama_barang = ? AND id != ?",
                    (data_baru["nama_barang"], id_satuan),
                )
                if cursor.fetchone():
                    result["error"] = "Nama produk sudah digunakan"
                    conn.rollback()
                    return result

                cursor.execute(
                    "SELECT 1 FROM produk_satuan WHERE sku = ? AND id != ?",
                    (data_baru["sku"], id_satuan),
                )
                if cursor.fetchone():
                    result["error"] = "SKU sudah digunakan"
                    conn.rollback()
                    return result

                cursor.execute(
                    """
                    UPDATE produk_satuan
                    SET sku         = ?,
                        nama_barang = ?,
                        harga_jual  = ?,
                        stok        = ?
                    WHERE id = ?
                    """,
                    (
                        data_baru["sku"],
                        data_baru["nama_barang"],
                        data_baru["harga_jual"],
                        data_baru["stok"],
                        id_satuan,
                    ),
                )

                cursor.execute(
                    "UPDATE harga_beli SET harga = ? WHERE id_satuan = ?",
                    (data_baru["harga_beli"], id_satuan),
                )

                if cursor.rowcount == 0:
                    cursor.execute(
                        "INSERT INTO harga_beli (id_satuan, harga) VALUES (?, ?)",
                        (id_satuan, data_baru["harga_beli"]),
                    )
            else:
                cursor.execute("SELECT id FROM produk_paket WHERE sku = ?", (sku_lama,))
                row = cursor.fetchone()
                if not row:
                    result["error"] = "Produk tidak ditemukan"
                    conn.rollback()
                    return result

                id_paket = row[0]

                cursor.execute(
                    "SELECT 1 FROM produk_paket WHERE nama_paket = ? AND id != ?",
                    (data_baru["nama_barang"], id_paket),
                )
                if cursor.fetchone():
                    result["error"] = "Nama paket sudah digunakan"
                    conn.rollback()
                    return result

                cursor.execute(
                    "SELECT 1 FROM produk_paket WHERE sku = ? AND id != ?",
                    (data_baru["sku"], id_paket),
                )
                if cursor.fetchone():
                    result["error"] = "SKU sudah digunakan"
                    conn.rollback()
                    return result

                cursor.execute(
                    "SELECT id FROM produk_satuan WHERE nama_barang = ?",
                    (data_baru["nama_satuan"],),
                )
                row_satuan = cursor.fetchone()
                if not row_satuan:
                    result["error"] = "Nama satuan tidak ditemukan"
                    conn.rollback()
                    return result

                cursor.execute(
                    """
                    UPDATE produk_paket
                    SET sku        = ?,
                        nama_paket = ?,
                        harga_jual = ?
                    WHERE id = ?
                    """,
                    (
                        data_baru["sku"],
                        data_baru["nama_barang"],
                        data_baru["harga_jual"],
                        id_paket,
                    ),
                )

                cursor.execute(
                    "DELETE FROM detail_paket WHERE id_paket = ?",
                    (id_paket,),
                )
                cursor.execute(
                    "INSERT INTO detail_paket (id_paket, id_produk, jumlah) VALUES (?,?,?)",
                    (id_paket, row_satuan[0], data_baru["jumlah"]),
                )

            conn.commit()
            result["updated"] = True
            return result
        except sqlite3.Error as error:
            conn.rollback()
            msg = log_error(error, context="update_produk", logger=self.logger)
            result["error"] = msg
            return result
        except Exception as e:
            conn.rollback()
            msg = log_error(e, context="update_produk (Uncaught)", logger=self.logger)
            result["error"] = msg
            return result
        finally:
            conn.close()

    def delete_produk_bersih(self, jenis, sku):
        """
        Hapus produk satuan/paket tanpa mengubah data histori transaksi.

        Catatan:
        - Histori transaksi, laba rugi, dan tabel sejarah lain tidak disentuh.
        - Untuk produk satuan, paket yang berisi produk tersebut ikut dihapus.

        Returns:
            dict: ringkasan hasil penghapusan.
        """
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        result = {
            "deleted": False,
            "deleted_produk_paket": 0,
            "deleted_produk_satuan": 0,
            "history_untouched": True,
        }

        try:
            if jenis == "satuan":
                cursor.execute("SELECT id FROM produk_satuan WHERE sku = ?", (sku,))
                row = cursor.fetchone()
                if not row:
                    conn.rollback()
                    return result

                id_satuan = row[0]

                cursor.execute("SELECT id_paket FROM detail_paket WHERE id_produk = ?", (id_satuan,))
                paket_ids = [r[0] for r in cursor.fetchall()]

                if paket_ids:
                    placeholders = ",".join("?" for _ in paket_ids)

                    cursor.execute(f"DELETE FROM detail_paket WHERE id_paket IN ({placeholders})", paket_ids)

                    cursor.execute(f"DELETE FROM produk_paket WHERE id IN ({placeholders})", paket_ids)
                    result["deleted_produk_paket"] = cursor.rowcount

                cursor.execute("DELETE FROM detail_paket WHERE id_produk = ?", (id_satuan,))
                cursor.execute("DELETE FROM harga_beli WHERE id_satuan = ?", (id_satuan,))

                cursor.execute("DELETE FROM produk_satuan WHERE id = ?", (id_satuan,))
                result["deleted_produk_satuan"] = cursor.rowcount
                result["deleted"] = cursor.rowcount > 0
            else:
                cursor.execute("SELECT id FROM produk_paket WHERE sku = ?", (sku,))
                row = cursor.fetchone()
                if not row:
                    conn.rollback()
                    return result

                id_paket = row[0]

                cursor.execute("DELETE FROM detail_paket WHERE id_paket = ?", (id_paket,))

                cursor.execute("DELETE FROM produk_paket WHERE id = ?", (id_paket,))
                result["deleted_produk_paket"] = cursor.rowcount
                result["deleted"] = cursor.rowcount > 0

            conn.commit()
            return result
        except sqlite3.Error as error:
            conn.rollback()
            log_error(error, context="delete_produk_bersih", logger=self.logger)
            raise
        except Exception as e:
            conn.rollback()
            log_error(e, context="delete_produk_bersih (Uncaught)", logger=self.logger)
            raise
        finally:
            conn.close()

    def get_transaction_history(self, filters: dict, limit: int = 9, offset: int = 0):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT 
                t.id, t.id_customer, t.id_kasir, t.subtotal, 
                t.diskon_nominal, t.diskon_persen, t.pembulatan, 
                t.total, t.metode_bayar, t.nominal_bayar, 
                t.nominal_kembali, t.catatan, t.tanggal,
                u.nama as nama_kasir, c.nama as nama_customer
            FROM transaksi t
            LEFT JOIN users u ON t.id_kasir = u.id
            LEFT JOIN customer c ON t.id_customer = c.id
            WHERE 1=1
        """
        filter_clauses, params = self._build_transaction_filter_clauses(filters)
        query += filter_clauses

        query += " ORDER BY t.tanggal DESC, t.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        result = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return result

    def get_transaction_detail_with_items(self, transaction_id):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Header
        cursor.execute("""
            SELECT 
                t.id, t.id_customer, t.id_kasir, t.subtotal, 
                t.diskon_nominal, t.diskon_persen, t.pembulatan, 
                t.total, t.metode_bayar, t.nominal_bayar, 
                t.nominal_kembali, t.catatan, t.tanggal,
                u.nama as nama_kasir, c.nama as nama_customer
            FROM transaksi t
            LEFT JOIN users u ON t.id_kasir = u.id
            LEFT JOIN customer c ON t.id_customer = c.id
            WHERE t.id = ?
        """, (transaction_id,))
        header_row = cursor.fetchone()
        if not header_row:
            conn.close()
            return None
        
        header = dict(header_row)

        # Laba
        cursor.execute("SELECT * FROM laba_transaksi WHERE id_transaksi = ?", (transaction_id,))
        laba_row = cursor.fetchone()
        if laba_row:
            header["laba"] = dict(laba_row)
        else:
            header["laba"] = None

        # Items
        cursor.execute("SELECT * FROM transaksi_detail WHERE id_transaksi = ?", (transaction_id,))
        items = [dict(row) for row in cursor.fetchall()]
        
        for item in items:
            jenis = item.get("jenis_produk")
            id_produk = item.get("id_produk")
            if jenis == "satuan":
                cursor.execute("SELECT nama_barang FROM produk_satuan WHERE id = ?", (id_produk,))
            else:
                cursor.execute("SELECT nama_paket as nama_barang FROM produk_paket WHERE id = ?", (id_produk,))
            prod_row = cursor.fetchone()
            if prod_row:
                item["nama_barang"] = prod_row["nama_barang"]
            else:
                item["nama_barang"] = f"Unknown ({id_produk})"

        conn.close()
        
        return {
            "header": header,
            "items": items
        }

    def get_transaction_statistics(self, filters: dict):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT COUNT(t.id) as total_count, COALESCE(SUM(t.total), 0) as total_revenue, COALESCE(AVG(t.total), 0) as avg_transaction 
            FROM transaksi t 
            LEFT JOIN customer c ON t.id_customer = c.id
            WHERE 1=1
        """
        filter_clauses, params = self._build_transaction_filter_clauses(filters)
        query += filter_clauses

        cursor.execute(query, params)
        stats = dict(cursor.fetchone())

        query_top = """
            SELECT u.nama as nama_kasir, COUNT(t.id) as tx_count 
            FROM transaksi t 
            LEFT JOIN users u ON t.id_kasir = u.id
            LEFT JOIN customer c ON t.id_customer = c.id
            WHERE 1=1
        """
        
        query_top += filter_clauses
        query_top += " GROUP BY u.nama ORDER BY tx_count DESC LIMIT 1"
        cursor.execute(query_top, params)
        top_cashier_row = cursor.fetchone()
        
        if top_cashier_row:
            stats["top_cashier"] = top_cashier_row["nama_kasir"]
            stats["top_cashier_count"] = top_cashier_row["tx_count"]
        else:
            stats["top_cashier"] = "-"
            stats["top_cashier_count"] = 0

        conn.close()
        return stats

    @staticmethod
    def _build_transaction_filter_clauses(filters: dict):
        """Build SQL WHERE clause additions and bound parameters for transaction filters.

        Args:
            filters: dict with optional keys: date_from, date_to, kasir_id,
                     payment_method, amount_min, amount_max, search_keyword.

        Returns:
            Tuple of (clauses, params) where clauses is a string of
            SQL AND conditions to append to a WHERE clause and params is the
            corresponding list of bound parameter values.
        """
        clauses = ""
        params = []

        if filters.get("date_from"):
            clauses += " AND date(t.tanggal) >= date(?)"
            params.append(filters["date_from"])

        if filters.get("date_to"):
            clauses += " AND date(t.tanggal) <= date(?)"
            params.append(filters["date_to"])

        if filters.get("kasir_id") not in ("", None, "Semua"):
            clauses += " AND t.id_kasir = ?"
            params.append(filters["kasir_id"])

        if filters.get("payment_method") not in ("", None, "Semua"):
            clauses += " AND t.metode_bayar = ?"
            params.append(filters["payment_method"])

        if filters.get("amount_min"):
            clauses += " AND t.total >= ?"
            params.append(filters["amount_min"])

        if filters.get("amount_max"):
            clauses += " AND t.total <= ?"
            params.append(filters["amount_max"])

        if filters.get("search_keyword"):
            kw = f"%{filters['search_keyword']}%"
            clauses += " AND (c.nama LIKE ? OR t.id LIKE ?)"
            params.extend([kw, kw])

        return clauses, params

    def import_batch_csv(self, filepath):
        hasil: dict[str, Any] = {"berhasil": 0, "gagal": 0, "errors": []}
        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                if not reader.fieldnames:
                    hasil["error_format"] = "File CSV kosong atau tidak valid."
                    return hasil
                
                headers = [h.strip().lower() for h in reader.fieldnames]
                reader.fieldnames = headers
                
                required = ['jenis', 'sku', 'nama', 'harga_jual', 'harga_beli', 'stok', 'konversi', 'nama_barang_satuan']
                if not all(r in headers for r in required):
                    hasil["error_format"] = "Format header CSV tidak sesuai! Pastikan ada kolom: jenis, sku, nama, harga_jual, harga_beli, stok, konversi, nama_barang_satuan."
                    return hasil
                
                for r_idx, row in enumerate(reader, start=2):
                    jenis = row.get('jenis', '').strip().lower()
                    sku = row.get('sku', '').strip()
                    nama = row.get('nama', '').strip()
                    
                    try:
                        harga_jual = int(float(row.get('harga_jual') or 0))
                        harga_beli = int(float(row.get('harga_beli') or 0))
                        stok = int(float(row.get('stok') or 0))
                        konversi = int(float(row.get('konversi') or 0))
                    except ValueError:
                        hasil["gagal"] += 1
                        hasil["errors"].append(f"Baris {r_idx}: Format angka salah pada SKU '{sku}'.")
                        continue
                        
                    nama_satuan = row.get('nama_barang_satuan', '').strip()
                    
                    if jenis == 'satuan':
                        valid = self.verify_is_valid('satuan', sku, nama)
                        if valid['is_valid']:
                            tanggal = datetime.now().isoformat()
                            self.insert_barang_baru_satuan(sku, nama, harga_jual, harga_beli, stok, tanggal)
                            hasil["berhasil"] += 1
                        else:
                            hasil["gagal"] += 1
                            hasil["errors"].append(f"Baris {r_idx}: Satuan SKU '{sku}' atau Nama '{nama}' sudah ada.")
                    elif jenis == 'paket':
                        valid = self.verify_is_valid('paket', sku, nama, nama_satuan)
                        if valid['is_valid']:
                            self.insert_barang_baru_paket(nama, harga_jual, nama_satuan, sku, konversi)
                            hasil["berhasil"] += 1
                        else:
                            hasil["gagal"] += 1
                            hasil["errors"].append(f"Baris {r_idx}: Paket SKU '{sku}'/'{nama}' gagal validasi atau Satuan '{nama_satuan}' tidak ada.")
                    else:
                        hasil["gagal"] += 1
                        hasil["errors"].append(f"Baris {r_idx}: Jenis '{jenis}' tidak dimengerti.")
                        
        except Exception as e:
            msg = log_error(e, context="import_batch_csv", logger=self.logger)
            hasil["error_format"] = f"Error membaca file CSV: {msg}"
            
        return hasil

    def get_all_customer_names(self) -> list[str]:
        """Ambil semua nama customer untuk keperluan auto-suggestion."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT nama FROM customer ORDER BY nama ASC")
        result = [row[0] for row in cursor.fetchall()]
        conn.close()
        return result

    def get_customers(self, limit=10, offset=0):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                c.id, c.nama, c.nomer_hp, c.alamat,
                COUNT(t.id) as total_transaksi
            FROM customer c
            LEFT JOIN transaksi t ON c.id = t.id_customer
            GROUP BY c.id
            ORDER BY c.nama ASC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        result = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return result

    def search_customers(self, keyword, limit=10, offset=0):
        kw = f"%{keyword}%"
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                c.id, c.nama, c.nomer_hp, c.alamat,
                COUNT(t.id) as total_transaksi
            FROM customer c
            LEFT JOIN transaksi t ON c.id = t.id_customer
            WHERE c.nama LIKE ? OR c.nomer_hp LIKE ?
            GROUP BY c.id
            ORDER BY c.nama ASC
            LIMIT ? OFFSET ?
        """, (kw, kw, limit, offset))
        
        result = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return result

    def get_customers_count(self, keyword=""):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        if keyword:
            kw = f"%{keyword}%"
            cursor.execute("SELECT COUNT(*) FROM customer WHERE nama LIKE ? OR nomer_hp LIKE ?", (kw, kw))
        else:
            cursor.execute("SELECT COUNT(*) FROM customer")
        result = cursor.fetchone()[0]
        conn.close()
        return result

    def insert_customer(self, nama, nomer_hp, alamat):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO customer (nama, nomer_hp, alamat)
                VALUES (?, ?, ?)
            """, (nama, nomer_hp, alamat))
            conn.commit()
            return {"success": True}
        except Exception as e:
            conn.rollback()
            msg = log_error(e, context="insert_customer", logger=self.logger)
            return {"success": False, "message": msg}
        finally:
            conn.close()

    def update_customer(self, id_customer, nama, nomer_hp, alamat):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE customer 
                SET nama = ?, nomer_hp = ?, alamat = ?
                WHERE id = ?
            """, (nama, nomer_hp, alamat, id_customer))
            conn.commit()
            return {"success": True}
        except Exception as e:
            conn.rollback()
            msg = log_error(e, context="update_customer", logger=self.logger)
            return {"success": False, "message": msg}
        finally:
            conn.close()

    def delete_customer(self, id_customer):
        if id_customer == 1:
            return {"success": False, "message": "Pelanggan Umum tidak bisa dihapus."}
            
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT nama FROM customer WHERE id = ?", (id_customer,))
            row = cursor.fetchone()
            if row and row[0] == "Pelanggan Umum":
                return {"success": False, "message": "Pelanggan Umum tidak bisa dihapus."}

            cursor.execute("DELETE FROM customer WHERE id = ?", (id_customer,))
            conn.commit()
            return {"success": True}
        except Exception as e:
            conn.rollback()
            msg = log_error(e, context="delete_customer", logger=self.logger)
            return {"success": False, "message": msg}
        finally:
            conn.close()
