from __future__ import annotations
import importlib.metadata, json, re, shutil, sys, tempfile, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from jsonschema import Draft202012Validator
from . import RESOURCES, ReviewError, __version__, digest, read_json, write_json
from .parsers import adapter_for

RUN_ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")

def _load_profile(path):
    profile=read_json(path)
    errors=sorted(Draft202012Validator(read_json(RESOURCES/"profile.schema.json")).iter_errors(profile),key=lambda e:list(e.path))
    if errors: raise ReviewError("Invalid profile: "+"; ".join(e.message for e in errors))
    return profile

def _default_id(): return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]

def prepare_run(document:Path,output_root:Path,*,run_id=None,profile_path=None,contexts=()):
    began=time.monotonic(); document=Path(document).resolve(); output_root=Path(output_root).resolve(); run_id=run_id or _default_id()
    if not RUN_ID.fullmatch(run_id): raise ReviewError("Invalid run-id")
    if not document.is_file(): raise ReviewError(f"Document not found: {document}")
    final=output_root/run_id
    if final.exists(): raise ReviewError(f"Run already exists: {run_id}")
    if profile_path:
        profile_path=Path(profile_path).resolve(); profile=_load_profile(profile_path); mode="selected"; base=profile_path.parent
    else:
        profile_path=RESOURCES/"base-profile.json"; profile=_load_profile(profile_path); mode="default"; base=profile_path.parent
    requested=[(base/entry).resolve() for entry in profile["context_files"]]+[Path(x).resolve() for x in contexts]
    seen=set(); requested=[x for x in requested if not (str(x) in seen or seen.add(str(x)))]
    output_root.mkdir(parents=True,exist_ok=True); temporary=Path(tempfile.mkdtemp(prefix=f".{run_id}-",dir=output_root))
    try:
        (temporary/"sources").mkdir(); (temporary/"raw").mkdir()
        sources=[]; fragments=[]; diagnostics=[]; parsers=[]
        for number,(path,role) in enumerate([(document,"document")]+[(p,"context") for p in requested],1):
            source_id=f"s{number:03d}"; record={"id":source_id,"role":role,"name":path.name,"original_path":str(path)}
            if not path.is_file():
                if role=="document": raise ReviewError(f"Document not found: {path}")
                record.update(status="unavailable",diagnostic="File not found"); sources.append(record); continue
            try: adapter=adapter_for(path); parsed=adapter.parse(path,source_id)
            except ReviewError as exc:
                if role=="document": raise
                record.update(status="unavailable",diagnostic=str(exc)); sources.append(record); continue
            if role=="document" and not parsed["fragments"]: raise ReviewError("No readable text in the primary document; OCR is outside this PoC")
            snapshot=f"sources/{source_id}{path.suffix.lower()}"; shutil.copyfile(path,temporary/snapshot)
            raw=f"raw/{source_id}.{parsed['parser']['name']}.json"; write_json(temporary/raw,{"schema_version":1,"source_id":source_id,**parsed["raw"]})
            record.update(status="available",snapshot=snapshot,sha256=digest(path),size=path.stat().st_size,parser=parsed["parser"],raw=raw)
            sources.append(record); fragments.extend(parsed["fragments"]); diagnostics.extend(parsed["diagnostics"]); parsers.append(parsed["parser"])
        bundle={"schema_version":1,"run_id":run_id,"sources":[{"id":s["id"],"role":s["role"],"name":s["name"],"status":s["status"]} for s in sources],"fragments":fragments,"diagnostics":diagnostics}
        settings={"schema_version":1,"normalization":"Unicode NFC + whitespace collapse for quote validation only","parsers":parsers}
        write_json(temporary/"bundle.json",bundle); write_json(temporary/"profile.json",profile); write_json(temporary/"settings.json",settings)
        template={"schema_version":1,"run_id":run_id,"generation":{"mode":"agent","agent":"unknown","model":"unknown","model_version":"unknown"},"summary":"Шаблон: смысловое ревью ещё не выполнено.","coverage":{"reviewed_fragment_ids":[],"unreviewed":[{"fragment_id":f["id"],"reason":"Смысловое ревью ещё не выполнено"} for f in fragments]},"findings":[],"limitations":["Шаблон подготовлен автоматически и не является результатом смыслового ревью."]}
        write_json(temporary/"report.template.json",template)
        artifact_names=["bundle.json","profile.json","settings.json","report.template.json"]+[s["raw"] for s in sources if s.get("raw")]
        artifacts={name:digest(temporary/name) for name in artifact_names}
        runtime={"python":sys.version.split()[0]}
        for package in ["pdfplumber","pdfminer.six","pypdfium2"]:
            try: runtime[package]=importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError: pass
        manifest={"schema_version":1,"run_id":run_id,"created_at":datetime.now(timezone.utc).isoformat(),"skill_version":__version__,"runtime":runtime,"profile_mode":mode,"profile_source":str(profile_path),"sources":sources,"artifacts":artifacts,"prepare_seconds":round(time.monotonic()-began,6)}
        write_json(temporary/"manifest.json",manifest); temporary.rename(final)
        return final
    except Exception:
        shutil.rmtree(temporary,ignore_errors=True); raise
