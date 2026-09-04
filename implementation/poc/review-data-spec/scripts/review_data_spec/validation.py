from __future__ import annotations
from pathlib import Path
from jsonschema import Draft202012Validator
from . import RESOURCES, ReviewError, digest, normalize, read_json, within, write_json


def _error(errors,message): errors.append(message)

def validate_report(run_dir:Path,report_path:Path|None=None,*,write_result=True):
    run_dir=Path(run_dir).resolve(); report_path=Path(report_path or run_dir/"report.json").resolve(); errors=[]
    try:
        manifest=read_json(run_dir/"manifest.json"); bundle=read_json(run_dir/"bundle.json"); report=read_json(report_path)
    except ReviewError as exc:
        result={"schema_version":1,"valid":False,"coverage_status":"invalid","report_sha256":None,"errors":[str(exc)]}
        if write_result and run_dir.is_dir(): write_json(run_dir/"validation.json",result)
        return result
    for relative,expected in manifest.get("artifacts",{}).items():
        try:
            path=within(run_dir,relative)
            if not path.is_file() or digest(path)!=expected:_error(errors,f"Prepared artifact changed: {relative}")
        except ReviewError as exc:_error(errors,str(exc))
    for source in manifest.get("sources",[]):
        if source.get("status")=="available":
            try:
                path=within(run_dir,source["snapshot"])
                if not path.is_file() or digest(path)!=source.get("sha256"):_error(errors,f"Source snapshot changed: {source.get('id')}")
            except (ReviewError,KeyError) as exc:_error(errors,f"Invalid source snapshot: {exc}")
    for item in sorted(Draft202012Validator(read_json(RESOURCES/"report.schema.json")).iter_errors(report),key=lambda e:list(e.path)):
        location=".".join(map(str,item.path)) or "$"; _error(errors,f"Schema {location}: {item.message}")
    fragments={f["id"]:f for f in bundle.get("fragments",[]) if isinstance(f,dict) and "id" in f}
    sources={s["id"]:s for s in bundle.get("sources",[]) if isinstance(s,dict) and "id" in s}
    if manifest.get("run_id")!=bundle.get("run_id") or report.get("run_id")!=manifest.get("run_id"):_error(errors,"Run-id mismatch")
    coverage=report.get("coverage",{}) if isinstance(report,dict) else {}; reviewed=coverage.get("reviewed_fragment_ids",[]); unread_items=coverage.get("unreviewed",[])
    unread=[x.get("fragment_id") for x in unread_items if isinstance(x,dict)] if isinstance(unread_items,list) else []
    if len(unread)!=len(set(unread)):_error(errors,"Duplicate unreviewed fragment")
    accounted=set(reviewed) | set(unread)
    if set(reviewed)&set(unread):_error(errors,"Coverage lists a fragment as both reviewed and unreviewed")
    if accounted!=set(fragments):_error(errors,"Coverage must account for every prepared fragment exactly once")
    ids=[]
    findings=report.get("findings",[]) if isinstance(report,dict) else []
    if isinstance(findings,list):
      for finding in findings:
        if not isinstance(finding,dict):continue
        ids.append(finding.get("id")); kind=finding.get("kind"); anchors=finding.get("anchors",[]); scope=finding.get("scope",[])
        if kind=="missing":
            if anchors:_error(errors,f"{finding.get('id')}: missing requirement must not fabricate anchors")
            if not scope:_error(errors,f"{finding.get('id')}: missing requirement needs document scope")
        elif not anchors:_error(errors,f"{finding.get('id')}: finding needs an anchor")
        bases=[]
        for anchor in anchors if isinstance(anchors,list) else []:
            if not isinstance(anchor,dict):continue
            fragment=fragments.get(anchor.get("fragment_id")); source=sources.get(anchor.get("source_id"))
            if not fragment or not source:_error(errors,f"{finding.get('id')}: unknown anchor")
            elif fragment.get("source_id")!=anchor.get("source_id"):_error(errors,f"{finding.get('id')}: source/fragment mismatch")
            elif normalize(anchor.get("quote","")) not in normalize(fragment.get("text","")):_error(errors,f"{finding.get('id')}: quote is not in fragment")
            else:bases.append(source.get("role"))
            if anchor.get("fragment_id") not in reviewed:_error(errors,f"{finding.get('id')}: anchor is outside reviewed coverage")
        for fragment_id in scope if isinstance(scope,list) else []:
            fragment=fragments.get(fragment_id)
            if not fragment:_error(errors,f"{finding.get('id')}: unknown scope fragment")
            else:bases.append(sources.get(fragment.get("source_id"),{}).get("role"))
            if fragment_id not in reviewed:_error(errors,f"{finding.get('id')}: scope is outside reviewed coverage")
        if "document" not in bases:_error(errors,f"{finding.get('id')}: no basis in primary document")
        status=finding.get("status"); human=finding.get("human_review")
        if status=="unreviewed" and human is not None:_error(errors,f"{finding.get('id')}: unreviewed finding cannot have human decision")
        if status!="unreviewed" and human is None:_error(errors,f"{finding.get('id')}: human decision details are required")
    if len(ids)!=len(set(ids)):_error(errors,"Duplicate finding id")
    incomplete=bool(unread) or any(s.get("status")!="available" for s in manifest.get("sources",[])) or bool(bundle.get("diagnostics"))
    status="invalid" if errors else ("partial" if incomplete else "complete")
    result={"schema_version":1,"valid":not errors,"coverage_status":status,"report_sha256":digest(report_path) if report_path.is_file() else None,"errors":errors}
    if write_result:write_json(run_dir/"validation.json",result)
    return result
