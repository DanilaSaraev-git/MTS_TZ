import copy, json
from pathlib import Path
from review_data_spec.validation import validate_report


def test_valid_report_and_render(text_run, report_for):
    path=text_run/"report.json"; path.write_text(json.dumps(report_for,ensure_ascii=False),encoding="utf-8")
    result=validate_report(text_run,path)
    assert result["valid"] and result["coverage_status"] == "complete"


def test_fabricated_quote_bad_coverage_and_tamper_are_rejected(text_run, report_for):
    cases=[]
    bad=copy.deepcopy(report_for); bad["findings"][0]["anchors"][0]["quote"]="Такого текста нет"; cases.append(bad)
    bad=copy.deepcopy(report_for); bad["coverage"]["reviewed_fragment_ids"].pop(); cases.append(bad)
    for index, case in enumerate(cases):
        path=text_run/f"bad-{index}.json"; path.write_text(json.dumps(case,ensure_ascii=False),encoding="utf-8")
        assert not validate_report(text_run,path)["valid"]
    (text_run/"bundle.json").write_text("{}",encoding="utf-8")
    assert not validate_report(text_run,text_run/"report.template.json")["valid"]


def test_missing_requirement_uses_document_scope(text_run, report_for):
    finding=report_for["findings"][0]; finding["kind"]="missing"; finding["anchors"]=[]
    finding["scope"]=[report_for["coverage"]["reviewed_fragment_ids"][0]]
    path=text_run/"report.json"; path.write_text(json.dumps(report_for,ensure_ascii=False),encoding="utf-8")
    assert validate_report(text_run,path)["valid"]


def test_non_human_status_requires_human_review(text_run, report_for):
    report_for["findings"][0]["status"]="confirmed"
    path=text_run/"report.json"; path.write_text(json.dumps(report_for,ensure_ascii=False),encoding="utf-8")
    assert not validate_report(text_run,path)["valid"]


def test_raw_extraction_tamper_is_rejected(text_run, report_for):
    manifest=json.loads((text_run/"manifest.json").read_text())
    raw=next(iter(path for path in manifest["artifacts"] if path.startswith("raw/")))
    (text_run/raw).write_text("{}",encoding="utf-8")
    path=text_run/"report.json"; path.write_text(json.dumps(report_for,ensure_ascii=False),encoding="utf-8")
    assert not validate_report(text_run,path)["valid"]
