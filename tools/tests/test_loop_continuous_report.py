import json,subprocess,sys
from types import SimpleNamespace
from pathlib import Path
from tools.loop.continuous_report import Reporter,render
def test_report_is_sent_once_during_08_moscow(tmp_path):
 status={"current":{"id":"one","state":"running","updated":0,"blocker":None,"pr_url":None},"next":{"id":"two","state":"ready"}}
 calls=[]
 def execute(argv,**kwargs):
  calls.append(json.loads(kwargs["input"]));return SimpleNamespace(returncode=0,stdout=b'{"message_id":1}')
 reporter=Reporter({"state_file":str(tmp_path/"report.json"),"command":["/trusted/send"]},execute)
 at=5*3600
 assert reporter.run(status,at)["status"]=="sent"
 assert reporter.run(status,at+60)["status"]=="deduplicated"
 assert len(calls)==1 and "Текущая: one" in calls[0]["text"]
def test_report_outside_hour_is_not_sent(tmp_path):
 reporter=Reporter({"state_file":str(tmp_path/"report.json"),"command":["/trusted/send"]})
 assert reporter.run({"current":None,"next":None},0)=={"status":"not_due"}


def test_report_separates_last_pr_and_final_blockers():
 status={"current":None,"next":None,"items":[
  {"id":"done","state":"merged","updated":2,"pr_url":"https://github.com/acme/repo/pull/1","lease_id":None},
  {"id":"bad","state":"rejected","updated":3,"blocker":"duplicate scope","lease_id":None}]}
 text=render(status)
 assert "Последний PR: https://github.com/acme/repo/pull/1" in text
 assert "Финальные блокеры: bad: duplicate scope." in text


def test_dedicated_report_timer_owns_08_moscow_schedule():
 root=Path(__file__).resolve().parents[2]
 timer=(root/"infra/loop-control/loop-continuous-report.timer").read_text()
 service=(root/"infra/loop-control/loop-continuous-report.service").read_text()
 tick=(root/"tools/loop/continuous_tick.py").read_text()
 assert "OnCalendar=*-*-* 08:00:00 Europe/Moscow" in timer and "Persistent=true" in timer
 assert "/opt/loop/continuous_report_once.py" in service
 assert 'Admission(config["admission"],client.call),None,observer,refresher' in tick


def test_report_imports_in_isolated_installed_layout(tmp_path):
 root=Path(__file__).resolve().parents[2]
 for name in ("continuous_report.py","continuous_admission.py"):
  (tmp_path/name).write_bytes((root/"tools/loop"/name).read_bytes())
 probe=tmp_path/"probe.py";probe.write_text("import sys;sys.path.insert(0,sys.argv[1]);import continuous_report;print(continuous_report.__name__)\n")
 result=subprocess.run([sys.executable,"-I",str(probe),str(tmp_path)],capture_output=True,text=True,check=False)
 assert result.returncode==0 and result.stdout.strip()=="continuous_report" and "night_batch" not in result.stderr


def test_continuous_unit_writes_common_git_directory():
 root=Path(__file__).resolve().parents[2];unit=(root/"infra/loop-control/loop-continuous.service").read_text()
 assert "/srv/loop/source/proxima-ai.git" in unit
 assert "/srv/loop/source/proxima-ai/.git" not in unit


def test_continuous_tick_bypasses_proxy_for_fixed_github_origins():
 root=Path(__file__).resolve().parents[2];unit=(root/"infra/loop-control/loop-continuous.service").read_text()
 assert "Environment=NO_PROXY=127.0.0.1,localhost,api.github.com,github.com" in unit
