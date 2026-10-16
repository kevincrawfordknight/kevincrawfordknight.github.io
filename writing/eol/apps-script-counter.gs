// Click counter for the Empire of Liberty pages (and the old "more" / "good" buttons).
//
// Each Prev/Next click calls this web app as  .../exec?button=Next18
//   "Counts" sheet: column A = button name (Next18, Prev5, NextProlog ...),
//                   column B = number of clicks. New names get a new row automatically.
//   "Log" sheet:    one row per click: time, button name.
//
// Install: open the Apps Script project behind your existing web-app link
// (script.google.com), replace its code with this file, then
// Deploy > Manage deployments > (pencil icon) Edit > Version: New version > Deploy.
// Editing the existing deployment keeps the same /exec link, so the pages need no change.
// Optional: run seedRows() once to pre-fill the Counts sheet in reading order.

// Leave empty if this script was created from the spreadsheet (Extensions > Apps Script).
// Otherwise paste the spreadsheet's ID (the long code in its URL) between the quotes.
var SHEET_ID = '';

function book_() {
  return SHEET_ID ? SpreadsheetApp.openById(SHEET_ID) : SpreadsheetApp.getActiveSpreadsheet();
}

function sheet_(ss, name) {
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function doGet(e) {
  var button = (e && e.parameter && e.parameter.button) || '';
  if (!/^[A-Za-z0-9]{1,40}$/.test(button)) {
    return ContentService.createTextOutput('ignored');
  }
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);   // two readers clicking at once must not overwrite each other
  try {
    var ss = book_();
    var counts = sheet_(ss, 'Counts');
    var names = counts.getRange(1, 1, Math.max(counts.getLastRow(), 1), 1).getValues();
    var row = -1;
    for (var i = 0; i < names.length; i++) {
      if (names[i][0] === button) { row = i + 1; break; }
    }
    if (row === -1) {
      counts.appendRow([button, 1]);
    } else {
      var cell = counts.getRange(row, 2);
      cell.setValue((Number(cell.getValue()) || 0) + 1);
    }
    sheet_(ss, 'Log').appendRow([new Date(), button]);
  } finally {
    lock.releaseLock();
  }
  return ContentService.createTextOutput('ok');
}

// Run once by hand (select seedRows, press Run) to list every button in reading order.
function seedRows() {
  var counts = sheet_(book_(), 'Counts');
  var have = {};
  if (counts.getLastRow() > 0) {
    counts.getRange(1, 1, counts.getLastRow(), 1).getValues()
      .forEach(function (r) { have[r[0]] = true; });
  }
  var rows = [];
  if (!have.NextProlog) rows.push(['NextProlog', 0]);
  for (var n = 1; n <= 20; n++) {
    if (!have['Prev' + n]) rows.push(['Prev' + n, 0]);
    if (!have['Next' + n]) rows.push(['Next' + n, 0]);
  }
  if (rows.length) {
    counts.getRange(counts.getLastRow() + 1, 1, rows.length, 2).setValues(rows);
  }
}
