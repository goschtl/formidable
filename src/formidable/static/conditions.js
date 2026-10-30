/* Conditional fields: shows, hides and resets fields as answers change.
 *
 * Reads `data-conditions` and `data-conditional-options`, the attributes
 * nva.dynamic_form_elements uses, without any dependency. It only decides
 * what is visible: the server still validates everything.
 */
(function () {
  if (window.FormidableConditions) return;

  var CONDITIONAL = ".conditional-field, [data-conditions]";
  var CONTAINER = ".mb-3, .col-md-6, .col-md-12, .col-12, .form-group, " +
    ".field-group, .fieldset-container";
  var ROW = ".field-list-item";
  var CONTROLS = "input, select, textarea";
  var MARKERS = "label.control-label, label.form-label, fieldset > legend";
  var OPTIONS = ".form-check, .field-radio-option";

  function all(root, selector) {
    return Array.prototype.slice.call(root.querySelectorAll(selector));
  }

  function byName(root, name, suffix) {
    var escaped = name.replace(/["\\]/g, "\\$&");
    return all(root, "[name" + (suffix ? "$" : "") + '="' +
      (suffix ? "." : "") + escaped + '"]');
  }

  /* Exact name, then within a row: `street` matches `users.0.street`. */
  function findIn(scope, name) {
    var found = byName(scope, name);
    return found.length || scope === document ? found : byName(scope, name, true);
  }

  function findControls(name, row) {
    if (!row) return findIn(document, name);
    var found = findIn(row, name);
    if (!found.length && name.indexOf(".items.") !== -1) {
      name = name.split(".items.")[1];
      found = findIn(row, name);
    }
    if (!found.length && name.indexOf(".") !== -1) {
      name = name.split(".").pop();
      found = findIn(row, name);
    }
    return found.length ? found : findIn(document, name);
  }

  function valueOf(controls) {
    var first = controls[0];
    if (first.type === "checkbox") {
      var checked = controls.filter(function (el) { return el.checked; })
        .map(function (el) { return el.value; });
      return controls.length > 1 ? checked : checked[0] || "";
    }
    if (first.type === "radio") {
      var picked = controls.filter(function (el) { return el.checked; })[0];
      return picked ? picked.value : "";
    }
    if (first.type === "hidden" && controls.length > 1) {
      return controls.map(function (el) { return el.value; });
    }
    if (first.multiple) {
      return Array.prototype.map.call(first.selectedOptions,
        function (option) { return option.value; });
    }
    return first.value || "";
  }

  function isEmpty(actual) {
    return actual.length === 0 || actual.toString().trim() === "";
  }

  function check(operator, actual, expected) {
    var isList = Array.isArray(actual);
    switch (operator) {
      case "equals":
        return isList ? actual.indexOf(expected) !== -1 : actual === expected;
      case "not_equals":
        return isList ? actual.indexOf(expected) === -1 : actual !== expected;
      case "contains":
        return !isEmpty(actual) && actual.toString().indexOf(expected) !== -1;
      case "not_contains":
        return isEmpty(actual) || actual.toString().indexOf(expected) === -1;
      case "starts_with":
        return !isEmpty(actual) && actual.toString().indexOf(expected) === 0;
      case "ends_with":
        return !isEmpty(actual) && actual.toString().slice(-expected.length) === expected;
      case "greater_than": return parseFloat(actual) > parseFloat(expected);
      case "less_than": return parseFloat(actual) < parseFloat(expected);
      case "greater_equal": return parseFloat(actual) >= parseFloat(expected);
      case "less_equal": return parseFloat(actual) <= parseFloat(expected);
      case "empty": return isEmpty(actual);
      case "not_empty": return !isEmpty(actual);
      case "in": return Array.isArray(expected) && expected.indexOf(actual) !== -1;
      case "not_in": return !Array.isArray(expected) || expected.indexOf(actual) === -1;
    }
    console.warn("Unknown operator: " + operator);
    return false;
  }

  function evaluateOne(condition, row) {
    var controls = findControls(condition.field, row);
    if (!controls.length) {
      console.warn('Target field "' + condition.field + '" not found');
      return false;
    }
    // a hidden field has no answer: whatever depends on it hides as well
    if (controls[0].disabled) return false;
    return check(condition.operator, valueOf(controls), condition.value);
  }

  function parse(text) {
    try {
      return JSON.parse(text);
    } catch (error) {
      // older generated templates use single quotes
      return JSON.parse(text.replace(/'/g, '"'));
    }
  }

  function isVisible(data, row) {
    if (data.conditions && Array.isArray(data.conditions)) {
      if (!data.conditions.length) return true;
      var results = data.conditions.map(function (condition) {
        return evaluateOne(condition, row);
      });
      return (data.logic || "and") === "and"
        ? results.every(Boolean) : results.some(Boolean);
    }
    if (data.field && data.operator) return evaluateOne(data, row);
    console.warn("Unknown condition format", data);
    return true;
  }

  function conditionsOf(field) {
    var holder = field.hasAttribute("data-conditions")
      ? field : field.querySelector("[data-conditions]");
    if (!holder) return null;
    try {
      return parse(holder.getAttribute("data-conditions"));
    } catch (error) {
      console.warn("Invalid conditions", holder, error);
      return null;
    }
  }

  function ownedBy(el, field) {
    var closest = el.closest(CONDITIONAL);
    return !closest || closest === field;
  }

  function show(field, container) {
    container.style.display = "";
    container.classList.remove("conditional-hidden");
    function wantsRequired(el) {
      var opted = el.closest('[data-not-required="true"]');
      return field.getAttribute("data-not-required") !== "true" &&
        !(opted && container.contains(opted));
    }
    all(container, CONTROLS).forEach(function (el) {
      if (!ownedBy(el, field)) return;
      el.disabled = false;
      if (el.type !== "hidden" && wantsRequired(el)) el.required = true;
    });
    all(container, MARKERS).forEach(function (el) {
      if (ownedBy(el, field) && wantsRequired(el)) el.classList.add("required");
    });
  }

  function hide(container) {
    container.style.display = "none";
    container.classList.add("conditional-hidden");
    all(container, MARKERS).forEach(function (el) {
      el.classList.remove("required");
    });
    all(container, CONTROLS).forEach(function (el) {
      // no stale answers when the field comes back
      if (el.type === "radio" || el.type === "checkbox") el.checked = false;
      else if (el.tagName === "SELECT") el.selectedIndex = el.multiple ? -1 : 0;
      else if (el.type !== "hidden") el.value = "";
      el.disabled = true;
      el.required = false;
      el.classList.remove("is-invalid", "is-valid");
    });
  }

  function applyField(field) {
    var data = conditionsOf(field);
    if (!data) return;
    var container = field.closest(CONTAINER) || field;
    // nothing inside a hidden field may come back and get submitted
    var insideHidden = container.parentElement &&
      container.parentElement.closest(".conditional-hidden");
    var visible = !insideHidden && isVisible(data, field.closest(ROW));
    if (visible) show(field, container);
    else hide(container);
  }

  function applyOptions(field) {
    var config;
    try {
      config = JSON.parse(field.getAttribute("data-conditional-options"));
    } catch (error) {
      console.warn("Invalid conditional options", field, error);
      return;
    }
    var row = field.closest(ROW);
    var scope = row || document;
    var source = byName(scope, config.source_field);
    if (!source.length && row) source = byName(row, config.source_field, true);
    var current = source.length ? valueOf(source) : "";
    var visible = config.default_options || [];
    (config.rules || []).some(function (rule) {
      if (rule.value !== current) return false;
      visible = rule.options;
      return true;
    });
    all(field, OPTIONS).forEach(function (option) {
      var input = option.querySelector("input");
      var allowed = visible.indexOf(input.value) !== -1;
      option.style.display = allowed ? "" : "none";
      input.disabled = !allowed;
      if (!allowed) input.checked = false;
    });
    all(field, "select option").forEach(function (option) {
      if (!option.value) return;
      var allowed = visible.indexOf(option.value) !== -1;
      option.hidden = !allowed;
      option.disabled = !allowed;
      if (!allowed) option.selected = false;
    });
  }

  function state(fields) {
    return fields.map(function (field) {
      var container = field.closest(CONTAINER) || field;
      return container.style.display;
    }).join();
  }

  function evaluate() {
    var fields = all(document, CONDITIONAL);
    // hiding a field can change what depends on it: repeat until stable
    for (var round = 0; round <= fields.length; round++) {
      var before = state(fields);
      fields.forEach(applyField);
      if (state(fields) === before && round > 0) break;
    }
    all(document, "[data-conditional-options]").forEach(applyOptions);
  }

  document.addEventListener("change", evaluate);
  document.addEventListener("formidable:rows", evaluate);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", evaluate);
  } else {
    evaluate();
  }

  window.FormidableConditions = { evaluate: evaluate };
})();
