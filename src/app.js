// Filtrování časové osy. Bez JavaScriptu zůstanou vidět všechny záznamy.
(function () {
  "use strict";
  var panel = document.getElementById("filters");
  if (!panel) return;
  panel.hidden = false;
  var more = document.getElementById("more");
  var wide = window.matchMedia("(min-width: 900px)");
  function syncMore() { if (wide.matches) more.open = true; }
  syncMore();
  if (wide.addEventListener) wide.addEventListener("change", syncMore);

  var events = Array.prototype.slice.call(document.querySelectorAll(".ev"));
  var years = Array.prototype.slice.call(document.querySelectorAll(".year"));
  var navItems = Array.prototype.slice.call(document.querySelectorAll(".years-nav li"));
  var buttons = Array.prototype.slice.call(panel.querySelectorAll(".fbtn[data-group]"));
  var q = document.getElementById("q");
  var onlyNew = document.getElementById("only-new");
  var count = document.getElementById("count");
  var empty = document.getElementById("empty");
  var timer;

  function active(group) {
    return buttons.filter(function (b) {
      return b.dataset.group === group && b.getAttribute("aria-pressed") === "true";
    }).map(function (b) { return b.dataset.key; });
  }

  function apply() {
    var lines = active("l");
    var verify = active("v");
    var needle = q.value.trim().toLowerCase();
    var newOnly = onlyNew.getAttribute("aria-pressed") === "true";
    var shown = 0;

    events.forEach(function (ev) {
      var v = ev.dataset.v === "otevrene" || ev.dataset.v === "pametnik" ? "neovereno" : ev.dataset.v;
      var ok = lines.indexOf(ev.dataset.l) !== -1 &&
        verify.indexOf(v) !== -1 &&
        (!newOnly || ev.dataset.dp === "ne") &&
        (!needle || ev.dataset.s.indexOf(needle) !== -1);
      ev.hidden = !ok;
      if (ok) shown++;
    });

    years.forEach(function (section, i) {
      var any = section.querySelector(".ev:not([hidden])") !== null;
      section.hidden = !any;
      if (navItems[i]) navItems[i].hidden = !any;
    });

    empty.hidden = shown !== 0;
    count.textContent = shown === events.length
      ? "Zobrazeny všechny záznamy (" + shown + ")."
      : "Zobrazeno " + shown + " z " + events.length + " záznamů.";
  }

  buttons.concat(onlyNew).forEach(function (b) {
    b.addEventListener("click", function () {
      b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") === "true" ? "false" : "true");
      apply();
    });
  });

  q.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(apply, 150);
  });

  document.getElementById("reset").addEventListener("click", function () {
    buttons.forEach(function (b) { b.setAttribute("aria-pressed", "true"); });
    onlyNew.setAttribute("aria-pressed", "false");
    q.value = "";
    apply();
  });

  apply();
})();
