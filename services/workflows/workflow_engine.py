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
            
        cat_obj = getattr(archive, 'category', None)
        category_name = cat_obj.name.lower() if cat_obj else ''
        bantuan_cat_keywords = [
            'bantuan', 'rutilahu', 'kesehatan', 'gharimin', 'pendidikan',
            'peribadatan', 'meubelair', 'meubellair', 'mebeulair', 'sarpras', 'sarana', 'prasarana',
            'sekolah', 'pesantren', 'pembangunan',
            'umkm', 'musafir', 'muallaf', 'santunan', 'sembako', 'lpj',
            'pendistribusian', 'penyaluran', 'rtlh'
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
        agendas = list(archive.agendas.all())
        latest_ag = agendas[-1] if agendas else None

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
        elif latest_ag and not latest_ag.is_completed and latest_ag.status != 'selesai':
            step = 4
            sch_str = latest_ag.scheduled_at.strftime('%d/%m/%Y %H:%M') if latest_ag.scheduled_at else ''
            if getattr(latest_ag, 'is_undangan_luar', False):
                stage_name = f'4. Agenda Hadiri Undangan Luar Kantor ({latest_ag.title} - {sch_str} WIB)'
                next_action = 'Menghadiri Undangan Luar & Pembuatan Laporan / Notulensi'
            else:
                stage_name = f'4. Agenda Terjadwal di Kantor BAZNAS ({latest_ag.title} - {sch_str} WIB)'
                next_action = 'Pelaksanaan Acara di Kantor & Pembuatan Laporan / Notulensi'
        elif d and (d.is_stage_waka or d.disposition_stage == 'waka_iv' or d.waka_forwarded_to.exists() or dispo_count >= 2):
            step = 4
            receivers = list(d.waka_forwarded_to.all())
            positions = ", ".join([e.position for e in receivers if e.position])
            names = ", ".join([e.full_name for e in receivers])
            pos_lower = positions.lower()
            
            if any(k in pos_lower for k in ['waka iv', 'waka 4', 'wakil ketua iv', 'wakil ketua 4', 'kabid iv', 'kabid 4', 'kepala bidang iv', 'administrasi', 'sdm', 'umum']):
                if 'kabid' in pos_lower or 'kepala bidang' in pos_lower:
                    stage_name = '4. Di Meja Kabid IV / Bidang IV (Administrasi, SDM & Umum)'
                else:
                    stage_name = '4. Di Meja Waka IV / Bidang IV (Administrasi, SDM & Umum)'
                next_action = 'Penanganan Bidang IV (Administrasi, SDM & Umum)'
            elif any(k in pos_lower for k in ['waka iii', 'waka 3', 'wakil ketua iii', 'wakil ketua 3', 'kabid iii', 'kabid 3', 'kepala bidang iii', 'perencanaan', 'keuangan', 'pelaporan']):
                if 'kabid' in pos_lower or 'kepala bidang' in pos_lower:
                    stage_name = '4. Di Meja Kabid III / Bidang III (Perencanaan, Keuangan & Pelaporan)'
                else:
                    stage_name = '4. Di Meja Waka III / Bidang III (Perencanaan, Keuangan & Pelaporan)'
                next_action = 'Penanganan Bidang III'
            elif any(k in pos_lower for k in ['waka ii', 'waka 2', 'wakil ketua ii', 'wakil ketua 2', 'kabid ii', 'kabid 2', 'kepala bidang ii', 'pendistribusian', 'pendayagunaan', 'pentasyarufan']):
                if 'kabid' in pos_lower or 'kepala bidang' in pos_lower:
                    stage_name = '4. Di Meja Kabid II / Bidang II (Penyaluran & Survey Bantuan)'
                else:
                    stage_name = '4. Di Meja Waka II / Bidang II (Penyaluran & Survey Bantuan)'
                next_action = 'Pelaksanaan Survey / Penyaluran Bantuan oleh Bidang II'
            elif any(k in pos_lower for k in ['waka i', 'waka 1', 'wakil ketua i', 'wakil ketua 1', 'kabid i', 'kabid 1', 'kepala bidang i', 'pengumpulan']):
                if 'kabid' in pos_lower or 'kepala bidang' in pos_lower:
                    stage_name = '4. Di Meja Kabid I / Bidang I (Pengumpulan)'
                else:
                    stage_name = '4. Di Meja Waka I / Bidang I (Pengumpulan)'
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
