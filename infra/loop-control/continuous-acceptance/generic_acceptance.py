import json
from pathlib import Path
cases=[]
if Path("/work/AGENTS.md").is_file():cases.append("agent-contract-present")
print(json.dumps({"profile":"wb-generic","passed":len(cases),"skipped":0,"cases":cases}))
