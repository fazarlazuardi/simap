# 🏛️ SIMAP BAZNAS KABUPATEN TANGERANG
### Sistem Informasi Manajemen & Arsip Pelayanan Terpadu

![Django](https://img.shields.io/badge/Django-4.2-092E20?style=for-the-badge&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-Baileys_WA-339933?style=for-the-badge&logo=node.js&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-Database-4479A1?style=for-the-badge&logo=mysql&logoColor=white)
![Cloudflare](https://img.shields.io/badge/Cloudflare_Tunnel-Secured-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)

---

## 📌 Tentang SIMAP BAZNAS

**SIMAP (Sistem Informasi Manajemen & Arsip Pelayanan)** adalah platform web *enterprise-grade* yang dirancang khusus untuk mendukung digitalisasi tata kelola administrasi, kearsipan, disposisi pimpinan, perjalanan dinas, serta komunikasi internal di **BAZNAS Kabupaten Tangerang**.

Sistem ini mengintegrasikan seluruh alur kerja operasional lembaga — mulai dari pencatatan surat masuk oleh *Front Office*, disposisi bertingkat pimpinan (Ketua & Wakil Ketua I–IV), penerbitan Surat Tugas dan SPPD, risalah notulensi rapat internal, hingga pengiriman notifikasi otomatis WhatsApp secara *real-time* kepada amil/pegawai.

---

## 🚀 Fitur Utama & Modul Sistem

### 📥 1. Manajemen Arsip & Surat (Bidang Front Office)
* **Pencatatan Berkas Terpadu**: Registrasi surat masuk, surat keluar, proposal permohonan bantuan, dan dokumen administrasi resmi.
* **Penomoran Otomatis Logis (`NumberingService`)**: Penomoran kode arsip dan dokumen teratur sesuai format resmi BAZNAS.
* **Sinkronisasi Google Drive**: Pengunggahan berkas digital otomatis ke penyimpanan awan Google Drive BAZNAS.
* **Tracking Status Berkas**: Pemantauan status alur arsip (*Diterima FO ➔ Disposisi Pimpinan ➔ Dalam Survei ➔ Telah Disalurkan ➔ Selesai*).

### 📋 2. Disposisi Pimpinan Bertingkat (Stage 1 & Stage 2)
* **Disposisi Ketua & Wakil Ketua (Waka I - IV)**: Alur disposisi 2 tingkat dari Ketua/Waka ke Kepala Bidang, Pelaksana, maupun Tim Lapangan.
* **Sinkronisasi Dua Arah (Bi-Directional Sync)**: Pembaruan status disposisi secara otomatis mengubah status arsip dan laporan terkait.
* **Penyebaran Instruksi Massal**: Distribusi instruksi disposisi sekaligus ke banyak pegawai dengan 1-click trigger notifikasi WA.

### 📄 3. Surat Tugas Amil & Pegawai
* **Penerbitan Surat Tugas Resmi**: Pembuatan dokumen Surat Tugas lengkap dengan perihal, tanggal kegiatan, lokasi tujuan, dan penandatangan resmi.
* **Pemicu SPPD Otomatis**: Integrasi instan yang memberi pemberitahuan ke Front Office & Bidang IV untuk menerbitkan SPPD begitu Surat Tugas disahkan.

### 🚗 4. SPPD (Surat Perintah Perjalanan Dinas)
* **Pengajuan & Persetujuan SPPD**: Manajemen rincian perjalanan dinas, uang harian, moda transportasi, dan pegawai yang ditugaskan.
* **Sinkronisasi Kalender Kerja**: SPPD yang disetujui otomatis tercatat pada Kalender Kerja Amil BAZNAS.

### 📝 5. Risalah Notulensi Rapat Internal
* **Manajemen Undangan Rapat**: Pembuatan undangan kegiatan rapat internal lengkap dengan pimpinan rapat dan daftar peserta.
* **Pencatatan Kesimpulan & Keputusan**: Dokumentasi notulensi rapat dan poin keputusan resmi.
* **Otomatisasi ke Agenda Kerja**: Penjadwalan rapat otomatis masuk ke modul Agenda Kerja amil.

### 📅 6. Agenda Kerja Amil & Pengingat
* **Kalender Kegiatan Terpadu**: Manajemen agenda kegiatan harian, mingguan, dan bulanan amil.
* **Pengingat Jadwal**: Pengiriman notifikasi pengingat agenda ke akun pegawai terkait.

### 📲 7. WA Gateway Service & Matriks Kontrol Notifikasi
* **Microservice WA Gateway Node.js (`wa-gateway`)**: Service mandiri berbasis `@whiskeysockets/baileys` yang berfungsi layaknya WhatsApp Web lokal di port `3000`.
* **Indikator Real-Time HUD Status**: Panel pemantau status koneksi WA Gateway yang futuristik (*LIVE ONLINE / OFFLINE*) dengan auto-polling Alpine.js 8 detik.
* **Konsol Outbox WA (`/notifications/wa-outbox/`)**: Riwayat pesan keluar, statistik terkirim/gagal, dan fitur *Resend Outbox*.
* **Matriks Pengaturan WA (`WANotificationSetting`)**: Kendali mode pengiriman per kategori kejadian:
  * 🤖 **Otomatis (`auto`)**: Dikirim otomatis via server WA Gateway di background (0ms delay UI).
  * 💬 **Manual (`manual`)**: Pembuatan draf log & 1-Click WhatsApp Direct Link (`wa.me`).
  * 🚫 **Nonaktif (`disabled`)**: Bypass instan tanpa koneksi jaringan.

### 💬 8. Interactive Amil Direct Messaging & Presence Status
* **Pesan Langsung Antar-Amil**: Fitur chat room internal antar pegawai/user.
* **Presence Status**: Indikator status keaktifan user (*Online/Offline*) secara real-time.

### 🤖 9. Gemini AI Assistant & Analytics Laporan
* **Asisten AI Terintegrasi**: Integrasi Google Gemini API untuk membantu amil dalam penyusunan draf narasi, ringkasan risalah, dan analisis data.
* **SLA Analytics & BI Report**: Pelaporan kinerja penanganan disposisi dan kecepatan penyelesaian berkas.

### 👥 10. Multi-Role & Switch POV (Point of View)
* **Hak Akses Berbasis Peran**: Superadmin, Ketua / Pimpinan, Wakil Ketua I-IV, Kepala Bidang, Staff / Amil Pelaksana, dan Front Office.
* **Fitur Switch POV**: Kemampuan Superadmin untuk mensimulasikan sudut pandang peran lain tanpa perlu relogin.

---

## 🛠️ Arsitektur & Teknologi (Tech Stack)

| Komponen | Teknologi | Keterangan |
| :--- | :--- | :--- |
| **Backend Framework** | **Python Django 4.2 LTS** | Arsitektur MVT, ORM, & Authentication |
| **Production WSGI** | **Waitress Server** | Production WSGI Server untuk Windows Server |
| **Database Engine** | **MySQL / MariaDB** | Production relational database (support SQLite dev) |
| **Asynchronous Engine**| **Celery + Redis / Threading**| Processing task & background notification runner |
| **Frontend Styling** | **Tailwind CSS 3.4 + Alpine.js**| Enterprise UI/UX, Glassmorphic HUD, HTMX interaktivitas |
| **WA Gateway Service**| **Node.js + Baileys v7** | `@whiskeysockets/baileys` + Express REST API (Port 3000) |
| **Cloud Security** | **Cloudflare Tunnel** | Tunneling aman tanpa port forwarding ke internet public |
| **Cloud Storage** | **Google Drive API v3** | Cloud backup arsip digital |

---

## 📁 Struktur Direktori Proyek

```text
simap/
├── apps/                          # Modul Aplikasi Utama Django
│   ├── agendas/                   # Agenda Kerja & Pengingat Kegiatan
│   ├── archives/                  # Arsip Surat Masuk, Keluar & Proposal
│   ├── dispositions/              # Disposisi Pimpinan (Stage 1 & Stage 2)
│   ├── internal_meetings/         # Undangan & Risalah Notulensi Rapat
│   ├── notifications/             # Outbox WA, Matriks Kontrol & Interactive Chat
│   ├── reports/                   # Laporan Kinerja, SLA & Analytics
│   ├── sppd_service/              # SPPD & Perjalanan Dinas Amil
│   ├── surat_tugas/               # Surat Tugas Resmi & Pemicu SPPD
│   └── users/                     # User, Employee, Dept, Switch POV & Gemini AI
├── config/                        # Konfigurasi Utama Django (settings, urls, wsgi)
├── services/                      # Business Logic & External Integrations
│   ├── ai/                        # Integrasi Google Gemini AI Service
│   ├── analytics/                 # Audit Logs & SLA Analytics
│   ├── archives/                  # NumberingService & Document Management
│   └── integrations/              # WA Gateway Service & Google Drive Client
├── static/                        # Assets CSS (Tailwind Compiled), JS, Images
├── templates/                     # Master Templates (Tailwind UI + Alpine.js)
├── wa-gateway/                    # Microservice WA Gateway Node.js (Baileys)
│   ├── index.js                   # Entrypoint Express REST API Server (Port 3000)
│   ├── package.json               # Dependensi Node.js Baileys
│   └── start_gateway.bat          # Shortcut Peluncur WA Gateway Server
├── activate_env.bat               # Script Aktivasi Environment Python
├── manage.py                      # CLI Admin Django
├── requirements.txt               # Daftar Dependensi Python Enterprise
├── run_server.py                  # Runner Server Production Waitress
├── start_all.bat                  # Script Starter Server Utama & Cloudflare Tunnel
└── start_tunnel.bat               # Runner Cloudflare Tunneling
```

---

## ⚙️ Panduan Instalasi & Pengoperasian

### 1. Prasyarat Sistem
* Python `3.10` atau versi lebih baru
* Node.js `v18` atau versi lebih baru
* MySQL / MariaDB Server (atau SQLite untuk pengembangan)
* Git

### 2. Clone Repositori & Setup Environment Python
```cmd
git clone https://github.com/fazarlazuardi/simap.git
cd simap
```

Aktivasi Virtual Environment & Install Dependensi:
```cmd
python -m venv env
call env\Scripts\activate.bat
pip install -r requirements.txt
```

### 3. Konfigurasi File Environment (`.env`)
Buat file `.env` di root direktori proyek (salin dari contoh):
```env
DEBUG=True
SECRET_KEY=your-django-secret-key
DATABASE_URL=mysql://user:password@127.0.0.1:3306/simap_db
WA_GATEWAY_URL=http://localhost:3000
GOOGLE_DRIVE_FOLDER_ID=your-google-drive-folder-id
GEMINI_API_KEY=your-gemini-api-key
```

### 4. Migrasi Database & Buat Superuser
```cmd
python manage.py migrate
python manage.py createsuperuser
```

---

## 📱 Cara Menjalankan Server SIMAP & WA Gateway

### A. Menjalankan Server Utama SIMAP
Anda dapat langsung mengeklik file **`start_all.bat`** atau menjalankannya via CMD:
```cmd
start_all.bat
```
*Script ini akan otomatis mengaktifkan server Waitress di `http://127.0.0.1:8000` dan memulai Cloudflare Tunnel.*

### B. Menjalankan WA Gateway Service (Node.js Baileys)
1. Buka folder `wa-gateway`:
   ```cmd
   cd C:\Apps\simap\wa-gateway
   ```
2. Klik 2x file **`start_gateway.bat`** (atau jalankan `node index.js`).
3. Scan **QR Code** yang muncul di layar CMD menggunakan aplikasi WhatsApp di HP Anda (**Perangkat Tertaut**).
4. Setelah terhubung, status pada dashboard Outbox WA SIMAP (`/notifications/wa-outbox/`) akan otomatis berubah menjadi **🟢 ONLINE • READY FOR DISPATCH**.

---

## 🔒 Keamanan & Data Privacy
* **Proteksi Sesi WA**: Folder autentikasi sesi WhatsApp (`auth_info_baileys/`) dan kredensial privat (`.env`, `credentials.json`) diabaikan oleh git (`.gitignore`) untuk mencegah kebocoran data.
* **Role-Based Authorization**: Setiap endpoint dan view dilindungi oleh decorator hak akses terpusat sesuai peran posisi amil.

---

## 📜 Hak Cipta & Lisensi
Hak Cipta © 2026 **BAZNAS Kabupaten Tangerang**. Seluruh hak cipta dilindungi undang-undang. Developed for BAZNAS Operational Excellence.
