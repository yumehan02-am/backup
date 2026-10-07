import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV = ROOT / "036RPP調整" / "最新CSV" / "normal-item20260825161522.csv"
CODES = ["skinc00", "fls3n00", "150fwn"]


def main():
    text = CSV.read_bytes().decode("cp932", "replace")
    for code in CODES:
        print(f"--- {code}")
        found = False
        for match in re.finditer(code, text):
            chunk = text[max(0, match.start() - 900): match.end() + 900]
            urls = list(dict.fromkeys(re.findall(r"https://[^\"<>\s]+", chunk)))
            for url in urls:
                if code in url or "image.rakuten.co.jp" in url:
                    print(url)
            found = True
            break
        if not found:
            print("not found")


if __name__ == "__main__":
    main()
