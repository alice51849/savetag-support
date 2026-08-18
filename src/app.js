/* SaveTag support site — locale renderer. No dependencies, no network, no tracking. */
(function () {
  'use strict';

  var I18N = window.SAVETAG_I18N;
  var PAGE = document.body.getAttribute('data-page');   // 's' = support, 'p' = privacy
  var MAIL = 'hourstag.app@gmail.com';
  var UPDATED = '2026-08-18';
  var RTL = { 'ar-SA': 1, 'he': 1, 'ur-PK': 1 };
  var STORE_KEY = 'savetag.lang';

  var ORDER = Object.keys(I18N);

  /* ---------- locale resolution ----------
     Unknown locales fall back to the closest shipped language, then en-US, so
     ?lang=<any App Store locale> always renders a readable page. */
  function normalise(tag) {
    if (!tag) return null;
    tag = String(tag).replace('_', '-');
    var i, lower = tag.toLowerCase();
    for (i = 0; i < ORDER.length; i++) if (ORDER[i].toLowerCase() === lower) return ORDER[i];
    var base = lower.split('-')[0];
    var alias = {
      en: 'en-US', pt: 'pt-BR', es: 'es-ES', fr: 'fr-FR', de: 'de-DE',
      nl: 'nl-NL', ar: 'ar-SA', bn: 'bn-BD', gu: 'gu-IN', kn: 'kn-IN', ml: 'ml-IN',
      mr: 'mr-IN', or: 'or-IN', pa: 'pa-IN', ta: 'ta-IN', te: 'te-IN', ur: 'ur-PK',
      sl: 'sl-SI', nb: 'no', nn: 'no', iw: 'he', in: 'id', tl: 'en-US'
    };
    if (base === 'zh') {
      if (/hant|tw|hk|mo/.test(lower)) return I18N['zh-Hant'] ? 'zh-Hant' : null;
      return I18N['zh-Hans'] ? 'zh-Hans' : (I18N['zh-Hant'] ? 'zh-Hant' : null);
    }
    if (base === 'pt') return I18N['pt-PT'] && /pt$/.test(lower) ? 'pt-PT' : (I18N['pt-BR'] ? 'pt-BR' : null);
    if (base === 'es') return I18N['es-MX'] && /mx|us|ar|cl|co|pe|ve/.test(lower) ? 'es-MX' : (I18N['es-ES'] ? 'es-ES' : null);
    if (base === 'fr') return I18N['fr-CA'] && /ca/.test(lower) ? 'fr-CA' : (I18N['fr-FR'] ? 'fr-FR' : null);
    if (base === 'en') {
      if (I18N['en-GB'] && /gb|ie|in|za|nz/.test(lower)) return 'en-GB';
      if (I18N['en-AU'] && /au/.test(lower)) return 'en-AU';
      if (I18N['en-CA'] && /ca/.test(lower)) return 'en-CA';
      return 'en-US';
    }
    if (alias[base] && I18N[alias[base]]) return alias[base];
    for (i = 0; i < ORDER.length; i++) if (ORDER[i].toLowerCase().split('-')[0] === base) return ORDER[i];
    return null;
  }

  function param() {
    var m = /[?&]lang=([^&#]+)/.exec(location.search) || /^#lang=(.+)$/.exec(location.hash);
    return m ? decodeURIComponent(m[1]) : null;
  }

  function stored() {
    try { return localStorage.getItem(STORE_KEY); } catch (e) { return null; }
  }

  function pick() {
    var langs = [param(), stored()].concat(navigator.languages || [navigator.language]);
    for (var i = 0; i < langs.length; i++) {
      var hit = normalise(langs[i]);
      if (hit) return hit;
    }
    return 'en-US';
  }

  /* ---------- tiny DOM helpers ---------- */
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }

  /* ---------- render ---------- */
  function render(code) {
    var t = I18N[code];
    if (!t) { code = 'en-US'; t = I18N[code]; }
    var page = t[PAGE];
    var dir = RTL[code] ? 'rtl' : 'ltr';

    document.documentElement.lang = t.l || code;
    document.documentElement.dir = dir;
    document.title = page.title;
    var md = document.querySelector('meta[name="description"]');
    if (md) md.setAttribute('content', page.meta);

    /* brand + nav */
    document.getElementById('brandSub').textContent = t.tag;
    var nav = document.getElementById('nav');
    clear(nav);
    [['index.html', t.nav[0], 's'], ['privacy.html', t.nav[1], 'p']].forEach(function (item) {
      var a = el('a', null, item[1]);
      a.href = item[0] + '?lang=' + encodeURIComponent(code);
      if (item[2] === PAGE) a.setAttribute('aria-current', 'page');
      nav.appendChild(a);
    });
    document.getElementById('langLabel').textContent = t.lang;

    /* hero */
    document.getElementById('badge').textContent = page.eyebrow;
    document.getElementById('h1').textContent = page.h1;
    document.getElementById('lead').textContent = page.lead;

    var body = document.getElementById('body');
    var extra = document.getElementById('heroExtra');
    clear(body);
    clear(extra);

    if (PAGE === 's') {
      var chips = el('ul', 'chips');
      page.chips.forEach(function (c) { chips.appendChild(el('li', null, c)); });
      extra.appendChild(chips);

      var h2 = el('h2', 'sect', page.faqT);
      h2.appendChild(el('span', 'rule'));
      body.appendChild(h2);

      var faq = el('div', 'faq');
      page.faq.forEach(function (qa, i) {
        var d = el('details', 'q');
        var s = el('summary');
        s.appendChild(el('span', 'n', String(i + 1)));
        s.appendChild(el('span', null, qa[0]));
        d.appendChild(s);
        d.appendChild(el('div', 'a', qa[1]));
        faq.appendChild(d);
      });
      body.appendChild(faq);
    } else {
      extra.appendChild(el('p', 'updated', page.upd + ' ' + UPDATED));

      var vow = el('section', 'card vow');
      vow.appendChild(el('strong', null, page.vow));
      body.appendChild(vow);

      page.sec.forEach(function (sec) {
        var c = el('section', 'card policy');
        c.appendChild(el('h3', null, sec[0]));
        c.appendChild(el('p', null, sec[1]));
        body.appendChild(c);
      });
    }

    /* contact */
    var contact = el('section', 'card contact');
    contact.appendChild(el('h2', null, page.cT));
    contact.appendChild(el('p', null, page.cL));
    var btn = el('a', 'btn', page.cB || MAIL);
    btn.href = 'mailto:' + MAIL + '?subject=' + encodeURIComponent('SaveTag — ' + code);
    contact.appendChild(btn);
    var m = el('a', 'mail', MAIL);
    m.href = 'mailto:' + MAIL;
    contact.appendChild(m);
    body.appendChild(contact);

    document.getElementById('foot').textContent = t.foot;

    /* keep the switcher in sync */
    var sel = document.getElementById('lang');
    if (sel.value !== code) sel.value = code;
  }

  /* ---------- boot ---------- */
  var sel = document.getElementById('lang');
  ORDER.forEach(function (code) {
    var o = el('option', null, I18N[code].n);
    o.value = code;
    sel.appendChild(o);
  });
  sel.addEventListener('change', function () {
    var code = sel.value;
    try { localStorage.setItem(STORE_KEY, code); } catch (e) {}
    render(code);
    /* make the chosen language shareable / bookmarkable */
    if (history.replaceState) {
      history.replaceState(null, '',
        location.pathname + '?lang=' + encodeURIComponent(code));
    }
    window.scrollTo(0, 0);
  });

  render(pick());
})();
