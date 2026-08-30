# 🏛️ SIMAP BAZNAS KABUPATEN TANGERANG
### Sistem Informasi Manajemen & Arsip Pelayanan Terpadu

![Django](https://img.shields.io/badge/Django-4.2_LTS-092E20?style=for-the-badge&logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5.6.3-37B24D?style=for-the-badge&logo=celery&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Cache-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-Baileys_v7-339933?style=for-the-badge&logo=node.js&logoColor=white)
![PM2](https://img.shields.io/badge/PM2-Daemon-2B037A?style=for-the-badge&logo=pm2&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-Database-4479A1?style=for-the-badge&logo=mysql&logoColor=white)

---

## 📌 Tentang SIMAP BAZNAS

**SIMAP (Sistem Informasi Manajemen & Arsip Pelayanan)** adalah platform web *enterprise-grade* yang dirancang khusus untuk mendukung digitalisasi tata kelola administrasi, kearsipan, disposisi pimpinan, perjalanan dinas, serta komunikasi internal di **BAZNAS Kabupaten Tangerang**.

Sistem ini mengintegrasikan seluruh alur kerja operasional lembaga — mulai dari pencatatan surat masuk oleh *Front Office*, disposisi bertingkat pimpinan (Ketua & Wakil Ketua I–IV), penerbitan Surat Tugas dan SPPD, risalah notulensi rapat internal, hingga pengiriman notifikasi otomatis WhatsApp secara *real-time* (< 100ms UI response) menggunakan **Celery + Redis Task Queue** dan microservice **Node.js Baileys WA Gateway**.

---

## 🚀 Fitur Utama & Modul Sistem

### ⚡ 1. Zero-Lag Persistence & Celery Async Worker Queue
* **Non-Blocking View Layer**: Seluruh operasi I/O berat (pengiriman WhatsApp, sync Google Drive, audit logging) dipindahkan dari HTTP request-response cycle menggunakan `transaction.atomic()` & `transaction.on_commit(lambda: task.delay(...))`.
* **Windows Server Resilience**: Pekerja Celery dikonfigurasi khusus untuk Windows Server menggunakan pool runner `-P solo` (`start_celery.bat`) untuk mencegah *dead-lock* akibat ketiadaan modul POSIX `fork()`.
* **Reliable Retry Logic**: Exponential backoff retry handler (`max_retries=5`, `default_retry_delay=10s`) dengan penanganan `acks_late=True` dan `prefetch_multiplier=1`.

### 📥 2. Manajemen Arsip & Surat (Bidang Front Office)
* **Pencatatan Berkas Terpadu**: Registrasi surat masuk, surat keluar, proposal permohonan bantuan, dan dokumen administrasi resmi.
* **Penomoran Otomatis Logis (`NumberingService`)**: Penomoran kode arsip dan dokumen teratur sesuai format resmi BAZNAS.
* **Sinkronisasi Google Drive**: Pengunggahan berkas digital otomatis ke penyimpanan awan Google Drive BAZNAS.
* **Tracking Status Berkas**: Pemantauan status alur arsip (*Diterima FO ➔ Disposisi Pimpinan ➔ Dalam Survei ➔ Telah Disalurkan ➔ Selesai*).

### 📋 3. Disposisi Pimpinan Bertingkat (Stage 1 & Stage 2)
* **Disposisi Ketua & Wakil Ketua (Waka I - IV)**: Alur disposisi 2 tingkat dari Ketua/Waka ke Kepala Bidang, Pelaksana, maupun Tim Lapangan.
* **Sinkronisasi Dua Arah (Bi-Directional Sync)**: Pembaruan status disposisi secara otomatis mengubah status arsip dan laporan terkait.
* **Penyebaran Instruksi Massal**: Distribusi instruksi disposisi sekaligus ke banyak pegawai dengan 1-click trigger notifikasi WA via Celery.

### 📄 4. Surat Tugas Amil & Pegawai
* **Penerbitan Surat Tugas Resmi**: Pembuatan dokumen Surat Tugas lengkap dengan perihal, tanggal kegiatan, lokasi tujuan, dan penandatangan resmi.
* **Pemicu SPPD Otomatis**: Integrasi instan yang memberi pemberitahuan ke Front Office & Bidang IV untuk menerbitkan SPPD begitu Surat Tugas disahkan.

### 🚗 5. SPPD (Surat Perintah Perjalanan Dinas)
* **Pengajuan & Persetujuan SPPD**: Manajemen rincian perjalanan dinas, uang harian, moda transportasi, dan pegawai yang ditugaskan.
* **Sinkronisasi Kalender Kerja**: SPPD yang disetujui otomatis tercatat pada Kalender Kerja Amil BAZNAS.

### 📝 6. Risalah Notulensi Rapat Internal
* **Manajemen Undangan Rapat**: Pembuatan undangan kegiatan rapat internal lengkap dengan pimpinan rapat dan daftar peserta.
* **Pencatatan Kesimpulan & Keputusan**: Dokumentasi notulensi rapat dan poin keputusan resmi.
* **Otomatisasi ke Agenda Kerja**: Penjadwalan rapat otomatis masuk ke modul Agenda Kerja amil.

### 📅 7. Agenda Kerja Amil & Pengingat
* **Kalender Kegiatan Terpadu**: Manajemen agenda kegiatan harian, mingguan, dan bulanan amil.
* **Pengingat Jadwal**: Pengiriman notifikasi pengingat agenda ke akun pegawai terkait.

### 📲 8. WA Gateway Service, Real-Time QR Scanner & Command Center HUD
* **Microservice WA Gateway Node.js (`wa-gateway`)**: Microservice mandiri berbasis `@whiskeysockets/baileys` v7 yang dikelola di bawah **PM2 Daemon** (`ecosystem.config.js`, port `3000`).
* **Anti-Ban Rate Limiter & Human Simulation**: Queue tunggal (`concurrency = 1`) dengan jeda acak humanis (*jitter delay 2000ms–5000ms*) dan simulasi status kehadiran `composing`.
* **Session Self-Healing**: Penanganan otomatis 401 `loggedOut` dengan pembersihan folder `auth_info_baileys/` dan *auto-reconnect* tanpa campur tangan manual.
* **Glassmorphic Command Center HUD Toolbar**: Panel visual futuristik bertema *Emerald Cybernetic* dengan 5 tombol kontrol 1-klik:
  * 🔄 **Refresh**: Pembaruan status koneksi instan.
  * 💻 **Live Log CMD**: Buka Web Terminal Console real-time.
  * 📲 **Status Pairing**: Modal pemindaian QR Code interaktif dengan sinar laser animasi & 3-step guide.
  * ⚡ **Restart Engine**: 1-Click pemuatan ulang socket Baileys.
  * 🔌 **Putus Sesi**: Reset otentikasi & pemicu pembuat QR Code baru.
* **Live Web Terminal Console (`logModal`)**: Terminal interaktif di dalam browser yang menampilkan aliran log keluaran PM2 (`GET /notifications/wa-gateway/logs/`) secara real-time.
* **Matriks Pengaturan WA (`WANotificationSetting`)**: Kendali mode pengiriman per kategori kejadian (`auto`, `manual`, `disabled`).

### 💬 9. Interactive Amil Direct Messaging & Presence Status
* **Pesan Langsung Antar-Amil**: Fitur chat room internal antar pegawai/user.
* **Presence Status**: Indikator status keaktifan user (*Online/Offline*) secara real-time.

### 🤖 10. Gemini AI Assistant & Analytics Laporan
* **Asisten AI Terintegrasi**: Integrasi Google Gemini API untuk membantu amil dalam penyusunan draf narasi, ringkasan risalah, dan analisis data.
* **SLA Analytics & BI Report**: Pelaporan kinerja penanganan disposisi dan kecepatan penyelesaian berkas.

### 👥 11. Multi-Role & Switch POV (Point of View)
* **Hak Akses Berbasis Peran**: Superadmin, Ketua / Pimpinan, Wakil Ketua I-IV, Kepala Bidang, Staff / Amil Pelaksana, dan Front Office.
* **Fitur Switch POV**: Kemampuan Superadmin untuk mensimulasikan sudut pandang peran lain tanpa perlu relogin.

---

## 🛠️ Arsitektur & Teknologi (Tech Stack)

| Komponen | Teknologi | Keterangan |
| :--- | :--- | :--- |
| **Backend Framework** | **Python Django 4.2 LTS** | Arsitektur MVT, ORM, & Authentication |
| **Production WSGI** | **Waitress Server** | Production WSGI Server untuk Windows Server |
| **Asynchronous Engine**| **Celery 5.6.3 + Redis** | Background worker pool `-P solo` untuk Windows |
| **Database Engine** | **MySQL / MariaDB** | Production relational database (support SQLite dev) |
| **Frontend Styling** | **Tailwind CSS 3.4 + Alpine.js v3**| Enterprise UI/UX, Glassmorphic HUD, Cybernetic Animations |
| **WA Gateway Microservice**| **Node.js + Baileys v7** | `@whiskeysockets/baileys` + Express REST API (Port 3000) |
| **Process Manager** | **PM2 Daemon Engine** | Management process runner dengan auto-restart & log rotation |
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
│   ├── notifications/             # Outbox WA, Tasks Celery, Matriks Kontrol & Chat
│   ├── reports/                   # Laporan Kinerja, SLA & Analytics
│   ├── sppd_service/              # SPPD & Perjalanan Dinas Amil
│   ├── surat_tugas/               # Surat Tugas Resmi & Pemicu SPPD
│   └── users/                     # User, Employee, Dept, Switch POV & Gemini AI
├── config/                        # Konfigurasi Utama Django & Celery Engine
│   ├── celery.py                  # Inisialisasi Celery App & Task Autodiscovery
│   ├── settings.py                # Konfigurasi Django + Celery + Redis Settings
│   └── wsgi.py                    # Gateway WSGI Server
├── services/                      # Business Logic & External Integrations
│   ├── ai/                        # Integrasi Google Gemini AI Service
│   ├── analytics/                 # Audit Logs & SLA Analytics
│   ├── archives/                  # NumberingService & Document Management
│   └── integrations/              # WhatsAppService Proxy Client & Google Drive
├── static/                        # Assets CSS (Tailwind Compiled), JS, Images
├── templates/                     # Master Templates (Tailwind UI + Alpine.js)
│   └── notifications/
│       └── components/
│           └── modal_wa_scanner.html # Command Center HUD, Live Log Console & QR Modal
├── wa-gateway/                    # Microservice WA Gateway Node.js (Baileys)
│   ├── index.js                   # Entrypoint Express REST API Server (Port 3000)
│   ├── ecosystem.config.js        # Konfigurasi Daemon PM2
│   ├── package.json               # Dependensi Node.js Baileys, QRCode & Express
│   ├── start_gateway_pm2.bat      # Shortcut Peluncur Gateway via PM2
│   ├── stop_gateway_pm2.bat       # Shortcut Penghenti Gateway via PM2
│   └── view_gateway_logs.bat      # Shortcut Terminal CMD Log Viewer PM2
├── activate_env.bat               # Script Aktivasi Environment Python
├── manage.py                      # CLI Admin Django
├── requirements.txt               # Daftar Dependensi Python Enterprise
├── run_server.py                  # Runner Server Production Waitress
├── start_all.bat                  # Script Starter Server Utama SIMAP
├── start_celery.bat               # Runner Worker Celery Solo Pool Windows Server
├── start_gateway_pm2.bat          # Shortcut PM2 Gateway dari Root Folder
├── stop_gateway_pm2.bat           # Shortcut Penghenti PM2 Gateway dari Root Folder
└── view_gateway_logs.bat          # Launcher Live Log CMD Windows
```

---

## ⚙️ Panduan Instalasi & Pengoperasian

### 1. Prasyarat Sistem
* Python `3.10` atau versi lebih baru
* Node.js `v18` atau versi lebih baru
* Redis Server (Port 6379)
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

### 3. Setup Microservice Node.js WA Gateway
```cmd
cd wa-gateway
npm install
cd ..
```

### 4. Konfigurasi File Environment (`.env`)
Buat file `.env` di root direktori proyek:
```env
DEBUG=True
SECRET_KEY=your-django-secret-key
DATABASE_URL=mysql://user:password@127.0.0.1:3306/simap_db
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
WA_GATEWAY_URL=http://localhost:3000
GOOGLE_DRIVE_FOLDER_ID=your-google-drive-folder-id
GEMINI_API_KEY=your-gemini-api-key
```

### 5. Migrasi Database & Buat Superuser
```cmd
python manage.py migrate
python manage.py createsuperuser
```

---

## 📱 Peluncuran Production Services di Windows Server

Jalankan service berikut di server Windows:

1. **Jalankan Worker Celery (Windows Solo Pool)**:
   ```cmd
   start_celery.bat
   ```
   *Worker Celery akan berjalan dengan pool `-P solo` untuk memproses notifikasi background secara asynchronous.*

2. **Jalankan Microservice WA Gateway (PM2 Daemon)**:
   ```cmd
   start_gateway_pm2.bat
   ```
   *PM2 akan mengelola proses Node.js di port 3000 dengan fitur auto-recovery dan restart limit 500MB.*

3. **Jalankan Server Utama SIMAP (Waitress WSGI)**:
   ```cmd
   python run_server.py
   ```
   *Server SIMAP aktif di `http://127.0.0.1:8000`.*

4. **Monitoring Log Real-Time (CMD Terminal)**:
   Klik 2x file **`view_gateway_logs.bat`** di folder root untuk membuka jendela Command Prompt live log streaming.

---

## 🔒 Keamanan & Data Privacy
* **Proteksi Sesi WA**: Folder autentikasi sesi WhatsApp (`auth_info_baileys/`) dan file log (`logs/`) diabaikan oleh git (`.gitignore`) untuk mencegah kebocoran data otentikasi.
* **Role-Based Authorization**: Setiap endpoint dan view dilindungi oleh decorator hak akses terpusat (`@superuser_only`, `@login_required`) sesuai peran posisi amil.

---

## 📜 Hak Cipta & Lisensi
Hak Cipta © 2026 **BAZNAS Kabupaten Tangerang**. Seluruh hak cipta dilindungi undang-undang. Developed for BAZNAS Operational Excellence.
