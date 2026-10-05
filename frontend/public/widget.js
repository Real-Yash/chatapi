/* ChatAPI embed widget — served at /widget.js.
 * Source of truth: widget/widget.js (copy it here after changes). */
(function () {
  'use strict';

  // Resolve the <script> tag that loaded this file.
  var script =
    document.currentScript ||
    (function () {
      var scripts = document.getElementsByTagName('script');
      return scripts[scripts.length - 1];
    })();

  var slug = script.getAttribute('data-agent') || script.getAttribute('data-slug') || '';
  var apiBase = script.getAttribute('data-api') || 'http://localhost:8000';
  var webBase = script.getAttribute('data-base') || 'http://localhost:3000';

  // Normalise trailing slashes so URL joins are predictable.
  function stripTrailingSlash(s) {
    return String(s).replace(/\/+$/, '');
  }
  apiBase = stripTrailingSlash(apiBase);
  webBase = stripTrailingSlash(webBase);

  if (!slug) {
    console.error('[chatapi-widget] Missing data-agent attribute. Usage: <script src="widget.js" data-agent="demo-bakery">');
    return;
  }

  // Prevent double initialisation if snippet is pasted twice.
  if (window.__chatapiWidgetInit && window.__chatapiWidgetInit[slug]) return;
  window.__chatapiWidgetInit = window.__chatapiWidgetInit || {};
  window.__chatapiWidgetInit[slug] = true;

  var DEFAULT_COLOR = '#10b981';
  var isOpen = false;
  var bubbleEl = null;
  var panelEl = null;
  var iframeEl = null;
  var iframeLoaded = false;

  var CHAT_SVG =
    '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>' +
    '</svg>';
  var CLOSE_SVG =
    '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">' +
    '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>' +
    '</svg>';

  function injectStyles() {
    var css =
      '#chatapi-bubble-{SLUG} { position: fixed; bottom: 24px; right: 24px; width: 60px; height: 60px; ' +
      'border-radius: 50%; border: none; cursor: pointer; z-index: 2147483000; display: flex; ' +
      'align-items: center; justify-content: center; box-shadow: 0 8px 24px rgba(0,0,0,0.25); ' +
      'transition: transform 0.2s ease, box-shadow 0.2s ease; padding: 0; }' +
      '#chatapi-bubble-{SLUG}:hover { transform: scale(1.06); box-shadow: 0 12px 32px rgba(0,0,0,0.3); }' +
      '#chatapi-bubble-{SLUG}:focus-visible { outline: 3px solid #fff; outline-offset: 2px; }' +
      '#chatapi-panel-{SLUG} { position: fixed; bottom: 100px; right: 24px; width: 380px; height: 600px; ' +
      'max-width: calc(100vw - 32px); max-height: calc(100vh - 140px); ' +
      'border-radius: 16px; overflow: hidden; z-index: 2147482999; background: #fff; ' +
      'box-shadow: 0 16px 48px rgba(0,0,0,0.28); display: none; flex-direction: column; ' +
      'transform-origin: bottom right; }' +
      '#chatapi-panel-{SLUG}.chatapi-open { display: flex; animation: chatapi-pop-{SLUG} 0.22s ease; }' +
      '#chatapi-panel-{SLUG} iframe { width: 100%; height: 100%; border: 0; flex: 1; background: #fff; }' +
      '@keyframes chatapi-pop-{SLUG} { from { opacity: 0; transform: scale(0.96) translateY(8px); } ' +
      'to { opacity: 1; transform: scale(1) translateY(0); } }' +
      '@media (max-width: 480px) { ' +
      '#chatapi-bubble-{SLUG} { bottom: 16px; right: 16px; }' +
      '#chatapi-panel-{SLUG} { left: 12px; right: 12px; bottom: 88px; width: auto; height: 70vh; ' +
      'max-height: calc(100dvh - 120px); border-radius: 14px; } }';

    // Scope ids per-agent so multiple widgets can coexist on one page.
    css = css.split('{SLUG}').join(slug.replace(/[^a-zA-Z0-9-_]/g, '-'));

    var style = document.createElement('style');
    style.type = 'text/css';
    style.setAttribute('data-chatapi-widget', slug);
    style.appendChild(document.createTextNode(css));
    document.head.appendChild(style);
  }

  function chatUrl() {
    return webBase + '/c/' + encodeURIComponent(slug) + '?embed=true';
  }

  function buildDom() {
    var safeId = slug.replace(/[^a-zA-Z0-9-_]/g, '-');

    bubbleEl = document.createElement('button');
    bubbleEl.id = 'chatapi-bubble-' + safeId;
    bubbleEl.type = 'button';
    bubbleEl.setAttribute('aria-label', 'Open chat');
    bubbleEl.setAttribute('aria-expanded', 'false');
    bubbleEl.style.background = DEFAULT_COLOR;
    bubbleEl.innerHTML = CHAT_SVG;

    panelEl = document.createElement('div');
    panelEl.id = 'chatapi-panel-' + safeId;
    panelEl.setAttribute('role', 'dialog');
    panelEl.setAttribute('aria-label', 'Chat with us');

    iframeEl = document.createElement('iframe');
    iframeEl.title = 'Chat';
    iframeEl.setAttribute('allow', 'clipboard-write; microphone');
    iframeEl.setAttribute('loading', 'lazy');
    // src is set lazily on first open so the embed costs nothing until used.
    panelEl.appendChild(iframeEl);

    document.body.appendChild(panelEl);
    document.body.appendChild(bubbleEl);

    bubbleEl.addEventListener('click', toggle);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen) close();
    });
  }

  function open() {
    if (!iframeLoaded) {
      iframeEl.src = chatUrl();
      iframeLoaded = true;
    }
    panelEl.classList.add('chatapi-open');
    bubbleEl.innerHTML = CLOSE_SVG;
    bubbleEl.setAttribute('aria-label', 'Close chat');
    bubbleEl.setAttribute('aria-expanded', 'true');
    isOpen = true;
  }

  function close() {
    panelEl.classList.remove('chatapi-open');
    bubbleEl.innerHTML = CHAT_SVG;
    bubbleEl.setAttribute('aria-label', 'Open chat');
    bubbleEl.setAttribute('aria-expanded', 'false');
    isOpen = false;
  }

  function toggle() {
    if (isOpen) close();
    else open();
  }

  // Fetch the agent so the bubble matches its brand colour.
  // Falls back to DEFAULT_COLOR when offline, unknown slug, or CORS-blocked.
  function applyBrandColor() {
    var candidates = [
      apiBase + '/api/agents/' + encodeURIComponent(slug),
      apiBase + '/agents/' + encodeURIComponent(slug)
    ];

    function pickColor(data) {
      if (!data || typeof data !== 'object') return null;
      return (
        data.primaryColor ||
        data.primary_color ||
        data.color ||
        (data.theme && data.theme.primaryColor) ||
        (data.config && data.config.primaryColor) ||
        null
      );
    }

    function tryFetch(i) {
      if (i >= candidates.length) return;
      fetch(candidates[i], { headers: { Accept: 'application/json' } })
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          var color = pickColor(data) || pickColor(data.agent) || pickColor(data.data);
          if (typeof color === 'string' && /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(color)) {
            bubbleEl.style.background = color;
          }
        })
        .catch(function () {
          tryFetch(i + 1);
        });
    }

    if (typeof fetch === 'function') tryFetch(0);
  }

  function init() {
    injectStyles();
    buildDom();
    applyBrandColor();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
