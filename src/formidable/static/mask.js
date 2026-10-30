/* Input masks: `data-mask="99-9999"` formats a field while typing.
 *
 * 9 is a digit, a a letter, * either; anything else is a literal, and a
 * `?` is ignored, as everything after the last typed character is
 * optional anyway. It only helps typing: the server validates the value.
 */
(function () {
  if (window.__formidable_masks) return;
  window.__formidable_masks = true;

  var SLOTS = { "9": /[0-9]/, "a": /[A-Za-z]/, "*": /[A-Za-z0-9]/ };

  function format(mask, raw) {
    var out = "", next = 0;
    for (var i = 0; i < mask.length && next < raw.length; i++) {
      var part = mask.charAt(i), slot = SLOTS[part];
      if (slot) {
        while (next < raw.length && !slot.test(raw.charAt(next))) next++;
        if (next < raw.length) out += raw.charAt(next++);
      } else {
        out += part;
        if (raw.charAt(next) === part) next++;
      }
    }
    return out;
  }

  document.addEventListener("input", function (ev) {
    var mask = ev.target.getAttribute && ev.target.getAttribute("data-mask");
    if (!mask) return;
    mask = mask.replace("?", "");
    var field = ev.target, raw = field.value, caret = field.selectionStart;
    var formatted = format(mask, raw);
    if (formatted === raw) return;
    field.value = formatted;
    if (caret !== null) {
      var position = format(mask, raw.slice(0, caret)).length;
      field.setSelectionRange(position, position);
    }
  });
})();
