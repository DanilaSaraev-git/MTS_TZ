import json, os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).parents[1]

def run(*args, cwd=None):
    env=os.environ.copy(); env["PYTHONPATH"]=str(ROOT/"scripts")
    return subprocess.run([sys.executable,"-m","review_data_spec.cli",*map(str,args)],cwd=cwd,env=env,text=True,capture_output=True)

def test_help_and_demo_outside_repository(tmp_path):
    assert run("--help",cwd=tmp_path).returncode == 0
    done=run("run-demo","--output-root",tmp_path/"runs","--run-id","cli-demo",cwd=tmp_path)
    assert done.returncode == 0, done.stderr
    payload=json.loads(done.stdout); report=Path(payload["report"])
    assert report.exists() and "demo_fixture" in report.read_text()

def test_validate_returns_two_for_bad_report(text_run,tmp_path):
    (text_run/"report.json").write_text("{}",encoding="utf-8")
    done=run("validate",text_run,cwd=tmp_path)
    assert done.returncode == 2 and json.loads(done.stdout)["valid"] is False
