Empire of Liberty web excerpt: Prolog + chapters 1-20, one page each

WHAT TO UPLOAD (to the kevincrawfordknight.github.io repository)
  writing/empire-of-liberty/        new folder: index.html (title page + Prolog),
                                    01.html ... 20.html, reader.css, reader.js
  writing/empire-of-liberty.html    replaces the old page; it now forwards readers to
                                    writing/empire-of-liberty/index.html, so the link on
                                    books.html keeps working

CLICK COUNTS
  Every Prev/Next click calls your existing Apps Script link with ?button=NAME:
    NextProlog          Next pressed on the Prolog page
    Next1 ... Next20    Next pressed at the end of chapter N (Next20 = last page)
    Prev1 ... Prev20    Prev pressed on chapter N
  apps-script-counter.gs counts these in a "Counts" sheet (one row per name) and logs
  every click in a "Log" sheet. Install instructions are at the top of that file.
  If your current script already counts clicks by button name, you can skip it.

THE LAST PAGE
  Next on chapter 20 logs Next20 and shows the message set in reader.js:
    var LAST_MESSAGE = "Empire of Liberty coming in 2026!";

REBUILDING FROM A NEW MANUSCRIPT
  pip install python-docx
  python3 web_build.py manuscript.docx writing/empire-of-liberty 20
  (web_build.py needs docx_to_latex.py in the same folder.)
