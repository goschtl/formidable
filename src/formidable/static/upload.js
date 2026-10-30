/* Turns file inputs carrying `data-upload-url` into FilePond widgets.
 *
 * Each file goes to that URL on its own; the form itself only submits the
 * ids the server answered with, in hidden inputs named like the field.
 * `data-upload-files` lists ids from an earlier submit, `data-upload-options`
 * any further FilePond options. The URL takes POST, DELETE and `GET ?id=`.
 */
(function () {
  function csrfHeaders(input) {
    var token = input.form && input.form.elements.__csrf__;
    return token ? { "X-CSRF-Token": token.value } : {};
  }

  function isBusy(form) {
    return FilePond.find && Array.prototype.some.call(
      form.querySelectorAll(".filepond--root"), function (el) {
        var pond = FilePond.find(el);
        return pond && pond.status === FilePond.Status.BUSY;
      });
  }

  function create(input) {
    var url = input.getAttribute("data-upload-url");
    var files = JSON.parse(input.getAttribute("data-upload-files") || "[]");
    var options = JSON.parse(input.getAttribute("data-upload-options") || "{}");
    // hidden by a condition, so only disabled for now: FilePond would keep it
    if (input.closest(".conditional-hidden")) input.disabled = false;
    return FilePond.create(input, Object.assign({
      credits: false,
      server: {
        process: url,
        revert: url,
        restore: url + "?id=",
        headers: csrfHeaders(input)
      },
      files: files.map(function (id) {
        return { source: id, options: { type: "limbo" } };
      })
    }, options));
  }

  function init() {
    FilePond.registerPlugin(
      window.FilePondPluginFileValidateType,
      window.FilePondPluginFileValidateSize);
    // a <template> row is not matched: its content is no part of the document
    document.querySelectorAll("input[data-upload-url]").forEach(create);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  if (window.__formidable_uploads) return;
  window.__formidable_uploads = true;
  document.addEventListener("formidable:rows", init);
  // a file still on its way has no id yet, and would get lost
  document.addEventListener("submit", function (ev) {
    if (isBusy(ev.target)) ev.preventDefault();
  });
})();
