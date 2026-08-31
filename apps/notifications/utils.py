from django.core.cache import cache

POVS = ['', 'waka_4', 'kabid_4', 'waka_2', 'kabid_2', 'waka_1', 'waka_3', 'sdm', 'front_office', 'fo', 'admin', 'ketua']

def invalidate_user_notif_cache(user_id):
    """
    Membersihkan seluruh cache notifikasi untuk user tertentu
    di seluruh variasi active_pov.
    """
    if not user_id:
        return
    for pov in POVS:
        cache_key = f"notif_ctx_u{user_id}_pov{pov}"
        try:
            cache.delete(cache_key)
        except Exception:
            pass
