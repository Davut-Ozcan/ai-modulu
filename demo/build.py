import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); os.chdir(ROOT)
from analyzer.api import MODEL_VERSION
d = json.load(open("findings.json"))
d["meta"]["model_version"] = MODEL_VERSION
for f in d["findings"]:
    f.pop("device_id", None); f.pop("capture_ids", None)
t = open("demo/template.html").read().replace("/*DATA*/null", json.dumps(d, ensure_ascii=False))
open("demo/gida-risk-demo.html", "w").write(t)
print("ok", len(d["findings"]))
