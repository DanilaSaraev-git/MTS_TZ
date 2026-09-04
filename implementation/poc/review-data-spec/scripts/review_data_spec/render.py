from __future__ import annotations
import os
from pathlib import Path
from urllib.parse import quote
from . import ReviewError, read_json, write_text
from .validation import validate_report

PRIORITY={"high":"Высокий","medium":"Средний","low":"Низкий"}; STATUS={"unreviewed":"Не рассмотрено","confirmed":"Подтверждено","rejected":"Отклонено","needs_context":"Нужен контекст"}
def clean(value): return str(value).replace("|","\\|").replace("\r"," ")
def render_report(run_dir:Path,report_path:Path|None=None,output:Path|None=None):
    run_dir=Path(run_dir).resolve(); report_path=Path(report_path or run_dir/"report.json").resolve(); output=Path(output or run_dir/"report.md").resolve()
    manifest=read_json(run_dir/"manifest.json")
    protected={run_dir/name for name in {"manifest.json","bundle.json","profile.json","settings.json","report.template.json","report.json","validation.json"}}
    protected.update((run_dir/item).resolve() for item in manifest.get("artifacts",{}))
    protected.update((run_dir/source["snapshot"]).resolve() for source in manifest.get("sources",[]) if source.get("snapshot"))
    protected.update(Path(source["original_path"]).resolve() for source in manifest.get("sources",[]) if source.get("original_path"))
    if output in protected:raise ReviewError("Refusing to overwrite an input or structured run artifact")
    validation=validate_report(run_dir,report_path)
    if not validation["valid"]:raise ReviewError("Report is invalid: "+"; ".join(validation["errors"]))
    report=read_json(report_path); bundle=read_json(run_dir/"bundle.json"); profile=read_json(run_dir/"profile.json")
    source_map={s["id"]:s for s in manifest["sources"]}; fragment_map={f["id"]:f for f in bundle["fragments"]}
    lines=["# Отчёт предварительного ревью ТЗ","",f"- Запуск: `{clean(report['run_id'])}`",f"- Режим: `{clean(report['generation']['mode'])}`",f"- Агент: `{clean(report['generation']['agent'])}`",f"- Модель: `{clean(report['generation']['model'])}` / `{clean(report['generation']['model_version'])}`",f"- Профиль: {clean(profile['name'])}, версия {clean(profile['version'])}",f"- Техническая проверка: `{validation['coverage_status']}`. Она проверяет структуру и привязки, а не правильность выводов.","","## Сводка","",clean(report["summary"]),"","## Охват","",f"Прочитано фрагментов: {len(report['coverage']['reviewed_fragment_ids'])} из {len(bundle['fragments'])}."]
    if report["coverage"]["unreviewed"]:
        lines += ["","Непрочитанные фрагменты:",""]+[f"- `{clean(x['fragment_id'])}` — {clean(x['reason'])}" for x in report["coverage"]["unreviewed"]]
    lines += ["","## Источники",""]
    for source in manifest["sources"]:
        if source["status"]=="available":
            target=os.path.relpath(run_dir/source["snapshot"],output.parent).replace(os.sep,"/")
            lines.append(f"- `{source['id']}` ({source['role']}): [{clean(source['name'])}]({quote(target, safe='/')}); SHA-256 `{source['sha256']}`; parser `{source['parser']['name']} {source['parser']['version']}`.")
        else:lines.append(f"- `{source['id']}` ({source['role']}): {clean(source['name'])} — недоступен: {clean(source['diagnostic'])}.")
    lines += ["","## Замечания",""]
    if not report["findings"]:lines.append("Адресных замечаний нет. Это допустимый результат при полном охвате; полезность и пропуски всё равно оценивает эксперт.")
    for finding in sorted(report["findings"],key=lambda x:({"high":0,"medium":1,"low":2}[x["priority"]],x["id"])):
        lines += [f"### {clean(finding['id'])}. {clean(finding['title'])}","",f"**Приоритет:** {PRIORITY[finding['priority']]}. {clean(finding['priority_reason'])}","",f"**Проблема:** {clean(finding['problem'])}","",f"**Почему:** {clean(finding['reason'])}","",f"**Вопрос:** {clean(finding['question'])}","",f"**Статус человека:** {STATUS[finding['status']]}",""]
        if finding["human_review"]: lines += [f"Reviewer: {clean(finding['human_review']['reviewer'])}. {clean(finding['human_review']['decision_reason'])}",""]
        if finding["anchors"]:
            lines.append("Основания:"); lines.append("")
            for anchor in finding["anchors"]:
                fragment=fragment_map[anchor["fragment_id"]]; source=source_map[anchor["source_id"]]; loc=fragment["location"]
                where=f"стр. {loc['page']}" if "page" in loc else f"строки {loc['line_start']}–{loc['line_end']}"
                if "table" in loc:where+=f", таблица {loc['table']}, строка {loc['row']}"
                target=os.path.relpath(run_dir/source["snapshot"],output.parent).replace(os.sep,"/")
                lines.append(f"- [{clean(source['name'])}, {where}]({quote(target,safe='/')}): «{clean(anchor['quote'])}» (`{anchor['fragment_id']}`).")
        else:lines += ["Проверенная область ТЗ:",""]+[f"- `{clean(item)}`" for item in finding["scope"]]
        lines.append("")
    lines += ["## Ограничения",""]+[f"- {clean(x)}" for x in report["limitations"]]
    for diagnostic in bundle.get("diagnostics",[]):lines.append(f"- Извлечение `{diagnostic['code']}` ({diagnostic.get('source_id')}, стр. {diagnostic.get('page','—')}): {clean(diagnostic['message'])}")
    write_text(output,"\n".join(lines).rstrip()+"\n"); return output
