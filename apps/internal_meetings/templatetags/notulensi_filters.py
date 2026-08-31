from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()

@register.filter(name='clean_notulensi')
def clean_notulensi(html_content):
    try:
        if not html_content:
            return ""

        content = str(html_content).strip()
        
        # 1. Sanitize mangled HTML tags missing opening '<' (e.g. h2>, h3>, /h2>, /h3>)
        content = re.sub(r'(?<!<)/([a-zA-Z0-9]+)>', r'</\1>', content)
        content = re.sub(r'(?<![</a-zA-Z0-9_-])\b(h[1-6]|p|div|span|strong|b|i|em|u|ol|ul|li|br)>', r'<\1>', content, flags=re.IGNORECASE)
        content = re.sub(r'<h[1-6]>\s*(?:<br\s*/?>|&nbsp;|\s*)*</h[1-6]>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<p>\s*(?:<br\s*/?>|&nbsp;|\s*)*</p>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'</?(?:span|div)[^>]*>', '', content, flags=re.IGNORECASE)

        # 2. Strip Quill UI elements and un-nest broken <ul> tags
        content = re.sub(r'<span class="ql-ui"[^>]*>.*?</span>', '', content, flags=re.DOTALL)
        content = re.sub(r'</?ul[^>]*>', '', content, flags=re.IGNORECASE)

        # Sub-bullet detection keywords
        subbullet_prefixes = (
            'rencana aksi:', 'penanggung jawab:', 'target waktu:', 'aksi:', 'pic:', 'target:',
            'tahap 1:', 'tahap 2:', 'tahap 3:', 'tahap 4:'
        )

        # 3. Fix flat/fragmented <ol> blocks
        def fix_ol(match):
            block = match.group(0)
            items = re.findall(r'<li([^>]*)>(.*?)</li>', block, re.DOTALL | re.IGNORECASE)
            if not items:
                return block

            flat_items = []
            for attrs, text in items:
                sub_parts = re.split(r'(?=<li[^>]*>)', text, flags=re.IGNORECASE)
                for part in sub_parts:
                    p_match = re.match(r'^(?:<li([^>]*)>)?(.*)$', part.strip(), re.DOTALL | re.IGNORECASE)
                    if p_match:
                        p_attrs = p_match.group(1) or attrs
                        p_text = re.sub(r'</?li[^>]*>', '', p_match.group(2), flags=re.IGNORECASE).strip()
                        if p_text:
                            flat_items.append((p_attrs, p_text))

            output_lis = []
            curr_main = None
            curr_bullets = []

            def flush():
                nonlocal curr_main, curr_bullets
                if curr_main is not None:
                    m_attrs, m_text = curr_main
                    if curr_bullets:
                        b_html = "".join([f"<li>{b_txt}</li>" for _, b_txt in curr_bullets])
                        output_lis.append(f"<li>{m_text}<ul class=\"notulensi-subbullet\">{b_html}</ul></li>")
                    else:
                        output_lis.append(f"<li>{m_text}</li>")
                    curr_main = None
                    curr_bullets = []

            for idx, (attrs, text) in enumerate(flat_items):
                clean_t = text.strip()
                lower_t = clean_t.lower()
                plain_txt = re.sub(r'<[^>]+>', '', clean_t).strip().lower()

                is_bullet = False

                if 'data-list="bullet"' in attrs or "data-list='bullet'" in attrs:
                    is_bullet = True
                elif 'ql-indent-' in attrs and 'data-list="ordered"' not in attrs:
                    is_bullet = True
                elif any(plain_txt.startswith(prefix) for prefix in subbullet_prefixes):
                    is_bullet = True
                elif clean_t.startswith('<em>') and not plain_txt.startswith(('1.', '2.', '3.', '4.', '5.')):
                    is_bullet = True
                elif curr_main is not None and (
                    'terjadi lonjakan' in lower_t or
                    'terkait persiapan' in lower_t or
                    'pembina upacara' in lower_t or
                    'tahap 1:' in lower_t or 'tahap 2:' in lower_t or 'tahap 3:' in lower_t or
                    clean_t.startswith('<strong>Arahan:') or clean_t.startswith('<strong>Tanggapan:')
                ):
                    is_bullet = True

                if is_bullet:
                    if curr_main is None:
                        curr_main = ('', clean_t)
                    else:
                        curr_bullets.append((attrs, clean_t))
                else:
                    flush()
                    curr_main = (attrs, clean_t)

            flush()
            return "<ol class=\"notulensi-ol\">" + "".join(output_lis) + "</ol>"

        content = re.sub(r'<ol[^>]*>.*?</ol>', fix_ol, content, flags=re.DOTALL)
        return mark_safe(content)
    except Exception as err:
        print("[WARN] Error rendering clean_notulensi template filter:", err)
        return mark_safe(str(html_content or ""))
