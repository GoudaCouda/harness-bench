from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.solution import plan_kubernetes_finalizer
data=json.loads((ROOT/'input.json').read_text())
out=plan_kubernetes_finalizer(*(data[name] for name in ('nodes', 'policy')))
(ROOT/'out').mkdir(exist_ok=True)
(ROOT/'out/result.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
