from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
import pdfplumber
from . import ReviewError

PDF_SETTINGS={"text":{"layout":False,"x_tolerance":3,"y_tolerance":3},"tables":{"vertical_strategy":"lines","horizontal_strategy":"lines"}}

class ParserAdapter(ABC):
    name: str
    @abstractmethod
    def parse(self,path:Path,source_id:str)->dict: ...

class TextAdapter(ParserAdapter):
    name="utf8-text"
    def parse(self,path,source_id):
        try: lines=path.read_text(encoding="utf-8").splitlines()
        except (UnicodeError,OSError) as exc: raise ReviewError(f"Cannot read UTF-8 text {path.name}: {exc}") from exc
        fragments=[]; start=None; current=[]
        def flush(end):
            nonlocal start,current
            text="\n".join(current).strip()
            if text:
                index=len(fragments)+1
                fragments.append({"id":f"{source_id}-b{index:04d}","source_id":source_id,"kind":"text","text":text,"location":{"line_start":start,"line_end":end}})
            start=None; current=[]
        for number,line in enumerate(lines,1):
            if line.strip():
                if start is None:start=number
                current.append(line)
            elif current:flush(number-1)
        if current:flush(len(lines))
        return {"parser":{"name":self.name,"version":"1","settings":{"encoding":"utf-8","blocks":"blank-lines"}},"fragments":fragments,"raw":{"line_count":len(lines)},"diagnostics":[]}

class PdfplumberAdapter(ParserAdapter):
    name="pdfplumber"
    def parse(self,path,source_id):
        fragments=[]; pages=[]; diagnostics=[]
        try:
            with pdfplumber.open(path) as pdf:
                if not pdf.pages: raise ReviewError(f"PDF {path.name} has no pages")
                for page_number,page in enumerate(pdf.pages,1):
                    text=page.extract_text(**PDF_SETTINGS["text"]) or ""
                    tables=[]
                    try:
                        found=page.find_tables(table_settings=PDF_SETTINGS["tables"])
                        for table_number,table in enumerate(found,1):
                            rows=table.extract(**PDF_SETTINGS["text"])
                            tables.append({"table_number":table_number,"bbox":list(table.bbox),"rows":rows})
                            for row_number,cells in enumerate(rows,1):
                                row_text=" | ".join("" if value is None else value for value in cells).strip(" |")
                                if row_text:
                                    fragments.append({"id":f"{source_id}-p{page_number:04d}-t{table_number:03d}-r{row_number:03d}","source_id":source_id,"kind":"table_row","text":row_text,"cells":cells,"location":{"page":page_number,"table":table_number,"row":row_number,"bbox":list(table.bbox)}})
                    except Exception as exc:
                        diagnostics.append({"code":"table_extraction_failed","source_id":source_id,"page":page_number,"message":str(exc)})
                    if text.strip():
                        fragments.insert(sum(1 for f in fragments if f["location"].get("page",0)<page_number),{"id":f"{source_id}-p{page_number:04d}-text","source_id":source_id,"kind":"text","text":text,"location":{"page":page_number,"bbox":[0,0,float(page.width),float(page.height)]}})
                    else:
                        diagnostics.append({"code":"empty_text_page","source_id":source_id,"page":page_number,"message":"No text was extracted; this does not prove that the page is empty."})
                    pages.append({"page_number":page_number,"width":float(page.width),"height":float(page.height),"text":text,"tables":tables})
        except ReviewError: raise
        except Exception as exc: raise ReviewError(f"Cannot parse PDF {path.name}: {exc}") from exc
        return {"parser":{"name":self.name,"version":pdfplumber.__version__,"settings":PDF_SETTINGS},"fragments":fragments,"raw":{"pages":pages},"diagnostics":diagnostics}

def adapter_for(path:Path)->ParserAdapter:
    suffix=path.suffix.lower()
    if suffix==".pdf": return PdfplumberAdapter()
    if suffix in {".md",".txt"}: return TextAdapter()
    raise ReviewError(f"Unsupported file type: {path.suffix or '<none>'}")
