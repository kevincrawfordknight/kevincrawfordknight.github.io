#!/usr/bin/env python3
"""Build the Empire of Liberty web excerpt: one HTML page per chapter, with Prev/Next buttons
that log each click to a Google Sheet through an Apps Script web app.

Usage:  python3 web_build.py manuscript.docx OUTDIR [LAST_CHAPTER]
Writes OUTDIR/index.html (title page + Prolog), OUTDIR/01.html ... OUTDIR/NN.html,
OUTDIR/reader.css and OUTDIR/reader.js. Upload OUTDIR as writing/empire-of-liberty/.
Uses the same document-passage list and chapter rules as docx_to_latex.py.
"""
import html
import os
import re
import sys

import docx

import docx_to_latex as D

BOOK = 'Empire of Liberty'
AUTHOR = 'Kevin Knight'


def page_name(num):
    return 'index.html' if num == 0 else '%02d.html' % num


def tidy(chars):
    """Dashes as the book sets them: '--', en and em dashes become an em dash with no
    spaces around it (a digit-to-digit en dash stays). chars: list of (char, fmt)."""
    out = []
    i, n = 0, len(chars)
    while i < n:
        c, f = chars[i]
        nxt = chars[i + 1][0] if i + 1 < n else ''
        is_dd = c == '-' and nxt == '-'
        if c in '–—' or is_dd:
            prevc = chars[i - 1][0] if i else ''
            after = chars[i + (2 if is_dd else 1)][0] if i + (2 if is_dd else 1) < n else ''
            if c == '–' and prevc.isdigit() and after.isdigit():
                out.append((c, f))
                i += 1
                continue
            while out and out[-1][0] == ' ':
                out.pop()
            out.append(('—', f))
            i += 2 if is_dd else 1
            while i < n and chars[i][0] == ' ':
                i += 1
            continue
        out.append((c, f))
        i += 1
    return out


def to_html(chars, keep_spaces=False):
    """Group characters by format and wrap them in HTML tags."""
    groups = []
    for c, f in tidy(chars):
        if groups and groups[-1][0] == f:
            groups[-1][1].append(c)
        else:
            groups.append([f, [c]])
    parts = []
    for (b, it, u, sup, red), cs in groups:
        s = ''.join(cs)
        if red:   # the hidden words never reach the page, only black bars of their length
            s = re.sub(r'\S+', lambda m: '<span class="redact">%s</span>' % ('█' * len(m.group())), s)
        else:
            s = html.escape(s, quote=False)
            if keep_spaces:
                s = re.sub(r'(?<=\S) {2,}', lambda m: ' ' * len(m.group()), s)
        if sup:
            s = '<sup>' + s + '</sup>'
        if u:
            s = '<u>' + s + '</u>'
        if it:
            s = '<em>' + s + '</em>'
        if b:
            s = '<strong>' + s + '</strong>'
        parts.append(s)
    return ''.join(parts)


def chapter_body(paras, docs, pindex, title):
    """HTML for one chapter's paragraphs."""
    bold_share, bi_share = D.chapter_profile(paras)
    first_text = next((p.text.strip() for p in paras if p.text.strip()), '')
    oslo = first_text.startswith('Oslo') or bold_share >= 0.95
    invert = oslo and bi_share >= 0.9
    entries, pending_blank = [], False
    for p in paras:
        if D.has_image(p):
            pending_blank = False
            entries.append({'kind': 'image'})
            continue
        if not p.text.strip():
            pending_blank = True
            continue
        chars = D.para_chars(p)
        is_doc = pindex[id(p._p)] in docs
        if invert:
            chars = [(c, (b, (not it) if b else it, u, s, r)) for c, (b, it, u, s, r) in chars]
        if is_doc:
            chars = [(c, (b, False, u, s, r)) for c, (b, it, u, s, r) in chars]
        for uchars, tabs, _end, spaces in D.split_units(chars):
            if pending_blank and entries:
                entries.append({'kind': 'blank', 'doc': is_doc})
            pending_blank = False
            nb = sum(1 for c, f in uchars if f[0] and not c.isspace())
            nv = sum(1 for c, f in uchars if not c.isspace())
            entries.append({'kind': 'text', 'html': to_html(uchars, keep_spaces=is_doc), 'tabs': tabs,
                            'spaces': spaces, 'doc': is_doc,
                            'sans': oslo and nv and nb / nv >= 0.5})
    out, in_doc = [], False
    for k, e in enumerate(entries):
        doc = e.get('doc', False) and e['kind'] != 'image'
        # a blank line between two document paragraphs stays inside the document
        if e['kind'] == 'blank':
            nxt = entries[k + 1] if k + 1 < len(entries) else None
            doc = in_doc and nxt is not None and nxt.get('doc')
        if doc and not in_doc:
            out.append('      <div class="doc">')
        if not doc and in_doc:
            out.append('      </div>')
        in_doc = doc
        pad = '        ' if in_doc else '      '
        if e['kind'] == 'blank':
            out.append(pad + '<p class="break">&nbsp;</p>')
        elif e['kind'] == 'image':
            out.append(pad + '<p class="figure"><img src="../empire-house.png" alt=""></p>')
        else:
            cls = []
            style = ''
            if in_doc:
                em = 1.5 * max(e['tabs'] - 1, 0) + 0.5 * e['spaces']
                if em:
                    style = ' style="padding-left:%.1fem"' % em
            else:
                if e['tabs'] == 0:
                    cls.append('noindent')
                elif e['tabs'] >= 2:
                    style = ' style="text-indent:%.1fem"' % (1.6 * e['tabs'])
                if e['sans']:
                    cls.append('sans')
            c = ' class="%s"' % ' '.join(cls) if cls else ''
            out.append('%s<p%s%s>%s</p>' % (pad, c, style, e['html']))
    if in_doc:
        out.append('      </div>')
    return '\n'.join(out), oslo


PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="../../styles.css">
  <link rel="stylesheet" href="reader.css">
</head>
<body>
  <header>
    <nav class="navbar">
      <ul>
        <li><a href="../index.html">Home</a></li>
        <li><a href="../books.html">Books</a></li>
        <li><a href="../stories.html">Stories</a></li>
        <li><a href="../zines.html">Zines</a></li>
        <li><a href="../contact.html">Contact</a></li>
      </ul>
    </nav>
  </header>

  <main class="reader">
{top}
    <section class="chapter{oslo}">
      <h2 class="chapter-title">{heading}</h2>
{body}
    </section>

    <nav class="pager" aria-label="Chapters">
{buttons}
    </nav>
    <p class="pager-message" id="pager-message" aria-live="polite"></p>
  </main>

  <footer>
    <p>&copy; 2026 <a href="../../index.html" class="footer-link">{author}</a></p>
  </footer>

  <script src="reader.js"></script>
</body>
</html>
'''

TITLEPAGE = '''    <div class="titlepage">
      <h1 class="book-title">{book}</h1>
      <p class="book-author">{author}</p>
    </div>
'''

RUNNING = '''    <p class="running-title"><a href="index.html">{book}</a></p>
'''

CSS = '''/* Empire of Liberty reader pages */
.reader {
  max-width: 38rem;
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.125rem;
  line-height: 1.65;
  color: #1a1a1a;
}
.titlepage { text-align: center; margin: 3rem 0 4rem; }
.titlepage .book-title { font-size: 2.4rem; letter-spacing: 0.02em; margin: 0 0 0.5rem; }
.titlepage .book-author {
  font-size: 1.2rem; font-style: italic; margin: 0 0 1.5rem; color: #444;
  text-align: center; text-indent: 0;
}
.reader p.running-title {
  text-align: center; text-indent: 0; margin: 0 0 2rem;
  font-variant: small-caps; letter-spacing: 0.06em; font-size: 0.95rem;
}
.running-title a { color: #555; text-decoration: none; }
.chapter { margin: 0; }
/* Chapter headings: Arial, never italic */
.chapter-title {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 1.3rem;
  font-weight: bold;
  font-style: normal;
  margin: 1.6rem 0 1.1rem;
}
/* Book paragraphs: no gap, first-line indent */
.reader p { margin: 0; text-indent: 1.6em; text-align: left; }
.reader p.noindent { text-indent: 0; }
.reader p.break { text-indent: 0; }
.reader em { font-style: italic; }
.reader strong { font-weight: bold; }
/* Oslo chapters and other bold sans passages */
.reader p.sans { font-family: Arial, Helvetica, sans-serif; font-size: 1.02rem; }
/* Documents: emails, faxes, memos, dossiers, forms, screens, FORTRAN */
.doc {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 1rem;
  line-height: 1.5;
  margin: 0 0 0 1.5em;
}
.doc p { text-indent: 0; font-style: normal; }
.reader .doc p { text-indent: 0; }
.redact { background: #000; color: #000; letter-spacing: -0.05em; user-select: none; }
.figure { text-align: center; text-indent: 0; }
.figure img { max-width: 80%; height: auto; }
/* Prev / Next */
.pager {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin: 3rem 0 0;
}
.pager button {
  font: inherit;
  font-size: 1rem;
  padding: 0.6rem 1.4rem;
  cursor: pointer;
  border: 1px solid #888;
  border-radius: 6px;
  background: #f4f4f4;
  color: #1a1a1a;
}
.pager button:hover { background: #e8e8e8; }
.pager .spacer { flex: 1; }
.reader p.pager-message {
  text-align: center;
  font-style: italic;
  color: #555;
  min-height: 1.5em;
  margin: 2rem 0 0;
  text-indent: 0;
}
'''

JS = '''// Prev / Next buttons. Each click is logged to the Google Sheet as e.g. "Next18"
// (Next pressed at the end of chapter 18) or "Prev5" (Prev pressed on chapter 5).
(function () {
  var ENDPOINT = "%(endpoint)s";
  var LAST_MESSAGE = "%(last_message)s";

  function record(button) {
    var url = ENDPOINT + "?button=" + encodeURIComponent(button) + "&t=" + Date.now();
    try {
      // keepalive lets the request finish even though the page is about to change
      fetch(url, { mode: "no-cors", keepalive: true });
      return true;
    } catch (e) {
      var beacon = new Image();
      beacon.src = url;
      return false;
    }
  }

  document.querySelectorAll(".pager button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var sent = record(btn.dataset.track);
      var href = btn.dataset.href;
      if (href) {
        // the Image fallback needs a moment before the page goes away
        if (sent) { window.location.href = href; }
        else { setTimeout(function () { window.location.href = href; }, 250); }
      } else {
        document.querySelector(".pager").style.display = "none";
        document.getElementById("pager-message").textContent = LAST_MESSAGE;
      }
    });
  });
})();
'''

REDIRECT = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Knight | Writing | Empire of Liberty</title>
  <meta http-equiv="refresh" content="0; url=empire-of-liberty/index.html">
  <link rel="canonical" href="empire-of-liberty/index.html">
</head>
<body>
  <p><a href="empire-of-liberty/index.html">Empire of Liberty</a></p>
</body>
</html>
'''


def main(src, outdir, last_chapter=20,
         endpoint='https://script.google.com/macros/s/AKfycbwZAsRWp2eQyloWH76fN7ZSl0ClH6aHDweOr1c8NWfakeockrIks0dOrN5TiRFtM080/exec',
         last_message='Empire of Liberty coming in 2026!'):
    d = docx.Document(src)
    P = d.paragraphs
    docs, _ = D.doc_paragraphs(P)
    pindex = {id(p._p): k for k, p in enumerate(P)}
    first_head = next(i for i, p in enumerate(P) if D.heading_text(p))
    chapters, num = [], -1
    for idx in range(first_head, len(P)):
        p = P[idx]
        h = D.heading_text(p)
        if h is not None:
            num = 0 if h == 'Prolog' else num + 1
            if num > last_chapter:
                break
            chapters.append({'num': num, 'title': h, 'paras': []})
        else:
            chapters[-1]['paras'].append(p)
    os.makedirs(outdir, exist_ok=True)
    plain = lambda s: to_html([(c, (False,) * 5) for c in s])
    for k, ch in enumerate(chapters):
        n = ch['num']
        body, oslo = chapter_body(ch['paras'], docs, pindex, ch['title'])
        heading = plain(ch['title']) if n == 0 else '%d. %s' % (n, plain(ch['title']))
        here = 'Prolog' if n == 0 else str(n)
        buttons = []
        if n > 0:
            buttons.append('      <button type="button" data-track="Prev%s" data-href="%s">Prev</button>'
                           % (here, page_name(chapters[k - 1]['num'])))
        else:
            buttons.append('      <span class="spacer"></span>')
        nxt = page_name(chapters[k + 1]['num']) if k + 1 < len(chapters) else ''
        buttons.append('      <button type="button" data-track="Next%s"%s>Next</button>'
                       % (here, ' data-href="%s"' % nxt if nxt else ''))
        title = 'Knight | Writing | %s' % BOOK + ('' if n == 0 else ' | %d' % n)
        top = (TITLEPAGE if n == 0 else RUNNING).format(book=BOOK, author=AUTHOR)
        page = PAGE.format(title=title, top=top, heading=heading, body=body,
                           oslo=' oslo' if oslo else '', buttons='\n'.join(buttons), author=AUTHOR)
        with open(os.path.join(outdir, page_name(n)), 'w', encoding='utf-8') as f:
            f.write(page)
    with open(os.path.join(outdir, 'reader.css'), 'w', encoding='utf-8') as f:
        f.write(CSS)
    with open(os.path.join(outdir, 'reader.js'), 'w', encoding='utf-8') as f:
        f.write(JS % {'endpoint': endpoint, 'last_message': last_message})
    with open(os.path.join(outdir, '..', 'empire-of-liberty.html'), 'w', encoding='utf-8') as f:
        f.write(REDIRECT)
    print('pages: %d (Prolog + chapters 1-%d)' % (len(chapters), chapters[-1]['num']))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 20)
