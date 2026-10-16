#!/usr/bin/env python3
"""Convert the Empire of Liberty manuscript (.docx) to a paperback LaTeX file.

Usage:  python3 docx_to_latex.py manuscript.docx empire_of_liberty.tex
Needs:  pip install python-docx
Then compile with xelatex (real Arial headings) or pdflatex (Helvetica headings), twice.
"""
import re
import sys

import docx
from docx.oxml.ns import qn

# --------------------------------------------------------------------------- characters

SIMPLE = {
    '\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
    '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
    '\u2212': r'$-$', '\u03c6': r'$\varphi$', '\u00b2': r'\textsuperscript{2}',
    '\u00a9': r'\textcopyright{}', '\u25a1': r'$\square$', '\u2026': r'\dots{}',
}
OPENERS = set(' \t([{')


class Tok:
    """One piece of output: LaTeX source, the run format, and a kind tag."""
    __slots__ = ('tex', 'fmt', 'kind')

    def __init__(self, tex, fmt, kind='text'):
        self.tex, self.fmt, self.kind = tex, fmt, kind


def tokenize(chars, epigraph=False):
    """chars: list of (char, fmt). Returns list of Tok with quotes and dashes converted."""
    out = []
    n = len(chars)
    i = 0
    prev_char = None  # last source character emitted (for quote direction)

    def drop_trailing_spaces():
        while out and out[-1].kind == 'text' and out[-1].tex == ' ':
            out.pop()

    while i < n:
        c, f = chars[i]
        nxt = chars[i + 1][0] if i + 1 < n else None
        # ---- dashes: "--", en dash, em dash  ->  --- with no spaces around it
        is_dd = (c == '-' and nxt == '-')
        is_epi = (epigraph and c == '-' and i == 0 and nxt == ' ')
        if c in '\u2013\u2014' or is_dd or is_epi:
            prevc = chars[i - 1][0] if i > 0 else ''
            after = chars[i + (2 if is_dd else 1)][0] if i + (2 if is_dd else 1) < n else ''
            if c == '\u2013' and prevc.isdigit() and after.isdigit():
                out.append(Tok('--', f))           # numeric range keeps an en dash
                i += 1
                prev_char = c
                continue
            drop_trailing_spaces()
            i += 2 if is_dd else 1
            if not is_epi:
                while i < n and chars[i][0] == ' ':
                    i += 1
            else:
                i += 1  # drop the single space after the attribution hyphen
            # \textemdash, never ---: a line may break after the dash only when a word
            # follows, so a closing quote can never be pushed to the next line.
            follow = chars[i][0] if i < n else ''
            if follow.isalnum() or follow in '\u201c\u2018(':
                out.append(Tok('\\textemdash\\allowbreak{}', f, 'dash'))
            else:
                out.append(Tok('\\textemdash{}', f, 'dash'))
            prev_char = '-'
            continue
        # ---- quotes
        if c in '\u201c\u201d\u2018\u2019"\'':
            if c == '\u201c':
                tex, kind = '``', 'q2'
            elif c == '\u201d':
                tex, kind = "''", 'q2'
            elif c == '\u2018':
                tex, kind = '`', 'q1'
            elif c == '\u2019':
                tex, kind = "'", 'q1'
            else:
                opening = prev_char is None or prev_char in OPENERS
                if c == '"':
                    tex, kind = ('``' if opening else "''"), 'q2'
                else:
                    tex, kind = ('`' if opening else "'"), 'q1'
            if out and out[-1].kind in ('q1', 'q2') and out[-1].kind != kind:
                out.append(Tok(r'\,', f, 'sep'))   # e.g. ''\,' instead of a ligature tangle
            out.append(Tok(tex, f, kind))
            prev_char = c
            i += 1
            continue
        # ---- everything else
        if c in SIMPLE:
            tex = SIMPLE[c]
        elif c == '@' and prev_char and prev_char.isalnum() and nxt and nxt.isalnum():
            tex = r'@\allowbreak{}'
        elif c in '<>,' and prev_char == c:
            tex = '{}' + c                          # avoid T1 ligatures << >> ,,
        elif c == '\t':
            tex = ' '
        else:
            tex = c
        out.append(Tok(tex, f))
        prev_char = c
        i += 1
    return out


def render(tokens):
    """Group tokens by format and wrap them in LaTeX commands."""
    groups = []
    for t in tokens:
        if groups and groups[-1][0] == t.fmt:
            groups[-1][1].append(t.tex)
        else:
            groups.append([t.fmt, [t.tex]])
    parts = []
    for (b, it, u, sup, red), texs in groups:
        s = ''.join(texs)
        if red:
            words = [w for w in s.split(' ') if w]
            s = ' '.join(r'\redact{%s}' % w for w in words)
            if texs and texs[0] == ' ':
                s = ' ' + s
            if texs and texs[-1] == ' ':
                s = s + ' '
        if sup:
            s = r'\textsuperscript{' + s + '}'
        if u:
            s = r'\underline{' + s + '}'
        if it:
            s = r'\textit{' + s + '}'
        if b:
            s = r'\textbf{' + s + '}'
        parts.append(s)
    return ''.join(parts)

# --------------------------------------------------------------------------- docx access


def run_fmt(r):
    rpr = r._r.rPr
    red = False
    if rpr is not None:
        h = rpr.find(qn('w:highlight'))
        s = rpr.find(qn('w:shd'))
        red = (h is not None and h.get(qn('w:val')) == 'black') or \
              (s is not None and (s.get(qn('w:fill')) or '').upper() == '000000')
    return (bool(r.bold), bool(r.italic), bool(r.underline), bool(r.font.superscript), red)


def para_chars(p):
    chars = []
    for r in p.runs:
        f = run_fmt(r)
        chars.extend((c, f) for c in r.text)
    return chars


def has_image(p):
    return bool(p._p.findall('.//' + qn('w:drawing'))) or bool(p._p.findall('.//' + qn('w:pict')))


HEAD = re.compile(r'^\s*(#|\d+)\.\s+(.*\S)\s*$')


def heading_text(p):
    if p.text.startswith('\t'):
        return None
    m = HEAD.match(p.text)
    return m.group(2) if m else None


def split_units(chars):
    """Split a paragraph at soft line breaks and at interior tabs (both are new paragraphs
    in this manuscript). Returns list of (chars, leading_tabs, endmark, leading_spaces)."""
    lines, cur = [], []
    for c, f in chars:
        if c == '\n':
            lines.append(cur)
            cur = []
        else:
            cur.append((c, f))
    lines.append(cur)
    units = []
    for li, line in enumerate(lines):
        # leading whitespace
        k = 0
        tabs = 0
        spaces = 0
        while k < len(line) and line[k][0] in ' \t':
            tabs += line[k][0] == '\t'
            spaces += line[k][0] == ' '
            k += 1
        line = line[k:]
        if li > 0:
            tabs = max(tabs, 1)  # a line after a soft break is an ordinary new paragraph
        # closing mark: tabs then a white square at the end
        s = ''.join(c for c, _ in line)
        endmark = False
        m = re.search(r'\t+\u25a1\s*$', s)
        if m:
            line = line[:m.start()]
            endmark = True
        # trailing whitespace
        while line and line[-1][0] in ' \t':
            line.pop()
        # interior tabs: paragraph breaks
        pieces, cur = [], []
        for c, f in line:
            if c == '\t' and cur:
                pieces.append(cur)
                cur = []
            elif c == '\t':
                continue
            else:
                cur.append((c, f))
        pieces.append(cur)
        for pi, piece in enumerate(pieces):
            while piece and piece[0][0] == ' ':
                piece = piece[1:]
            if not piece:
                continue
            units.append((piece, tabs if pi == 0 else 1,
                          endmark and pi == len(pieces) - 1, spaces if pi == 0 else 0))
    return units

# --------------------------------------------------------------------------- documents
# Passages the characters read as documents -- emails, faxes, Agency memos, dossiers,
# forms, intercept transcripts, screens, printouts, FORTRAN -- are set in Arial
# (\sffamily), upright, as an indented block. Bold is kept; italics are dropped.
# Each entry: (regex for the first paragraph, regex for the last paragraph or None for a
# one-paragraph passage). Paragraph text is matched after leading tabs and spaces.
# To add or remove a passage, edit this list and re-run.
A = "['’]"   # either apostrophe
DOC_PASSAGES = [
    (r'National Security Agency phone intercept, January 7', r'Carter: I' + A + 'll confer with my Secretary'),  # Prolog
    (r'Name: Vivian Wu$', r'Notes: Uncontrolled workplace violence'),        # ch 1 spreadsheet
    (r'1972\. A year of reflection and rebirth', None),                        # ch 9 lobby screen
    (r'This work falls under confidentiality regulations', r'Authorized signature'),  # ch 18 form
    (r'From: chairman@alicent\.cn', r'No one embodies these values'),          # ch 21 email
    (r'Name: Deacon Wang', r'\(2\) The longest I have stayed awake'),          # ch 21 profile
    (r'FORTRAN 73 Programming Manual$', r'Chapter 3\. Constants, Variables'),  # ch 26 manual
    (r'Cherry Xu \(HR\) requests', r'\[A\]ccept, or \[D\]ecline'),             # ch 35 screen
    (r'William Ye owes Vivian Wu', r'Constantine Zhang owes Vivian Wu'),       # ch 37 ledger
    (r'From: cherry\.xu@alicent\.cn', r'(As most of you are aware|Please save the date)'),  # ch 39, 63
    (r'\(F\)uckable, \(N\)ot fuckable', None),                                  # ch 40 screen
    (r'Revive the company' + A + 's start-up spirit', None),                   # ch 42 email
    (r'Subject: Disruption newsletter', r'People cry if you kill a baby panda'),  # ch 48
    (r'National Security Agency phone intercept\.$', r'Dillinger: That' + A + 's the spirit'),  # ch 49
    (r'SUBJECT: Carson Hawke', r'PREPARED BY:'),                                # ch 51 dossier
    (r'C\s+Electric Brain Cash 1973', r'C\s+PS\. I am working'),                # ch 59 FORTRAN header
    (r'From: hr@alicent\.cn', r'(As most of you are aware, the Board|The company sent out|'
                              r'Dear Classmate: We remind|Be great, be you)'),  # ch 74 emails
    (r'Name, National ID #, Gender', r'Vivian Wu, 0001688816681'),             # ch 78 spreadsheet
    (r'Birth name: Janet Szwitzky', r'Unit evaluation:'),                       # ch 80 dossier
    (r'Name, position sought, phone', None),                                    # ch 84 form
    (r'Previous employer\?', None),
    (r'May we contact this employer\?', None),
    (r'Reason for leaving\?', None),
    (r'Name: Brenda Mann\.', r'Employer: University of Nova Scotia'),          # ch 95 fax
    (r'FROM: C0092314', r'It' + A + 's not Bill'),                              # ch 99 faxes
    (r'Date: June 16, 1971', r'5\. Agency personnel will not'),                 # ch 106 memo
]
DOC_PASSAGES = [(re.compile(s), re.compile(e) if e else None) for s, e in DOC_PASSAGES]
DOC_MAX = 40   # a passage longer than this many paragraphs means a broken end pattern


def doc_paragraphs(P):
    """Indexes of paragraphs that belong to a document passage, plus a report."""
    inside, report = set(), []
    i = 0
    while i < len(P):
        t = P[i].text.lstrip(' \t')
        hit = next(((s, e) for s, e in DOC_PASSAGES if s.match(t)), None)
        if not hit:
            i += 1
            continue
        s, e = hit
        j = i
        if e is not None:
            while j < len(P) and j - i < DOC_MAX and not e.match(P[j].text.lstrip(' \t')):
                j += 1
            if j >= len(P) or j - i >= DOC_MAX:
                report.append('WARNING: no end found for document passage "%s"' % t[:50])
                i += 1
                continue
        inside.update(range(i, j + 1))
        report.append((i, j, t[:60]))
        i = j + 1
    return inside, report

# --------------------------------------------------------------------------- template


PREAMBLE = r'''% =====================================================================
%  TITLE -- AUTHOR
%  Paperback edition, 5.5 x 8.5 in trim.
%  Compile with XeLaTeX for real Arial chapter headings
%  (or with pdflatex, which uses Helvetica, its metric twin). Run twice.
%  Needs house.png in the same folder.
% =====================================================================
\documentclass[10pt,twoside,openright]{memoir}

% ---------- trim size and margins
\setstocksize{8.5in}{5.5in}
\settrimmedsize{\stockheight}{\stockwidth}{*}
\settrims{0pt}{0pt}
\setlrmarginsandblock{0.8in}{0.6in}{*}   % inner (spine), outer
\setulmarginsandblock{0.75in}{0.8in}{*}  % top, bottom
\setheadfoot{\baselineskip}{2\baselineskip}
\setheaderspaces{*}{1.5\baselineskip}{*}
\checkandfixthelayout

% ---------- fonts
\usepackage{iftex}
\ifPDFTeX
  \usepackage[T1]{fontenc}
  \usepackage[utf8]{inputenc}
  \usepackage[sc]{mathpazo}                    % body: Palatino
  \usepackage[scaled=0.92]{helvet}             % sans (headings, Oslo): Helvetica, Arial's twin
  \pdfinfo{/Title (TITLE) /Author (AUTHOR)}
\else
  \usepackage{fontspec}
  \setmainfont{TeX Gyre Pagella}[Ligatures=TeX]   % body: Palatino
  \IfFontExistsTF{Arial}                           % sans (headings, Oslo): Arial
    {\setsansfont{Arial}[Ligatures=TeX,Scale=MatchLowercase]}
    {\IfFontExistsTF{Liberation Sans}
      {\setsansfont{Liberation Sans}[Ligatures=TeX,Scale=MatchLowercase]}
      {\setsansfont{TeX Gyre Heros}[Ligatures=TeX,Scale=MatchLowercase]}}
\fi
\linespread{1.05}
\usepackage[final]{microtype}
\usepackage{amssymb}
\usepackage{graphicx}
\usepackage{needspace}
\frenchspacing
\raggedbottom
\setlength{\emergencystretch}{3em}
\hfuzz=1pt
\clubpenalty=10000
\widowpenalty=10000

% ---------- running heads: author on the left, title on the right
\makepagestyle{novel}
\makeevenhead{novel}{\thepage}{\small\textsc{\MakeLowercase{AUTHOR}}}{}
\makeoddhead{novel}{}{\small\textsc{\MakeLowercase{TITLE}}}{\thepage}
\makeevenfoot{novel}{}{}{}
\makeoddfoot{novel}{}{}{}
\makepagestyle{chapopen}
\makeevenfoot{chapopen}{}{\thepage}{}
\makeoddfoot{chapopen}{}{\thepage}{}

% ---------- chapter headings ("#. Title" in the manuscript)
% Arial (\sffamily), \Large, bold; 1.25 lines of space above, 1 line below.
% Oslo chapters are set in \sffamily too.
% Set \chapternewpagetrue to start every chapter on a new page.
\newif\ifchapternewpage \chapternewpagefalse
\makeatletter
\newcommand{\storyhead}[1]{%
  \par
  \ifchapternewpage\clearpage\thispagestyle{chapopen}\vspace*{4\baselineskip}%
  \else\needspace{3\baselineskip}\vspace{1.25\baselineskip}\fi
  {\noindent\sffamily\Large\bfseries #1\par}%
  \nopagebreak\vspace{\baselineskip}%
  \@afterindenttrue\@afterheading}   % first paragraph of a chapter is indented
\makeatother
\newcommand{\storychapter}[1]{\refstepcounter{chapter}\storyhead{\thechapter.\enspace #1}}
\newcommand{\storyprolog}[1]{\storyhead{#1}}

% ---------- documents (emails, faxes, memos, dossiers, forms, screens, FORTRAN):
% Arial, upright, indented a little and set ragged-right
\newenvironment{docblock}
  {\par\begin{adjustwidth}{1.5em}{0pt}\sffamily\raggedright\setlength{\parindent}{0pt}}
  {\par\end{adjustwidth}}

% ---------- a blank line in the manuscript
\newcommand{\blankline}{\par\vspace{\baselineskip}}

% ---------- end-of-chapter square, pushed to the right margin (TeXbook \qed)
\newcommand{\chapend}{{\unskip\nobreak\hfil\penalty50\hskip1em\null\nobreak\hfil$\square$%
  \parfillskip=0pt\finalhyphendemerits=0\par}}

% ---------- black redaction bar, as wide as the hidden word (text is not in the PDF)
\newcommand{\redact}[1]{{\setbox0\hbox{#1}\vrule width\wd0 height 0.78em depth 0.24em}}

\begin{document}

% ---------- front matter
\frontmatter
\pagestyle{empty}
\begin{titlingpage}
  \vspace*{0.28\textheight}
  \begin{center}
    {\Huge TITLE\par}
    \vspace{2\baselineskip}
    {\Large AUTHOR\par}
  \end{center}
\end{titlingpage}

\null\vfill
\noindent COPYLINE
\clearpage

\vspace*{\stretch{1}}
\begin{adjustwidth}{1.5em}{1.5em}
\raggedright
EPIGRAPHS
\end{adjustwidth}
\vspace*{\stretch{2}}
\cleardoublepage

% ---------- main text
\mainmatter
\pagestyle{novel}
\thispagestyle{chapopen}
'''


def norm_words(s):
    s = (s.replace('\u2019', "'").replace('\u2018', "'")
          .replace('\u201c', '"').replace('\u201d', '"')).lower()
    s = re.sub(r"[^a-z0-9' ]+", ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def chapter_profile(paras):
    """Bold and bold-italic share of a chapter's visible characters."""
    tot = b = bi = 0
    for p in paras:
        for r in p.runs:
            n = len(r.text.strip())
            if not n:
                continue
            tot += n
            if r.bold:
                b += n
                if r.italic:
                    bi += n
    return (b / tot if tot else 0), (bi / tot if tot else 0)


def main(src, dst):
    d = docx.Document(src)
    P = d.paragraphs
    notes = []

    first_head = next(i for i, p in enumerate(P) if heading_text(p))
    front = P[:first_head]
    title, author, copy = front[0].text.strip(), front[1].text.strip(), front[2].text.strip()

    def plain(s):
        return render(tokenize([(c, (False,) * 5) for c in s]))

    copyline = r'\textcopyright{} ' + plain(re.sub(r'^c\s+', '', copy)) + ' ' + plain(author)

    # ---- epigraphs: blocks separated by blank paragraphs
    epis, cur = [], []
    for p in front[3:]:
        if not p.text.strip():
            if cur:
                epis.append(cur)
                cur = []
            continue
        chars = para_chars(p)
        while chars and chars[0][0] in ' \t':
            chars = chars[1:]
        while chars and chars[-1][0] in ' \t\n':
            chars = chars[:-1]
        cur.append(render(tokenize(chars, epigraph=True)))
    if cur:
        epis.append(cur)

    # ---- split the main text into chapters
    chapters = []
    for idx in range(first_head, len(P)):
        p = P[idx]
        h = heading_text(p)
        if h is not None:
            if not p.text.lstrip().startswith('#'):
                notes.append('Hard-coded number in heading "%s" -- set as an auto-numbered chapter.'
                             % p.text.strip())
            chapters.append({'title': h, 'paras': []})
        else:
            chapters[-1]['paras'].append(p)

    # ---- title check
    num = 0
    for ch in chapters:
        if ch['title'] != 'Prolog':
            num += 1
        ch['num'] = num if ch['title'] != 'Prolog' else 0
        if not ch['title'].strip():
            notes.append('Chapter %d has a blank title.' % ch['num'])
        elif ch['title'] != 'Prolog':
            body_text = norm_words(' '.join(p.text for p in ch['paras']))
            if norm_words(ch['title']) not in body_text:
                notes.append('Chapter %d title "%s" does not appear in the chapter.' % (ch['num'], ch['title']))

    docs, doc_report = doc_paragraphs(P)
    pindex = {id(p._p): k for k, p in enumerate(P)}

    body = []
    for ch in chapters:
        paras = ch['paras']
        bold_share, bi_share = chapter_profile(paras)
        first_text = next((p.text.strip() for p in paras if p.text.strip()), '')
        oslo = first_text.startswith('Oslo') or bold_share >= 0.95
        invert = oslo and bi_share >= 0.9      # whole chapter bold+italic: italic was not meant
        if ch['title'] == 'Prolog':
            body.append('\n\\storyprolog{%s}\n' % plain(ch['title']))
        else:
            body.append('\n\\storychapter{%s}\n' % plain(ch['title']))   # headings never italic
        entries = []          # dicts: kind text/blank/image
        pending_blank = False
        for p in paras:
            if has_image(p):
                if pending_blank and entries:
                    entries.append({'kind': 'blank'})
                pending_blank = False
                entries.append({'kind': 'image'})
                continue
            if not p.text.strip():
                pending_blank = True
                continue
            chars = para_chars(p)
            is_doc = pindex[id(p._p)] in docs
            if invert:
                chars = [(c, (b, (not it) if b else it, u, s, r)) for c, (b, it, u, s, r) in chars]
            if is_doc:   # documents: upright Arial, bold kept
                chars = [(c, (b, False, u, s, r)) for c, (b, it, u, s, r) in chars]
            for uchars, tabs, _endmark, spaces in split_units(chars):
                if pending_blank and entries:
                    entries.append({'kind': 'blank'})
                pending_blank = False
                nb = sum(1 for c, f in uchars if f[0] and not c.isspace())
                nv = sum(1 for c, f in uchars if not c.isspace())
                entries.append({'kind': 'text', 'tex': render(tokenize(uchars)), 'tabs': tabs,
                                'sf': oslo and nv and nb / nv >= 0.5,
                                'doc': is_doc, 'spaces': spaces})
        # the closing square goes on the last paragraph of the chapter
        last = max((k for k, e in enumerate(entries) if e['kind'] == 'text'), default=None)
        trailing_image = last is not None and any(e['kind'] == 'image' for e in entries[last + 1:])
        def is_doc(k):
            return 0 <= k < len(entries) and entries[k].get('doc')

        for k, e in enumerate(entries):
            if e['kind'] == 'text' and e['doc']:
                if not is_doc(k - 1) and not (entries[k - 1]['kind'] == 'blank' and is_doc(k - 2)
                                              if k >= 2 else False):
                    body.append('\\begin{docblock}\n')
                # extra tabs and leading spaces become indentation; runs of spaces are kept
                em = 1.5 * max(e['tabs'] - 1, 0) + 0.5 * e['spaces']
                indent = '\\hspace*{%.1fem}' % em if em else ''
                tex = re.sub(r'(?<=\S) {2,}', lambda m: '\\hspace*{%.1fem}' % (0.5 * len(m.group())),
                             e['tex'])
                end = '\\chapend' if (k == last and not trailing_image) else ''
                body.append(indent + tex + end + '\n\n')
                nxt_doc = is_doc(k + 1) or (k + 2 < len(entries) and entries[k + 1]['kind'] == 'blank'
                                            and is_doc(k + 2))
                if not nxt_doc:
                    body.append('\\end{docblock}\n')
                continue
            if e['kind'] == 'blank':
                body.append('\\blankline\n')
            elif e['kind'] == 'image':
                body.append('\\begin{center}\n\\includegraphics[width=0.8\\linewidth]{house}\n\\end{center}\n')
            else:
                prefix = ('\\noindent ' if e['tabs'] == 0 else
                          '\\noindent\\hspace*{%d\\parindent}' % e['tabs'] if e['tabs'] >= 2 else '')
                end = '\\chapend' if (k == last and not trailing_image) else ''
                if e['sf']:
                    body.append('{\\sffamily' + (prefix or ' ') + e['tex'] + end + '\\par}\n\n')
                else:
                    body.append(prefix + e['tex'] + end + '\n\n')
        if last is None or trailing_image:
            body.append('\\noindent\\hfill$\\square$\\par\n\n')

    epi_tex = '\n\\bigskip\n\n'.join('\n'.join('\\noindent ' + line + '\\par' for line in e) for e in epis)
    pre = (PREAMBLE.replace('TITLE', plain(title)).replace('AUTHOR', plain(author))
           .replace('COPYLINE', copyline).replace('EPIGRAPHS', epi_tex))
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(pre)
        f.write(''.join(body))
        f.write('\n\\end{document}\n')
    print('chapters: %d (+ prolog), epigraphs: %d' % (num, len(epis)))
    print('document passages (set in Arial):')
    for r in doc_report:
        print('  ' + r if isinstance(r, str) else '  paragraphs %d-%d: %s' % r)
    for n in notes:
        print('NOTE', n)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
