require("../../src/formidable/static/mask.js");

function typed(mask, value, caret) {
  document.body.innerHTML = `<input id="i" data-mask="${mask}">`;
  const input = document.getElementById("i");
  input.value = value;
  input.setSelectionRange(caret ?? value.length, caret ?? value.length);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  return input;
}

describe("masks", () => {
  test.each([
    ["99-9999", "12", "12"],
    ["99-9999", "123", "12-3"],
    ["99-9999", "123456", "12-3456"],
    ["99-9999", "12-3456", "12-3456"],
    ["99-9999", "1234567890", "12-3456"],
    ["99-9999", "1a2b3", "12-3"],
    ["99-9999", "abc", ""],
    ["aa-99", "xy12", "xy-12"],
    ["aa-99", "1x", "x"],
    ["**", "a1b", "a1"],
    ["(99) 99", "1234", "(12) 34"],
    ["99?-99", "1234", "12-34"],
  ])("%s: %s becomes %s", (mask, value, expected) => {
    expect(typed(mask, value).value).toBe(expected);
  });

  test("deleting the digit behind a literal doesn't bring it back", () => {
    expect(typed("99-9999", "12-").value).toBe("12-");
    expect(typed("99-9999", "12").value).toBe("12");
  });

  test("the caret stays where it was typed", () => {
    const input = typed("99-9999", "1923456", 2);
    expect(input.value).toBe("19-2345");
    expect(input.selectionStart).toBe(2);
  });

  test("the caret moves over a new literal", () => {
    const input = typed("99-9999", "123");
    expect(input.value).toBe("12-3");
    expect(input.selectionStart).toBe(4);
  });

  test("fields without a mask are left alone", () => {
    document.body.innerHTML = '<input id="i">';
    const input = document.getElementById("i");
    input.value = "abc";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    expect(input.value).toBe("abc");
  });

  test("rows added later work too", () => {
    document.body.innerHTML = '<div id="rows"></div>';
    document.getElementById("rows").innerHTML = '<input id="i" data-mask="99-9">';
    const input = document.getElementById("i");
    input.value = "123";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    expect(input.value).toBe("12-3");
  });
});
