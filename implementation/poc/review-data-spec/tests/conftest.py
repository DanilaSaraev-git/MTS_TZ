import json
from pathlib import Path
import pytest
from review_data_spec.prepare import prepare_run

@pytest.fixture
def text_run(tmp_path):
    document = tmp_path / "document.md"
    document.write_text("# Поток\n\nЗадержка менее 60 секунд.\n\nДанные хранятся 24 часа.\n", encoding="utf-8")
    run = prepare_run(document, tmp_path / "runs", run_id="test-run")
    return run

@pytest.fixture
def report_for(text_run):
    report = json.loads((text_run / "report.template.json").read_text())
    bundle = json.loads((text_run / "bundle.json").read_text())
    fragments = bundle["fragments"]
    anchor = fragments[1] if len(fragments) > 1 else fragments[0]
    report.update({
      "generation": {"mode":"agent", "agent":"pytest", "model":"unknown", "model_version":"unknown"},
      "summary": "Найдено место для уточнения.",
      "coverage": {"reviewed_fragment_ids":[f["id"] for f in fragments], "unreviewed":[]},
      "findings": [{"id":"F-001", "kind":"ambiguity", "title":"Граница задержки", "problem":"Не определена точка измерения.", "reason":"Разработчик может применить разную границу.", "question":"От какой до какой точки измерять?", "priority":"high", "priority_reason":"Влияет на контроль SLA.", "status":"unreviewed", "human_review":None, "anchors":[{"source_id":anchor["source_id"], "fragment_id":anchor["id"], "quote":"Задержка менее 60 секунд."}], "scope":[]}],
      "limitations":["Смысловая полезность не подтверждена экспертом."]})
    return report
