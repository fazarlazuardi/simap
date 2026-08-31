import html

try:
    import nh3
    HAS_NH3 = True
except ImportError:
    HAS_NH3 = False

ALLOWED_TAGS = {'b', 'i', 'u', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li', 'span', 'blockquote'}
ALLOWED_ATTRIBUTES = {}

def sanitize_user_input(content: str, allow_basic_html: bool = True) -> str:
    """
    Membersihkan tag JavaScript, event handler (onerror, onload, dll)
    dan skrip berbahaya dari input teks bebas pengguna.
    """
    if not content:
        return ""

    if not isinstance(content, str):
        return content

    if HAS_NH3 and allow_basic_html:
        return nh3.clean(
            content,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            strip_comments=True
        )
    
    if not allow_basic_html:
        return html.escape(content)

    # Basic Fallback
    cleaned = content.replace('<script', '&lt;script').replace('</script>', '&lt;/script&gt;')
    cleaned = cleaned.replace('javascript:', '').replace('onerror=', '').replace('onload=', '')
    return cleaned
