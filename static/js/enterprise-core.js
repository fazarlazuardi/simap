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
 * Global Web Audio API Dual-Tone Chime Synthesizer (C5 -> G5)
 * Dual-tone audio playback for system notifications and interactive feedback.
 */
let _sharedAudioContext = null;

function getSharedAudioContext() {
    if (!_sharedAudioContext) {
        const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
        if (AudioCtxClass) {
            _sharedAudioContext = new AudioCtxClass();
        }
    }
    if (_sharedAudioContext && _sharedAudioContext.state === 'suspended') {
        _sharedAudioContext.resume().catch(function() {});
    }
    return _sharedAudioContext;
}

// Automatically unlock AudioContext on any user gesture (click, touch, keydown)
if (typeof window !== 'undefined') {
    ['click', 'touchstart', 'keydown'].forEach(function(evtType) {
        document.addEventListener(evtType, function unlockAudioOnGesture() {
            getSharedAudioContext();
            document.removeEventListener(evtType, unlockAudioOnGesture);
        }, { once: true });
    });
}

window.playSystemNotifSound = function() {
    try {
        const ctx = getSharedAudioContext();
        if (!ctx) return;

        // Ensure AudioContext is active
        if (ctx.state === 'suspended') {
            ctx.resume();
        }

        const now = ctx.currentTime;

        // Tone 1: C5 (523.25 Hz)
        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(523.25, now);
        gain1.gain.setValueAtTime(0.35, now);
        gain1.gain.exponentialRampToValueAtTime(0.0001, now + 0.4);

        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start(now);
        osc1.stop(now + 0.4);

        // Tone 2: G5 (783.99 Hz) - Starts 90ms later
        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(783.99, now + 0.09);
        gain2.gain.setValueAtTime(0.4, now + 0.09);
        gain2.gain.exponentialRampToValueAtTime(0.0001, now + 0.65);

        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(now + 0.09);
        osc2.stop(now + 0.65);
    } catch (e) {
        console.warn('Notification audio chime playback error:', e);
    }
};

/**
 * Global Enterprise Popup Toast Notification (Top-Right Screen Corner)
 * Displays a sleek toast banner with audio chime on the top-right
 */
window.showEnterpriseNotificationToast = function(title, body, icon = 'info', linkUrl = '') {
    if (window.playSystemNotifSound) {
        window.playSystemNotifSound();
    }
    
    if (window.Swal) {
        Swal.fire({
            toast: true,
            position: 'bottom-end',
            icon: icon,
            title: title,
            text: body,
            showConfirmButton: false,
            timer: 6000,
            timerProgressBar: true,
            didOpen: (toast) => {
                toast.addEventListener('mouseenter', Swal.stopTimer);
                toast.addEventListener('mouseleave', Swal.resumeTimer);
                if (linkUrl) {
                    toast.style.cursor = 'pointer';
                    toast.addEventListener('click', () => {
                        window.location.href = linkUrl;
                    });
                }
            }
        });
    }
};


// SILKY SMOOTH ENTERPRISE MODULE NAVIGATION INTERCEPTOR
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('module-page-container');
    if (container) {
        container.style.opacity = '1';
    }

    // Intercept internal link clicks for smooth fade
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        const target = link.getAttribute('target');

        // Only intercept standard internal navigation links
        if (href && href.startsWith('/') && !href.startsWith('//') && target !== '_blank' && !href.includes('#') && !link.hasAttribute('download')) {
            const container = document.getElementById('module-page-container');
            const progressBar = document.getElementById('htmx-progress-bar');

            if (progressBar) {
                progressBar.classList.remove('finished');
                progressBar.classList.add('loading');
            }

            if (container) {
                container.style.transition = 'opacity 120ms ease-out, transform 120ms ease-out';
                container.style.opacity = '0.7';
                container.style.transform = 'translateY(2px)';
            }
        }
    });
});
