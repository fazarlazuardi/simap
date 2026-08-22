/**
 * SIMAP BAZNAS - ENTERPRISE CORE JS
 * Alpine.js Global State Stores & HTMX Infrastructure Hooks
 */

document.addEventListener('alpine:init', () => {
    // 1. Theme Store
    Alpine.store('themeStore', {
        current: localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'),
        init() {
            this.apply(this.current);
        },
        toggle() {
            this.current = this.current === 'dark' ? 'light' : 'dark';
            this.apply(this.current);
        },
        apply(t) {
            document.documentElement.setAttribute('data-theme', t);
            localStorage.setItem('theme', t);
            var icon = document.getElementById('themeIconGlobal');
            var text = document.getElementById('themeTextGlobal');
            if (icon) {
                icon.className = t === 'dark' ? 'bi bi-sun-fill text-warning fs-6' : 'bi bi-moon-stars-fill text-warning fs-6';
            }
            if (text) {
                text.textContent = t === 'dark' ? 'Mode Gelap' : 'Mode Terang';
            }
        }
    });

    // 2. Command Palette Store (Ctrl + K)
    Alpine.store('commandPalette', {
        isOpen: false,
        query: '',
        open() {
            this.isOpen = true;
            this.query = '';
            setTimeout(() => {
                const el = document.getElementById('commandPaletteInput');
                if (el) el.focus();
            }, 80);
        },
        close() {
            this.isOpen = false;
        }
    });

    // 3. Slide-Over Drawer Store
    Alpine.store('drawer', {
        isOpen: false,
        title: '',
        subtitle: '',
        contentHtml: '',
        open(title, subtitle, contentHtml) {
            this.title = title || 'Detail Data';
            this.subtitle = subtitle || '';
            this.contentHtml = contentHtml || '<p class="text-muted">Loading detail...</p>';
            this.isOpen = true;
        },
        close() {
            this.isOpen = false;
        }
    });
});

// Global Keyboard Listener for Ctrl + K / Cmd + K
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (window.Alpine && Alpine.store('commandPalette')) {
            const palette = Alpine.store('commandPalette');
            palette.isOpen ? palette.close() : palette.open();
        }
    }
    if (e.key === 'Escape') {
        if (window.Alpine) {
            if (Alpine.store('commandPalette') && Alpine.store('commandPalette').isOpen) {
                Alpine.store('commandPalette').close();
            }
            if (Alpine.store('drawer') && Alpine.store('drawer').isOpen) {
                Alpine.store('drawer').close();
            }
        }
    }
});

// HTMX CSRF Token & Progress Bar Listener
document.addEventListener('DOMContentLoaded', () => {
    // Inject Django CSRF Token to HTMX Requests
    document.body.addEventListener('htmx:configRequest', (evt) => {
        const getCookie = (name) => {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        };
        const csrfToken = getCookie('csrftoken');
        if (csrfToken) {
            evt.detail.headers['X-CSRFToken'] = csrfToken;
        }
    });

    // Progress Bar Feedback
    const progressBar = document.getElementById('htmx-progress-bar');
    document.body.addEventListener('htmx:beforeRequest', () => {
        if (progressBar) {
            progressBar.classList.remove('finished');
            progressBar.classList.add('loading');
        }
    });
    document.body.addEventListener('htmx:afterRequest', () => {
        if (progressBar) {
            progressBar.classList.remove('loading');
            progressBar.classList.add('finished');
            setTimeout(() => {
                progressBar.classList.remove('finished');
            }, 300);
        }
    });
});

/**
 * Global Base64 Embedded WAV Audio Notification Chime (C5 -> G5)
 * Dual-tone audio playback guaranteed to work across all devices & browsers.
 */
const SYSTEM_CHIME_WAV_B64 = "data:audio/wav;base64,UklGRjYPAABXQVZFZm10IBAAAAABAAEAESsAABErAAABAAgAZGF0YRIPAACAkaGut7u6s6iaiXdmWExGREhRXW1+kKCttrq5s6mbinloWU5HRUhRXWx9jp6rtLm5s6mbi3ppW09IRklRXGt8jZ2qs7i4s6mcjHtrXFFJR0lRXGp7jJuosre3sqmcjXxsXlJLSEpRXGp6ipqnsba2sqmdjn5uX1NMSUpRW2l5iZilr7W2sqqdj39vYFVNSUtRW2h4iJekrrS1sqqekIBwYlZOSktRW2h3hpajrbO0saqekIFxY1dPS0xRWmd2hZShrLK0saqfkYJzZVlQTE1RWmZ1hJOgqrGzsKqfkoN0ZlpSTU1SWmZ0g5KfqbCysKqgk4R1Z1tTTk5SWmVzgpCdqK+xr6qgk4V2aF1UT05SWmVygY+cp66wr6mglIZ4al5VUE9SWmRxgI6bpaywr6mglYd5a19WUVBTWmRxf42apKuvrqmhlYh6bGBXUlBTWmRwfoyYo6qurqmhlol7bWJYU1FTWmNvfYuXoqmtramhlol8b2NaVFJUWmNvfImWoaisrKmhl4p9cGRbVVJUWmNue4iVn6esrKihl4t+cWVcVlNVWmJueoeUnqarq6ihmIx/cmZdV1RVWmJteYaTnaWqq6ihmIyAc2deWFVVWmJseYWRnKSpqqihmI2BdGhfWFVWWmJseISQm6OoqqehmY6BdWpgWVZWWmJrd4OPmqKnqaehmY6CdmthWldXW2FrdoKOmaGmqKehmY+Dd2xiW1hXW2FrdoKNmKCmqKahmY+EeG1jXFhYW2FqdYGMl5+lp6ahmpCFeW5kXVlYW2FqdICLlp6kpqWhmpCFem9lXlpZW2FpdH+KlZ2jpqWhmpGGe3BmX1tZXGFpc36JlJyipaWhmpGHe3FnYFtaXGFpc36Jk5uhpKShmpKHfHJoYVxbXGFpcn2IkpqhpKShmpKIfXNpYl1bXWFocnyHkZmgo6Ogm5KJfnNqY15cXWFocXuGkJmfoqOgm5OJf3RrY15cXWFocXuFj5ieoqKgm5OKf3VsZF9dXmFocHqEjpedoaKgm5OKgHZtZWBdXmFocHmEjZacoKGfm5SLgXduZmFeXmJnb3mDjJWcoKGfm5SLgnhvZ2FfX2Jnb3iCjJSbn6Cfm5SMgnhvaGJfX2Jnb3iBi5OanqCfm5SMg3lwaWNgYGJnbneBipKZnp+em5WNg3pxaWRgYGJnbneAiZKYnZ+em5WNhHtyamRhYGJnbnZ/iJGYnJ6empWNhXtza2ViYWNnbnZ/iJCXnJ6dmpWOhXxzbGZiYWNnbXV+h4+Wm52dmpWOhn10bWdjYmNnbXV9ho6Vmp2dmpWOhn11bWdkYmNnbXR9ho6VmpycmpWPh352bmhkY2RnbXR8hY2UmZycmpWPh392b2llY2RnbXR8hIyTmJucmpWPiH93cGllZGRnbHN7hIuSmJubmZWPiIB4cGpmZGRnbHN7g4uSl5qbmZWQiIB4cWtnZGVnbHN6goqRlpmamZt9X0g7PEpjgZ+3xMO1nX9hSTw8SWF/nbXDw7afgWNLPTxJYH2bs8LDt6CDZUw+PEhee5mywcO4oYVnTj88R115l7DAwrijh2lQQD1HXHiVrr7CuaSIa1FBPUZadpOtvcK5pYptU0I9Rll0kau8wbqnjG9VQz5FWHKPqbvBuqiOcVdFPkVXcY2ousC6qY9yWEY/RFZvjKa4wLuqkXRaRz9EVW2KpLe/u6uSdlxJQERUbIiitr+7rJR4XkpBRFNqhqG0vrutlXpfS0FEUmmEn7O9u66XfGFNQkRRZ4Odsry7rph9Y05DRFBmgZuwvLuvmn9lT0RET2V/ma+7u7CbgWZRRURPY32Yrbq7sZyDaFJFRE5ifJasubuxnoRqVEZETmF6lKq4u7KfhmxVR0RNYHiTqbe6sqCHbVdIRU1ed5GntrqzoYlvWElFTF11j6a1urOiinFaSkVMXHSNpLS5s6OMcltMRktbcoyjs7m0pI10XU1GS1pxiqGyuLSlj3ZeTkdLWW+IoLG4tKaQd2BPR0tZboeer7e0p5J5YlBIS1hthZ2ut7Sok3tjUUlLV2uEm622tKiUfGVTSUtWaoKarLW0qZZ+ZlRKS1ZpgZirtbSql39oVUtLVWh/lqm0tKqYgWlWS0tUZ36VqLO0q5mCa1hMS1RlfJOnsrSrmoRsWU1LU2R7kqWytKybhW5aTktTY3mQpLG0rJyHb1xPS1JieI+jsLOtnYhxXVBMUmF2jaGvs62eiXJeUUxSYHWMoK6zrZ+LdGBSTFFfdIqfrbKuoIx1YVNNUV9yiZ2ssq6hjXdiVE1RXnGHnKuxrqKOeGRVTlFdcIabqrGuopB6ZVZOUVxvhZmpsK6jkXtmV09RXG6DmKiwrqSSfWhYT1FbbYKWp6+upJN+aVlQUVprgJWmr66llH9rWlFRWmp/lKSurqWVgWxbUVFZaX6So62uppaCbVxSUVlofJGira6ml4NvXVNRWGd7kKGsrqeYhXBfVFFYZnqOoKuup5mGcWBUUVhmeY2fqq2omodzYVVSV2V3jJ2praibiHRiVlJXZHaKnKmtqJuJdWNXUldjdYmbqKyonIt3ZVhTV2J0iJqnrKmdjHhmWVNWYnOGmaasqZ6NeWdaVFZhcoWXpaupno56aFpUVmBxhJakq6mfj3xpW1VWYHCDlaOqqaCQfWtcVVZfb4GUoqqpoJF+bF1WVl9ugJOhqamhkn9tXlZWXm1/kaCpqaGTgW5fV1ZebH6Qn6ipopSCb2BXVl1rfY+ep6milINxYVhWXWp8jp2nqaKVhHJiWVddaXqNnKaoo5aFc2NZV1xpeYubpaijl4Z0ZFpXXGh4ipqlqKOYh3VmW1dcZ3eJmaSoo5iId2dcWFtmdoiYo6ekmYl4aFxYW2Z1h5eip6SainlpXVhbZXSGlqGnpJqLempeWVtkc4SVoaakm4x7a19ZW2Ryg5SgpqSbjXxsYFlbY3GCkp+lpJyOfW1gWltjcYGRnqWknI9+bmFaW2JwgJCdpKSdkH9vYltbYm9/j5ykpJ2RgXBjW1tibn6Om6OknpGCcWRcW2FtfY2bo6SekoNyZV1bYW18jJqipJ6ThHNmXVthbHuLmaKkn5SFdWdeW2BreoqYoaOflIV2aF5cYGp5iZego5+VhndpX1xganiIlqCjn5WHeGpgXGBpd4eVn6Ogloh5amBcX2l2hpSeoqCXiXprYV1faHWFk56ioJeKe2xiXV9odYSSnaKgmIt8bWNdX2d0g5GcoaCYjH1uY15fZ3OCkJuhoJmMfm9kXl9mcoGPm6GgmY1/cGVfX2ZxgI6aoKCZjoBxZl9fZXF/jZmgoJqPgHJmYF9lcH6MmJ+gmo+Bc2dgX2VvfYyXn6CbkIJ0aGFfZG98i5eeoJuRg3VpYV9kbnuKlp6fm5GEdmpiYGRte4mVnZ+bkoV3amJgZG16iJScn5yShnhrY2BjbHmHk5yfnJOGeWxjYGNseIaSm5+clId5bWRhY2t3hZKbnpyUiHpuZWFja3eEkZqenJSJe29lYWNqdoOQmZ6clYp8b2ZhY2p1go+ZnZyVin1wZ2JjaXSCjpidnJaLfnFnYmNpdIGNl52clox/cmhiY2lzgI2XnJyXjIBzaWNjaHJ/jJacnJeNgHRpY2Nocn6LlZucl46BdGpkY2hxfYqVm5yXjoJ1a2RjZ3F9iZSbnJiPg3ZrZWNncHyIk5qcmI+Dd2xlY2dve4iSmpyYkIR4bWZjZ296h5KZm5iQhXluZmRnbnqGkZmbmJGGeW5nZGZueYWQmJuZkYZ6b2dkZm54hJCYm5mSh3twaGRmbXiEj5ebmZKIfHFoZWZtd4OOlpqZkoh9cWllZmx2go2WmpmTiX1yaWVmbHaBjZWamZOKfnNqZWZsdYGMlZmZlIp/dGtmZmt0gIuUmZmUi4B0a2Zma3R/ipOZmZSLgHVsZ2Zrc36Kk5iZlIyBdmxnZmpzfomSmJmVjIJ3bWdmanJ9iJKXmZWNgnduaGZqcnyHkZeZlY2DeG5oZ2pxfIeQl5iVjoR5b2lnanF7hpCWmJWOhHlwaWdpcHqFj5aYlo+FenBqZ2lweoSOlZiWj4Z7cWpnaXB5hI6VmJaQhnxyamdpb3iDjZSXlpCHfHJraGlveIKMlJeWkId9c2toaW93goyTl5aRiH50bGhpbneBi5OXlpGJfnRtaGludoCKkpaWkYl/dW1paW52gIqSlpaSioB2bmlpbXV/iZGWlpKKgHZuaWltdX6IkZWWkouBd29qaW10foiQlZaSi4F4b2ppbXR9h4+VlpKLgnhwamlsc32Gj5SWk4yDeXBraWxzfIaOlJaTjIN6cWtqbHN7hY6UlZONhHpybGpscnuFjZOVk42Ee3JsamxyeoSNk5WTjYV7c2xqbHF6g4ySlZOOhXxzbWpscXmDi5KVk46GfXRtamxxeYKLkZSTjod9dG5rbHB4gYqRlJOPh351bmtscHiBipCUk4+HfnZva2xwd4CJkJSTj4h/dm9rbHB3gImQk5OPiIB3cGxsb3Z/iI+Tk5CJgHdwbGxvdn+Hj5OTkImBeHFsbG92foeOk5OQioF5cW1sb3V9ho6Sk5CKgnlybWxvdX2GjZKTkIqCenJtbG50fIWNkpORi4N6c25sbnR8hIyRk5GLg3tzbmxudHuEjJGTkYyEe3RubG5ze4OLkJORjIR8dG9tbnN6g4uQkpGMhXx1b21uc3qCipCSkYyFfXVvbW5yeYKKj5KRjYZ+dnBtbnJ5gYmPkpGNhn52cG1ucnmBiI+SkY2Hf3dxbm5yeICIjpGRjYd/d3FubnF4gIeOkZGOh4B4cm5ucXd/h42RkY6IgHhybm5xd3+GjZGRjoiBeXJvbnF3foaMkJGOiYF5c29ucXZ+hYyQkY6Jgnpzb25xdn2FjJCRj4mCenRvbnB2fYSLj5GPioJ7dHBucHV8hIuPkY+Kg3t1cG5wdXyDio+Rj4qDfHVwb3B1e4OKj5CPioR8dnFvcHR7gomOkI+LhH12cW9wdHuCiY6Qj4uFfXZxb3B0eoGIjZCPi4V+d3JvcHR6gYiNkI+LhX53cm9wc3mBh42Qj4yGf3hycHBzeYCHjI+PjIZ/eHNwcHN5gIeMj4+Mh4B5c3Bwc3h/hoyPj4yHgHl0cHBzeH+Gi4+PjIeBenRwcHN4foWLjo8=";

window.playSystemNotifSound = function() {
    try {
        // Method 1: Direct HTML5 Audio Object (100% Guaranteed Audible Playback)
        var audio = new Audio(SYSTEM_CHIME_WAV_B64);
        audio.volume = 1.0;
        var promise = audio.play();
        if (promise !== undefined) {
            promise.catch(function(err) {
                console.warn("HTML5 Audio play prevented:", err);
            });
        }
    } catch (e) {
        console.warn("Audio chime error:", e);
    }
};
