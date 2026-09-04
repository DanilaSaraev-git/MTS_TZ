import json
from pathlib import Path
import pytest
from reportlab.pdfgen.canvas import Canvas
from review_data_spec import ReviewError, digest
from review_data_spec.prepare import prepare_run


def test_prepare_preserves_source_and_stable_fragment_ids(tmp_path):
    source = tmp_path / "x.txt"; source.write_text("Первая строка\nВторая строка\n", encoding="utf-8")
    before = digest(source)
    a = prepare_run(source, tmp_path / "runs", run_id="a")
    b = prepare_run(source, tmp_path / "runs", run_id="b")
    ba = json.loads((a/"bundle.json").read_text()); bb = json.loads((b/"bundle.json").read_text())
    assert [x["id"] for x in ba["fragments"]] == [x["id"] for x in bb["fragments"]]
    assert digest(source) == before == json.loads((a/"manifest.json").read_text())["sources"][0]["sha256"]
    assert (a/"sources"/"s001.txt").read_bytes() == source.read_bytes()


def test_pdf_text_and_table_geometry_are_recorded(tmp_path):
    path=tmp_path/"table.pdf"; c=Canvas(str(path))
    for x in [70,180,280,380]: c.line(x,700,x,760)
    for y in [700,730,760]: c.line(70,y,380,y)
    for x,value in [(75,"FIELD_A"),(185,"string"),(285,"value")]: c.drawString(x,740,value)
    for x,value in [(75,"FIELD_B"),(185,"int"),(285,"nullable")]: c.drawString(x,710,value)
    c.save()
    run=prepare_run(path,tmp_path/"runs",run_id="pdf")
    bundle=json.loads((run/"bundle.json").read_text()); raw=json.loads((run/"raw"/"s001.pdfplumber.json").read_text())
    assert "FIELD_A" in bundle["fragments"][0]["text"]
    assert raw["pages"][0]["page_number"] == 1 and raw["pages"][0]["tables"]
    assert any(f["kind"]=="table_row" and f["cells"][0]=="FIELD_A" for f in bundle["fragments"])


def test_missing_context_is_recorded_and_bad_primary_is_rejected(tmp_path):
    profile=tmp_path/"profile.json"; base=json.loads((Path(__file__).parents[1]/"scripts/review_data_spec/resources/base-profile.json").read_text())
    base["context_files"]=["missing.md"]; profile.write_text(json.dumps(base),encoding="utf-8")
    document=tmp_path/"x.txt"; document.write_text("Требование",encoding="utf-8")
    run=prepare_run(document,tmp_path/"runs",run_id="ctx",profile_path=profile)
    assert json.loads((run/"manifest.json").read_text())["sources"][1]["status"] == "unavailable"
    empty=tmp_path/"empty.txt"; empty.write_text("  ",encoding="utf-8")
    with pytest.raises(ReviewError): prepare_run(empty,tmp_path/"runs",run_id="empty")
    with pytest.raises(ReviewError): prepare_run(document,tmp_path/"runs",run_id="ctx")


def test_blank_and_broken_pdf_are_rejected_and_partial_pdf_is_diagnostic(tmp_path):
    blank=tmp_path/"blank.pdf"; Canvas(str(blank)).save()
    with pytest.raises(ReviewError): prepare_run(blank,tmp_path/"runs",run_id="blank")
    broken=tmp_path/"broken.pdf"; broken.write_bytes(b"not a pdf")
    with pytest.raises(ReviewError): prepare_run(broken,tmp_path/"runs",run_id="broken")
    partial=tmp_path/"partial.pdf"; c=Canvas(str(partial)); c.drawString(72,750,"Readable page"); c.showPage(); c.showPage(); c.save()
    run=prepare_run(partial,tmp_path/"runs",run_id="partial")
    assert any(x["code"]=="empty_text_page" for x in json.loads((run/"bundle.json").read_text())["diagnostics"])


def test_profiles_resolve_context_relative_to_themselves_without_mixing(tmp_path):
    document=tmp_path/"document.txt"; document.write_text("Требование",encoding="utf-8")
    names=[]
    for label in ["alpha","beta"]:
        folder=tmp_path/label; folder.mkdir(); (folder/f"{label}.md").write_text(label,encoding="utf-8")
        profile=json.loads((Path(__file__).parents[1]/"scripts/review_data_spec/resources/base-profile.json").read_text())
        profile["name"]=label; profile["context_files"]=[f"{label}.md"]
        path=folder/"profile.json"; path.write_text(json.dumps(profile),encoding="utf-8")
        run=prepare_run(document,tmp_path/"runs",run_id=label,profile_path=path)
        names.append([s["name"] for s in json.loads((run/"manifest.json").read_text())["sources"]])
    assert names==[["document.txt","alpha.md"],["document.txt","beta.md"]]
