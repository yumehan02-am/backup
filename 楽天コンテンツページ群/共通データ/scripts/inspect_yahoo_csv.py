import csv
import io
import pathlib
import sys


CSV_PATH = pathlib.Path(r"C:\Users\i58400am\Desktop\newapp\Yahoo!\data202608061154.csv")


def read_text(path):
    data = path.read_bytes()
    for enc in ("utf-8-sig", "cp932", "shift_jis", "utf-8"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return data.decode("cp932", "replace"), "cp932-replace"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    text, enc = read_text(CSV_PATH)
    sample = "\n".join(text.splitlines()[:5])
    dialect = csv.Sniffer().sniff(sample)
    rows = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = rows.fieldnames or []
    print("encoding:", enc)
    print("columns:", len(headers))
    for i, h in enumerate(headers, 1):
        print(f"{i:03d}: {h}")
    print("--- sample rows")
    for i, row in zip(range(3), rows):
        print(f"row {i + 1}")
        for h in headers[:30]:
            v = (row.get(h) or "").replace("\n", " ")[:100]
            if v:
                print(f"  {h}: {v}")


if __name__ == "__main__":
    main()
