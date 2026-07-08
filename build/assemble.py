"""Splice libs + payload into the template -> dist/accra-flood-grid.html."""
import os

ROOT = "/Users/osborn/BIG PROJECT/accra-flood-grid"
TP = f"{ROOT}/build/three-pkg"

with open(f"{ROOT}/build/template.html") as f:
    html = f.read()

libs = {
    "//__THREE__": f"{TP}/build/three.min.js",
    "//__ORBIT__": f"{TP}/examples/js/controls/OrbitControls.js",
    "//__PASS__": f"{TP}/examples/js/postprocessing/Pass.js",
    "//__EFFECTCOMPOSER__": f"{TP}/examples/js/postprocessing/EffectComposer.js",
    "//__RENDERPASS__": f"{TP}/examples/js/postprocessing/RenderPass.js",
    "//__SHADERPASS__": f"{TP}/examples/js/postprocessing/ShaderPass.js",
    "//__COPYSHADER__": f"{TP}/examples/js/shaders/CopyShader.js",
    "//__LUMSHADER__": f"{TP}/examples/js/shaders/LuminosityHighPassShader.js",
    "//__BLOOMPASS__": f"{TP}/examples/js/postprocessing/UnrealBloomPass.js",
}
for marker, path in libs.items():
    with open(path) as f:
        code = f.read()
    assert marker in html, marker
    assert "</script" not in code, path
    html = html.replace(marker, code)

with open(f"{ROOT}/build/earcut-pkg/src/earcut.js") as f:
    ec = f.read()
ec = ec.replace("module.exports = earcut;", "window.earcut = earcut;")
ec = ec.replace("module.exports.default = earcut;", "")
assert "window.earcut" in ec
html = html.replace("//__EARCUT__", ec)

with open(f"{ROOT}/data/payload.json") as f:
    payload = f.read()
assert "</" not in payload
html = html.replace('{"__PAYLOAD__":1}', payload)

with open(f"{ROOT}/data/places.json") as f:
    places = f.read()
assert "</" not in places
assert '["__PLACES__"]' in html
html = html.replace('["__PLACES__"]', places)

import base64
with open(f"{ROOT}/data/satellite.jpg", "rb") as f:
    sat = base64.b64encode(f.read()).decode()
assert '"__SAT__"' in html
html = html.replace('"__SAT__"', '"' + sat + '"')

out = f"{ROOT}/dist/accra-flood-grid.html"
with open(out, "w") as f:
    f.write(html)
print(f"assembled: {out} ({os.path.getsize(out)/1e6:.1f} MB)")
