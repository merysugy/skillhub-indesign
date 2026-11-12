// test_translate_mock.js - Run a built translation script against a simulated
// InDesign document before delivering it.  Needs Node.js 14+.
//
//     node test_translate_mock.js Translate-EN.jsx
//
// Each entry of TRANSLATIONS becomes a paragraph with realistic variations
// (forced line breaks, non-breaking spaces, lower case set as All Caps, typed
// bullets) and the script must replace it with the right text, formatting and
// language. Synthetic edge cases are added on top: a sentence cut over several
// paragraphs, repeated texts on two pages, two labels in one paragraph, an
// anchored object, a paragraph that must not change and a lost column start.
// This tests the script's logic, not InDesign itself.
const fs = require('fs');
const file = process.argv[2];
if (!file) { console.error('usage: node test_translate_mock.js script.jsx'); process.exit(2); }
eval(fs.readFileSync(file, 'utf8').replace(/^#target.*\n/, ''));

const NORMAL = { fontStyle: 'Regular', fillColor: 'Grey' }, MARK = { fontStyle: 'Bold', fillColor: 'Blue' };
class Story {
  constructor(page, chars, K) { this.page = page; this.chars = chars; this.K = K || 1e9; this.tables = { length: 0 }; this.overflows = false; }
  charInfo(gi) { const col = Math.floor(gi / this.K); return { parentTextFrames: [{ id: 'F' + Math.floor(col / 2) }], baseline: gi % this.K }; }
  get text() { return this.chars.map(c => c.ch).join(''); }
  get paragraphs() {
    const t = this.text, b = []; let s = 0;
    for (let i = 0; i < t.length; i++) if (t[i] === '\r') { b.push([s, i]); s = i + 1; }
    if (s < t.length) b.push([s, t.length - 1]);
    return b.map(([a, z]) => this.para(a, z));
  }
  para(a, b) {
    const st = this;
    const chars = new Proxy({ length: b - a + 1, itemByRange: (x, y) => ({ texts: [st.range(a + x, a + y)] }) }, {
      get: (o, k) => (typeof k === 'string' && /^\d+$/.test(k)) ? Object.assign({}, st.chars[a + +k].fmt, st.charInfo(a + +k)) : o[k] });
    return { get contents() { return st.text.substring(a, b + 1); }, characters: chars,
             parentTextFrames: [{ parentPage: st.page, geometricBounds: [0, 0, 0, 0] }] };
  }
  range(a, b) {
    const st = this;
    return new Proxy({}, { set(o, k, v) {
      if (k === 'contents') { const f = st.chars[a].fmt; st.chars.splice(a, b - a + 1, ...[...v].map(ch => ({ ch, fmt: Object.assign({}, f) }))); }
      else for (let i = a; i <= b; i++) st.chars[i].fmt[k] = v;
      return true; } });
  }
}
const page = n => ({ name: String(n), documentOffset: n, parent: { constructor: { name: 'Spread' } } });
const run = (s, f) => [...s].map(ch => ({ ch, fmt: Object.assign({}, f) }));
const cr = () => run('\r', NORMAL);
function build(marked, o = {}) {
  const { plain, runs } = parseMarked(marked);
  let out = [...plain].map((ch, i) => ({ ch, fmt: Object.assign({}, inRuns(i, runs) ? MARK : NORMAL) }));
  if (o.softBreak) { const k = out.findIndex((c, i) => i > 10 && c.ch === ' '); if (k > 0) out[k].ch = '\n'; }
  if (o.nbsp) { const k = out.findIndex((c, i) => i > 3 && c.ch === ' '); if (k > 0) out[k].ch = '\u00A0'; }
  if (o.lower) out.forEach(c => { c.ch = c.ch.toLowerCase(); });
  if (o.prefix) out = run(o.prefix, NORMAL).concat(out);
  return out;
}

// Synthetic edge cases (texts that cannot exist in a real document)
const SYN = {
  multi: { es: 'Zqx frase cortada en tres lineas de prueba final.', en: 'Zqx sentence cut over three lines.' },
  dup: { es: 'Zqx subtitulo repetido', en: ['Zqx first', 'Zqx second'] },
  lab1: { es: 'ZQX ETIQUETA UNO', en: 'ZQX LABEL ONE' },
  lab2: { es: 'Zqx etiqueta dos', en: 'Zqx label two' },
  anch: { es: 'Zqx parrafo con objeto anclado.', en: 'Zqx paragraph with an anchored object.' },
  col1: { es: 'Zqx primer parrafo largo que llena la columna entera de texto en origen.', en: 'Zqx short first.' },
  col2: { es: 'Zqx **segundo parrafo** que empieza la columna dos.', en: 'Zqx **second paragraph** that starts column two.' },
  spaces: { es: 'Zqx cabecera  ·   con espacios', en: 'Zqx header  ·   with spaces' }
};
Object.keys(SYN).forEach(k => TRANSLATIONS.push(SYN[k]));

const stories = [], expected = [], skip = new Set(Object.keys(SYN).map(k => SYN[k].es));
TRANSLATIONS.forEach((e, n) => {
  if (skip.has(e.es)) return;
  if (e.en instanceof Array) {   // one paragraph per variant, on consecutive pages
    e.en.forEach((v, i) => { const s = new Story(page(20 + i), build(e.es).concat(cr())); stories.push(s); expected.push({ s, prefix: '', en: v }); });
    return;
  }
  const label = /^\*\*[^*]{2,15}\*\*:?\s/.test(e.es);
  const o = { softBreak: n % 3 === 0, nbsp: n % 4 === 1, lower: /^[^a-z]+$/.test(e.es) && n % 2 === 0, prefix: label ? '\u2022\t' : '' };
  const s = new Story(page(2 + (n % 9)), build(e.es, o).concat(cr()));
  stories.push(s); expected.push({ s, prefix: o.prefix, en: e.en });
});
const S = (pg, chars, K) => { const s = new Story(page(pg), chars, K); stories.push(s); return s; };
const multi = S(3, build('Zqx frase cortada en tres').concat(cr(), build('lineas de prueba'), cr(), build('final.'), cr()));
const dup9 = S(9, build(SYN.dup.es).concat(cr())), dup8 = S(8, build(SYN.dup.es).concat(cr()));
const combo = S(4, build(SYN.lab1.es).concat(run('\n', NORMAL), build(SYN.lab2.es), cr()));
const anch = S(6, build('Zqx parrafo con objeto\uFFFC anclado.').concat(cr()));
const FOREIGN = 'Zqx texto ajeno con zqx etiqueta dos dentro de una frase larga de cuerpo, que no es una etiqueta corta y que por eso no debe cambiar nunca.';
const foreign = S(5, build(FOREIGN).concat(cr()));
const p1 = build(SYN.col1.es).concat(cr());
const colS = S(2, p1.concat(build(SYN.col2.es), cr()), p1.length);
const spaces = S(1, build(SYN.spaces.es).concat(cr()));
const doc = { stories: Object.assign(stories.slice(), { length: stories.length }) };
const fakeApp = { languagesWithVendors: { length: 1, 0: { icuLocaleName: CONFIG.targetLocale } } };

const r = runTranslation(doc, fakeApp);
let fails = 0; const fail = m => { fails++; console.log('FAIL:', m); };
expected.forEach(x => {
  const { plain, runs } = parseMarked(x.en);
  // Trailing spaces of the source paragraph stay after the replaced text: they are invisible, so ignore them.
  if (x.s.text.replace(/[ \u00A0]+\r$/, '\r') !== x.prefix + plain + '\r') return fail('text: ' + JSON.stringify(x.s.text.slice(0, 60)));
  [...plain].forEach((ch, i) => {
    const f = x.s.chars[x.prefix.length + i].fmt, w = inRuns(i, runs) ? MARK : NORMAL;
    if (f.fontStyle !== w.fontStyle || f.fillColor !== w.fillColor) fail('format «' + plain.slice(0, 40) + '» pos ' + i);
    if (!f.appliedLanguage || f.appliedLanguage.icuLocaleName !== CONFIG.targetLocale) fail('language «' + plain.slice(0, 30) + '»');
  });
});
const t = s => s.text.replace(/\r$/, '');
if (t(multi) !== SYN.multi.en) fail('multi-paragraph: ' + JSON.stringify(t(multi)));
if (t(dup8) !== 'Zqx first' || t(dup9) !== 'Zqx second') fail('page order: ' + t(dup8) + ' / ' + t(dup9));
if (t(combo) !== 'ZQX LABEL ONE\nZqx label two') fail('labels in one paragraph: ' + JSON.stringify(t(combo)));
if (!/\uFFFC/.test(t(anch))) fail('anchored object lost');
if (t(foreign) !== FOREIGN) fail('unrelated paragraph changed: ' + t(foreign));
if (t(spaces) !== SYN.spaces.en) fail('spaces: ' + JSON.stringify(t(spaces)));
if (!r.breaks.some(b => /second paragraph/.test(b))) fail('lost column start not reported');
if (!r.merged.length) fail('merge not reported');
const realNotFound = r.notFound.filter(x => !/^Zqx parrafo con objeto/.test(x));
console.log('Paragraphs replaced: ' + r.replaced + ' | report: not found ' + r.notFound.length +
            ' (anchored case expected), partial ' + r.partial.length + ', merged ' + r.merged.length +
            ', lost column starts ' + r.breaks.length);
if (realNotFound.length) fail('not found: ' + realNotFound.join(' | '));
console.log(fails ? fails + ' FAILURE(S)' : 'ALL CHECKS PASSED (' + (expected.length + 8) + ' cases)');
process.exit(fails ? 1 : 0);
