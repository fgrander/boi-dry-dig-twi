# Vendored browser libraries

Copied unchanged from the npm registry tarball (via the con-pre-dig-twi repository, where the
tarball was verified against the registry `integrity` sha512). `tests/unit/webapp/test_vendor.py`
checks the sha256 below. Do not edit these files; to update, replace them from a newer tarball
and change this table.

| File | Package | Version | Licence | sha256 |
|---|---|---|---|---|
| temml.mjs | temml | 0.13.5 | MIT | 49753197751c1ff7fa2c76c3b8503b6cee03774c7c92ccd71c3c4b7fa5b31fe1 |
| Temml-Local.css | temml | 0.13.5 | MIT | 544f4e3fee4c36f4568e4f145fa626dc9573c5f4c96c523aadcc433c3989a239 |
| Temml.woff2 | temml | 0.13.5 | MIT | fc70501355ae6d38ff0b80f825af153557d5f2f474198d6b9b7dd2d3a291a0cc |
| LICENSE-temml.txt | temml | 0.13.5 | MIT | 12b4e5592a12baaf50637881f2cb9d66667b26b8d51a73cd8f0d6bcefe176ab6 |

Source: https://registry.npmjs.org/temml/-/temml-0.13.5.tgz. Temml turns LaTeX into MathML,
which the browser typesets; `Temml-Local.css` uses the system math font (Cambria Math on
Windows), `Temml.woff2` is only used for `\mathcal`.
