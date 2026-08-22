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
 * Global Web Audio API Melodic System Notification Chime (C5 -> G5)
 * Dual-tone audio synthesizer for interactive feedback
 */
window.playSystemNotifSound = function() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        
        const audioCtx = new AudioContext();
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
        
        // Tone 1: C5 (523.25 Hz)
        const osc1 = audioCtx.createOscillator();
        const gain1 = audioCtx.createGain();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(523.25, audioCtx.currentTime);
        gain1.gain.setValueAtTime(0.12, audioCtx.currentTime);
        gain1.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.35);
        
        osc1.connect(gain1);
        gain1.connect(audioCtx.destination);
        osc1.start(audioCtx.currentTime);
        osc1.stop(audioCtx.currentTime + 0.35);

        // Tone 2: G5 (783.99 Hz) - Starts 80ms later
        const osc2 = audioCtx.createOscillator();
        const gain2 = audioCtx.createGain();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(783.99, audioCtx.currentTime + 0.08);
        gain2.gain.setValueAtTime(0.16, audioCtx.currentTime + 0.08);
        gain2.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.55);
        
        osc2.connect(gain2);
        gain2.connect(audioCtx.destination);
        osc2.start(audioCtx.currentTime + 0.08);
        osc2.stop(audioCtx.currentTime + 0.55);
    } catch (e) {
        console.warn('AudioContext sound prevented by browser policy:', e);
    }
};
