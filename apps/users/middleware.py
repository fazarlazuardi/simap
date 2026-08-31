from django.core.cache import cache
from django.utils import timezone
from users.models import User
import time
from colorama import init, Fore, Style

init(autoreset=True)

class ActiveUserMiddleware:
    """
    Middleware untuk mencatat aktivitas & status Online/Offline pengguna secara real-time.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now()
            cache_key = f'user_last_seen_{request.user.pk}'
            # Cache status aktif presisi 60 detik (1 menit)
            try:
                cache.set(cache_key, now, 60)
            except Exception:
                pass

            # Simpan ke Database setiap 30 detik sekali agar akurat
            last_seen_db = getattr(request.user, 'last_seen', None)
            if not last_seen_db or (now - last_seen_db).total_seconds() > 30:
                User.objects.filter(pk=request.user.pk).update(last_seen=now)

        response = self.get_response(request)
        return response


class CloudflareTrafficMonitorMiddleware:
    """
    Middleware untuk memantau, mendeteksi, dan menampilkan seluruh log lalu lintas
    serta percobaan akses mencurigakan (brute force/force endpoint scan)
    langsung di terminal konsol secara real-time dengan format visual berwarna.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = int((time.time() - start_time) * 1000)

        # 1. Ambil Data Header Cloudflare / Remote Address
        client_ip = request.META.get('HTTP_CF_CONNECTING_IP', request.META.get('REMOTE_ADDR', '127.0.0.1'))
        country = request.META.get('HTTP_CF_IPCOUNTRY', 'LOC')
        user = request.user.username if getattr(request, 'user', None) and request.user.is_authenticated else 'ANON'
        method = request.method
        path = request.get_full_path()
        status = response.status_code

        # 2. Pewarnaan & Flagging Anomali
        if status >= 500:
            tag = f"{Fore.RED}{Style.BRIGHT}[SERVER-ERR]"
            status_color = f"{Fore.RED}{status}"
        elif status in [401, 403]:
            tag = f"{Fore.YELLOW}{Style.BRIGHT}[ACCESS-DENIED]"
            status_color = f"{Fore.YELLOW}{status}"
        elif status == 404:
            tag = f"{Fore.MAGENTA}[NOT-FOUND/SCAN]"
            status_color = f"{Fore.MAGENTA}{status}"
        elif status >= 400:
            tag = f"{Fore.RED}[BAD-REQUEST]"
            status_color = f"{Fore.RED}{status}"
        elif status >= 300:
            tag = f"{Fore.YELLOW}[REDIRECT]"
            status_color = f"{Fore.YELLOW}{status}"
        else:
            tag = f"{Fore.GREEN}[CF-INSPECT]"
            status_color = f"{Fore.CYAN}{status}"

        # 3. Print Live Log ke Terminal Server
        print(f"{tag} [{Fore.LIGHTBLUE_EX}{country}{Fore.RESET}] [{Fore.WHITE}{client_ip}{Fore.RESET}] {Fore.LIGHTYELLOW_EX}{user}{Fore.RESET} | {method} {path} -> {status_color} {Fore.RESET}({duration}ms)")

        return response

