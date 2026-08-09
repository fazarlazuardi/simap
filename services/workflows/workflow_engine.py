import re
from typing import Dict, Any, List

class WorkflowEngine:
    """
    SIMAP Enterprise Dynamic Workflow Engine
    Mengelola alur 2-Tahap Disposisi Resmi BAZNAS:
    FO -> Verifikasi Kabid -> Disposisi Tahap 1 (Ketua) -> Meja Waka IV (Disposisi Tahap 2) -> Pembagian (Bidang II untuk Bantuan / Bagian Terkait untuk Umum) -> Selesai
    """

    BANTUAN_SUB_KEYWORDS = {
        'rtlh': ['rutilahu', 'bedah rumah', 'rumah roboh', 'perbaikan rumah', 'renovasi rumah'],
        'berobat': ['pengobatan', 'berobat', 'kesehatan', 'rumah sakit', 'pasien', 'operasi', 'alat bantu', 'kursi roda', 'medis'],
        'hutang': ['gharimin', 'gharim', 'hutang', 'hutanh', 'piutang', 'tunggakan sewa', 'tunggakan hidup', 'kontrakan'],
        'pendidikan': ['beasiswa', 'spp', 'sekolah', 'ijazah', 'tunggakan sekolah', 'kuliah', 'pendidikan', 'siswa', 'mahasiswa', 'tunggakan pendidikan', 'tunggakan spp'],
        'sarpras_ibadah': ['masjid', 'mesjid', 'musholla', 'mushola', 'majlis', 'majelis', 'peribadatan', 'pembangunan mesjid', 'pembangunan musholla', 'pembangunan peribadatan', 'karpet', 'sound system', 'kubah'],
        'sarpras_sekolah': ['meubelair', 'mebeulair', 'meubellair', 'pesantren', 'madrasah', 'ponpes', 'mebel', 'meja kursi', 'ruang kelas'],
        'umkm': ['umkm', 'modal usaha', 'gerobak', 'gerobak usaha', 'usaha', 'dagang', 'warung', 'modal kerja'],
        'musafir': ['musafir', 'bekal perjalanan', 'terlantar', 'ongkos pulang', 'ibnu sabil'],
        'muallaf': ['mualaf', 'muallaf', 'masuk islam', 'pembinaan muallaf'],
        'santunan': ['sembako', 'santunan', 'yatim', 'piatu', 'logistik', 'paket sembako', 'tanggap bencana'],
        'lainnya': ['bantuan', 'permohonan'],
    }

    SUB_CATEGORY_NAMES = {
        'rtlh': 'Bantuan Rutilahu',
        'berobat': 'Bantuan Kesehatan',
        'hutang': 'Bantuan Gharimin',
        'pendidikan': 'Bantuan Pendidikan',
        'sarpras_ibadah': 'Pembangunan Peribadatan',
        'sarpras_sekolah': 'Bantuan Meubelair',
        'umkm': 'Bantuan UMKM',
        'musafir': 'Bantuan Musafir',
        'muallaf': 'Bantuan Muallaf',
        'santunan': 'Santunan Sembako',
        'lainnya': 'Bantuan Lainnya',
    }

    @classmethod
    def is_bantuan(cls, archive) -> bool:
        if not archive:
            return False
            
        text_to_check = f"{archive.title or ''} {archive.description or ''} {archive.sender_receiver or ''}".lower()
        
        surat_umum_keywords = [
            'audiensi', 'undangan', 'kerjasama', 'kerja sama', 'koordinasi',
            'narasumber', 'kunjungan', 'nota dinas', 'rapat', 'sosialisasi', 'studi banding', 'vendor', 'pengadaan'
        ]
        if any(kw in text_to_check for kw in surat_umum_keywords):
            return False

        if archive.archive_type == 'proposal':
            if 'vendor' in text_to_check or 'penawaran' in text_to_check or 'pengadaan' in text_to_check:
                return False
            return True
            
        category_name = archive.category.name.lower() if archive.category else ''
        bantuan_cat_keywords = [
            'bantuan', 'rutilahu', 'kesehatan', 'gharimin', 'pendidikan',
            'peribadatan', 'meubelair', 'umkm', 'musafir', 'muallaf',
            'santunan', 'sembako', 'lpj', 'pendistribusian', 'penyaluran'
        ]
        if any(kw in category_name for kw in bantuan_cat_keywords):
            return True
        
        bantuan_keywords = [
            'bantuan', 'mohon bantuan', 'permohonan bantuan', 'biaya',
            'berobat', 'kesehatan', 'medis', 'rs', 'rumah sakit', 'gerobak', 'modal',
            'usaha', 'umkm', 'dagang', 'beasiswa', 'pendidikan', 'spp', 'sekolah',
            'kuliah', 'ijazah', 'rtlh', 'bedah rumah', 'rumah layak', 'santunan',
            'bencana', 'kemanusiaan', 'pelunasan', 'hutang', 'utang', 'gharimin',
            'gharim', 'tunggakan', 'fakir', 'miskin', 'mustahik', 'mustahiq',
            'peribadatan', 'mesjid', 'musholla', 'masjid', 'mushola', 'meubelair', 'mebeulair'
        ]
        
        return any(kw in text_to_check for kw in bantuan_keywords)

    @classmethod
    def get_bantuan_subcategory(cls, archive) -> str:
        """
        Mengklasifikasikan sub-jenis permohonan bantuan secara cerdas.
        """
        if not cls.is_bantuan(archive):
            return 'Surat / Dokumen Umum'

        text = f"{archive.title or ''} {archive.description or ''}".lower()
        
        for key, keywords in cls.BANTUAN_SUB_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return cls.SUB_CATEGORY_NAMES[key]

        return cls.SUB_CATEGORY_NAMES['lainnya']

    @classmethod
    def get_workflow_info(cls, archive) -> Dict[str, Any]:
        if not archive:
            return {'type': 'umum', 'stage_name': 'Draft', 'step': 1, 'next_action': 'Upload Registrasi'}

        is_bantuan_doc = cls.is_bantuan(archive)
        dispositions = list(archive.dispositions.all())
        dispo_count = len(dispositions)
        d = dispositions[-1] if dispositions else None

        status = archive.status
        sppd = archive.latest_sppd
        st = archive.latest_st

        if status == 'selesai':
            step = 5
            stage_name = '5. Dokumen Selesai & Terarsip'
            next_action = 'Dokumen Telah Diarsipkan'
        elif sppd:
            step = 4
            stage_name = f'4. Perjalanan Dinas / SPPD Terbit ({sppd.sppd_number})'
            next_action = 'Pelaksanaan Tugas Lapangan & Laporan SPPD'
        elif st:
            step = 4
            stage_name = f'4. Penugasan Berkelanjutan / Surat Tugas Terbit ({st.nomor_surat or "ST"})'
            next_action = 'Pelaksanaan Tugas / Pembuatan SPPD'
        elif d and (d.is_stage_waka or d.disposition_stage == 'waka_iv' or d.waka_forwarded_to.exists() or dispo_count >= 2):
            step = 4
            receivers = list(d.waka_forwarded_to.all())
            positions = ", ".join([e.position for e in receivers if e.position])
            names = ", ".join([e.full_name for e in receivers])
            
            if 'Wakil Ketua II' in positions or 'Waka II' in positions or 'Kabid II' in positions:
                stage_name = '4. Di Meja Waka II / Bidang II (Penyaluran & Survey Bantuan)'
                next_action = 'Pelaksanaan Survey / Penyaluran Bantuan oleh Bidang II'
            elif 'Wakil Ketua III' in positions or 'Waka III' in positions or 'Kabid III' in positions:
                stage_name = '4. Di Meja Waka III / Bidang III'
                next_action = 'Penanganan Bidang III'
            elif 'Wakil Ketua I' in positions or 'Waka I' in positions or 'Kabid I' in positions:
                stage_name = '4. Di Meja Waka I / Bidang I'
                next_action = 'Penanganan Bidang I'
            elif positions:
                stage_name = f'4. Di Meja {positions}'
                next_action = 'Tindak Lanjut Bidang Pelaksana'
            elif names:
                stage_name = f'4. Di Meja {names}'
                next_action = 'Tindak Lanjut Bidang Pelaksana'
            else:
                stage_name = '4. Dalam Proses Unit Terkait'
                next_action = 'Pelaksanaan Tugas / Penanganan'
        elif d:
            step = 3
            stage_name = '3. Meja Waka IV (Disposisi Tahap 2)'
            next_action = 'Waka IV Membagi: Ke Bidang II (Jika Bantuan) atau Ke Bagian Terkait (Jika Umum)'
        elif status == 'terverifikasi':
            step = 2
            stage_name = '2. Terverifikasi Kabid IV'
            next_action = 'Siap Didisposisikan oleh Ketua BAZNAS (Disposisi Tahap 1)'
        elif status == 'baru':
            step = 1
            stage_name = '1. Registrasi Front Office'
            next_action = 'Verifikasi oleh Kabid IV'
        else:
            step = 2
            stage_name = '2. Dalam Proses Disposisi'
            next_action = 'Proses Disposisi Pimpinan'

        return {
            'is_bantuan': is_bantuan_doc,
            'sub_category': cls.get_bantuan_subcategory(archive) if is_bantuan_doc else 'Surat / Dokumen Umum',
            'stage_name': stage_name,
            'step': step,
            'next_action': next_action,
            'dispo_count': dispo_count
        }
