import os
import glob
import json
from django.apps import AppConfig

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        try:
            from users.models import SystemSetting

            # Auto-detect OAuth JSON file if GOOGLE_OAUTH_CLIENT_CONFIG is missing
            current_config = SystemSetting.get_value('GOOGLE_OAUTH_CLIENT_CONFIG', '')
            if not current_config:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                possible_patterns = [
                    os.path.join(base_dir, "*.json"),
                    os.path.join(base_dir, "config", "*.json"),
                    os.path.join(base_dir, "credentials", "*.json"),
                ]
                for pattern in possible_patterns:
                    for filepath in glob.glob(pattern):
                        filename = os.path.basename(filepath).lower()
                        if "oauth" in filename or "client" in filename or "credential" in filename or "gdrive" in filename:
                            try:
                                with open(filepath, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    if 'installed' in data or 'web' in data:
                                        SystemSetting.set_setting('GOOGLE_OAUTH_CLIENT_CONFIG', json.dumps(data))
                                        print(f"[AUTO-OAUTH] Loaded OAuth Client JSON from {filepath}")
                                        break
                            except Exception:
                                pass
        except Exception:
            pass

        try:
            import users.signals
        except Exception:
            pass
