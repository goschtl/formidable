function load(html) {
  jest.resetModules();
  delete window.__formidable_uploads;
  document.body.innerHTML = html;
  window.FilePondPluginFileValidateType = "type";
  window.FilePondPluginFileValidateSize = "size";
  window.FilePond = {
    registerPlugin: jest.fn(),
    create: jest.fn((input, options) => {
      input.removeAttribute("data-upload-url");
      return options;
    }),
    find: jest.fn(),
    Status: { BUSY: 3 },
  };
  require("../../src/formidable/static/upload.js");
  return window.FilePond;
}

const FIELD = `<form><input type="hidden" name="__csrf__" value="tok">
  <input type="file" name="f" data-upload-url="/upload"></form>`;

describe("upload widgets", () => {
  test("wires the upload url and the csrf token", () => {
    const options = load(FIELD).create.mock.calls[0][1];
    expect(options.server.process).toBe("/upload");
    expect(options.server.revert).toBe("/upload");
    expect(options.server.restore).toBe("/upload?id=");
    expect(options.server.headers).toEqual({ "X-CSRF-Token": "tok" });
    expect(options.credits).toBe(false);
  });

  test("works without a csrf token", () => {
    const pond = load('<form><input type="file" data-upload-url="/u"></form>');
    expect(pond.create.mock.calls[0][1].server.headers).toEqual({});
  });

  test("a field hidden by a condition stays usable, a disabled one does not", () => {
    const pond = load(`<form><div class="conditional-hidden">
      <input type="file" data-upload-url="/a" disabled></div>
      <input type="file" data-upload-url="/b" disabled></form>`);
    expect(pond.create.mock.calls[0][0].disabled).toBe(false);
    expect(pond.create.mock.calls[1][0].disabled).toBe(true);
  });

  test("restores earlier uploads", () => {
    const pond = load(`<form><input type="file" data-upload-url="/u"
      data-upload-files='["a","b"]'></form>`);
    expect(pond.create.mock.calls[0][1].files).toEqual([
      { source: "a", options: { type: "limbo" } },
      { source: "b", options: { type: "limbo" } },
    ]);
  });

  test("further options apply", () => {
    const pond = load(`<form><input type="file" data-upload-url="/u"
      data-upload-options='{"labelIdle":"Hier"}'></form>`);
    expect(pond.create.mock.calls[0][1].labelIdle).toBe("Hier");
  });

  test("leaves template rows alone until they are added", () => {
    const pond = load(`<form><template>
      <input type="file" data-upload-url="/u"></template></form>`);
    expect(pond.create).not.toHaveBeenCalled();
    const form = document.querySelector("form");
    form.insertAdjacentHTML("beforeend", form.querySelector("template").innerHTML);
    document.dispatchEvent(new CustomEvent("formidable:rows"));
    expect(pond.create).toHaveBeenCalledTimes(1);
  });

  test("holds back the submit while a file is on its way", () => {
    const pond = load(`<form><div class="filepond--root"></div></form>`);
    pond.find.mockReturnValue({ status: pond.Status.BUSY });
    const busy = new Event("submit", { bubbles: true, cancelable: true });
    document.querySelector("form").dispatchEvent(busy);
    expect(busy.defaultPrevented).toBe(true);

    pond.find.mockReturnValue({ status: 1 });
    const idle = new Event("submit", { bubbles: true, cancelable: true });
    document.querySelector("form").dispatchEvent(idle);
    expect(idle.defaultPrevented).toBe(false);
  });
});
