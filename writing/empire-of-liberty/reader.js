// Prev / Next buttons. Each click is logged to the Google Sheet as e.g. "Next18"
// (Next pressed at the end of chapter 18) or "Prev5" (Prev pressed on chapter 5).
(function () {
  var ENDPOINT = "https://script.google.com/macros/s/AKfycbwZAsRWp2eQyloWH76fN7ZSl0ClH6aHDweOr1c8NWfakeockrIks0dOrN5TiRFtM080/exec";
  var LAST_MESSAGE = "Empire of Liberty coming in 2026!";

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
