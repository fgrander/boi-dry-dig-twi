# PyInstaller recipe for BoiDryTwin.exe: one file with Python, the models, the web app,
# its assets (templates, static, plotly.min.js), pint's unit definitions and the examples.
# Build: powershell -File scripts/build_exe.ps1  (output: dist/BoiDryTwin.exe)
# ruff: noqa
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 - defined by PyInstaller

datas = []
datas += collect_data_files("boidrytwin", includes=["webapp/templates/*", "webapp/static/*", "webapp/ui/**/*", "webapp/recirculation_block.toml"])
datas += collect_data_files("plotly", includes=["package_data/plotly.min.js"])
datas += collect_data_files("pint")
datas += [(str(p), str(Path("examples") / p.parent.relative_to(ROOT / "examples")))
          for p in (ROOT / "examples").rglob("*") if p.is_file()]

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("boidrytwin")
    + ["multipart", "python_multipart", "jinja2"]
)

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["cantera", "CoolProp", "pytest", "hypothesis", "mypy", "ruff", "tkinter",
              "matplotlib", "IPython", "plotly.express", "plotly.graph_objects"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BoiDryTwin",
    console=True,  # a small window shows where the data is; closing it stops the app
    upx=False,
)
