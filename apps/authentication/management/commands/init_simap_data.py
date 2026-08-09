import os
import shutil
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Inisialisasi database fisik MariaDB/MySQL simap dan direktori statis/media."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== Memulai Inisialisasi Data SIMAP BAZNAS ==="))
        base_dir = settings.BASE_DIR

        # 1. Pastikan direktori media & staticfiles ada
        media_dir = base_dir / 'media'
        staticfiles_dir = base_dir / 'staticfiles'
        media_dir.mkdir(parents=True, exist_ok=True)
        staticfiles_dir.mkdir(parents=True, exist_ok=True)
        self.stdout.write(self.style.SUCCESS(f"Direktori media & staticfiles terverifikasi di: {media_dir}"))

        # 2. Inisialisasi basis data jika MySQLdb tersedia
        try:
            import MySQLdb
            conn = MySQLdb.connect(
                host=getattr(settings, 'DATABASES', {}).get('default', {}).get('HOST', '127.0.0.1'),
                user=getattr(settings, 'DATABASES', {}).get('default', {}).get('USER', 'root'),
                passwd=getattr(settings, 'DATABASES', {}).get('default', {}).get('PASSWORD', ''),
                port=int(getattr(settings, 'DATABASES', {}).get('default', {}).get('PORT', 3306))
            )
            cur = conn.cursor()
            cur.execute("CREATE DATABASE IF NOT EXISTS `simap` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cur.execute("SHOW DATABASES LIKE 'baznas';")
            has_baznas = cur.fetchone()

            if has_baznas:
                cur.execute("SHOW TABLES FROM `baznas`")
                tbls = [r[0] for r in cur.fetchall()]
                cur.execute("USE `simap`;")
                cur.execute("SET FOREIGN_KEY_CHECKS=0;")
                for t in tbls:
                    cur.execute(f"CREATE TABLE IF NOT EXISTS `simap`.`{t}` LIKE `baznas`.`{t}`;")
                    cur.execute(f"INSERT IGNORE INTO `simap`.`{t}` SELECT * FROM `baznas`.`{t}`;")
                cur.execute("SET FOREIGN_KEY_CHECKS=1;")
                conn.commit()
                self.stdout.write(self.style.SUCCESS("Database 'simap' berhasil diselaraskan dari 'baznas'."))
            else:
                self.stdout.write(self.style.WARNING("Database 'baznas' tidak ditemukan. Database 'simap' baru telah dibuat."))

            conn.close()
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Info inisialisasi database: {e}"))

        self.stdout.write(self.style.SUCCESS("=== Inisialisasi SIMAP BAZNAS Selesai Sempurna ==="))
