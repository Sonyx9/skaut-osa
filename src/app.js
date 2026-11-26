// Filtrování časové osy. Bez JavaScriptu zůstanou vidět všechny záznamy.
(function () {
  "use strict";
  var panel = document.getElementById("filters");
  if (!panel) return;
  panel.hidden = false;
  var more = document.getElementById("more");
  var moreBtn = document.getElementById("more-btn");
  var allBtn = document.getElementById("all");
  moreBtn.addEventListener("click", function () {
    var open = more.hidden;
    more.hidden = !open;
    moreBtn.setAttribute("aria-expanded", open ? "true" : "false");
  });

  var events = Array.prototype.slice.call(document.querySelectorAll(".ev"));
  var years = Array.prototype.slice.call(document.querySelectorAll(".year"));
  var navItems = Array.prototype.slice.call(document.querySelectorAll(".years-nav li[data-y]"));
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
    var allLines = lines.length === 0;
    allBtn.setAttribute("aria-pressed", allLines ? "true" : "false");
    var verify = active("v");
    var needle = q.value.trim().toLowerCase();
    var newOnly = onlyNew.getAttribute("aria-pressed") === "true";
    var shown = 0;

    events.forEach(function (ev) {
      var v = ev.dataset.v === "otevrene" || ev.dataset.v === "pametnik" ? "neovereno" : ev.dataset.v;
      var ok = (allLines || lines.indexOf(ev.dataset.l) !== -1) &&
        verify.indexOf(v) !== -1 &&
        (!newOnly || ev.dataset.dp === "ne") &&
        (!needle || ev.dataset.s.indexOf(needle) !== -1);
      ev.hidden = !ok;
      if (ok) shown++;
    });

    var visible = {};
    years.forEach(function (section) {
      var any = section.querySelector(".ev:not([hidden])") !== null;
      section.hidden = !any;
      if (any) visible[section.id.slice(1)] = true;
    });
    navItems.forEach(function (li) { li.hidden = !visible[li.dataset.y]; });

    empty.hidden = shown !== 0;
    count.textContent = shown === events.length
      ? "Zobrazeny všechny záznamy (" + shown + ")."
      : "Zobrazeno " + shown + " z " + events.length + " záznamů.";
  }

  buttons.concat(onlyNew).forEach(function (b) {
    b.addEventListener("click", function () {
      var on = b.getAttribute("aria-pressed") === "true";
      if (b.dataset.group === "l") {
        buttons.forEach(function (o) { if (o.dataset.group === "l") o.setAttribute("aria-pressed", "false"); });
        if (!on) b.setAttribute("aria-pressed", "true");
      } else {
        b.setAttribute("aria-pressed", on ? "false" : "true");
      }
      apply();
    });
  });
  allBtn.addEventListener("click", function () {
    buttons.forEach(function (o) { if (o.dataset.group === "l") o.setAttribute("aria-pressed", "false"); });
    apply();
  });

  q.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(apply, 150);
  });

  document.getElementById("reset").addEventListener("click", function () {
    buttons.forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.group === "l" ? "false" : "true"); });
    onlyNew.setAttribute("aria-pressed", "false");
    q.value = "";
    apply();
  });

  var params = new URLSearchParams(location.search);
  if (params.get("q")) { q.value = params.get("q"); more.hidden = false; moreBtn.setAttribute("aria-expanded", "true"); }
  var pr = params.get("proud");
  if (pr) buttons.forEach(function (b) { if (b.dataset.group === "l" && b.dataset.key === pr) b.setAttribute("aria-pressed", "true"); });
  apply();
})();
