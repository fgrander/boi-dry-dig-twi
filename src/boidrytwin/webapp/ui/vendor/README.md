# Vendored browser libraries of the single-page interface (feature 005)

Copied unchanged from the npm registry tarballs (via the con-pre-dig-twi repository, where the
tarballs were verified against the registry `integrity` sha512). `tests/unit/webapp/test_vendor.py`
checks the sha256 below. Do not edit these files; to update, replace them from a newer tarball
and change this table.

| File | Package | Version | Licence | sha256 |
|---|---|---|---|---|
| preact.module.js | preact | 10.29.8 | MIT | c30e721ebfdc6e2ad4c18c14d2dfb82667829c8aec27de1207774e3fc16858a8 |
| hooks.module.js | preact | 10.29.8 | MIT | a6ee626f2d01570592dd569a792e3f050154aa02890eead8c223fa3ed5aa3d5a |
| LICENSE-preact.txt | preact | 10.29.8 | MIT | 1fe6958409c8c257a70c587a18b6f7f412b179b456630790d30b2ec9a8e4b7d4 |
| htm.module.js | htm | 3.1.1 | Apache-2.0 | ab33dd3f38059b9be4d5f5350128eefb2356639c4e0bbe9d9e8b3ba75847e9e4 |
| LICENSE-htm.txt | htm | 3.1.1 | Apache-2.0 | 740725f7252e750af735d0028cc534970772f513331e9f68150fede8fb3ce00f |
| uPlot.esm.js | uplot | 1.6.32 | MIT | 5dd9b3281aa64b461b42d9945f6adb2649d346502b12281a9ae0d46599a80eba |
| uPlot.min.css | uplot | 1.6.32 | MIT | df630c6a8d6f8eeaff264b50f73ce5b114f646ffd9a0bb74f049b0a00135fa04 |
| LICENSE-uplot.txt | uplot | 1.6.32 | MIT | 8f989229699b4fe2f1a0432d0e9edc338a8a911e250e2d1b01ecd770a5f5b1bd |

Sources:
- https://registry.npmjs.org/preact/-/preact-10.29.8.tgz
- https://registry.npmjs.org/htm/-/htm-3.1.1.tgz
- https://registry.npmjs.org/uplot/-/uplot-1.6.32.tgz

`hooks.module.js` imports the bare name `preact`. `index.html` maps it to
`/ui/vendor/preact.module.js` with an import map, so the files stay unchanged. Temml, which
typesets the formulas, is in `../../static/vendor`.
