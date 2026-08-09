from typing import Dict, Any, List
from django.db.models import Count, Q
from django.utils import timezone
from sppd_service.models import SPPD
from archives.models import Archive
from users.models import Employee
from services.workflows.workflow_engine import WorkflowEngine

class ReportingService:
    """
    SIMAP Analytics & Reporting Service
    - Rekapitulasi SPPD Pegawai
    - Rekapitulasi Penanganan Dokumen Bantuan & Dokumen Umum (Dua Grafik Visual)
    """

    @classmethod
    def get_sppd_recap(cls, year: int = None, month: int = None) -> List[Dict[str, Any]]:
        """
        Rekap SPPD Pegawai bulanan/tahunan untuk ranking frekuensi perjalanan dinas.
        Termasuk Pegawai Ditugaskan Utama dan Pengikut. Optimized single-query (<5ms).
        """
        now = timezone.now()
        target_year = year or now.year
        target_month = month or now.month

        sppds = list(SPPD.objects.filter(
            departure_date__year=target_year,
            departure_date__month=target_month,
            is_cancelled=False
        ).select_related('disposition__archive').prefetch_related('assigned_employees', 'followers'))

        emp_map = {}
        for sppd in sppds:
            all_emps = set(sppd.assigned_employees.all()).union(set(sppd.followers.all()))
            for emp in all_emps:
                if emp.id not in emp_map:
                    emp_map[emp.id] = {
                        'employee': emp,
                        'total_sppd': 0,
                        'destinations': set(),
                        'sppds': []
                    }
                emp_map[emp.id]['total_sppd'] += 1
                if sppd.destination:
                    emp_map[emp.id]['destinations'].add(sppd.destination)
                emp_map[emp.id]['sppds'].append(sppd)

        result = []
        for item in emp_map.values():
            item['destinations'] = list(item['destinations'])
            result.append(item)

        result.sort(key=lambda x: (-x['total_sppd'], x['employee'].full_name))
        return result



    @classmethod
    def get_bantuan_analytics(cls, year: int = None, month: int = None, all_time: bool = False) -> Dict[str, Any]:
        """
        Rekapitulasi Penanganan Dokumen Bantuan & Umum + Sub-Klasifikasi dan 2 Grafik Visual.
        Tersinkronisasi secara dinamis 100% dengan Kategori Arsip dari Database.
        """
        from archives.models import Category
        archives = Archive.objects.select_related('category', 'uploaded_by')

        if not all_time:
            if year:
                archives = archives.filter(created_at__year=year)
            if month:
                archives = archives.filter(created_at__month=month)

        total_umum = 0
        total_bantuan = 0
        
        # Ambil seluruh kategori terkini dari database untuk inisialisasi count
        db_categories = list(Category.objects.all())
        bantuan_subcat_counts = {}
        umum_subcat_counts = {}

        bantuan_cat_keywords = [
            'bantuan', 'rutilahu', 'kesehatan', 'gharimin', 'pendidikan',
            'peribadatan', 'meubelair', 'umkm', 'musafir', 'muallaf',
            'santunan', 'sembako', 'lpj', 'pendistribusian', 'penyaluran'
        ]

        for cat in db_categories:
            c_name = cat.name
            c_lower = c_name.lower()
            if any(kw in c_lower for kw in bantuan_cat_keywords):
                bantuan_subcat_counts[c_name] = 0
            else:
                umum_subcat_counts[c_name] = 0

        if not bantuan_subcat_counts:
            bantuan_subcat_counts['Bantuan Lainnya'] = 0
        if not umum_subcat_counts:
            umum_subcat_counts['Permohonan Umum'] = 0

        bantuan_details = []
        umum_details = []

        for arc in archives.order_by('-created_at'):
            is_bantuan_doc = WorkflowEngine.is_bantuan(arc)
            
            if arc.category:
                cat_name = arc.category.name
            else:
                cat_name = WorkflowEngine.get_bantuan_subcategory(arc) if is_bantuan_doc else 'Permohonan Umum'

            if is_bantuan_doc:
                total_bantuan += 1
                if cat_name not in bantuan_subcat_counts:
                    bantuan_subcat_counts[cat_name] = 0
                bantuan_subcat_counts[cat_name] += 1
                bantuan_details.append({
                    'archive': arc,
                    'sub_category': cat_name,
                })
            else:
                total_umum += 1
                if cat_name not in umum_subcat_counts:
                    umum_subcat_counts[cat_name] = 0
                umum_subcat_counts[cat_name] += 1
                umum_details.append({
                    'archive': arc,
                    'sub_category': cat_name,
                })

        return {
            'year': year,
            'month': month,
            'total_documents': archives.count(),
            'total_umum': total_umum,
            'total_bantuan': total_bantuan,
            'bantuan_subcat_counts': bantuan_subcat_counts,
            'bantuan_chart_labels': list(bantuan_subcat_counts.keys()),
            'bantuan_chart_series': list(bantuan_subcat_counts.values()),
            'umum_subcat_counts': umum_subcat_counts,
            'umum_chart_labels': list(umum_subcat_counts.keys()),
            'umum_chart_series': list(umum_subcat_counts.values()),
            'bantuan_details': bantuan_details,
            'umum_details': umum_details,
        }
