"""One separate process startup probe; no KB, API or benchmark replay."""
from pathlib import Path
import subprocess,sys,time,json

code='''import time,json
t=time.perf_counter()
import execution_engine
engine=time.perf_counter()-t
t=time.perf_counter()
from sklearn.cluster import KMeans
sklearn=time.perf_counter()-t
print(json.dumps(dict(executor_import_seconds=engine,sklearn_import_seconds=sklearn)))
'''
t=time.perf_counter()
r=subprocess.run([sys.executable,'-X','utf8','-c',code],cwd=Path(__file__).parent,
                 capture_output=True,text=True,encoding='utf-8',check=True)
data=json.loads(r.stdout)
data.update(child_process_wall_seconds=time.perf_counter()-t,
            scope='one new Python process with existing OS caches; separate startup diagnostic, not retroactive timing of the completed replay')
(Path(__file__).parent/'startup-probe.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(data,ensure_ascii=False))
