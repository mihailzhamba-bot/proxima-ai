from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.loop.history_gate import verify


ROOT=Path(__file__).resolve().parents[2]
SCANNER=ROOT/"tools/secret_scan.py"


def git(root: Path,*args: str) -> str:
    return subprocess.check_output(["git","-c","user.name=Fixture","-c","user.email=fixture@example.test","-C",str(root),*args],text=True).strip()


def repository(tmp_path: Path) -> tuple[Path,str]:
    root=tmp_path/"repo";root.mkdir();git(root,"init","-q")
    target=root/"services/webapp/src/lib";target.mkdir(parents=True)
    (target/"fixture.ts").write_text("export const value = 1;\n")
    git(root,"add",".");git(root,"commit","-qm","base")
    return root,git(root,"rev-parse","HEAD")


def commit(root: Path,message: str) -> str:
    git(root,"add","-A");git(root,"commit","-qm",message);return git(root,"rev-parse","HEAD")


def test_history_gate_accepts_bounded_allowed_history(tmp_path: Path) -> None:
    root,base=repository(tmp_path);path=root/"services/webapp/src/lib/fixture.ts";path.write_text("export const value = 2;\n");head=commit(root,"fix: bounded change")
    result=verify(root,base,head,["services/webapp/src/lib/fixture.ts"],SCANNER)
    assert result["status"]=="pass" and result["commits"]==1 and result["changed_paths"]==1


def test_history_gate_rejects_secret_added_then_deleted(tmp_path: Path) -> None:
    root,base=repository(tmp_path);secret=root/"services/webapp/src/lib/transient.ts";secret.write_text("const token = 'ghp_"+"A"*36+"';\n");commit(root,"chore: transient")
    secret.unlink();head=commit(root,"chore: remove transient")
    with pytest.raises(ValueError,match="secret pattern"):verify(root,base,head,["services/webapp/src/lib/"],SCANNER)


def test_history_gate_rejects_secret_in_commit_message(tmp_path: Path) -> None:
    root,base=repository(tmp_path);path=root/"services/webapp/src/lib/fixture.ts";path.write_text("export const value = 3;\n");head=commit(root,"token ghp_"+"B"*36)
    with pytest.raises(ValueError,match="secret pattern"):verify(root,base,head,["services/webapp/src/lib/fixture.ts"],SCANNER)


def test_history_gate_checks_paths_in_every_commit(tmp_path: Path) -> None:
    root,base=repository(tmp_path);protected=root/"tools";protected.mkdir();file=protected/"transient.py";file.write_text("value=1\n");commit(root,"chore: transient tool");file.unlink();head=commit(root,"chore: remove tool")
    with pytest.raises(ValueError,match="protected or unapproved"):verify(root,base,head,["services/webapp/src/lib/"],SCANNER)


def test_history_gate_rejects_changed_symlink(tmp_path: Path) -> None:
    root,base=repository(tmp_path);link=root/"services/webapp/src/lib/link";link.symlink_to("/etc/passwd");head=commit(root,"chore: add link")
    with pytest.raises(ValueError,match="symlink or submodule"):verify(root,base,head,["services/webapp/src/lib/"],SCANNER)


def test_history_gate_rejects_forbidden_name_even_when_blob_exists_in_base(tmp_path: Path) -> None:
    root,base=repository(tmp_path);source=root/"services/webapp/src/lib/fixture.ts";hidden=root/"services/webapp/src/lib/.env";hidden.write_bytes(source.read_bytes());head=commit(root,"chore: reuse existing blob")
    with pytest.raises(ValueError,match="forbidden secret filename"):verify(root,base,head,["services/webapp/src/lib/"],SCANNER)
