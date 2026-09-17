import json
from types import SimpleNamespace
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
