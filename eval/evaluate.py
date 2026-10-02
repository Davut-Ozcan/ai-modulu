"""Ortak benchmark: her ekip üyesinin modeli aynı test setinde ölçülür.
Kullanım: python -m eval.evaluate   (predict fonksiyonunu değiştirerek kendi modelini tak)
Model arayüzü: predict(text:str) -> set[str] (kategori kodları)
"""
import json
from collections import defaultdict
from analyzer.engine import classify

def predict(text: str) -> set[str]:
    return {h.category for h in classify(text, "text") if h.severity != "low" or h.category in ("hakaret",)}

rows = [json.loads(l) for l in open("eval/test_set.jsonl")]
tp, fp, fn = defaultdict(int), defaultdict(int), defaultdict(int)
errors = []
for r in rows:
    gold, pred = set(r["labels"]), predict(r["text"])
    for c in pred & gold: tp[c] += 1
    for c in pred - gold: fp[c] += 1
    for c in gold - pred: fn[c] += 1
    if gold != pred: errors.append((r["text"], sorted(gold), sorted(pred)))

cats = sorted(set(tp) | set(fp) | set(fn))
print(f"{'kategori':16}{'P':>6}{'R':>6}{'F1':>6}  tp fp fn")
T = {"tp":0,"fp":0,"fn":0}
for c in cats:
    p = tp[c]/(tp[c]+fp[c]) if tp[c]+fp[c] else 0
    rc = tp[c]/(tp[c]+fn[c]) if tp[c]+fn[c] else 0
    f = 2*p*rc/(p+rc) if p+rc else 0
    T["tp"]+=tp[c];T["fp"]+=fp[c];T["fn"]+=fn[c]
    print(f"{c:16}{p:6.2f}{rc:6.2f}{f:6.2f}  {tp[c]:2} {fp[c]:2} {fn[c]:2}")
P=T["tp"]/(T["tp"]+T["fp"]); R=T["tp"]/(T["tp"]+T["fn"])
print(f"{'MICRO':16}{P:6.2f}{R:6.2f}{2*P*R/(P+R):6.2f}")
print(f"\nexact-match acc: {1-len(errors)/len(rows):.2f}  ({len(rows)} örnek)")
print("\nHatalar:")
for e in errors: print(" ", e)
