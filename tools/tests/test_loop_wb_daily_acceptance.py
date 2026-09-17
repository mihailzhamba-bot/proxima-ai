import importlib.util,json,subprocess
from pathlib import Path
import pytest
P=Path(__file__).resolve().parents[2]/"infra/loop-control/continuous-acceptance/wb_daily_contract.py"
spec=importlib.util.spec_from_file_location("wb_daily_contract",P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SQL="""BEGIN READ ONLY; SET LOCAL proxima.tenant_id='fixture-tenant';
WITH ds AS (SELECT last_full_day,stale,collected_at FROM data_status_current),
norms AS (SELECT sample_days,window_days FROM norm_daily_current),brief AS (SELECT brief_day,status FROM brief_current)
SELECT json_build_object('data_date',ds.last_full_day,'stale',ds.stale,'norm_sample_days',norms.sample_days,'norm_window_days',norms.window_days,'norm_status_ok',true,'norm_metric_count',2,'brief_date',brief.brief_day,'brief_status',brief.status) FROM ds,norms,brief; COMMIT;"""
REFERENCE_SQL="""BEGIN READ ONLY; SET LOCAL proxima.tenant_id='fixture-tenant'; SELECT jsonb_build_object('last_full_day',d.last_full_day,'stale',d.stale,'collected_at',d.collected_at,'brief_day',b.brief_day,'brief_status',b.status,'actual',b.payload->'actual','norm',b.payload->'norm') FROM data_status_current d JOIN brief_current b USING(tenant_id) WHERE d.tenant_id='fixture-tenant'; COMMIT;"""
RECORD={"last_full_day":"2026-09-16","stale":False,"collected_at":"2026-09-17T02:00:00Z","brief_day":"2026-09-16","brief_status":"ok","norm":{"sample_days":14,"window_days":14},"actual":{"orders":46}}

def test_execute_adapter_matches_subprocess_check_and_timeout_semantics():
 cmd=["docker","run"]
 plain=m.execute_reply(cmd,{"check":False,"text":True},{"returncode":7,"stdout":"out","stderr":"err"});assert plain.returncode==7 and isinstance(plain.stdout,str)
 binary=m.execute_reply(cmd,{"check":False},{"returncode":0,"stdout":"out","stderr":"err"});assert binary.stdout==b"out" and binary.stderr==b"err"
 with pytest.raises(subprocess.CalledProcessError) as failed:m.execute_reply(cmd,{"check":True,"text":True},{"returncode":7,"stdout":"out","stderr":"err"})
 assert failed.value.output=="out" and failed.value.stderr=="err"
 with pytest.raises(subprocess.TimeoutExpired) as timeout:m.execute_reply(cmd,{"timeout":12,"text":True},{"error":"timeout","stdout":"partial","stderr":"late"})
 assert timeout.value.timeout==12 and timeout.value.output=="partial" and timeout.value.stderr=="late"

def test_sql_probe_accepts_reference_shell_stdin_and_direct_psql_c():
 reference=["docker","exec","-i","fixture-postgres","sh","-c",'read -r dbuser < "$POSTGRES_USER_FILE"; exec psql -X -A -t -U "$dbuser" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1']
 direct=["docker","exec","fixture-postgres","psql","-X","-c",SQL]
 assert m.exec_container(reference)==m.exec_container(direct)=="fixture-postgres"
 assert m.sql_from(reference,{"input":SQL})==SQL and m.sql_from(direct,{})==SQL
 assert m.direct_psql_command(reference) is None and m.direct_psql_command(direct)[0]=="psql"

def test_exact_pinned_reference_shell_transport_and_query_are_accepted():
 command=["docker","exec","-i","fixture-postgres","sh","-c",'read -r dbuser < "$POSTGRES_USER_FILE"; exec psql -X -A -t -U "$dbuser" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1']
 assert m.sql_from(command,{"input":REFERENCE_SQL})==REFERENCE_SQL

def test_shell_wrapper_cannot_hide_another_psql_command():
 wrapper=["docker","exec","-i","fixture-postgres","sh","-c",'read -r dbuser < "$POSTGRES_USER_FILE"; exec psql -X -A -t -U "$dbuser" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT 1"']
 with pytest.raises(AssertionError,match="unapproved SQL wrapper"):m.sql_from(wrapper,{"input":REFERENCE_SQL})

@pytest.mark.parametrize("suffix",[' --command=SELECT1'," -cSELECT1"," </dev/null"])
def test_shell_wrapper_rejects_concatenated_commands_and_redirects(suffix):
 wrapper=["docker","exec","-i","fixture-postgres","sh","-c",'read -r dbuser < "$POSTGRES_USER_FILE"; exec psql -X -A -t -U "$dbuser" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'+suffix]
 with pytest.raises(AssertionError,match="unapproved SQL wrapper"):m.sql_from(wrapper,{"input":REFERENCE_SQL})

def test_sql_probe_rejects_true_direct_psql_transport_ambiguity():
 direct=["docker","exec","fixture-postgres","psql","-c",SQL]
 with pytest.raises(AssertionError,match="ambiguous"):m.sql_from(direct,{"input":SQL})

@pytest.mark.parametrize("sql",[SQL.replace("BEGIN READ ONLY;", "BEGIN;"),SQL.replace("SET LOCAL proxima.tenant_id='fixture-tenant';", ""),SQL+" DELETE FROM brief_current;",SQL.replace("'fixture-tenant'","'other'")])
def test_sql_probe_rejects_missing_readonly_tenant_or_mutation(sql):
 with pytest.raises(AssertionError):m.sql_from(["docker","exec","fixture-postgres","psql","-c",sql],{})

def test_postgres_oracle_is_tenant_isolated_readonly_and_preserves_output_flags():
 source=(P.parent/"wb_daily_pg.py").read_text()
 assert source.count("ENABLE ROW LEVEL SECURITY")==5 and source.count("CREATE POLICY tenant_")==5
 assert "default_transaction_read_only=on" in source
 spec=importlib.util.spec_from_file_location("wb_daily_pg",P.parent/"wb_daily_pg.py");pg=importlib.util.module_from_spec(spec);spec.loader.exec_module(pg)
 oracle=pg.DailyPostgres()
 assert oracle.output_flags(["docker","exec","db","psql","--csv","-A","-t","-F",";"])==["--csv","-A","-t","-F",";"]
 assert oracle.output_flags(["docker","exec","db","psql","-At","-F;"])==["-A","-t","-F",";"]

def test_acceptance_source_does_not_impose_undocumented_900_or_unconditional_stop_count():
 source=(P.parent/"wb_daily_acceptance.py").read_text()
 assert "<=900" not in source and "len(stops)==len(stages)" not in source
 assert "timed out owned container was not stopped" in source and "foreign container stop" in source
 assert "pg.run(sql,cmd,day,scenario)" in source
