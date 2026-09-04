from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from . import ReviewError
from .demo import run_demo
from .prepare import prepare_run
from .render import render_report
from .validation import validate_report

def parser():
    root=argparse.ArgumentParser(prog="review-data-spec",description="Prepare evidence and validate an agent-authored review")
    commands=root.add_subparsers(dest="command",required=True)
    prepare=commands.add_parser("prepare",help="create an immutable input snapshot")
    prepare.add_argument("input",type=Path); prepare.add_argument("--output-root",type=Path,required=True); prepare.add_argument("--run-id"); prepare.add_argument("--profile",type=Path); prepare.add_argument("--context",type=Path,action="append",default=[])
    validate=commands.add_parser("validate",help="validate report structure, integrity and citations")
    validate.add_argument("run_dir",type=Path); validate.add_argument("--report",type=Path)
    render=commands.add_parser("render",help="validate and render Markdown")
    render.add_argument("run_dir",type=Path); render.add_argument("--report",type=Path); render.add_argument("--output",type=Path)
    demo=commands.add_parser("run-demo",help="run a deterministic synthetic fixture; no model is called")
    demo.add_argument("--output-root",type=Path,required=True); demo.add_argument("--run-id")
    return root

def main(argv=None):
    args=parser().parse_args(argv)
    try:
      if args.command=="prepare":
        run=prepare_run(args.input,args.output_root,run_id=args.run_id,profile_path=args.profile,contexts=args.context)
        manifest=json.loads((run/"manifest.json").read_text()); print(json.dumps({"run_dir":str(run),"run_id":run.name,"diagnostics":json.loads((run/"bundle.json").read_text())["diagnostics"],"unavailable_sources":[x["id"] for x in manifest["sources"] if x["status"]!="available"]},ensure_ascii=False))
      elif args.command=="validate":
        result=validate_report(args.run_dir,args.report); print(json.dumps(result,ensure_ascii=False)); return 0 if result["valid"] else 2
      elif args.command=="render":
        output=render_report(args.run_dir,args.report,args.output); print(json.dumps({"report":str(output)},ensure_ascii=False))
      else:
        run,output=run_demo(args.output_root,args.run_id); print(json.dumps({"run_dir":str(run),"report":str(output)},ensure_ascii=False))
    except ReviewError as exc:
      print(json.dumps({"error":str(exc)},ensure_ascii=False)); return 2
    return 0

if __name__=="__main__": raise SystemExit(main())
