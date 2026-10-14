import argparse, json, re
from pathlib import Path
from engine import Catalog, calculate, parse_with_llm
from documents import render_docx

ROOT=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser(description="Пакетная обработка писем в коммерческие предложения")
    ap.add_argument("--input",default=str(ROOT/"letters"))
    ap.add_argument("--output",default=str(ROOT/"results"))
    ap.add_argument("--no-llm",action="store_true",help="не обращаться к LLM; использовать только готовые JSON-разборы")
    ap.add_argument("--parsed-dir",default=str(ROOT/"parsed"),help="папка JSON-разборов, если --no-llm")
    args=ap.parse_args()
    inp=Path(args.input); out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    cat=Catalog()
    letters=sorted(inp.glob("Письмо_*.txt"))
    if not letters: print(f"Писем не найдено: {inp}"); return
    errors=[]
    for f in letters:
      m=re.search(r"(\d+)",f.stem); lid=(m.group(1) if m else "00").zfill(2)
      json_out = out/f"kp_{lid}.json"
      docx_out = out/f"kp_{lid}.docx"
      try:
        if args.no_llm:
          pf=Path(args.parsed_dir)/f"letter_{lid}.json"
          if not pf.exists(): raise FileNotFoundError(f"Нет готового разбора {pf}")
          parsed=json.loads(pf.read_text(encoding="utf-8"))
        else:
          parsed=parse_with_llm(f.read_text(encoding="utf-8"))
        parsed["letter_id"]=lid
        result=calculate(parsed,cat)
        json_out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        render_docx(result,docx_out,ROOT/"templates"/"Шаблон_КП.docx")
        print(f"OK {f.name} -> kp_{lid}.json, kp_{lid}.docx")
      except Exception as e:
        # Don't leave a stale successful result from a previous run for a failed letter.
        json_out.unlink(missing_ok=True)
        docx_out.unlink(missing_ok=True)
        errors.append({"letter_id":lid,"file":f.name,"error":str(e)})
        print(f"ERROR {f.name}: {e}")
    error_file = out/"errors.json"
    if errors:
      error_file.write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding="utf-8")
      print(f"Не обработано писем: {len(errors)}; подробности в errors.json")
    else:
      error_file.unlink(missing_ok=True)
if __name__=="__main__": main()
