import requests

LID = "4846240843956224"
CAT = "5726225838374912"
HDR = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://letsreadasia.org/",
}

url = (
    "https://letsreadasia.org/api/tag/get-books/"
    + CAT
    + "?limit=20&lId="
    + LID
    + "&cursor="
)
r = requests.get(url, headers=HDR, timeout=15)
data = r.json()
book = data["books"][0]
import json

print("Title:", book["name"])
print("masterBookId:", book["masterBookId"])
pdf = book.get("pdfUrl")
print("pdfUrl:", json.dumps(pdf)[:150])
cover = book.get("thumborCoverImageUrl")
print("thumborCover:", json.dumps(cover)[:120])
cover2 = book.get("coverImageUrl")
print("coverImageUrl:", json.dumps(cover2)[:120])
print("readingLevel:", book.get("readingLevel"))
print("totalPages:", book.get("totalPages"))
print("slug:", book.get("slug"))
desc = book.get("description") or ""
print("description:", str(desc)[:100])
print()
cursor = data["cursorWebSafeString"]
print("P1 cursor:", cursor[:60])
print("P1 books:", len(data["books"]))

url2 = (
    "https://letsreadasia.org/api/tag/get-books/"
    + CAT
    + "?limit=20&lId="
    + LID
    + "&cursor="
    + cursor
)
r2 = requests.get(url2, headers=HDR, timeout=15)
data2 = r2.json()
print("P2 books:", len(data2["books"]))
print("P2 cursor:", (data2.get("cursorWebSafeString") or "(empty)")[:40])
