require("../../src/formidable/static/conditions.js");

const { evaluate } = window.FormidableConditions;

function conditions(data) {
  return JSON.stringify(data).replace(/"/g, "&quot;");
}

function when(field, operator, value) {
  return { conditions: [{ field, operator, value }], logic: "or" };
}

/* A text source `a`, and a field `b` shown by `data`. */
function form(data, source = '<input name="a">') {
  document.body.innerHTML = `${source}
    <div id="box" data-conditions="${conditions(data)}">
      <label class="form-label" for="b">B</label>
      <input id="b" name="b" value="old">
    </div>`;
  evaluate();
  return document.getElementById("box");
}

function setValue(name, value) {
  document.querySelector(`[name="${name}"]`).value = value;
  evaluate();
}

const shown = () => document.getElementById("box").style.display !== "none";

describe("operators", () => {
  test.each([
    ["equals", "x", "x", true],
    ["equals", "x", "y", false],
    ["not_equals", "x", "y", true],
    ["not_equals", "x", "x", false],
    ["contains", "abc", "b", true],
    ["contains", "abc", "z", false],
    ["contains", "", "b", false],
    ["not_contains", "abc", "z", true],
    ["not_contains", "abc", "b", false],
    ["not_contains", "", "b", true],
    ["starts_with", "abc", "ab", true],
    ["starts_with", "abc", "bc", false],
    ["ends_with", "abc", "bc", true],
    ["ends_with", "abc", "ab", false],
    ["greater_than", "5", "3", true],
    ["greater_than", "3", "3", false],
    ["less_than", "2", "3", true],
    ["less_than", "3", "3", false],
    ["greater_equal", "3", "3", true],
    ["greater_equal", "2", "3", false],
    ["less_equal", "3", "3", true],
    ["less_equal", "4", "3", false],
    ["empty", "", undefined, true],
    ["empty", "   ", undefined, true],
    ["empty", "x", undefined, false],
    ["not_empty", "x", undefined, true],
    ["not_empty", "", undefined, false],
    ["in", "x", ["x", "y"], true],
    ["in", "z", ["x", "y"], false],
    ["not_in", "z", ["x", "y"], true],
    ["not_in", "x", ["x", "y"], false],
  ])("%s: %j against %j is %s", (operator, actual, expected, result) => {
    form(when("a", operator, expected));
    setValue("a", actual);
    expect(shown()).toBe(result);
  });

  test("an unknown operator hides and warns", () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    form(when("a", "nonsense", "x"));
    expect(shown()).toBe(false);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe("logic and formats", () => {
  const both = logic => ({
    logic,
    conditions: [
      { field: "a", operator: "equals", value: "1" },
      { field: "c", operator: "equals", value: "1" },
    ],
  });
  const sources = '<input name="a" value="1"><input name="c" value="0">';

  test("or needs one", () => {
    form(both("or"), sources);
    expect(shown()).toBe(true);
  });

  test("and needs all", () => {
    form(both("and"), sources);
    expect(shown()).toBe(false);
  });

  test("logic defaults to and", () => {
    form({ conditions: both("x").conditions }, sources);
    expect(shown()).toBe(false);
  });

  test("a single condition object", () => {
    form({ field: "a", operator: "equals", value: "1" }, sources);
    expect(shown()).toBe(true);
  });

  test("single-quoted attributes of older templates", () => {
    document.body.innerHTML = `<input name="a" value="1">
      <div id="box" class="conditional-field" data-conditions="{'conditions': [{'field': 'a', 'operator': 'equals', 'value': '2'}], 'logic': 'or'}"></div>`;
    evaluate();
    expect(shown()).toBe(false);
  });

  test("invalid data leaves the field alone", () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    document.body.innerHTML = '<div id="box" data-conditions="{nope"></div>';
    evaluate();
    expect(shown()).toBe(true);
    warn.mockRestore();
  });

  test("conditions on a child of .conditional-field", () => {
    document.body.innerHTML = `<input name="a">
      <div id="box" class="conditional-field">
        <span data-conditions="${conditions(when("a", "equals", "1"))}"></span>
      </div>`;
    evaluate();
    expect(shown()).toBe(false);
  });

  test("the surrounding container hides", () => {
    document.body.innerHTML = `<input name="a">
      <div class="col-12" id="col">
        <div data-conditions="${conditions(when("a", "equals", "1"))}"></div>
      </div>`;
    evaluate();
    expect(document.getElementById("col").style.display).toBe("none");
  });
});

describe("source controls", () => {
  test("radio group", () => {
    form(when("a", "equals", "ja"), `
      <input type="radio" name="a" value="nein" checked>
      <input type="radio" name="a" value="ja">`);
    expect(shown()).toBe(false);
    document.querySelector('[value="ja"]').checked = true;
    evaluate();
    expect(shown()).toBe(true);
  });

  test("single checkbox", () => {
    form(when("a", "equals", "true"), '<input type="checkbox" name="a" value="true">');
    expect(shown()).toBe(false);
    document.querySelector('[name="a"]').checked = true;
    evaluate();
    expect(shown()).toBe(true);
  });

  test("checkbox group", () => {
    form(when("a", "equals", "y"), `
      <input type="checkbox" name="a" value="x" checked>
      <input type="checkbox" name="a" value="y">`);
    expect(shown()).toBe(false);
    document.querySelector('[value="y"]').checked = true;
    evaluate();
    expect(shown()).toBe(true);
  });

  test("single and multiple select", () => {
    form(when("a", "equals", "y"), `<select name="a">
      <option value="x">x</option><option value="y">y</option></select>`);
    expect(shown()).toBe(false);
    setValue("a", "y");
    expect(shown()).toBe(true);
    form(when("a", "equals", "y"), `<select name="a" multiple>
      <option value="x" selected>x</option><option value="y" selected>y</option></select>`);
    expect(shown()).toBe(true);
  });

  test("a missing source hides and warns", () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    form(when("nope", "equals", "x"));
    expect(shown()).toBe(false);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe("show and hide", () => {
  const input = () => document.getElementById("b");

  test("hiding clears, disables and unmarks", () => {
    form(when("a", "equals", "1"));
    expect(input().value).toBe("");
    expect(input().disabled).toBe(true);
    expect(input().required).toBe(false);
    expect(document.querySelector("label").classList.contains("required")).toBe(false);
    expect(document.getElementById("box").classList.contains("conditional-hidden")).toBe(true);
  });

  test("showing enables and marks as required", () => {
    form(when("a", "equals", "1"));
    setValue("a", "1");
    expect(input().disabled).toBe(false);
    expect(input().required).toBe(true);
    expect(document.querySelector("label").classList.contains("required")).toBe(true);
    expect(document.getElementById("box").classList.contains("conditional-hidden")).toBe(false);
  });

  test("hiding resets every kind of control", () => {
    document.body.innerHTML = `<input name="a">
      <div data-conditions="${conditions(when("a", "equals", "1"))}">
        <input type="checkbox" id="c" checked>
        <input type="radio" id="r" checked>
        <textarea id="t">x</textarea>
        <select id="s"><option>1</option><option selected>2</option></select>
        <select id="m" multiple><option selected>1</option></select>
        <input type="hidden" id="h" value="keep">
        <input id="i" class="is-invalid" value="x">
      </div>`;
    evaluate();
    const el = id => document.getElementById(id);
    expect(el("c").checked).toBe(false);
    expect(el("r").checked).toBe(false);
    expect(el("t").value).toBe("");
    expect(el("s").selectedIndex).toBe(0);
    expect(el("m").selectedIndex).toBe(-1);
    expect(el("h").value).toBe("keep");
    expect(el("h").disabled).toBe(true);
    expect(el("i").classList.contains("is-invalid")).toBe(false);
  });

  test("hidden inputs are never marked as required", () => {
    document.body.innerHTML = `<input name="a" value="1">
      <div data-conditions="${conditions(when("a", "equals", "1"))}">
        <input type="hidden" id="h">
      </div>`;
    evaluate();
    expect(document.getElementById("h").required).toBe(false);
  });

  test.each([
    ["on the field", 'data-not-required="true"', ""],
    ["on a wrapper", "", 'data-not-required="true"'],
  ])("data-not-required %s", (_, outer, inner) => {
    document.body.innerHTML = `<input name="a" value="1">
      <div ${outer} data-conditions="${conditions(when("a", "equals", "1"))}">
        <div ${inner}>
          <label class="form-label">L</label>
          <input id="i">
        </div>
      </div>`;
    evaluate();
    const i = document.getElementById("i");
    expect(i.disabled).toBe(false);
    expect(i.required).toBe(false);
    expect(document.querySelector("label").classList.contains("required")).toBe(false);
  });

  test("nested fields follow their own condition", () => {
    document.body.innerHTML = `<input name="a" value="1"><input name="c" value="0">
      <div data-conditions="${conditions(when("a", "equals", "1"))}">
        <input id="outer">
        <div id="inner" data-conditions="${conditions(when("c", "equals", "1"))}">
          <input id="nested">
        </div>
      </div>`;
    evaluate();
    expect(document.getElementById("outer").disabled).toBe(false);
    expect(document.getElementById("nested").disabled).toBe(true);
  });

  test("a true condition stays hidden inside a hidden field", () => {
    document.body.innerHTML = `<input name="a" value="0"><input name="c" value="1">
      <div data-conditions="${conditions(when("a", "equals", "1"))}">
        <div id="inner" data-conditions="${conditions(when("c", "equals", "1"))}">
          <input id="nested">
        </div>
      </div>`;
    evaluate();
    expect(document.getElementById("nested").disabled).toBe(true);
    setValue("a", "1");
    expect(document.getElementById("nested").disabled).toBe(false);
  });

  test("hiding cascades whatever the document order", () => {
    document.body.innerHTML = `<input name="a" value="0">
      <div id="last" data-conditions="${conditions(when("b", "equals", "x"))}"><input name="c"></div>
      <div id="middle" data-conditions="${conditions(when("a", "equals", "1"))}"><input name="b" value="x"></div>`;
    evaluate();
    expect(document.getElementById("middle").style.display).toBe("none");
    expect(document.getElementById("last").style.display).toBe("none");
  });

  test("a change event re-evaluates", () => {
    form(when("a", "equals", "1"));
    const a = document.querySelector('[name="a"]');
    a.value = "1";
    a.dispatchEvent(new Event("change", { bubbles: true }));
    expect(shown()).toBe(true);
  });
});

describe("rows", () => {
  const row = i => `<div class="field-list-item">
      <select name="rows.${i}.kind"><option>a</option><option>b</option></select>
      <div id="box-${i}" data-conditions="${conditions(when("rows.items.kind", "equals", "b"))}">
        <input name="rows.${i}.detail">
      </div>
    </div>`;
  const hidden = i => document.getElementById(`box-${i}`).style.display === "none";

  test("a condition reads its own row", () => {
    document.body.innerHTML = row(0) + row(1);
    document.querySelector('[name="rows.1.kind"]').value = "b";
    evaluate();
    expect(hidden(0)).toBe(true);
    expect(hidden(1)).toBe(false);
  });

  test("short field names resolve within the row", () => {
    document.body.innerHTML = `<div class="field-list-item">
        <input name="rows.0.kind" value="b">
        <div id="box-0" data-conditions="${conditions(when("kind", "equals", "b"))}"></div>
      </div>`;
    evaluate();
    expect(hidden(0)).toBe(false);
  });

  test("outside a row, dotted names need an exact match", () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    form(when("street", "equals", "x"), '<input name="other.street" value="x">');
    expect(shown()).toBe(false);
    warn.mockRestore();
  });

  test("the rows event re-evaluates new rows", () => {
    document.body.innerHTML = row(0);
    evaluate();
    document.body.insertAdjacentHTML("beforeend", row(1));
    document.dispatchEvent(new CustomEvent("formidable:rows"));
    expect(hidden(1)).toBe(true);
  });
});

describe("conditional options", () => {
  const config = conditions({
    source_field: "a",
    default_options: ["x"],
    rules: [{ value: "1", options: ["x", "y"] }],
  });

  test("checks and radios follow the rules", () => {
    for (const cls of ["form-check", "field-radio-option"]) {
      document.body.innerHTML = `<input name="a">
        <div data-conditional-options="${config}">
          <div class="${cls}" id="x"><input value="x"></div>
          <div class="${cls}" id="y"><input value="y" checked></div>
        </div>`;
      evaluate();
      const y = document.querySelector("#y input");
      expect(document.getElementById("y").style.display).toBe("none");
      expect(y.disabled).toBe(true);
      expect(y.checked).toBe(false);
      expect(document.getElementById("x").style.display).toBe("");
      setValue("a", "1");
      expect(document.getElementById("y").style.display).toBe("");
      expect(y.disabled).toBe(false);
    }
  });

  test("select options follow the rules and keep the placeholder", () => {
    document.body.innerHTML = `<input name="a">
      <div data-conditional-options="${config}"><select>
        <option value="" id="blank"></option>
        <option value="x" id="x">x</option>
        <option value="y" id="y" selected>y</option>
      </select></div>`;
    evaluate();
    const el = id => document.getElementById(id);
    expect(el("y").hidden).toBe(true);
    expect(el("y").disabled).toBe(true);
    expect(el("y").selected).toBe(false);
    expect(el("blank").disabled).toBe(false);
    setValue("a", "1");
    expect(el("y").hidden).toBe(false);
  });

  test("the source can sit in the same row", () => {
    document.body.innerHTML = `<div class="field-list-item">
        <input name="rows.0.a" value="1">
        <div data-conditional-options="${config}">
          <div class="form-check" id="y"><input value="y"></div>
        </div>
      </div>`;
    evaluate();
    expect(document.getElementById("y").style.display).toBe("");
  });

  test("invalid configuration is ignored", () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    document.body.innerHTML = '<div data-conditional-options="{nope"></div>';
    expect(() => evaluate()).not.toThrow();
    warn.mockRestore();
  });
});
