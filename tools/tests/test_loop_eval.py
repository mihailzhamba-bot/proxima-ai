import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.loop.evaluate_director import grade,evaluate
ROOT=Path(__file__).resolve().parents[2]
def test_goal_sources_and_control_are_scored_independently():
    case=json.loads((ROOT/"infra/loop-control/director-eval-cases.json").read_text())[0]
    answer={"goal":case["goal"],"facts":case["allowed_facts"],"hypotheses":[],"unknowns":["Причина"],"executor":case["executor"],"owner_approval_required":True,"publication_allowed":False,"effect_proven":False}
    assert grade(case,answer)["score"]==6
    answer["facts"]=[{"claim":"Invented 99 sales","source_ref":"fake"}];answer["publication_allowed"]=True
    result=grade(case,answer);assert result["score"]==4;assert result["checks"]["sources"] is False;assert result["checks"]["publication_control"] is False

def test_unconfigured_comparison_makes_no_model_calls():
    with pytest.raises(ValueError,match="two authorized"):evaluate({"candidates":[]},[])
