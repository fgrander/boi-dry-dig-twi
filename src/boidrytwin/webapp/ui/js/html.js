// Preact + htm: components with tagged-template markup, no build step.
import { h, render } from "preact";
import htm from "htm";

export const html = htm.bind(h);
export { h, render };
