"use strict";

window.addEventListener("load", () => {
  window.ui = SwaggerUIBundle({
    url: "/openapi.json",
    dom_id: "#swagger-ui",
    deepLinking: true,
    displayRequestDuration: true,
    persistAuthorization: false,
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
    layout: "StandaloneLayout",
  });

  const dateParameters = new Set(["date_from", "date_to"]);
  const addDatePickers = () => {
    document.querySelectorAll("input[placeholder]").forEach((input) => {
      const parameterName = input.getAttribute("placeholder");
      if (parameterName && dateParameters.has(parameterName) && input.type !== "date") {
        input.type = "date";
        input.setAttribute("aria-label", `${parameterName} date picker`);
        input.removeAttribute("placeholder");
      }
    });
  };
  new MutationObserver(addDatePickers).observe(document.documentElement, { childList: true, subtree: true });
  addDatePickers();
});
