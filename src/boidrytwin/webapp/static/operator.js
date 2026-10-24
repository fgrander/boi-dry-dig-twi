// Editor of released inputs (engineer view; FR-012).
"use strict";

function releaseEditor(container, initial) {
  const rows = initial.map((r) => ({ ...r }));
  const fields = [["key", "text", 44], ["label", "text", 20], ["unit", "text", 6],
    ["minimum", "number", 8], ["maximum", "number", 8]];

  function render() {
    container.innerHTML = "";
    rows.forEach((r, i) => {
      const line = document.createElement("div");
      line.className = "toolbar";
      for (const [name, type, size] of fields) {
        const input = document.createElement("input");
        input.type = type; input.size = size; input.placeholder = name; input.step = "any";
        input.value = r[name] ?? "";
        input.addEventListener("input", () => { r[name] = type === "number" ? Number(input.value) : input.value; });
        line.append(input);
      }
      const step = document.createElement("label");
      const box = document.createElement("input");
      box.type = "checkbox"; box.checked = !!r.allow_step;
      box.addEventListener("change", () => { r.allow_step = box.checked; });
      step.append(box, " step allowed");
      const del = document.createElement("button");
      del.className = "secondary"; del.textContent = "remove";
      del.addEventListener("click", () => { rows.splice(i, 1); render(); });
      line.append(step, del);
      container.append(line);
    });
  }

  render();
  return {
    add() { rows.push({ key: "", label: "", unit: "", minimum: 0, maximum: 1, allow_step: false }); render(); },
    value() { return rows.map((r) => ({ ...r })); },
  };
}
window.releaseEditor = releaseEditor;
