// GLOBAL LOADER: navigation + fetch + XHR + button clicks
(() => {
  const LOADER_ID = 'app-loader';
  let el = document.getElementById(LOADER_ID);
  if (!el) {
    el = document.createElement('div');
    el.id = LOADER_ID;
    el.innerHTML = `
      <div class="loader-card">
        <div class="spinner" role="progressbar" aria-label="Loading"></div>
        <img class="gif" alt="Loading" src="" />
        <div class="text">Loading…</div>
      </div>
    `;
    document.documentElement.appendChild(el);
  }

  const state = { pending: 0 };

  function setText(msg){ el.querySelector('.text').textContent = msg || 'Loading…'; }
  function setGif(src){
    if (src) {
      el.dataset.mode = 'gif';
      el.querySelector('.gif').src = src;
    } else {
      el.dataset.mode = 'spinner';
      el.querySelector('.gif').src = '';
    }
  }
  // Allow opt-in GIF via <body data-loader-gif="/web_files/assets/loader.gif">
  const bodyGif = (document.body && document.body.dataset && document.body.dataset.loaderGif) || '';
  if (bodyGif) setGif(bodyGif);

  function show(msg){ if (msg) setText(msg); el.classList.add('active'); el.setAttribute('aria-busy','true'); }
  function hide(){ el.classList.remove('active'); el.removeAttribute('aria-busy'); setText('Loading…'); }

  const Loader = {
    show, hide,
    setText, setGif,
    pending(){ return state.pending; },
    increment(){ state.pending++; show(); },
    decrement(){
      state.pending = Math.max(0, state.pending - 1);
      if (state.pending === 0) hide();
    },
    with(promiseOrFn, msg){
      show(msg);
      try {
        const p = (typeof promiseOrFn === 'function') ? Promise.resolve().then(promiseOrFn) : promiseOrFn;
        return p.finally(hide);
      } catch (e) { hide(); throw e; }
    }
  };
  window.AppLoader = Loader;

  // --- Wrap fetch with a reference counter ---
  const _fetch = window.fetch.bind(window);
  window.fetch = (...args) => {
    Loader.increment();
    return _fetch(...args).finally(() => Loader.decrement());
  };

  // --- Wrap XMLHttpRequest as well (if any pages still use XHR) ---
  if (window.XMLHttpRequest) {
    const _open = XMLHttpRequest.prototype.open;
    const _send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(...args){ this.__track = true; return _open.apply(this, args); };
    XMLHttpRequest.prototype.send = function(...args){
      if (this.__track) {
        Loader.increment();
        this.addEventListener('loadend', () => Loader.decrement(), { once: true });
      }
      return _send.apply(this, args);
    };
  }

  // --- Show on same-origin link clicks ---
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href]');
    if (!a) return;
    const href = a.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
    let url;
    try { url = new URL(href, window.location.href); } catch { return; }
    if (url.origin === window.location.origin) {
      show('Loading page…');
    }
  }, true);

  // --- Show on form submissions (navigation or AJAX) ---
  document.addEventListener('submit', () => { show('Submitting…'); }, true);

  // --- Programmatic navigations ---
  const _assign = window.location.assign.bind(window.location);
  const _replace = window.location.replace.bind(window.location);
  Object.defineProperties(window.location, {
    assign: { value: (url) => { show('Loading…'); _assign(url); } },
    replace: { value: (url) => { show('Loading…'); _replace(url); } }
  });

  // --- Button clicks: show quickly; auto-hide if nothing starts ---
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn || btn.dataset.noLoader !== undefined) return; // opt-out with data-no-loader
    // show but cancel if no navigation/fetch starts within 800ms
    show('Loading…');
    const startPending = state.pending;
    setTimeout(() => {
      const nothingStarted = (state.pending === startPending) && !document.hidden;
      if (nothingStarted) hide();
    }, 800);
  }, true);

  // --- Fallback: show during unload so user sees feedback immediately ---
  window.addEventListener('beforeunload', () => { show('Loading…'); });

  // --- Initial page ready -> hide (if something left it on) ---
  window.addEventListener('DOMContentLoaded', () => { hide(); });
})();
