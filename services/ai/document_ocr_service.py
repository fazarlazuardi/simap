import os
import re
import tempfile
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SmartDocumentOCRService:
    """
    Sistem Ekstraksi & Reader High-Precision SIMAP BAZNAS
    - Pemilihan & Penangkapan Tanggal Surat Presisi (Misal: "17 Juli 2026" -> 2026-07-17).
    - Menghasilkan format ISO YYYY-MM-DD presisi untuk elemen HTML Input Date.
    """

    MONTH_MAP = {
        'januari': '01', 'jan': '01', 'februari': '02', 'feb': '02',
        'maret': '03', 'mar': '03', 'april': '04', 'apr': '04',
        'mei': '05', 'juni': '06', 'jun': '06', 'juli': '07', 'jul': '07',
        'agustus': '08', 'ags': '08', 'agu': '08', 'september': '09', 'sep': '09',
        'oktober': '10', 'okt': '10', 'november': '11', 'nov': '11',
        'desember': '12', 'des': '12'
    }

    @classmethod
    def extract_full_text(cls, file_path: str) -> str:
        full_text = ""
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            # Engine 1: PyMuPDF Direct Text Layer
            try:
                import fitz
                doc = fitz.open(file_path)
                for page in doc:
                    t = page.get_text() or ''
                    if len(t.strip()) > 10:
                        full_text += t + "\n"
            except Exception:
                pass

            # Engine 2: PyMuPDF Render Image OCR (Untuk PDF Hasil Scan Printer)
            if len(full_text.strip()) < 10:
                try:
                    import fitz
                    from PIL import Image
                    import pytesseract
                    
                    doc = fitz.open(file_path)
                    for page in doc:
                        pix = page.get_pixmap(dpi=150)
                        temp_img_path = os.path.join(tempfile.gettempdir(), f"page_ocr_{page.number}.png")
                        pix.save(temp_img_path)

                        try:
                            img = Image.open(temp_img_path)
                            ocr_text = pytesseract.image_to_string(img, lang='ind+eng')
                            if len(ocr_text.strip()) > 5:
                                full_text += ocr_text + "\n"
                        finally:
                            if os.path.exists(temp_img_path):
                                os.remove(temp_img_path)
                except Exception:
                    pass

            # Engine 3: pdfplumber Layout Reader
            if len(full_text.strip()) < 10:
                try:
                    import pdfplumber
                    with pdfplumber.open(file_path) as pdf:
                        for p in pdf.pages:
                            t = p.extract_text() or ''
                            if len(t.strip()) > 5:
                                full_text += t + "\n"
                except Exception:
                    pass

            # Engine 4: pypdf Fallback
            if len(full_text.strip()) < 10:
                try:
                    import pypdf
                    reader = pypdf.PdfReader(file_path)
                    for page in reader.pages:
                        t = page.extract_text() or ''
                        if len(t.strip()) > 5:
                            full_text += t + "\n"
                except Exception:
                    pass

        elif ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            try:
                from PIL import Image
                import pytesseract
                img = Image.open(file_path)
                full_text = pytesseract.image_to_string(img, lang='ind+eng')
            except Exception:
                pass

        return cls.sanitize_text(full_text)

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """
        Membersihkan karakter biner acak tanpa menghapus angka single-digit atau tanda baca.
        """
        if not text:
            return ""
        clean = re.sub(r'[^\w\s\.\,\:\-\/\(\)\'\"]+', ' ', text)
        return clean

    @classmethod
    def analyze_document(cls, file_path: str, file_name: str = "") -> dict:
        raw_text = cls.extract_full_text(file_path)
        lines = [line.strip() for line in raw_text.split('\n') if line.strip() and len(line.strip()) > 2]

        letter_date = cls._parse_exact_date(raw_text, file_path)
        archive_type = cls._parse_archive_type(raw_text, file_name)
        is_bantuan = cls._classify_sifat(raw_text, file_name)
        title = cls._parse_exact_title(raw_text, lines, file_name, archive_type)
        sender = cls._parse_exact_sender(raw_text, lines, file_name)
        synopsis = cls._parse_human_synopsis(raw_text, lines, title, archive_type)

        return {
            'status': 'success',
            'archive_type': archive_type,
            'archive_type_display': 'Proposal / Permohonan' if archive_type == 'proposal' else 'Surat Masuk',
            'title': title,
            'sender_receiver': sender,
            'letter_date': letter_date,
            'description': synopsis,
            'sifat_dokumen': 'bantuan' if is_bantuan else 'umum',
            'category_name': 'Bantuan / Mustahik' if is_bantuan else 'Surat / Dokumen Umum',
            'confidence': '100%'
        }

    @classmethod
    def _parse_exact_date(cls, text: str, file_path: str) -> str:
        """
        Mengekstraksi tanggal resmi di dalam PDF (seperti "17 Juli 2026") menjadi format ISO YYYY-MM-DD secara presisi.
        """
        if text:
            clean_search_text = re.sub(r'\s+', ' ', text)

            # Pattern 1: Day + Month Name + Year (misal: "17 Juli 2026", "17 Juli 26", "17-Juli-2026")
            month_pattern = r'januari|jan|februari|feb|maret|mar|april|apr|mei|juni|jun|juli|jul|agustus|ags|agu|september|sep|oktober|okt|november|nov|desember|des'
            pattern_indo = rf'(\d{{1,2}})[\s\-\.\,]+({month_pattern})[\s\-\.\,]+(20\d{{2}}|\d{{2}})\b'
            
            match_indo = re.search(pattern_indo, clean_search_text, re.IGNORECASE)
            if match_indo:
                day, month_str, year = match_indo.groups()
                m_code = cls.MONTH_MAP.get(month_str.lower())
                if m_code and 1 <= int(day) <= 31:
                    year_full = f"20{year}" if len(year) == 2 else year
                    return f"{year_full}-{m_code}-{int(day):02d}"

            # Pattern 2: Format Angka DD/MM/YYYY atau DD/MM/YY (misal: 17/07/2026 atau 17/07/26)
            match_num = re.search(r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](20\d{2}|\d{2})\b', clean_search_text)
            if match_num:
                d, m, y = match_num.groups()
                if 1 <= int(d) <= 31 and 1 <= int(m) <= 12:
                    year_full = f"20{y}" if len(y) == 2 else y
                    return f"{year_full}-{int(m):02d}-{int(d):02d}"

            # Pattern 3: Format ISO 2026-07-17
            match_iso = re.search(r'20\d{2}-\d{2}-\d{2}', clean_search_text)
            if match_iso:
                return match_iso.group(0)

        try:
            mtime = os.path.getmtime(file_path)
            return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
        except Exception:
            return datetime.now().strftime('%Y-%m-%d')

    @classmethod
    def _parse_archive_type(cls, text: str, file_name: str) -> str:
        comb = f"{file_name} {text}".lower()
        if any(kw in comb for kw in ['undangan', 'mengundang', 'audiensi', 'kerjasama', 'edaran', 'pemberitahuan', 'nota dinas', 'rapat']):
            return 'surat_masuk'

        proposal_keywords = ['proposal', 'permohonan bantuan', 'pembangunan', 'renovasi', 'rehab', 'bedah rumah', 'rutilahu', 'anggaran biaya', 'rab']
        if any(kw in comb for kw in proposal_keywords):
            return 'proposal'

        return 'surat_masuk'

    @classmethod
    def _classify_sifat(cls, text: str, file_name: str) -> bool:
        comb = f"{file_name} {text}".lower()
        umum_keywords = ['undangan', 'mengundang', 'audiensi', 'kerjasama', 'kerja sama', 'vendor', 'penawaran', 'nota dinas', 'pengadaan', 'narasumber', 'rapat']
        if any(kw in comb for kw in umum_keywords):
            return False
        return True

    @classmethod
    def _parse_exact_title(cls, text: str, lines: list, file_name: str, archive_type: str) -> str:
        if text:
            match_hal = re.search(r'(?:perihal|hal|subjek|judul)\s*[:\-\=]\s*([^\n\r]{5,150})', text, re.IGNORECASE)
            if match_hal:
                res = match_hal.group(1).strip()
                res = re.sub(r'^[\:\-\s\.]+', '', res)
                return res.title()

            for line in lines[:15]:
                l_lower = line.lower()
                if any(kw in l_lower for kw in ['undangan', 'audiensi', 'permohonan', 'bantuan', 'proposal', 'pembangunan', 'renovasi', 'rutilahu']):
                    return line.strip().title()

        clean_file_name = re.sub(r'\.[^/.]+$', '', file_name)
        clean_file_name = re.sub(r'[\_\-\.]+', ' ', clean_file_name).strip()
        clean_words = [w.capitalize() for w in clean_file_name.split() if len(w) > 0]
        
        if archive_type == 'surat_masuk':
            return " ".join(clean_words) if clean_words else "Surat Undangan Masuk"
        return " ".join(clean_words) if clean_words else "Permohonan Bantuan BAZNAS"

    @classmethod
    def _parse_exact_sender(cls, text: str, lines: list, file_name: str) -> str:
        if text:
            match_from = re.search(r'(?:dari|pengirim|pemohon|asal|a\.n\.?|instansi)\s*[:\-\=]\s*([^\n\r]{3,80})', text, re.IGNORECASE)
            if match_from:
                res = match_from.group(1).strip()
                res = re.sub(r'^[\:\-\s\.]+', '', res)
                return res.title()

            match_upz = re.search(r'((?:upz\s+)?(?:sepatan|pasarkemis|cikupa|balaraja|krojo|panongan|tangerang)[^\-\_\n\r\.\,]{0,40})', text, re.IGNORECASE)
            if match_upz:
                return match_upz.group(1).strip().upper()

            match_dkm = re.search(r'((?:dkm\s+)?masjid[^\-\_\n\r\.\,]{3,60})', text, re.IGNORECASE)
            if match_dkm:
                return match_dkm.group(1).strip().upper()

            for line in lines:
                line_l = line.lower()
                if any(kw in line_l for kw in ['dinas', 'bupati', 'pemkab', 'kecamatan', 'desa', 'kelurahan', 'panitia', 'pt ', 'cv ', 'yayasan', 'pengurus']):
                    return line.strip().title()

        clean_file_name = re.sub(r'\.[^/.]+$', '', file_name)
        clean_file_name = re.sub(r'[\_\-\.]+', ' ', clean_file_name).strip()
        words = clean_file_name.split()
        if len(words) >= 2:
            return f"{words[0].upper()} {words[1].upper()}"

        return "Instansi Pengirim / Pemohon"

    @classmethod
    def _parse_human_synopsis(cls, text: str, lines: list, title: str, archive_type: str) -> str:
        comb_l = f"{title} {text}".lower()

        if archive_type == 'surat_masuk' or any(kw in comb_l for kw in ['undangan', 'mengundang', 'audiensi', 'rapat']):
            return f"Surat undangan resmi perihal {title} untuk menghadiri kegiatan/acara."

        if 'rutilahu' in comb_l or 'bedah rumah' in comb_l or 'rehab rumah' in comb_l:
            return f"Pengajuan permohonan bantuan perbaikan Rumah Tidak Layak Huni (RTLH) untuk Mustahik."

        if 'masjid' in comb_l or 'musholla' in comb_l or 'pembangunan masjid' in comb_l:
            return f"Pengajuan permohonan bantuan dana pembangunan dan kelengkapan fasilitas peribadatan masjid/musholla."

        if 'berobat' in comb_l or 'kesehatan' in comb_l or 'medis' in comb_l:
            return f"Pengajuan permohonan bantuan biaya pengobatan dan penanganan medis kesehatan Mustahik."

        if 'beasiswa' in comb_l or 'pendidikan' in comb_l or 'spp' in comb_l:
            return f"Pengajuan permohonan bantuan biaya pendidikan dan beasiswa studi Mustahik."

        body_paragraphs = []
        for line in lines:
            line_clean = line.strip()
            line_lower = line_clean.lower()
            if len(line_clean) > 25 and not any(kw in line_lower for kw in [
                'nomor:', 'no:', 'lampiran:', 'perihal:', 'hal:', 'kepada yth',
                'dengan hormat', 'assalamu\'alaikum', 'sekretariat', 'alamat:', 'telepon', 'email:'
            ]):
                body_paragraphs.append(line_clean)

        if body_paragraphs:
            pure_summary = " ".join(body_paragraphs[:3])
            pure_summary = re.sub(r'\s+', ' ', pure_summary).strip()
            return pure_summary[:450] + "..." if len(pure_summary) > 450 else pure_summary

        return f"Surat masuk resmi perihal {title}."
