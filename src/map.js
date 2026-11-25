(function () {
  var el = document.getElementById("map");
  if (!el || !window.L) return;
  var css = getComputedStyle(document.documentElement);
  var color = function (l) { return css.getPropertyValue("--l-" + l).trim() || "#6f6c63"; };
  var map = L.map(el, { scrollWheelZoom: false });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);
  var bounds = [];
  PLACES.forEach(function (p) {
    var c = color(p.l);
    var m = L.circleMarker([p.lat, p.lon], {
      radius: 7 + Math.min(p.n, 12) * 0.6,
      color: c, weight: 3,
      fillColor: p.approx ? "#ffffff" : c,
      fillOpacity: p.approx ? 0.9 : 0.85,
      dashArray: p.approx ? "3 3" : null
    }).addTo(map);
    var a = document.createElement("a");
    a.href = "#" + p.id;
    a.textContent = p.name;
    var box = document.createElement("div");
    box.className = "map__pop";
    var b = document.createElement("strong");
    b.appendChild(a);
    box.appendChild(b);
    var t = document.createElement("div");
    t.textContent = p.typ + " · " + p.n + " zázn.";
    box.appendChild(t);
    m.bindPopup(box);
    m.bindTooltip(p.name);
    bounds.push([p.lat, p.lon]);
  });
  if (bounds.length) map.fitBounds(bounds, { padding: [24, 24] });
  if (location.hash) {
    var card = document.getElementById(location.hash.slice(1));
    if (card) card.classList.add("card--hit");
  }
  window.addEventListener("hashchange", function () {
    document.querySelectorAll(".card--hit").forEach(function (x) { x.classList.remove("card--hit"); });
    var card = document.getElementById(location.hash.slice(1));
    if (card) card.classList.add("card--hit");
  });
})();
