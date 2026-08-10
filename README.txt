# MANUAL BOOK & PANDUAN PENGGUNAAN SISTEM SIMAP
## SISTEM INFORMASI MANAJEMEN ARSIP & PERSURATAN BAZNAS KABUPATEN TANGERANG

---

> [!NOTE]
> **Dokumen Resmi Panduan Operasional Sistem**
> Manual Book ini disusun secara komprehensif untuk memberikan panduan langkah demi langkah dalam mengoperasikan seluruh fitur dan modul pada Sistem SIMAP BAZNAS Kabupaten Tangerang.

---

## DAFTAR ISI

1. [PENDAHULUAN & GAMBARAN UMUM SISTEM](#1-pendahuluan--gambaran-umum-sistem)
2. [HAK AKSES & PERAN PENGGUNA (ROLE ACCESS)](#2-hak-akses--peran-pengguna-role-access)
3. [MODUL 1: REGISTRASI & PENGELOLAAN ARSIP DOKUMEN](#3-modul-1-registrasi--pengelolaan-arsip-dokumen)
4. [MODUL 2: ALUR DISPOSISI DOKUMEN 2-TAHAP RESMI BAZNAS](#4-modul-2-alur-disposisi-dokumen-2-tahap-resmi-baznas)
5. [MODUL 3: PENERBITAN SURAT TUGAS](#5-modul-3-penerbitan-surat-tugas)
6. [MODUL 4: SURAT PERINTAH PERJALANAN DINAS (SPPD)](#6-modul-4-surat-perintah-perjalanan-dinas-sppd)
7. [MODUL 5: MANAJEMEN AGENDA & MEETINGS](#7-modul-5-manajemen-agenda--meetings)
8. [MODUL 6: LAPORAN HASIL PELAKSANAAN (LHP) & BACKUP AUTOMATION](#8-modul-6-laporan-hasil-pelaksanaan-lhp--backup-automation)
9. [MODUL 7: MANAJEMEN PEGAWAI, AUDIT LOG & NOTIFIKASI](#9-modul-7-manajemen-pegawai-audit-log--notifikasi)
10. [PANDUAN TROUBLESHOOTING & FAQ](#10-panduan-troubleshooting--faq)

---

## 1. PENDAHULUAN & GAMBARAN UMUM SISTEM

**Sistem Informasi Manajemen Arsip & Persuratan (SIMAP)** BAZNAS Kabupaten Tangerang merupakan platform aplikasi web terintegrasi yang dirancang untuk mengoperasionalkan alur kerja tata kelola persuratan, disposisi pimpinan, penugasan lapangan, perjalanan dinas (SPPD), hingga pengarsipan dan pelaporan hasil secara digital dan otomatis.

### Tujuan Utama SIMAP:
- **Digitalisasi Berkas**: Menghilangkan risiko kehilangan surat/proposal fisik melalui digitalisasi file PDF & Gambar.
- **Akuntabilitas Alur Kerja (BPMN Workflow)**: Menyediakan pelacakan alur dokumen secara transparan mulai dari pendaftaran oleh Front Office hingga penuntasan oleh Bidang Pelaksana.
- **Ketepatan Disposisi Pimpinan**: Menerapkan alur disposisi 2-tahap standar pemerintah/lembaga resmi (Ketua BAZNAS ➔ Waka IV ➔ Bidang Pelaksana).
- **Integrasi Penugasan & SPPD**: Otomatisasi penerbitan Surat Tugas dan SPPD langsung dari lembar disposisi atau agenda kegiatan.
- **Backup & Reporting Otomatis**: Sinkronisasi rekapitulasi data secara berkala ke Google Sheets (23 Kolom Presisi) dan Google Drive resmi BAZNAS Kabupaten Tangerang (`kabupatenbaznastangerang@gmail.com`).

---

## 2. HAK AKSES & PERAN PENGGUNA (ROLE ACCESS)

Sistem SIMAP menerapkan pengamanan berbasis peran (*Role-Based Access Control*):

| Peran (Role) | Wewenang & Tanggung Jawab Utama |
| :--- | :--- |
| **Administrator (Admin / SDM)** | Pengelolaan master data pegawai, pengaturan sistem, kelola OAuth Google Drive, reset data, dan pengawasan audit log. |
| **Front Office (Secretariat)** | Registrasi surat masuk/proposal, cetak tanda terima dokumen, pengunggahan berkas digital awal. |
| **Kabid IV (SDM & Administrasi Umum)** | Verifikasi awal kelengkapan dokumen registrasi sebelum diteruskan ke pimpinan. |
| **Ketua BAZNAS (Pimpinan Tahap 1)** | Menerbitkan Disposisi Tahap 1, memberikan arahan utama, dan meneruskan surat ke Wakil Ketua terkait. |
| **Waka IV / Pimpinan Terkait (Tahap 2)** | Menerbitkan Disposisi Tahap 2, menginstruksikan pelaksana bidang (Bidang I, II, III, IV, atau Sekretariat). |
| **Pelaksana / Amil (Staff Bidang)** | Menerima instruksi penugasan, melaksanakan tugas lapangan/survei/penyaluran, menerbitkan SPPD, dan mengunggah Laporan Hasil Pelaksanaan (LHP). |

---

## 3. MODUL 1: REGISTRASI & PENGELOLAAN ARSIP DOKUMEN

Modul Arsip digunakan untuk menginput dan memproses setiap dokumen yang masuk atau keluar dari lembaga.

```mermaid
flowchart LR
    A["Front Office / Input"] --> B["Penomoran Otomatis REG-XXXX"]
    B --> C["Upload Berkas PDF/Gambar / OCR Scan"]
    C --> D["Cetak Tanda Terima Dokumen"]
    D --> E["Verifikasi Kabid IV"]
```

### Langkah Operasional Registrasi Dokumen Baru:
1. **Buka Menu Registrasi**: Masuk ke menu `Arsip & Surat` ➔ Klik tombol **`+ Registrasi Surat / Proposal`**.
2. **Isi Formulir Dokumen**:
   - **Jenis Dokumen**: Pilih *Surat Masuk*, *Proposal*, *Surat Keluar*, atau *Dokumen Internal*.
   - **Nomor Surat Asli**: Masukkan nomor surat resmi dari pengirim (jika ada).
   - **Pengirim / Asal Instansi**: Isi nama pemohon, mustahik, atau instansi pengirim.
   - **Perihal / Judul Dokumen**: Isi perihal surat secara jelas dan ringkas.
   - **Kategori Arsip**: Pilih kategori yang sesuai (*Kerjasama*, *Santunan Yatim Piatu*, *Bantuan Rutilahu*, *Bantuan Kesehatan*, dll).
   - **Tanggal Surat & Tanggal Diterima**: Pilih tanggal sesuai dokumen fisik.
   - **Sifat Keamanan & Tanggapan**: Tentukan tingkat kerahasiaan (*Biasa*, *Penting*, *Rahasia*) dan tingkat urgensi (*Biasa*, *Segera*, *Kilat*).
3. **Pengunggahan File Digital**:
   - Unggah berkas berkategori `.pdf`, `.jpg`, `.jpeg`, atau `.png` (Maksimal 10MB per file).
   - **Fitur OCR Scanning**: Klik **`Scan OCR`** jika ingin mengekstrak teks otomatis dari foto/gambar dokumen fisik.
4. **Simpan & Cetak Tanda Terima**:
   - Klik **`Simpan Dokumen`**. Sistem akan mengenerate Nomor Registrasi SIMAP secara otomatis (`REG-XXXX`).
   - Klik tombol **`Cetak Tanda Terima`** untuk memberikan bukti penerimaan fisik kepada pengirim/pemohon.

---

## 4. MODUL 2: ALUR DISPOSISI DOKUMEN 2-TAHAP RESMI BAZNAS

Disposisi merupakan inti alur kerja instruksi pimpinan di BAZNAS Kabupaten Tangerang.

```mermaid
sequenceDiagram
    participant FO as Front Office / Sekretariat
    participant K4 as Kabid IV (Verifikasi)
    participant KETUA as Ketua BAZNAS (Tahap 1)
    participant WAKA as Waka IV / Pimpinan (Tahap 2)
    participant STAFF as Bidang Pelaksana

    FO->>K4: Registrasi & Upload Dokumen
    K4->>KETUA: Dokumen Terverifikasi
    KETUA->>WAKA: Disposisi Tahap 1 (Arahan Utama)
    WAKA->>STAFF: Disposisi Tahap 2 (Penugasan Bidang)
    STAFF->>STAFF: Pelaksanaan Tugas / SPPD / Laporan
```

### Prosedur Disposisi Tahap 1 (Ketua BAZNAS):
1. Buka daftar surat berstatus *`Menunggu Disposisi Pimpinan`*.
2. Klik tombol **`Disposisi`** pada dokumen yang dipilih.
3. Pilih **Peneruskan Disposisi** (misalnya diteruskan ke *Wakil Ketua IV* atau *Wakil Ketua II*).
4. Beri tanda centang pada instruksi utama:
   - `[ ] Selesaikan / Jawab`
   - `[ ] Untuk diketahui / Simpan`
   - `[ ] Laporkan hasilnya`
   - `[ ] Koordinasikan`
5. Isi **Catatan / Arahan Pimpinan** pada kolom teks yang disediakan.
6. Beri centang `[x] Memerlukan SPPD / Dinas Luar` jika penugasan ini membutuhkan perjalanan dinas.
7. Klik **`Kirim Disposisi`**.

### Prosedur Disposisi Tahap 2 (Waka IV / Pimpinan Terkait):
1. Buka dokumen berstatus *`Dalam Proses Disposisi Pimpinan`*.
2. Klik **`Tindak Lanjut Waka IV`**.
3. Pilih Pegawai/Bidang Pelaksana akhir yang ditugaskan (misal: *Staff Bidang II Penyaluran*, *Tim Survei*, dll).
4. Masukkan instruksi teknis pelaksanaan pada **Catatan Waka IV**.
5. Klik **`Simpan Disposisi Tahap 2`**. Sistem akan mengirim notifikasi otomatis ke pegawai pelaksana yang ditunjuk.

---

## 5. MODUL 3: PENERBITAN SURAT TUGAS

Surat Tugas diterbitkan sebagai dasar hukum penugasan amil/pegawai dalam melaksanakan tugas lapangan, audiensi, maupun rapat luar kantor.

### Langkah Menerbitkan Surat Tugas:
1. **Melalui Detail Dokumen / Lembar Disposisi**:
   - Pada halaman detail dokumen, klik tombol **`+ Buat Surat Tugas`**.
2. **Pengisian Data Penugasan**:
   - **Nomor Surat Tugas**: Tergenerate otomatis sesuai penomoran resmi BAZNAS (`ST/XXX/BAZNAS-TGN/MM/YYYY`).
   - **Perihal Penugasan**: Terisi otomatis sesuai perihal disposisi (dapat disesuaikan).
   - **Pegawai Ditugaskan**: Pilih penanggung jawab utama dan anggota tim yang ditugaskan.
   - **Tanggal Tugas & Lokasi**: Isi tanggal mulai/selesai serta alamat tujuan penugasan.
3. **Cetak Surat Tugas**:
   - Klik **`Simpan & Cetak`**. Sistem menampilkan format Surat Tugas resmi ber-Kop BAZNAS yang siap ditandatangani dan distempel.

---

## 6. MODUL 4: SURAT PERINDAH PERJALANAN DINAS (SPPD)

Modul SPPD digunakan untuk mempertanggungjawabkan perjalanan dinas dan biaya operasional penugasan amil.

### Penentuan *Purpose* Cerdas Otomatis:
Sistem SIMAP secara cerdas mengklasifikasikan maksud perjalanan dinas berdasarkan jenis dokumen & tugas:
- **Survei Lapangan**: Untuk permohonan bantuan/proposal mustahik yang membutuhkan verifikasi tempat/rutilahu/kesehatan.
- **Penyaluran Bantuan**: Untuk kegiatan pentasyarufan/penyerahan dana bantuan BAZNAS.
- **Audiensi / Dinas Luar**: Untuk koordinasi instansi, rapat peribadatan, atau undangan dinas luar.

### Langkah Membuat SPPD:
1. Klik tombol **`+ Buat SPPD`** pada halaman Detail Dokumen atau Surat Tugas.
2. Masukkan data pendukung:
   - **Tempat Berangkat & Tempat Tujuan**: Contoh: *Islamic Center Panongan ➔ Kec. Mauk, Kab. Tangerang*.
   - **Lama Perjalanan**: Masukkan jumlah hari (tanggal berangkat s.d. tanggal kembali).
   - **Mata Anggaran**: Pilih sumber dana operasional (misal: *DAP / Hak Amil / Operasional Bidang II*).
   - **Pengikut (Followers)**: Tambahkan anggota amil yang ikut dalam perjalanan dinas.
3. Klik **`Simpan SPPD`**.
4. Klik **`Cetak Lembar SPPD`** (Lembar 1 & Lembar 2 siap cetak).

---

## 7. MODUL 5: MANAJEMEN AGENDA & MEETINGS

Modul Agenda mengelola jadwal kegiatan rapat internal BAZNAS, audiensi pimpinan, maupun acara luar kantor.

### Fitur Utama Modul Agenda:
- **Penjadwalan Berulang (Recurring Meetings)**: Pengaturan jadwal rapat harian, mingguan (contoh: *Rapat Pleno Pimpinan Setiap Senin*), atau bulanan.
- **Auto-Generate SPPD**: Dapatkan SPPD otomatis dari agenda audiensi/dinas luar tanpa perlu menginput ulang data dari awal.
- **Upload Notulensi & Synchronize Report**: Pengunggahan berkas hasil notulensi rapat yang otomatis tersinkronisasi sebagai berkas laporan dokumen.

---

## 8. MODUL 6: LAPORAN HASIL PELAKSANAAN (LHP) & BACKUP AUTOMATION

Setiap penugasan yang telah selesai wajib dilengkapi dengan Laporan Hasil Pelaksanaan (LHP) sebagai bukti pertanggungjawaban akhir.

```mermaid
flowchart TD
    A["Tugas Lapangan / SPPD Selesai"] --> B["Upload Berkas LHP / Laporan Hasil"]
    B --> C["Status Dokumen Selesai & Terekap"]
    C --> D["Auto-Sync Google Sheet Rekapitulasi"]
    D --> E["Pengiriman Laporan Email Backup"]
```

### 1. Unggah Laporan Hasil (LHP):
- Masuk ke Detail Dokumen ➔ Klik tombol **`+ Unggah Laporan Hasil`**.
- Isi Nomor Laporan (Format: `XXX/LHP/MM/YYYY`), Judul Laporan, dan unggah file PDF Laporan Pelaksanaan & Foto Kegiatan.
- Status dokumen berubah menjadi **`Selesai & Terekap`**.

### 2. Monitoring 8 Tahapan Disposisi Vertikal:
Sistem secara otomatis mengevaluasi 8 tahapan progres pada kisi-kisi rekapitulasi:
1. `Verifikasi Kabid IV` (Telah diverifikasi oleh Sekretariat/Kabid 4)
2. `Disposisi Ketua` (Disposisi Tahap 1 terbit)
3. `Disposisi Waka IV` (Disposisi Tahap 2 diteruskan ke pelaksana)
4. `Proses Bidang/Unit` (Surat Tugas / SPPD diterbitkan)
5. `Survei` (Memiliki SPPD/ST Survei Lapangan yang tereksekusi)
6. `Penyaluran` (Memiliki SPPD/ST Penyaluran Bantuan yang tereksekusi)
7. `Laporan` (Berkas Laporan LHP diunggah)
8. `Selesai` (Dokumen ditutup & terarsip penuh)

### 3. Backup Google Drive & Google Sheets:
- Rekapitulasi bulanan tersimpan otomatis pada Google Sheet resmi dengan format **23 Kolom Presisi**:
  - **Kop Laporan**: Warna **Hijau BAZNAS (`#006633`)**, Teks Putih Bold, Rata Kiri.
  - **Header Utama**: Warna **Kuning (`#FFD966`)**, Teks Hitam Bold.
  - **Diagram 8 Tahapan Vertikal**: Sub-header berwarna-warni (Biru Tua, Biru Muda, Oranye, Kuning, Hijau) berotasi 90° dengan tinggi baris 120px.
  - **All Border**: Seluruh tabel dibingkai garis **Hitam Tegas (Solid Black)**.
  - **Smart Column Widths**: Lebar kolom disesuaikan secara cerdas (misal: *Kolom Pengirim = 160px*, *Kolom Perihal = 250px*, *Kolom Tahapan = 45px*).

---

## 9. MODUL 7: MANAJEMEN PEGAWAI, AUDIT LOG & NOTIFIKASI

### 1. Data Master Pegawai & Pengguna:
- Menu `Pengaturan Pengguna` ➔ Pengelolaan NIP, nama lengkap, jabatan, bidang kerja, serta pengaturan kata sandi akun amil.

### 2. Audit Log Trail (BPMN Timeline):
- Setiap tindakan pengguna (registrasi, disposisi, cetak SPPD, edit, hapus, upload laporan) tercatat secara murni di **Audit Log Trail**.
- Pelacakan alur kerja dapat dilihat secara visual melalui timeline interaktif di halaman detail dokumen.

### 3. Notifikasi Otomatis (WhatsApp & Email):
- Notifikasi pengingat disposisi baru, penugasan SPPD, dan jadwal agenda dikirimkan langsung ke nomor WhatsApp dan email penerima tugas.

---

## 10. PANDUAN TROUBLESHOOTING & FAQ

### Q1: Mengapa tombol Backup Google Drive tidak merespons atau menampilkan URL otorisasi?
> **Solusi**: Akun Google OAuth belum terhubung. Administrator perlu mengeklik tautan otorisasi Google OAuth yang muncul di halaman pengaturan backup, lalu menyetujui izin akses Google Drive & Google Sheets.

### Q2: Mengapa tanda centang pada kolom Survei atau Penyaluran di Google Sheet bernilai (-)?
> **Solusi**: Sistem SIMAP bekerja 100% berdasarkan bukti empiris. Jika dokumen tersebut merupakan *Surat Masuk Biasa* atau *Proposal yang tidak memerlukan SPPD Survei/Penyaluran*, maka sistem secara jujur memberikan nilai `(-)`. Tanda centang `(✓)` hanya diberikan jika terdapat record SPPD/ST/Audit Log survei & penyaluran yang sah.

### Q3: Bagaimana cara mengubah data surat yang salah diinput oleh Front Office?
> **Solusi**: Buka halaman detail dokumen ➔ Klik tombol **`Edit Dokumen`**. Perubahan hanya dapat dilakukan oleh pengunggah awal, Kabid 4, atau Administrator Sistem.

---

*Manual Book SIMAP BAZNAS Kabupaten Tangerang - Versi 2.4 (Agustus 2026)*
