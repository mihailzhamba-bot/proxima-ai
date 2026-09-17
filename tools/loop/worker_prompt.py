"""Deterministic worker delivery prompt and bounded prior-attempt feedback."""
from __future__ import annotations
import hashlib,json,re,uuid
from pathlib import PurePosixPath
SHA=re.compile(r"^[0-9a-f]{40}$");DIGEST=re.compile(r"^[0-9a-f]{64}$");JOB=re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$");TEMPLATE=re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
FEEDBACK={
 "missing_resource_limits":"Add the required Docker memory, CPU and PID limits to every stage invocation.",
 "missing_readonly_tenant_transaction":"Run the readiness probe in a READ ONLY transaction with the exact configured tenant bound by SET LOCAL.",
 "timeout_cleanup_contract":"On timeout, stop only the container name created by that stage.",
 "subprocess_check_semantics":"Honor subprocess check semantics and preserve a truthful failed status.",
 "reference_behavior_mismatch":"Match the pinned operator reference behavior while staying inside the existing allowed paths.",
}
def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def template_fingerprint(name,definition):
 portable={key:definition.get(key) for key in ("base_sha","prompt_sha256","allowed_paths","contract_files","profile","profile_id","profile_revision")}
 for key in ("allowed_paths","contract_files"):
  if isinstance(portable[key],list):portable[key]=sorted(portable[key])
 return hashlib.sha256(canonical({"name":name,"contract":portable}).encode()).hexdigest()
def allowed_paths_digest(paths):return digest(sorted(paths))
def validate_paths(paths):
 if not isinstance(paths,list) or not paths:raise ValueError("template paths unavailable")
 for value in paths:
  path=PurePosixPath(value) if isinstance(value,str) else None
  if path is None or not value or any(ord(char)<32 for char in value) or path.is_absolute() or ".." in path.parts or path.parts[0]==".git":raise ValueError("invalid template path")
 return paths
def validate_sidecar(value,job,template_name,template,policy=None):
 required={"schema_version","job_id","queue_id","attempt","requirement_id","path_set_id","policy_fingerprint","template_name","template_fingerprint","base_sha","raw_prompt_sha256","allowed_paths_sha256","predecessor","feedback_codes","reference"}
 if not isinstance(value,dict) or set(value)!=required or value.get("schema_version")!=1:raise ValueError("invalid attempt feedback schema")
 if value.get("job_id")!=job or not JOB.fullmatch(job) or not DIGEST.fullmatch(str(value.get("policy_fingerprint",""))) or value.get("template_name")!=template_name or not TEMPLATE.fullmatch(template_name):raise ValueError("attempt feedback identity mismatch")
 attempt=value.get("attempt");queue=value.get("queue_id")
 if not isinstance(attempt,int) or isinstance(attempt,bool) or not 2<=attempt<=3 or not isinstance(queue,str) or job!=f"{queue}-a{attempt}" or len(job)>40:raise ValueError("attempt feedback retry identity mismatch")
 paths=validate_paths(template.get("allowed_paths"))
 if (value.get("template_fingerprint")!=template_fingerprint(template_name,template) or value.get("base_sha")!=template.get("base_sha")
     or value.get("raw_prompt_sha256")!=template.get("prompt_sha256") or value.get("allowed_paths_sha256")!=allowed_paths_digest(paths)):raise ValueError("attempt feedback template binding mismatch")
 predecessor=value.get("predecessor");receipt=predecessor.get("acceptance_receipt") if isinstance(predecessor,dict) else None
 if (not isinstance(predecessor,dict) or set(predecessor)!={"job_id","attempt","head_sha","diff_sha256","acceptance_receipt"}
     or predecessor.get("attempt")!=attempt-1 or predecessor.get("job_id")!=f"{queue}-a{attempt-1}" or not SHA.fullmatch(str(predecessor.get("head_sha","")))
     or not DIGEST.fullmatch(str(predecessor.get("diff_sha256",""))) or not isinstance(receipt,dict)
     or set(receipt)!={"base_sha","sha","diff_sha256","status","reason","evidence_sha256"}
     or (receipt.get("base_sha"),receipt.get("sha"),receipt.get("diff_sha256"))!=(template.get("base_sha"),predecessor.get("head_sha"),predecessor.get("diff_sha256"))
     or receipt.get("status")!="blocked" or receipt.get("reason")!="independent_acceptance_blocked" or not DIGEST.fullmatch(str(receipt.get("evidence_sha256","")))):raise ValueError("attempt feedback acceptance evidence mismatch")
 codes=value.get("feedback_codes")
 if not isinstance(codes,list) or not 1<=len(codes)<=4 or len(set(codes))!=len(codes) or any(code not in FEEDBACK for code in codes):raise ValueError("attempt feedback code unavailable")
 reference=value.get("reference")
 if (not isinstance(reference,dict) or set(reference)!={"ref","sha256","content"} or not isinstance(reference.get("ref"),str)
     or not DIGEST.fullmatch(str(reference.get("sha256",""))) or not isinstance(reference.get("content"),str)
     or not reference["content"] or len(reference["content"].encode())>65536 or "\x00" in reference["content"]
     or hashlib.sha256(reference["content"].encode()).hexdigest()!=reference["sha256"]):raise ValueError("attempt feedback reference mismatch")
 if policy is not None:
  if value["policy_fingerprint"]!=digest(policy):raise ValueError("attempt feedback policy fingerprint mismatch")
  requirement=policy.get("requirements",{}).get(value.get("requirement_id"));scope=requirement.get("path_sets",{}).get(value.get("path_set_id")) if isinstance(requirement,dict) else None
  if (not isinstance(scope,dict) or requirement.get("base_sha")!=template.get("base_sha") or scope.get("allowed_paths")!=paths
      or scope.get("contract_files")!=template.get("contract_files")):raise ValueError("attempt feedback policy binding mismatch")
  sources={(item.get("ref"),item.get("sha256")) for item in requirement.get("source_evidence",[]) if isinstance(item,dict)}
  if (reference["ref"],reference["sha256"]) not in sources:raise ValueError("attempt feedback reference is not pinned")
 return value
def delivery_prompt(raw,template,job,template_name,sidecar=None):
 if hashlib.sha256(raw).hexdigest()!=template.get("prompt_sha256"):raise ValueError("raw prompt differs from template")
 paths=validate_paths(template.get("allowed_paths"));authority={"checkout":"proxima-ai","base_sha":template.get("base_sha"),"allowed_paths":paths,"commit":"Create exactly one scoped commit containing only changes within allowed_paths."}
 result=raw.rstrip(b"\n")+b"\n\nTRUSTED DELIVERY CONSTRAINTS (authoritative):\n"+json.dumps(authority,sort_keys=True,ensure_ascii=False,indent=2).encode()+b"\n"
 sidecar_sha=None
 if sidecar is not None:
  validate_sidecar(sidecar,job,template_name,template);sidecar_sha=digest(sidecar);reference=sidecar["reference"]
  feedback={"codes":[{"code":code,"instruction":FEEDBACK[code]} for code in sidecar["feedback_codes"]],"predecessor":{key:sidecar["predecessor"][key] for key in ("job_id","head_sha","diff_sha256")},"reference":{"ref":reference["ref"],"sha256":reference["sha256"],"content":reference["content"]}}
  result+=b"\nTRUSTED PRIOR ATTEMPT FEEDBACK (authoritative, scope unchanged):\n"+json.dumps(feedback,sort_keys=True,ensure_ascii=False,indent=2).encode()+b"\n"
 return result,{"raw_prompt_sha256":hashlib.sha256(raw).hexdigest(),"feedback_sidecar_sha256":sidecar_sha,"delivery_prompt_sha256":hashlib.sha256(result).hexdigest()}
