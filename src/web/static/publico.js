(function () {
  var form = document.getElementById("form-suscribir");
  var boton = document.getElementById("btn-suscribir");
  if (!form || !boton) return;
  form.addEventListener("submit", function () {
    boton.disabled = true;
    boton.textContent = "Guardando…";
  });
})();
