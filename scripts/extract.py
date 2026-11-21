# Extract xlsx -> data/merchants_all.csv (UTF-8)
import openpyxl, csv, sys, glob
src = glob.glob("*.xlsx")[0]
wb = openpyxl.load_workbook(src, read_only=True)
ws = wb.worksheets[0]
with open("data/merchants_all.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    for row in ws.iter_rows(values_only=True):
        w.writerow(["" if v is None else str(v).strip() for v in row[:4]])
