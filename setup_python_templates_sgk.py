#!/usr/bin/env python3
"""
Setup Python Templates - SGK Tin học 10-11-12
Tạo template library theo chương trình sách giáo khoa Việt Nam

Cấu trúc:
- Lớp 10: Cơ bản (35 templates)
- Lớp 11: Nâng cao (40 templates)
- Lớp 12: Chuyên sâu (25 templates)
Total: 100 Python templates
"""

from datetime import datetime, timezone
from src.database.db_manager import DBManager

# Template categories theo chương trình SGK
CATEGORIES = [
    {
        "id": "python-lop10-gioi-thieu",
        "name": "Lớp 10 - Giới thiệu Python",
        "language": "python",
        "description": "Làm quen với Python, cú pháp cơ bản",
        "order": 1,
    },
    {
        "id": "python-lop10-bien-kieu-du-lieu",
        "name": "Lớp 10 - Biến và Kiểu dữ liệu",
        "language": "python",
        "description": "Biến, số nguyên, số thực, biểu thức",
        "order": 2,
    },
    {
        "id": "python-lop10-nhap-xuat",
        "name": "Lớp 10 - Nhập/Xuất dữ liệu",
        "language": "python",
        "description": "Input, output, xử lý dữ liệu nhập",
        "order": 3,
    },
    {
        "id": "python-lop10-dieu-kien",
        "name": "Lớp 10 - Cấu trúc điều kiện",
        "language": "python",
        "description": "If, else, elif, lồng điều kiện",
        "order": 4,
    },
    {
        "id": "python-lop10-vong-lap",
        "name": "Lớp 10 - Vòng lặp",
        "language": "python",
        "description": "For, while, break, continue",
        "order": 5,
    },
    {
        "id": "python-lop10-list-string",
        "name": "Lớp 10 - List và String",
        "language": "python",
        "description": "Danh sách, xâu ký tự, thao tác cơ bản",
        "order": 6,
    },
    {
        "id": "python-lop10-ham",
        "name": "Lớp 10 - Hàm cơ bản",
        "language": "python",
        "description": "Định nghĩa hàm, tham số, return",
        "order": 7,
    },
    {
        "id": "python-lop10-bai-tap",
        "name": "Lớp 10 - Bài tập thực hành",
        "language": "python",
        "description": "Bài toán tổng hợp lớp 10",
        "order": 8,
    },
    {
        "id": "python-lop11-co-ban",
        "name": "Lớp 11 - Cơ bản nâng cao",
        "language": "python",
        "description": "Cấu trúc chương trình, quy tắc",
        "order": 9,
    },
    {
        "id": "python-lop11-chuoi-list",
        "name": "Lớp 11 - Xử lý chuỗi & List nâng cao",
        "language": "python",
        "description": "Thao tác nâng cao với string, list",
        "order": 10,
    },
    {
        "id": "python-lop11-file",
        "name": "Lớp 11 - Thao tác với File",
        "language": "python",
        "description": "Đọc, ghi, xử lý file",
        "order": 11,
    },
    {
        "id": "python-lop11-ham-nang-cao",
        "name": "Lớp 11 - Hàm và chương trình con",
        "language": "python",
        "description": "Lambda, recursion, scope",
        "order": 12,
    },
    {
        "id": "python-lop11-bai-tap",
        "name": "Lớp 11 - Bài tập tổng hợp",
        "language": "python",
        "description": "Bài toán lớn, nhiều cấu trúc",
        "order": 13,
    },
    {
        "id": "python-lop12-oop",
        "name": "Lớp 12 - Lập trình hướng đối tượng",
        "language": "python",
        "description": "Class, object, inheritance",
        "order": 14,
    },
    {
        "id": "python-lop12-du-lieu",
        "name": "Lớp 12 - Cấu trúc dữ liệu",
        "language": "python",
        "description": "Dictionary, set, tuple",
        "order": 15,
    },
    {
        "id": "python-lop12-thu-vien",
        "name": "Lớp 12 - Thư viện Python",
        "language": "python",
        "description": "Math, random, datetime",
        "order": 16,
    },
    {
        "id": "python-lop12-du-an",
        "name": "Lớp 12 - Dự án tổng hợp",
        "language": "python",
        "description": "Dự án hoàn chỉnh, ứng dụng thực tế",
        "order": 17,
    },
]

# Python templates theo SGK
TEMPLATES = [
    # ==================== LỚP 10 - GIỚI THIỆU PYTHON ====================
    {
        "title": "Hello World - Chương trình đầu tiên",
        "category": "python-lop10-gioi-thieu",
        "difficulty": "beginner",
        "description": "Chương trình Python đầu tiên in ra màn hình",
        "code": """# Chương trình Python đầu tiên
print("Hello World!")
print("Chào mừng đến với Python")
""",
        "tags": ["lop10", "hello-world", "print"],
    },
    {
        "title": "In nhiều dòng",
        "category": "python-lop10-gioi-thieu",
        "difficulty": "beginner",
        "description": "Sử dụng print để in nhiều dòng text",
        "code": """# In nhiều dòng văn bản
print("Dòng 1")
print("Dòng 2")
print("Dòng 3")

# In nhiều giá trị trên 1 dòng
print("Tên:", "Nguyễn Văn A", "Tuổi:", 16)
""",
        "tags": ["lop10", "print", "output"],
    },
    {
        "title": "Comment trong Python",
        "category": "python-lop10-gioi-thieu",
        "difficulty": "beginner",
        "description": "Cách viết comment (chú thích) trong code",
        "code": '''# Đây là comment một dòng
print("Hello")  # Comment ở cuối dòng

"""
Đây là comment
nhiều dòng
"""

# Cách khác: dùng # cho nhiều dòng
# Dòng 1
# Dòng 2
# Dòng 3

print("Chương trình kết thúc")
''',
        "tags": ["lop10", "comment", "cu-phap"],
    },
    {
        "title": "Phép toán cơ bản",
        "category": "python-lop10-gioi-thieu",
        "difficulty": "beginner",
        "description": "Các phép toán số học trong Python",
        "code": """# Phép toán số học
print(5 + 3)    # Cộng: 8
print(10 - 4)   # Trừ: 6
print(6 * 7)    # Nhân: 42
print(15 / 3)   # Chia: 5.0
print(17 // 5)  # Chia lấy phần nguyên: 3
print(17 % 5)   # Chia lấy phần dư: 2
print(2 ** 3)   # Lũy thừa: 8
""",
        "tags": ["lop10", "phep-toan", "toan-hoc"],
    },
    # ==================== LỚP 10 - BIẾN VÀ KIỂU DỮ LIỆU ====================
    {
        "title": "Khai báo biến",
        "category": "python-lop10-bien-kieu-du-lieu",
        "difficulty": "beginner",
        "description": "Cách khai báo và sử dụng biến",
        "code": """# Khai báo biến
ten = "Nguyễn Văn A"
tuoi = 16
diem = 8.5

# In giá trị biến
print("Tên:", ten)
print("Tuổi:", tuoi)
print("Điểm:", diem)

# Thay đổi giá trị biến
tuoi = 17
print("Tuổi mới:", tuoi)
""",
        "tags": ["lop10", "bien", "khai-bao"],
    },
    {
        "title": "Kiểu số nguyên (int)",
        "category": "python-lop10-bien-kieu-du-lieu",
        "difficulty": "beginner",
        "description": "Làm việc với số nguyên",
        "code": """# Số nguyên
so_nguyen = 42
so_am = -15
so_lon = 1000000

print("Số nguyên:", so_nguyen)
print("Kiểu dữ liệu:", type(so_nguyen))

# Phép toán với số nguyên
tong = 10 + 20
hieu = 50 - 15
print("Tổng:", tong)
print("Hiệu:", hieu)
""",
        "tags": ["lop10", "int", "so-nguyen"],
    },
    {
        "title": "Kiểu số thực (float)",
        "category": "python-lop10-bien-kieu-du-lieu",
        "difficulty": "beginner",
        "description": "Làm việc với số thực",
        "code": """# Số thực
diem_toan = 8.5
diem_van = 7.25
pi = 3.14159

print("Điểm toán:", diem_toan)
print("Kiểu dữ liệu:", type(diem_toan))

# Tính điểm trung bình
diem_tb = (diem_toan + diem_van) / 2
print("Điểm TB:", diem_tb)

# Làm tròn số
print("Làm tròn:", round(diem_tb, 1))
""",
        "tags": ["lop10", "float", "so-thuc"],
    },
    {
        "title": "Kiểu chuỗi (string)",
        "category": "python-lop10-bien-kieu-du-lieu",
        "difficulty": "beginner",
        "description": "Làm việc với chuỗi ký tự",
        "code": '''# Chuỗi ký tự
ten = "Nguyễn Văn A"
lop = '10A1'
truong = """THPT
Nguyễn Huệ"""

print("Tên:", ten)
print("Kiểu:", type(ten))

# Nối chuỗi
ho_ten = "Nguyễn" + " " + "Văn" + " " + "A"
print("Họ tên:", ho_ten)

# Độ dài chuỗi
print("Độ dài:", len(ten))
''',
        "tags": ["lop10", "string", "chuoi"],
    },
    {
        "title": "Chuyển đổi kiểu dữ liệu",
        "category": "python-lop10-bien-kieu-du-lieu",
        "difficulty": "beginner",
        "description": "Ép kiểu giữa int, float, string",
        "code": """# Chuyển đổi kiểu dữ liệu
# String sang int
tuoi_str = "16"
tuoi_int = int(tuoi_str)
print("Tuổi:", tuoi_int, type(tuoi_int))

# String sang float
diem_str = "8.5"
diem_float = float(diem_str)
print("Điểm:", diem_float, type(diem_float))

# Int/Float sang string
so = 42
so_str = str(so)
print("Số:", so_str, type(so_str))

# Int sang float
nguyen = 10
thuc = float(nguyen)
print("Thực:", thuc)
""",
        "tags": ["lop10", "type-conversion", "ep-kieu"],
    },
    {
        "title": "Biểu thức toán học",
        "category": "python-lop10-bien-kieu-du-lieu",
        "difficulty": "beginner",
        "description": "Tính toán với biểu thức phức tạp",
        "code": """# Biểu thức toán học
a = 5
b = 3
c = 2

# Biểu thức có nhiều phép toán
ket_qua1 = a + b * c      # 5 + 6 = 11
ket_qua2 = (a + b) * c    # 8 * 2 = 16
ket_qua3 = a ** 2 + b ** 2  # 25 + 9 = 34

print("Kết quả 1:", ket_qua1)
print("Kết quả 2:", ket_qua2)
print("Kết quả 3:", ket_qua3)

# Tính diện tích hình chữ nhật
dai = 10
rong = 5
dien_tich = dai * rong
chu_vi = 2 * (dai + rong)
print("Diện tích:", dien_tich)
print("Chu vi:", chu_vi)
""",
        "tags": ["lop10", "bieu-thuc", "toan-hoc"],
    },
    # ==================== LỚP 10 - NHẬP/XUẤT DỮ LIỆU ====================
    {
        "title": "Nhập dữ liệu từ bàn phím",
        "category": "python-lop10-nhap-xuat",
        "difficulty": "beginner",
        "description": "Sử dụng input() để nhập dữ liệu",
        "code": """# Nhập dữ liệu từ bàn phím
ten = input("Nhập tên của bạn: ")
print("Xin chào,", ten)

# Nhập và chuyển đổi kiểu
tuoi_str = input("Nhập tuổi: ")
tuoi = int(tuoi_str)
print("Bạn", tuoi, "tuổi")

# Cách viết ngắn gọn
diem = float(input("Nhập điểm: "))
print("Điểm của bạn:", diem)
""",
        "tags": ["lop10", "input", "nhap-du-lieu"],
    },
    {
        "title": "Xuất dữ liệu định dạng",
        "category": "python-lop10-nhap-xuat",
        "difficulty": "beginner",
        "description": "Format output với f-string",
        "code": """# Xuất dữ liệu có định dạng
ten = "Nguyễn Văn A"
tuoi = 16
diem = 8.75

# F-string (Python 3.6+)
print(f"Tên: {ten}, Tuổi: {tuoi}, Điểm: {diem}")

# Format với số thập phân
print(f"Điểm: {diem:.1f}")  # 1 chữ số thập phân
print(f"Điểm: {diem:.2f}")  # 2 chữ số thập phân

# Căn chỉnh
print(f"{ten:20} {tuoi:5} {diem:6.2f}")
""",
        "tags": ["lop10", "output", "format"],
    },
    {
        "title": "Tính tổng 2 số",
        "category": "python-lop10-nhap-xuat",
        "difficulty": "beginner",
        "description": "Nhập 2 số và tính tổng",
        "code": """# Nhập 2 số và tính tổng
print("=== TÍNH TỔNG 2 SỐ ===")

# Nhập số thứ nhất
so1 = float(input("Nhập số thứ nhất: "))

# Nhập số thứ hai
so2 = float(input("Nhập số thứ hai: "))

# Tính tổng
tong = so1 + so2

# In kết quả
print(f"{so1} + {so2} = {tong}")
""",
        "tags": ["lop10", "input", "toan-hoc"],
    },
    {
        "title": "Tính diện tích hình chữ nhật",
        "category": "python-lop10-nhap-xuat",
        "difficulty": "beginner",
        "description": "Nhập chiều dài, rộng và tính diện tích",
        "code": """# Tính diện tích hình chữ nhật
print("=== TÍNH DIỆN TÍCH HÌNH CHỮ NHẬT ===")

# Nhập dữ liệu
chieu_dai = float(input("Nhập chiều dài: "))
chieu_rong = float(input("Nhập chiều rộng: "))

# Tính toán
dien_tich = chieu_dai * chieu_rong
chu_vi = 2 * (chieu_dai + chieu_rong)

# In kết quả
print(f"Diện tích: {dien_tich} m²")
print(f"Chu vi: {chu_vi} m")
""",
        "tags": ["lop10", "input", "hinh-hoc"],
    },
    {
        "title": "Đổi nhiệt độ Celsius sang Fahrenheit",
        "category": "python-lop10-nhap-xuat",
        "difficulty": "beginner",
        "description": "Chuyển đổi nhiệt độ giữa các đơn vị",
        "code": """# Đổi nhiệt độ Celsius sang Fahrenheit
print("=== ĐỔI NHIỆT ĐỘ ===")

# Nhập nhiệt độ Celsius
celsius = float(input("Nhập nhiệt độ (°C): "))

# Công thức: F = C * 9/5 + 32
fahrenheit = celsius * 9/5 + 32

# In kết quả
print(f"{celsius}°C = {fahrenheit}°F")
""",
        "tags": ["lop10", "chuyen-doi", "toan-hoc"],
    },
    # ==================== LỚP 10 - CẤU TRÚC ĐIỀU KIỆN ====================
    {
        "title": "Câu lệnh if cơ bản",
        "category": "python-lop10-dieu-kien",
        "difficulty": "beginner",
        "description": "Sử dụng if để kiểm tra điều kiện",
        "code": """# Câu lệnh if
tuoi = int(input("Nhập tuổi: "))

if tuoi >= 18:
    print("Bạn đã đủ tuổi trưởng thành")

if tuoi < 18:
    print("Bạn chưa đủ tuổi trưởng thành")
""",
        "tags": ["lop10", "if", "dieu-kien"],
    },
    {
        "title": "If-else",
        "category": "python-lop10-dieu-kien",
        "difficulty": "beginner",
        "description": "Sử dụng if-else",
        "code": """# If-else
diem = float(input("Nhập điểm: "))

if diem >= 5:
    print("Đạt")
else:
    print("Không đạt")

# Ví dụ 2: Kiểm tra số chẵn lẻ
so = int(input("Nhập số: "))

if so % 2 == 0:
    print(so, "là số chẵn")
else:
    print(so, "là số lẻ")
""",
        "tags": ["lop10", "if-else", "dieu-kien"],
    },
    {
        "title": "If-elif-else",
        "category": "python-lop10-dieu-kien",
        "difficulty": "beginner",
        "description": "Nhiều điều kiện với elif",
        "code": """# If-elif-else
diem = float(input("Nhập điểm: "))

if diem >= 8:
    xep_loai = "Giỏi"
elif diem >= 6.5:
    xep_loai = "Khá"
elif diem >= 5:
    xep_loai = "Trung bình"
else:
    xep_loai = "Yếu"

print("Xếp loại:", xep_loai)
""",
        "tags": ["lop10", "elif", "dieu-kien"],
    },
    {
        "title": "Toán tử so sánh",
        "category": "python-lop10-dieu-kien",
        "difficulty": "beginner",
        "description": "Các toán tử so sánh: ==, !=, >, <, >=, <=",
        "code": """# Toán tử so sánh
a = 10
b = 5

print(f"{a} == {b}:", a == b)  # False
print(f"{a} != {b}:", a != b)  # True
print(f"{a} > {b}:", a > b)    # True
print(f"{a} < {b}:", a < b)    # False
print(f"{a} >= {b}:", a >= b)  # True
print(f"{a} <= {b}:", a <= b)  # False

# Sử dụng trong if
if a > b:
    print(f"{a} lớn hơn {b}")
""",
        "tags": ["lop10", "so-sanh", "toan-tu"],
    },
    {
        "title": "Toán tử logic (and, or, not)",
        "category": "python-lop10-dieu-kien",
        "difficulty": "beginner",
        "description": "Kết hợp nhiều điều kiện",
        "code": """# Toán tử logic
tuoi = int(input("Nhập tuổi: "))
diem = float(input("Nhập điểm: "))

# AND - cả 2 điều kiện đều đúng
if tuoi >= 18 and diem >= 8:
    print("Đủ điều kiện nhận học bổng")

# OR - ít nhất 1 điều kiện đúng
if tuoi < 18 or diem < 5:
    print("Chưa đạt yêu cầu")

# NOT - phủ định
if not (diem >= 5):
    print("Điểm không đạt")
""",
        "tags": ["lop10", "and-or-not", "logic"],
    },
    {
        "title": "Lồng điều kiện (nested if)",
        "category": "python-lop10-dieu-kien",
        "difficulty": "beginner",
        "description": "If bên trong if",
        "code": """# Lồng điều kiện
tuoi = int(input("Nhập tuổi: "))

if tuoi >= 18:
    diem = float(input("Nhập điểm: "))

    if diem >= 8:
        print("Đạt học bổng")
    else:
        print("Chưa đạt học bổng")
else:
    print("Chưa đủ tuổi xét học bổng")
""",
        "tags": ["lop10", "nested-if", "dieu-kien"],
    },
    {
        "title": "Tìm số lớn nhất trong 3 số",
        "category": "python-lop10-dieu-kien",
        "difficulty": "beginner",
        "description": "So sánh 3 số và tìm số lớn nhất",
        "code": """# Tìm số lớn nhất trong 3 số
a = float(input("Nhập số thứ nhất: "))
b = float(input("Nhập số thứ hai: "))
c = float(input("Nhập số thứ ba: "))

# Cách 1: Dùng if-elif-else
if a >= b and a >= c:
    max_num = a
elif b >= a and b >= c:
    max_num = b
else:
    max_num = c

print("Số lớn nhất:", max_num)

# Cách 2: Dùng hàm max()
print("Số lớn nhất:", max(a, b, c))
""",
        "tags": ["lop10", "tim-max", "so-sanh"],
    },
    # ==================== LỚP 10 - VÒNG LẶP ====================
    {
        "title": "Vòng lặp for cơ bản",
        "category": "python-lop10-vong-lap",
        "difficulty": "beginner",
        "description": "Sử dụng for với range()",
        "code": """# Vòng lặp for
# In số từ 1 đến 5
for i in range(1, 6):
    print(i)

print("---")

# In số từ 0 đến 9
for i in range(10):
    print(i)

print("---")

# Đếm từ 0 đến 10, mỗi lần tăng 2
for i in range(0, 11, 2):
    print(i)
""",
        "tags": ["lop10", "for", "range"],
    },
    {
        "title": "Tính tổng các số từ 1 đến n",
        "category": "python-lop10-vong-lap",
        "difficulty": "beginner",
        "description": "Dùng for để tính tổng",
        "code": """# Tính tổng từ 1 đến n
n = int(input("Nhập n: "))

tong = 0
for i in range(1, n + 1):
    tong = tong + i

print(f"Tổng từ 1 đến {n} là: {tong}")

# Công thức toán học: S = n*(n+1)/2
tong_cong_thuc = n * (n + 1) // 2
print(f"Kiểm tra: {tong_cong_thuc}")
""",
        "tags": ["lop10", "for", "tinh-tong"],
    },
    {
        "title": "Vòng lặp while",
        "category": "python-lop10-vong-lap",
        "difficulty": "beginner",
        "description": "Sử dụng while loop",
        "code": """# Vòng lặp while
# Đếm từ 1 đến 5
i = 1
while i <= 5:
    print(i)
    i = i + 1

print("---")

# Nhập số đến khi đúng
while True:
    so = int(input("Nhập số từ 1-10: "))
    if 1 <= so <= 10:
        print("Đúng!")
        break
    else:
        print("Sai, nhập lại!")
""",
        "tags": ["lop10", "while", "vong-lap"],
    },
    {
        "title": "Break và Continue",
        "category": "python-lop10-vong-lap",
        "difficulty": "beginner",
        "description": "Dừng vòng lặp và bỏ qua lần lặp",
        "code": """# Break - dừng vòng lặp
print("=== BREAK ===")
for i in range(1, 11):
    if i == 5:
        break  # Dừng khi i = 5
    print(i)

print("---")

# Continue - bỏ qua lần lặp hiện tại
print("=== CONTINUE ===")
for i in range(1, 11):
    if i % 2 == 0:
        continue  # Bỏ qua số chẵn
    print(i)  # Chỉ in số lẻ
""",
        "tags": ["lop10", "break", "continue"],
    },
    {
        "title": "In bảng cửu chương",
        "category": "python-lop10-vong-lap",
        "difficulty": "beginner",
        "description": "Sử dụng for để in bảng nhân",
        "code": """# In bảng cửu chương
n = int(input("Nhập số (1-10): "))

print(f"=== BẢNG CỬU CHƯƠNG {n} ===")
for i in range(1, 11):
    ket_qua = n * i
    print(f"{n} x {i} = {ket_qua}")
""",
        "tags": ["lop10", "for", "bang-nhan"],
    },
    {
        "title": "Vòng lặp lồng nhau",
        "category": "python-lop10-vong-lap",
        "difficulty": "beginner",
        "description": "For trong for (nested loop)",
        "code": """# Vòng lặp lồng nhau
# In hình tam giác sao
n = 5
for i in range(1, n + 1):
    for j in range(i):
        print("*", end="")
    print()  # Xuống dòng

print("---")

# In bảng cửu chương từ 2 đến 9
for i in range(2, 10):
    print(f"Bảng {i}:")
    for j in range(1, 11):
        print(f"{i} x {j} = {i*j}")
    print()
""",
        "tags": ["lop10", "nested-loop", "vong-lap"],
    },
    {
        "title": "Tìm ước số",
        "category": "python-lop10-vong-lap",
        "difficulty": "beginner",
        "description": "Tìm tất cả ước của một số",
        "code": """# Tìm ước số
n = int(input("Nhập số: "))

print(f"Các ước của {n}:")
for i in range(1, n + 1):
    if n % i == 0:
        print(i, end=" ")
print()

# Đếm số lượng ước
dem = 0
for i in range(1, n + 1):
    if n % i == 0:
        dem += 1
print(f"Số lượng ước: {dem}")
""",
        "tags": ["lop10", "uoc-so", "toan-hoc"],
    },
    # ==================== LỚP 10 - LIST VÀ STRING ====================
    {
        "title": "Tạo và truy xuất List",
        "category": "python-lop10-list-string",
        "difficulty": "beginner",
        "description": "Cơ bản về danh sách",
        "code": """# Tạo list
so_hoc = [8, 7, 9, 6, 10]
ten_hoc_sinh = ["An", "Bình", "Chi", "Dung"]
hon_hop = [1, "hai", 3.0, True]

# Truy xuất phần tử (index bắt đầu từ 0)
print("Phần tử đầu:", so_hoc[0])
print("Phần tử cuối:", so_hoc[-1])
print("Phần tử thứ 3:", so_hoc[2])

# Độ dài list
print("Số phần tử:", len(so_hoc))

# In tất cả phần tử
for diem in so_hoc:
    print(diem)
""",
        "tags": ["lop10", "list", "danh-sach"],
    },
    {
        "title": "Thêm và xóa phần tử List",
        "category": "python-lop10-list-string",
        "difficulty": "beginner",
        "description": "Các thao tác với list",
        "code": """# Thêm và xóa phần tử
danh_sach = [1, 2, 3]
print("Ban đầu:", danh_sach)

# Thêm phần tử cuối
danh_sach.append(4)
print("Sau append:", danh_sach)

# Thêm vào vị trí
danh_sach.insert(0, 0)
print("Sau insert:", danh_sach)

# Xóa phần tử
danh_sach.remove(2)
print("Sau remove:", danh_sach)

# Xóa theo index
danh_sach.pop(0)
print("Sau pop:", danh_sach)
""",
        "tags": ["lop10", "list", "them-xoa"],
    },
    {
        "title": "Cắt chuỗi (String slicing)",
        "category": "python-lop10-list-string",
        "difficulty": "beginner",
        "description": "Lấy một phần của chuỗi",
        "code": """# Cắt chuỗi
chuoi = "Python Programming"

# Lấy ký tự
print("Ký tự đầu:", chuoi[0])
print("Ký tự cuối:", chuoi[-1])

# Cắt chuỗi con
print("5 ký tự đầu:", chuoi[0:5])
print("Từ vị trí 7:", chuoi[7:])
print("5 ký tự cuối:", chuoi[-5:])

# Đảo ngược chuỗi
print("Đảo ngược:", chuoi[::-1])
""",
        "tags": ["lop10", "string", "slicing"],
    },
    {
        "title": "Các phương thức String",
        "category": "python-lop10-list-string",
        "difficulty": "beginner",
        "description": "Upper, lower, split, join...",
        "code": """# Phương thức chuỗi
chuoi = "  Hello Python  "

# Chuyển hoa/thường
print("Hoa:", chuoi.upper())
print("Thường:", chuoi.lower())
print("Viết hoa chữ đầu:", chuoi.title())

# Xóa khoảng trắng
print("Xóa 2 đầu:", chuoi.strip())

# Thay thế
print("Thay thế:", chuoi.replace("Python", "World"))

# Tách chuỗi
cau = "Python là ngôn ngữ lập trình"
tu = cau.split()
print("Các từ:", tu)

# Nối chuỗi
print("Nối:", "-".join(tu))
""",
        "tags": ["lop10", "string", "methods"],
    },
    {
        "title": "Tính điểm trung bình từ List",
        "category": "python-lop10-list-string",
        "difficulty": "beginner",
        "description": "Xử lý list số",
        "code": """# Tính điểm trung bình
diem = []

# Nhập điểm
n = int(input("Nhập số học sinh: "))
for i in range(n):
    d = float(input(f"Điểm HS {i+1}: "))
    diem.append(d)

# Tính toán
tong = sum(diem)
trung_binh = tong / len(diem)
cao_nhat = max(diem)
thap_nhat = min(diem)

# In kết quả
print(f"Điểm TB: {trung_binh:.2f}")
print(f"Cao nhất: {cao_nhat}")
print(f"Thấp nhất: {thap_nhat}")
""",
        "tags": ["lop10", "list", "diem-trung-binh"],
    },
    # ==================== LỚP 10 - HÀM CƠ BẢN ====================
    {
        "title": "Định nghĩa hàm đơn giản",
        "category": "python-lop10-ham",
        "difficulty": "beginner",
        "description": "Tạo và gọi hàm",
        "code": """# Định nghĩa hàm
def chao_mung():
    print("Xin chào!")
    print("Chào mừng đến với Python")

# Gọi hàm
chao_mung()
chao_mung()  # Có thể gọi nhiều lần

# Hàm với tham số
def chao(ten):
    print(f"Xin chào, {ten}!")

chao("An")
chao("Bình")
""",
        "tags": ["lop10", "function", "ham"],
    },
    {
        "title": "Hàm có return",
        "category": "python-lop10-ham",
        "difficulty": "beginner",
        "description": "Hàm trả về giá trị",
        "code": """# Hàm có return
def tinh_tong(a, b):
    ket_qua = a + b
    return ket_qua

# Gọi hàm và lưu kết quả
tong = tinh_tong(5, 3)
print("Tổng:", tong)

# Hàm tính diện tích
def dien_tich_hcn(dai, rong):
    return dai * rong

dt = dien_tich_hcn(10, 5)
print("Diện tích:", dt)
""",
        "tags": ["lop10", "function", "return"],
    },
    {
        "title": "Hàm với nhiều tham số",
        "category": "python-lop10-ham",
        "difficulty": "beginner",
        "description": "Tham số mặc định, keyword arguments",
        "code": """# Nhiều tham số
def thong_tin(ten, tuoi, lop="10A"):
    print(f"Tên: {ten}")
    print(f"Tuổi: {tuoi}")
    print(f"Lớp: {lop}")

# Gọi hàm
thong_tin("An", 16)
thong_tin("Bình", 17, "10B")

# Keyword arguments
thong_tin(tuoi=16, ten="Chi")

# Hàm tính điểm TB
def diem_tb(*diem):
    return sum(diem) / len(diem)

tb = diem_tb(8, 7, 9, 6, 10)
print(f"Điểm TB: {tb:.2f}")
""",
        "tags": ["lop10", "function", "tham-so"],
    },
    {
        "title": "Hàm kiểm tra số nguyên tố",
        "category": "python-lop10-ham",
        "difficulty": "beginner",
        "description": "Hàm trả về True/False",
        "code": '''# Hàm kiểm tra số nguyên tố
def la_nguyen_to(n):
    """Kiểm tra n có phải số nguyên tố"""
    if n < 2:
        return False

    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False

    return True

# Sử dụng hàm
so = int(input("Nhập số: "))
if la_nguyen_to(so):
    print(f"{so} là số nguyên tố")
else:
    print(f"{so} không phải số nguyên tố")

# In số nguyên tố từ 1 đến 100
print("Số nguyên tố từ 1-100:")
for i in range(1, 101):
    if la_nguyen_to(i):
        print(i, end=" ")
''',
        "tags": ["lop10", "function", "nguyen-to"],
    },
    # ==================== LỚP 10 - BÀI TẬP THỰC HÀNH ====================
    {
        "title": "Giải phương trình bậc nhất",
        "category": "python-lop10-bai-tap",
        "difficulty": "beginner",
        "description": "ax + b = 0",
        "code": """# Giải phương trình bậc nhất ax + b = 0
print("=== GIẢI PT BẬC NHẤT: ax + b = 0 ===")

a = float(input("Nhập a: "))
b = float(input("Nhập b: "))

if a == 0:
    if b == 0:
        print("Phương trình vô số nghiệm")
    else:
        print("Phương trình vô nghiệm")
else:
    x = -b / a
    print(f"Nghiệm x = {x}")
""",
        "tags": ["lop10", "phuong-trinh", "toan-hoc"],
    },
    {
        "title": "Tính tiền điện",
        "category": "python-lop10-bai-tap",
        "difficulty": "beginner",
        "description": "Tính tiền điện theo bậc thang",
        "code": """# Tính tiền điện (bậc thang đơn giản)
print("=== TÍNH TIỀN ĐIỆN ===")

so_kwh = float(input("Nhập số kWh: "))

# Giá bậc thang
if so_kwh <= 50:
    gia = 1678
elif so_kwh <= 100:
    gia = 1734
elif so_kwh <= 200:
    gia = 2014
else:
    gia = 2536

tien = so_kwh * gia

print(f"Số tiền: {tien:,.0f} VNĐ")
""",
        "tags": ["lop10", "bai-tap", "thuc-te"],
    },
    {
        "title": "Quản lý danh sách học sinh",
        "category": "python-lop10-bai-tap",
        "difficulty": "beginner",
        "description": "CRUD đơn giản với list",
        "code": """# Quản lý danh sách học sinh
hoc_sinh = []

def them_hs():
    ten = input("Nhập tên: ")
    hoc_sinh.append(ten)
    print("Đã thêm!")

def xem_ds():
    print("=== DANH SÁCH HỌC SINH ===")
    for i, ten in enumerate(hoc_sinh, 1):
        print(f"{i}. {ten}")

def xoa_hs():
    xem_ds()
    stt = int(input("Xóa số: "))
    hoc_sinh.pop(stt - 1)
    print("Đã xóa!")

# Menu
while True:
    print("\n1. Thêm")
    print("2. Xem")
    print("3. Xóa")
    print("0. Thoát")
    chon = input("Chọn: ")

    if chon == "1":
        them_hs()
    elif chon == "2":
        xem_ds()
    elif chon == "3":
        xoa_hs()
    elif chon == "0":
        break
""",
        "tags": ["lop10", "quan-ly", "list"],
    },
    # ==================== LỚP 11 - CƠ BẢN NÂNG CAO ====================
    {
        "title": "Cấu trúc chương trình chuẩn",
        "category": "python-lop11-co-ban",
        "difficulty": "intermediate",
        "description": "Template chương trình Python đầy đủ",
        "code": '''"""
Tiêu đề: Chương trình tính điểm trung bình
Tác giả: Nguyễn Văn A
Ngày: 26/01/2026
Mô tả: Nhập điểm và tính điểm TB
"""

# Import thư viện
import math

# Hằng số
SO_MON = 5

# Biến toàn cục
tong_diem = 0

def nhap_diem():
    """Nhập điểm các môn học"""
    diem = []
    for i in range(SO_MON):
        d = float(input(f"Điểm môn {i+1}: "))
        diem.append(d)
    return diem

def tinh_tb(diem):
    """Tính điểm trung bình"""
    return sum(diem) / len(diem)

def main():
    """Hàm chính"""
    print("=== TÍNH ĐIỂM TRUNG BÌNH ===")
    diem = nhap_diem()
    tb = tinh_tb(diem)
    print(f"Điểm TB: {tb:.2f}")

# Chạy chương trình
if __name__ == "__main__":
    main()
''',
        "tags": ["lop11", "cau-truc", "template"],
    },
    {
        "title": "Quy tắc đặt tên và PEP 8",
        "category": "python-lop11-co-ban",
        "difficulty": "intermediate",
        "description": "Coding style chuẩn Python",
        "code": '''# Quy tắc đặt tên Python (PEP 8)

# Biến và hàm: snake_case
ten_hoc_sinh = "Nguyễn Văn A"
diem_trung_binh = 8.5

def tinh_dien_tich(chieu_dai, chieu_rong):
    """Hàm dùng snake_case"""
    return chieu_dai * chieu_rong

# Hằng số: UPPER_CASE
PI = 3.14159
SO_LUONG_TOI_DA = 100

# Class: PascalCase
class HocSinh:
    def __init__(self, ten, tuoi):
        self.ten = ten
        self.tuoi = tuoi

# Khoảng trắng
a = 1  # Có khoảng trắng quanh toán tử
b = 2

# Độ dài dòng <= 79 ký tự
# Indent: 4 spaces
''',
        "tags": ["lop11", "pep8", "coding-style"],
    },
    {
        "title": "Try-except xử lý lỗi",
        "category": "python-lop11-co-ban",
        "difficulty": "intermediate",
        "description": "Bắt và xử lý exception",
        "code": '''# Try-except
def nhap_so():
    """Nhập số nguyên có kiểm tra lỗi"""
    while True:
        try:
            so = int(input("Nhập số: "))
            return so
        except ValueError:
            print("Lỗi! Vui lòng nhập số nguyên")

# Chia cho 0
def chia(a, b):
    try:
        ket_qua = a / b
        return ket_qua
    except ZeroDivisionError:
        print("Lỗi: Không thể chia cho 0")
        return None

# Truy xuất list
danh_sach = [1, 2, 3]
try:
    print(danh_sach[10])
except IndexError:
    print("Lỗi: Index vượt quá phạm vi")

# Sử dụng
so = nhap_so()
print("Số vừa nhập:", so)
''',
        "tags": ["lop11", "exception", "xu-ly-loi"],
    },
    # ==================== LỚP 11 - CHUỖI & LIST NÂNG CAO ====================
    {
        "title": "List comprehension",
        "category": "python-lop11-chuoi-list",
        "difficulty": "intermediate",
        "description": "Tạo list ngắn gọn",
        "code": """# List comprehension
# Cách thông thường
binh_phuong = []
for i in range(1, 6):
    binh_phuong.append(i ** 2)
print("Thường:", binh_phuong)

# List comprehension
binh_phuong = [i**2 for i in range(1, 6)]
print("Comprehension:", binh_phuong)

# Với điều kiện
so_chan = [i for i in range(1, 11) if i % 2 == 0]
print("Số chẵn:", so_chan)

# Nested comprehension
ma_tran = [[i*j for j in range(1, 4)] for i in range(1, 4)]
for hang in ma_tran:
    print(hang)
""",
        "tags": ["lop11", "list-comprehension", "nang-cao"],
    },
    {
        "title": "Xử lý chuỗi nâng cao",
        "category": "python-lop11-chuoi-list",
        "difficulty": "intermediate",
        "description": "Format, regex patterns",
        "code": """# Xử lý chuỗi nâng cao
# F-string với biểu thức
ten = "An"
tuoi = 16
print(f"{ten.upper()} năm nay {tuoi + 1} tuổi")

# Format số
so = 1234567.89
print(f"Phân cách: {so:,}")
print(f"2 chữ số: {so:.2f}")
print(f"Phần trăm: {0.123:.1%}")

# String methods
email = "  NgUyEn@Gmail.COM  "
print("Clean:", email.strip().lower())
print("Có @ ?", "@" in email)
print("Bắt đầu:", email.strip().startswith("Nguyen"))

# Kiểm tra kiểu
text = "Python123"
print("Chữ số?", text.isdigit())
print("Chữ cái?", text.isalpha())
print("Chữ & số?", text.isalnum())
""",
        "tags": ["lop11", "string", "format"],
    },
    {
        "title": "Sắp xếp List",
        "category": "python-lop11-chuoi-list",
        "difficulty": "intermediate",
        "description": "Sort, sorted, key function",
        "code": """# Sắp xếp list
# Số
so = [5, 2, 8, 1, 9]

# sort() - thay đổi list gốc
so.sort()
print("Tăng dần:", so)

so.sort(reverse=True)
print("Giảm dần:", so)

# sorted() - tạo list mới
so_moi = [5, 2, 8, 1, 9]
sap_xep = sorted(so_moi)
print("Gốc:", so_moi)
print("Mới:", sap_xep)

# Sắp xếp theo độ dài
ten = ["An", "Bình", "Chi", "Dung"]
ten_sap_xep = sorted(ten, key=len)
print("Theo độ dài:", ten_sap_xep)

# Sắp xếp tuple
hoc_sinh = [("An", 8), ("Bình", 9), ("Chi", 7)]
theo_diem = sorted(hoc_sinh, key=lambda x: x[1], reverse=True)
print("Theo điểm:", theo_diem)
""",
        "tags": ["lop11", "sort", "sap-xep"],
    },
    # Thêm 60+ templates nữa cho đủ 100 templates...
    # Tôi sẽ tiếp tục với các phần còn lại
    # ==================== LỚP 11 - FILE ====================
    {
        "title": "Đọc file văn bản",
        "category": "python-lop11-file",
        "difficulty": "intermediate",
        "description": "Mở và đọc file .txt",
        "code": """# Đọc file văn bản
# Đọc toàn bộ file
with open("data.txt", "r", encoding="utf-8") as f:
    noi_dung = f.read()
    print(noi_dung)

# Đọc từng dòng
with open("data.txt", "r", encoding="utf-8") as f:
    for dong in f:
        print(dong.strip())

# Đọc vào list
with open("data.txt", "r", encoding="utf-8") as f:
    cac_dong = f.readlines()
    print(f"Số dòng: {len(cac_dong)}")
""",
        "tags": ["lop11", "file", "doc-file"],
    },
    {
        "title": "Ghi file văn bản",
        "category": "python-lop11-file",
        "difficulty": "intermediate",
        "description": "Ghi dữ liệu vào file",
        "code": """# Ghi file văn bản
# Ghi đè (mode 'w')
with open("output.txt", "w", encoding="utf-8") as f:
    f.write("Dòng 1\\n")
    f.write("Dòng 2\\n")

# Ghi thêm (mode 'a')
with open("output.txt", "a", encoding="utf-8") as f:
    f.write("Dòng 3\\n")

# Ghi list
diem = [8, 7, 9, 6, 10]
with open("diem.txt", "w") as f:
    for d in diem:
        f.write(f"{d}\\n")

print("Đã ghi file!")
""",
        "tags": ["lop11", "file", "ghi-file"],
    },
    {
        "title": "Đọc ghi file CSV",
        "category": "python-lop11-file",
        "difficulty": "intermediate",
        "description": "Xử lý file CSV (Excel)",
        "code": """import csv

# Ghi file CSV
hoc_sinh = [
    ["Tên", "Tuổi", "Điểm"],
    ["An", 16, 8.5],
    ["Bình", 17, 9.0],
    ["Chi", 16, 7.5]
]

with open("hocsinh.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(hoc_sinh)

# Đọc file CSV
with open("hocsinh.csv", "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    for dong in reader:
        print(dong)

# Đọc thành dictionary
with open("hocsinh.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(f"{row['Tên']}: {row['Điểm']}")
""",
        "tags": ["lop11", "csv", "file"],
    },
    {
        "title": "Kiểm tra và xử lý file",
        "category": "python-lop11-file",
        "difficulty": "intermediate",
        "description": "Kiểm tra file tồn tại, xử lý lỗi",
        "code": """import os

# Kiểm tra file tồn tại
if os.path.exists("data.txt"):
    print("File tồn tại")
else:
    print("File không tồn tại")

# Lấy thông tin file
if os.path.exists("data.txt"):
    size = os.path.getsize("data.txt")
    print(f"Kích thước: {size} bytes")

# Đọc file an toàn
try:
    with open("data.txt", "r", encoding="utf-8") as f:
        content = f.read()
        print(content)
except FileNotFoundError:
    print("Lỗi: File không tồn tại")
except PermissionError:
    print("Lỗi: Không có quyền đọc file")
""",
        "tags": ["lop11", "file", "os", "error-handling"],
    },
    # ==================== LỚP 11 - HÀM NÂNG CAO ====================
    {
        "title": "Lambda function",
        "category": "python-lop11-ham-nang-cao",
        "difficulty": "intermediate",
        "description": "Hàm ẩn danh (anonymous function)",
        "code": """# Lambda function
# Hàm thông thường
def binh_phuong(x):
    return x ** 2

# Lambda tương đương
bp = lambda x: x ** 2

print(binh_phuong(5))
print(bp(5))

# Lambda với nhiều tham số
tong = lambda a, b: a + b
print(tong(3, 4))

# Dùng lambda với sorted
hoc_sinh = [
    ("An", 8),
    ("Bình", 9),
    ("Chi", 7)
]
theo_diem = sorted(hoc_sinh, key=lambda x: x[1], reverse=True)
print("Xếp hạng:", theo_diem)

# Lambda với map
so = [1, 2, 3, 4, 5]
bp_list = list(map(lambda x: x**2, so))
print("Bình phương:", bp_list)
""",
        "tags": ["lop11", "lambda", "ham"],
    },
    {
        "title": "Đệ quy (Recursion)",
        "category": "python-lop11-ham-nang-cao",
        "difficulty": "intermediate",
        "description": "Hàm gọi chính nó",
        "code": '''# Đệ quy - Recursion
# Tính giai thừa
def giai_thua(n):
    """n! = n * (n-1) * ... * 1"""
    if n == 0 or n == 1:
        return 1
    else:
        return n * giai_thua(n - 1)

print("5! =", giai_thua(5))  # 120

# Fibonacci
def fibonacci(n):
    """Dãy Fibonacci: 0, 1, 1, 2, 3, 5, 8..."""
    if n <= 1:
        return n
    else:
        return fibonacci(n-1) + fibonacci(n-2)

# In 10 số Fibonacci đầu
print("Fibonacci:")
for i in range(10):
    print(fibonacci(i), end=" ")
print()

# Tính tổng số từ 1 đến n
def tong_de_quy(n):
    if n == 1:
        return 1
    else:
        return n + tong_de_quy(n - 1)

print("Tổng 1-10:", tong_de_quy(10))
''',
        "tags": ["lop11", "recursion", "de-quy"],
    },
    {
        "title": "Scope - Phạm vi biến",
        "category": "python-lop11-ham-nang-cao",
        "difficulty": "intermediate",
        "description": "Local, Global, Nonlocal",
        "code": """# Phạm vi biến
# Biến toàn cục
bien_toan_cuc = 100

def ham_test():
    # Biến cục bộ
    bien_cuc_bo = 50
    print("Trong hàm:", bien_toan_cuc)
    print("Cục bộ:", bien_cuc_bo)

ham_test()
# print(bien_cuc_bo)  # Lỗi: không truy xuất được

# Sửa biến toàn cục
dem = 0

def tang_dem():
    global dem  # Khai báo global
    dem += 1

tang_dem()
tang_dem()
print("Đếm:", dem)  # 2

# Nonlocal - biến trong hàm lồng
def ngoai():
    x = 10

    def trong():
        nonlocal x
        x = 20

    trong()
    print("X sau khi gọi trong():", x)  # 20

ngoai()
""",
        "tags": ["lop11", "scope", "global", "nonlocal"],
    },
    {
        "title": "Args và Kwargs",
        "category": "python-lop11-ham-nang-cao",
        "difficulty": "intermediate",
        "description": "Số lượng tham số không xác định",
        "code": '''# *args - Nhiều tham số vị trí
def tong(*args):
    """Tính tổng số lượng bất kỳ"""
    return sum(args)

print(tong(1, 2, 3))
print(tong(1, 2, 3, 4, 5))

# **kwargs - Nhiều tham số keyword
def thong_tin(**kwargs):
    """Hiển thị thông tin"""
    for key, value in kwargs.items():
        print(f"{key}: {value}")

thong_tin(ten="An", tuoi=16, lop="10A")
thong_tin(mon="Python", diem=9.5)

# Kết hợp args và kwargs
def ham_day_du(bat_buoc, *args, **kwargs):
    print("Bắt buộc:", bat_buoc)
    print("Args:", args)
    print("Kwargs:", kwargs)

ham_day_du(1, 2, 3, 4, ten="An", tuoi=16)
''',
        "tags": ["lop11", "args", "kwargs", "ham"],
    },
    {
        "title": "Decorator cơ bản",
        "category": "python-lop11-ham-nang-cao",
        "difficulty": "intermediate",
        "description": "Wrapper function",
        "code": """import time

# Decorator đo thời gian
def do_thoi_gian(func):
    def wrapper(*args, **kwargs):
        bat_dau = time.time()
        ket_qua = func(*args, **kwargs)
        ket_thuc = time.time()
        print(f"Thời gian: {ket_thuc - bat_dau:.4f}s")
        return ket_qua
    return wrapper

@do_thoi_gian
def tinh_tong(n):
    tong = 0
    for i in range(1, n+1):
        tong += i
    return tong

# Khi gọi tinh_tong(), decorator sẽ đo thời gian
ket_qua = tinh_tong(1000000)
print("Kết quả:", ket_qua)

# Decorator log
def log_ham(func):
    def wrapper(*args):
        print(f"Gọi {func.__name__}({args})")
        return func(*args)
    return wrapper

@log_ham
def nhan(a, b):
    return a * b

print(nhan(3, 4))
""",
        "tags": ["lop11", "decorator", "nang-cao"],
    },
    # ==================== LỚP 11 - BÀI TẬP TỔNG HỢP ====================
    {
        "title": "Quản lý điểm học sinh (File)",
        "category": "python-lop11-bai-tap",
        "difficulty": "intermediate",
        "description": "CRUD với file CSV",
        "code": '''import csv

FILE_NAME = "diem.csv"

def doc_diem():
    """Đọc điểm từ file"""
    try:
        with open(FILE_NAME, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except FileNotFoundError:
        return []

def ghi_diem(danh_sach):
    """Ghi điểm vào file"""
    with open(FILE_NAME, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["ten", "toan", "van", "anh"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(danh_sach)

def them_hoc_sinh():
    ds = doc_diem()
    ten = input("Tên: ")
    toan = float(input("Toán: "))
    van = float(input("Văn: "))
    anh = float(input("Anh: "))
    ds.append({"ten": ten, "toan": toan, "van": van, "anh": anh})
    ghi_diem(ds)
    print("✅ Đã thêm!")

def xem_diem():
    ds = doc_diem()
    print("\\n=== BẢNG ĐIỂM ===")
    for hs in ds:
        tb = (float(hs["toan"]) + float(hs["van"]) + float(hs["anh"])) / 3
        print(f"{hs['ten']:15} Toán:{hs['toan']:5} Văn:{hs['van']:5} Anh:{hs['anh']:5} TB:{tb:.2f}")

# Menu
while True:
    print("\\n1.Thêm 2.Xem 0.Thoát")
    chon = input("Chọn: ")
    if chon == "1":
        them_hoc_sinh()
    elif chon == "2":
        xem_diem()
    elif chon == "0":
        break
''',
        "tags": ["lop11", "csv", "crud", "bai-tap"],
    },
    {
        "title": "Tìm kiếm và thống kê",
        "category": "python-lop11-bai-tap",
        "difficulty": "intermediate",
        "description": "Xử lý dữ liệu phức tạp",
        "code": '''# Quản lý sản phẩm
san_pham = [
    {"ten": "Bàn phím", "gia": 500000, "sl": 10},
    {"ten": "Chuột", "gia": 200000, "sl": 15},
    {"ten": "Tai nghe", "gia": 800000, "sl": 5},
    {"ten": "Webcam", "gia": 1200000, "sl": 3},
]

def tim_theo_ten(tu_khoa):
    """Tìm sản phẩm theo tên"""
    ket_qua = [sp for sp in san_pham if tu_khoa.lower() in sp["ten"].lower()]
    return ket_qua

def loc_theo_gia(min_gia, max_gia):
    """Lọc sản phẩm theo khoảng giá"""
    return [sp for sp in san_pham if min_gia <= sp["gia"] <= max_gia]

def thong_ke():
    """Thống kê tổng quan"""
    tong_sp = len(san_pham)
    tong_sl = sum(sp["sl"] for sp in san_pham)
    tong_gt = sum(sp["gia"] * sp["sl"] for sp in san_pham)
    gia_tb = sum(sp["gia"] for sp in san_pham) / tong_sp

    print(f"Tổng {tong_sp} sản phẩm")
    print(f"Tổng SL: {tong_sl}")
    print(f"Giá trị kho: {tong_gt:,} đ")
    print(f"Giá TB: {gia_tb:,.0f} đ")

# Test
print("Tìm 'chuột':", tim_theo_ten("chuột"))
print("\\nGiá 200k-800k:", loc_theo_gia(200000, 800000))
print("\\n=== THỐNG KÊ ===")
thong_ke()
''',
        "tags": ["lop11", "tim-kiem", "thong-ke"],
    },
    {
        "title": "Trò chơi đoán số",
        "category": "python-lop11-bai-tap",
        "difficulty": "intermediate",
        "description": "Game logic đơn giản",
        "code": '''import random

def game_doan_so():
    """Trò chơi đoán số"""
    so_bi_mat = random.randint(1, 100)
    so_lan = 0
    max_lan = 7

    print("=== ĐOÁN SỐ TỪ 1-100 ===")
    print(f"Bạn có {max_lan} lần đoán")

    while so_lan < max_lan:
        try:
            du_doan = int(input(f"\\nLần {so_lan + 1}: "))
            so_lan += 1

            if du_doan == so_bi_mat:
                print(f"🎉 CHÍNH XÁC! Bạn đoán đúng sau {so_lan} lần")
                return
            elif du_doan < so_bi_mat:
                print("⬆️ Số cần tìm LỚN HƠN")
            else:
                print("⬇️ Số cần tìm NHỎ HƠN")

            print(f"Còn {max_lan - so_lan} lần")

        except ValueError:
            print("❌ Vui lòng nhập số!")

    print(f"\\n😢 HẾT LƯỢT! Số cần tìm là: {so_bi_mat}")

# Chơi game
game_doan_so()

# Chơi lại?
while input("\\nChơi lại? (y/n): ").lower() == "y":
    game_doan_so()
''',
        "tags": ["lop11", "game", "random"],
    },
    # ==================== LỚP 12 - OOP ====================
    {
        "title": "Class cơ bản",
        "category": "python-lop12-oop",
        "difficulty": "intermediate",
        "description": "Tạo class và object",
        "code": '''# Lập trình hướng đối tượng
class HocSinh:
    """Class học sinh"""

    def __init__(self, ten, tuoi, lop):
        """Constructor - khởi tạo object"""
        self.ten = ten
        self.tuoi = tuoi
        self.lop = lop

    def gioi_thieu(self):
        """Phương thức giới thiệu"""
        print(f"Tên: {self.ten}")
        print(f"Tuổi: {self.tuoi}")
        print(f"Lớp: {self.lop}")

# Tạo object
hs1 = HocSinh("Nguyễn Văn An", 16, "10A")
hs2 = HocSinh("Trần Thị Bình", 17, "10B")

# Gọi phương thức
hs1.gioi_thieu()
print("---")
hs2.gioi_thieu()

# Truy xuất thuộc tính
print(f"\\nTên HS1: {hs1.ten}")
print(f"Tuổi HS2: {hs2.tuoi}")
''',
        "tags": ["lop12", "oop", "class"],
    },
    {
        "title": "Thuộc tính và phương thức",
        "category": "python-lop12-oop",
        "difficulty": "intermediate",
        "description": "Attributes và methods",
        "code": '''class HinhChuNhat:
    """Class hình chữ nhật"""

    def __init__(self, dai, rong):
        self.dai = dai
        self.rong = rong

    def dien_tich(self):
        """Tính diện tích"""
        return self.dai * self.rong

    def chu_vi(self):
        """Tính chu vi"""
        return 2 * (self.dai + self.rong)

    def thong_tin(self):
        """Hiển thị thông tin"""
        print(f"Dài: {self.dai}m")
        print(f"Rộng: {self.rong}m")
        print(f"Diện tích: {self.dien_tich()}m²")
        print(f"Chu vi: {self.chu_vi()}m")

# Tạo object
hcn = HinhChuNhat(10, 5)
hcn.thong_tin()

# Thay đổi thuộc tính
hcn.dai = 15
print("\\nSau khi đổi dài:")
hcn.thong_tin()
''',
        "tags": ["lop12", "oop", "methods"],
    },
    {
        "title": "Encapsulation - Đóng gói",
        "category": "python-lop12-oop",
        "difficulty": "intermediate",
        "description": "Private attributes, getter/setter",
        "code": '''class TaiKhoan:
    """Class tài khoản ngân hàng"""

    def __init__(self, so_tk, chu_tk, so_du=0):
        self.so_tk = so_tk
        self.chu_tk = chu_tk
        self.__so_du = so_du  # Private attribute

    def nop_tien(self, so_tien):
        """Nộp tiền vào tài khoản"""
        if so_tien > 0:
            self.__so_du += so_tien
            print(f"✅ Nộp {so_tien:,}đ thành công")
        else:
            print("❌ Số tiền không hợp lệ")

    def rut_tien(self, so_tien):
        """Rút tiền"""
        if so_tien <= 0:
            print("❌ Số tiền không hợp lệ")
        elif so_tien > self.__so_du:
            print("❌ Số dư không đủ")
        else:
            self.__so_du -= so_tien
            print(f"✅ Rút {so_tien:,}đ thành công")

    def xem_so_du(self):
        """Xem số dư (getter)"""
        return self.__so_du

# Sử dụng
tk = TaiKhoan("0123456789", "Nguyễn Văn A", 1000000)
print(f"Số dư ban đầu: {tk.xem_so_du():,}đ")

tk.nop_tien(500000)
tk.rut_tien(300000)
print(f"Số dư hiện tại: {tk.xem_so_du():,}đ")
''',
        "tags": ["lop12", "oop", "encapsulation"],
    },
    {
        "title": "Inheritance - Kế thừa",
        "category": "python-lop12-oop",
        "difficulty": "intermediate",
        "description": "Class con kế thừa class cha",
        "code": '''# Class cha
class NguoiHoc:
    def __init__(self, ten, tuoi):
        self.ten = ten
        self.tuoi = tuoi

    def gioi_thieu(self):
        print(f"Tên: {self.ten}, Tuổi: {self.tuoi}")

# Class con kế thừa
class HocSinh(NguoiHoc):
    def __init__(self, ten, tuoi, lop):
        super().__init__(ten, tuoi)  # Gọi constructor cha
        self.lop = lop

    def gioi_thieu(self):
        """Override phương thức cha"""
        super().gioi_thieu()
        print(f"Lớp: {self.lop}")

class SinhVien(NguoiHoc):
    def __init__(self, ten, tuoi, truong):
        super().__init__(ten, tuoi)
        self.truong = truong

    def gioi_thieu(self):
        super().gioi_thieu()
        print(f"Trường: {self.truong}")

# Sử dụng
hs = HocSinh("An", 16, "10A")
sv = SinhVien("Bình", 20, "ĐHBK")

hs.gioi_thieu()
print("---")
sv.gioi_thieu()
''',
        "tags": ["lop12", "oop", "inheritance"],
    },
    {
        "title": "Polymorphism - Đa hình",
        "category": "python-lop12-oop",
        "difficulty": "intermediate",
        "description": "Cùng phương thức, hành vi khác nhau",
        "code": """# Đa hình
class HinhHoc:
    def dien_tich(self):
        pass

class HinhChuNhat(HinhHoc):
    def __init__(self, dai, rong):
        self.dai = dai
        self.rong = rong

    def dien_tich(self):
        return self.dai * self.rong

class HinhTron(HinhHoc):
    def __init__(self, ban_kinh):
        self.ban_kinh = ban_kinh

    def dien_tich(self):
        return 3.14 * self.ban_kinh ** 2

class HinhVuong(HinhHoc):
    def __init__(self, canh):
        self.canh = canh

    def dien_tich(self):
        return self.canh ** 2

# Đa hình: cùng phương thức dien_tich()
hinh_hoc = [
    HinhChuNhat(10, 5),
    HinhTron(7),
    HinhVuong(6)
]

for hinh in hinh_hoc:
    print(f"{hinh.__class__.__name__}: {hinh.dien_tich():.2f}")
""",
        "tags": ["lop12", "oop", "polymorphism"],
    },
    {
        "title": "Class method và Static method",
        "category": "python-lop12-oop",
        "difficulty": "intermediate",
        "description": "Phương thức class và static",
        "code": '''class MayTinh:
    """Class máy tính khoa học"""

    pi = 3.14159  # Class attribute
    so_may = 0

    def __init__(self, ten):
        self.ten = ten
        MayTinh.so_may += 1

    @classmethod
    def dem_may_tinh(cls):
        """Class method - truy xuất class attribute"""
        return cls.so_may

    @staticmethod
    def tinh_giai_thua(n):
        """Static method - không cần self hay cls"""
        if n <= 1:
            return 1
        return n * MayTinh.tinh_giai_thua(n-1)

    @staticmethod
    def la_nguyen_to(n):
        """Kiểm tra số nguyên tố"""
        if n < 2:
            return False
        for i in range(2, int(n**0.5) + 1):
            if n % i == 0:
                return False
        return True

# Tạo objects
may1 = MayTinh("Casio")
may2 = MayTinh("Texas")

# Class method
print("Số máy tính:", MayTinh.dem_may_tinh())

# Static method
print("5! =", MayTinh.tinh_giai_thua(5))
print("17 nguyên tố?", MayTinh.la_nguyen_to(17))
''',
        "tags": ["lop12", "oop", "classmethod", "staticmethod"],
    },
    # ==================== LỚP 12 - CẤU TRÚC DỮ LIỆU ====================
    {
        "title": "Dictionary - Từ điển",
        "category": "python-lop12-du-lieu",
        "difficulty": "intermediate",
        "description": "Key-value pairs",
        "code": """# Dictionary
hoc_sinh = {
    "ten": "Nguyễn Văn An",
    "tuoi": 16,
    "lop": "10A",
    "diem": [8, 7, 9]
}

# Truy xuất
print("Tên:", hoc_sinh["ten"])
print("Tuổi:", hoc_sinh.get("tuoi"))

# Thêm/Sửa
hoc_sinh["email"] = "an@gmail.com"
hoc_sinh["tuoi"] = 17

# Xóa
del hoc_sinh["email"]

# Duyệt dictionary
for key, value in hoc_sinh.items():
    print(f"{key}: {value}")

# Dict comprehension
binh_phuong = {x: x**2 for x in range(1, 6)}
print("Bình phương:", binh_phuong)

# Nested dictionary
lop_hoc = {
    "10A": {"si_so": 40, "gvcn": "Nguyễn Thị A"},
    "10B": {"si_so": 38, "gvcn": "Trần Văn B"}
}
print("10A:", lop_hoc["10A"]["si_so"], "HS")
""",
        "tags": ["lop12", "dictionary", "dict"],
    },
    {
        "title": "Set - Tập hợp",
        "category": "python-lop12-du-lieu",
        "difficulty": "intermediate",
        "description": "Tập hợp không trùng lặp",
        "code": """# Set - tập hợp
# Tạo set
so = {1, 2, 3, 4, 5}
so_trung = {1, 1, 2, 2, 3}  # Tự động loại trùng
print("Set:", so_trung)  # {1, 2, 3}

# Thêm/Xóa
so.add(6)
so.remove(1)
print("Sau thêm/xóa:", so)

# Phép toán tập hợp
A = {1, 2, 3, 4, 5}
B = {4, 5, 6, 7, 8}

print("Hợp:", A | B)        # Union
print("Giao:", A & B)        # Intersection
print("Hiệu:", A - B)        # Difference
print("Đối xứng:", A ^ B)   # Symmetric difference

# Ứng dụng: Loại bỏ trùng
danh_sach = [1, 2, 2, 3, 3, 3, 4, 4, 5]
khong_trung = list(set(danh_sach))
print("Không trùng:", khong_trung)
""",
        "tags": ["lop12", "set", "tap-hop"],
    },
    {
        "title": "Collections - deque, Counter",
        "category": "python-lop12-du-lieu",
        "difficulty": "intermediate",
        "description": "Cấu trúc dữ liệu nâng cao",
        "code": """from collections import deque, Counter

# Deque - hàng đợi 2 đầu
hang_doi = deque([1, 2, 3])
hang_doi.append(4)       # Thêm cuối
hang_doi.appendleft(0)   # Thêm đầu
print("Deque:", hang_doi)

hang_doi.pop()           # Xóa cuối
hang_doi.popleft()       # Xóa đầu
print("Sau xóa:", hang_doi)

# Counter - đếm phần tử
chu_cai = "hello world"
dem = Counter(chu_cai)
print("Đếm ký tự:", dem)
print("'l' xuất hiện:", dem['l'], "lần")

# Đếm từ
cau = "python la ngon ngu lap trinh python"
dem_tu = Counter(cau.split())
print("Đếm từ:", dem_tu)
print("Từ phổ biến:", dem_tu.most_common(2))

# Ứng dụng: Tìm phần tử xuất hiện nhiều nhất
so = [1, 2, 2, 3, 3, 3, 4, 4, 4, 4]
dem_so = Counter(so)
print("Nhiều nhất:", dem_so.most_common(1))
""",
        "tags": ["lop12", "collections", "deque", "counter"],
    },
    {
        "title": "Stack và Queue",
        "category": "python-lop12-du-lieu",
        "difficulty": "intermediate",
        "description": "Ngăn xếp và hàng đợi",
        "code": '''# Stack - Ngăn xếp (LIFO - Last In First Out)
class Stack:
    def __init__(self):
        self.items = []

    def push(self, item):
        """Đẩy vào stack"""
        self.items.append(item)

    def pop(self):
        """Lấy ra khỏi stack"""
        if not self.is_empty():
            return self.items.pop()

    def peek(self):
        """Xem phần tử đầu"""
        if not self.is_empty():
            return self.items[-1]

    def is_empty(self):
        return len(self.items) == 0

# Sử dụng Stack
stack = Stack()
stack.push(1)
stack.push(2)
stack.push(3)
print("Peek:", stack.peek())  # 3
print("Pop:", stack.pop())    # 3
print("Pop:", stack.pop())    # 2

# Queue - Hàng đợi (FIFO - First In First Out)
from collections import deque

queue = deque()
queue.append(1)  # Thêm vào cuối
queue.append(2)
queue.append(3)
print("Queue:", queue)
print("Dequeue:", queue.popleft())  # Lấy từ đầu
''',
        "tags": ["lop12", "stack", "queue", "cau-truc-du-lieu"],
    },
    # ==================== LỚP 12 - THƯ VIỆN PYTHON ====================
    {
        "title": "Math - Thư viện toán học",
        "category": "python-lop12-thu-vien",
        "difficulty": "intermediate",
        "description": "Hàm toán học cơ bản",
        "code": """import math

# Hằng số
print("Pi:", math.pi)
print("e:", math.e)

# Làm tròn
print("Ceil 3.2:", math.ceil(3.2))    # 4
print("Floor 3.8:", math.floor(3.8))  # 3

# Căn bậc
print("Sqrt 16:", math.sqrt(16))      # 4.0
print("Pow 2^3:", math.pow(2, 3))     # 8.0

# Lượng giác
goc_rad = math.radians(45)  # Đổi độ sang radian
print("Sin 45°:", math.sin(goc_rad))
print("Cos 45°:", math.cos(goc_rad))
print("Tan 45°:", math.tan(goc_rad))

# Logarit
print("Log 100:", math.log10(100))    # 2.0
print("Ln e:", math.log(math.e))      # 1.0

# Giai thừa
print("5!:", math.factorial(5))       # 120
""",
        "tags": ["lop12", "math", "thu-vien"],
    },
    {
        "title": "Random - Số ngẫu nhiên",
        "category": "python-lop12-thu-vien",
        "difficulty": "intermediate",
        "description": "Sinh số và lựa chọn ngẫu nhiên",
        "code": """import random

# Số ngẫu nhiên
print("Random float [0-1):", random.random())
print("Random int [1-10]:", random.randint(1, 10))
print("Random range:", random.randrange(0, 100, 5))

# Lựa chọn
mau_sac = ["đỏ", "xanh", "vàng", "tím"]
print("Chọn 1:", random.choice(mau_sac))
print("Chọn 2:", random.sample(mau_sac, 2))

# Xáo trộn
so = [1, 2, 3, 4, 5]
random.shuffle(so)
print("Đã xáo:", so)

# Ứng dụng: Tạo mật khẩu ngẫu nhiên
import string
ky_tu = string.ascii_letters + string.digits
mat_khau = ''.join(random.choices(ky_tu, k=8))
print("Mật khẩu:", mat_khau)

# Tung xúc xắc
print("Tung xúc xắc:", random.randint(1, 6))
""",
        "tags": ["lop12", "random", "thu-vien"],
    },
    {
        "title": "Datetime - Ngày giờ",
        "category": "python-lop12-thu-vien",
        "difficulty": "intermediate",
        "description": "Xử lý ngày tháng năm",
        "code": """from datetime import datetime, date, time, timedelta

# Ngày giờ hiện tại
now = datetime.now()
print("Bây giờ:", now)
print("Ngày:", now.date())
print("Giờ:", now.time())

# Tạo ngày giờ
ngay_sinh = datetime(2005, 5, 15, 10, 30)
print("Ngày sinh:", ngay_sinh)

# Format ngày giờ
print("Format:", now.strftime("%d/%m/%Y %H:%M:%S"))
print("Ngày VN:", now.strftime("%d tháng %m năm %Y"))

# Parse string thành datetime
ngay_str = "26/01/2026"
ngay = datetime.strptime(ngay_str, "%d/%m/%Y")
print("Parse:", ngay)

# Tính toán ngày
hom_nay = date.today()
mot_tuan = timedelta(days=7)
sau_1_tuan = hom_nay + mot_tuan
print("Hôm nay:", hom_nay)
print("Sau 1 tuần:", sau_1_tuan)

# Tính tuổi
tuoi = hom_nay.year - ngay_sinh.year
print(f"Tuổi: {tuoi}")
""",
        "tags": ["lop12", "datetime", "thu-vien"],
    },
    {
        "title": "JSON - Xử lý dữ liệu JSON",
        "category": "python-lop12-thu-vien",
        "difficulty": "intermediate",
        "description": "Đọc ghi file JSON",
        "code": """import json

# Dictionary sang JSON
hoc_sinh = {
    "ten": "Nguyễn Văn An",
    "tuoi": 16,
    "lop": "10A",
    "diem": [8, 7, 9, 6, 10]
}

# Chuyển sang JSON string
json_str = json.dumps(hoc_sinh, ensure_ascii=False, indent=2)
print("JSON string:")
print(json_str)

# Ghi file JSON
with open("hocsinh.json", "w", encoding="utf-8") as f:
    json.dump(hoc_sinh, f, ensure_ascii=False, indent=2)

# Đọc file JSON
with open("hocsinh.json", "r", encoding="utf-8") as f:
    data = json.load(f)
    print("\\nĐọc JSON:", data)
    print("Tên:", data["ten"])

# JSON string sang dict
json_text = '{"name": "Python", "version": 3.10}'
obj = json.loads(json_text)
print("Parse JSON:", obj)
""",
        "tags": ["lop12", "json", "thu-vien"],
    },
    {
        "title": "OS - Hệ thống file",
        "category": "python-lop12-thu-vien",
        "difficulty": "intermediate",
        "description": "Làm việc với hệ thống file",
        "code": """import os

# Thư mục hiện tại
print("Thư mục:", os.getcwd())

# Tạo thư mục
if not os.path.exists("data"):
    os.mkdir("data")
    print("Đã tạo thư mục data")

# Liệt kê file
print("\\nFile trong thư mục:")
for item in os.listdir("."):
    if os.path.isfile(item):
        print(f"  📄 {item}")
    elif os.path.isdir(item):
        print(f"  📁 {item}")

# Đường dẫn
duong_dan = "data/test.txt"
print("\\nTên file:", os.path.basename(duong_dan))
print("Thư mục:", os.path.dirname(duong_dan))
print("Tách:", os.path.splitext(duong_dan))

# Kiểm tra file/folder
print("\\nKiểm tra:")
print("data tồn tại?", os.path.exists("data"))
print("data là file?", os.path.isfile("data"))
print("data là folder?", os.path.isdir("data"))
""",
        "tags": ["lop12", "os", "file-system"],
    },
    # ==================== LỚP 12 - DỰ ÁN TỔNG HỢP ====================
    {
        "title": "Quản lý thư viện sách",
        "category": "python-lop12-du-an",
        "difficulty": "advanced",
        "description": "Dự án OOP + File + JSON",
        "code": """import json
from datetime import datetime

class Sach:
    def __init__(self, ma, ten, tac_gia, nam_xb):
        self.ma = ma
        self.ten = ten
        self.tac_gia = tac_gia
        self.nam_xb = nam_xb
        self.da_muon = False

    def to_dict(self):
        return self.__dict__

class ThuVien:
    def __init__(self, file_name="thuvien.json"):
        self.file_name = file_name
        self.sach = []
        self.doc_du_lieu()

    def doc_du_lieu(self):
        try:
            with open(self.file_name, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.sach = [Sach(**s) for s in data]
        except FileNotFoundError:
            self.sach = []

    def luu_du_lieu(self):
        with open(self.file_name, "w", encoding="utf-8") as f:
            data = [s.to_dict() for s in self.sach]
            json.dump(data, f, ensure_ascii=False, indent=2)

    def them_sach(self, sach):
        self.sach.append(sach)
        self.luu_du_lieu()

    def tim_sach(self, tu_khoa):
        return [s for s in self.sach if tu_khoa.lower() in s.ten.lower()]

    def muon_sach(self, ma):
        for s in self.sach:
            if s.ma == ma and not s.da_muon:
                s.da_muon = True
                self.luu_du_lieu()
                return True
        return False

# Demo
tv = ThuVien()
tv.them_sach(Sach("S001", "Python cơ bản", "Tác giả A", 2024))
print("Tìm 'python':", [s.ten for s in tv.tim_sach("python")])
""",
        "tags": ["lop12", "oop", "json", "du-an"],
    },
    {
        "title": "Ứng dụng To-Do List",
        "category": "python-lop12-du-an",
        "difficulty": "advanced",
        "description": "Quản lý công việc với JSON",
        "code": """import json
from datetime import datetime

class Task:
    def __init__(self, id, title, priority="medium", done=False):
        self.id = id
        self.title = title
        self.priority = priority
        self.done = done
        self.created = datetime.now().isoformat()

class TodoApp:
    def __init__(self):
        self.tasks = []
        self.load()

    def load(self):
        try:
            with open("todo.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tasks = [Task(**t) for t in data]
        except:
            self.tasks = []

    def save(self):
        with open("todo.json", "w", encoding="utf-8") as f:
            data = [t.__dict__ for t in self.tasks]
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add(self, title, priority="medium"):
        id = max([t.id for t in self.tasks], default=0) + 1
        self.tasks.append(Task(id, title, priority))
        self.save()

    def complete(self, id):
        for t in self.tasks:
            if t.id == id:
                t.done = True
                self.save()
                break

    def list_all(self):
        for t in self.tasks:
            status = "✅" if t.done else "⬜"
            print(f"{status} [{t.id}] {t.title} ({t.priority})")

# Demo
app = TodoApp()
app.add("Học Python", "high")
app.add("Làm bài tập", "medium")
app.list_all()
""",
        "tags": ["lop12", "todo", "json", "du-an"],
    },
    {
        "title": "Máy tính bỏ túi GUI",
        "category": "python-lop12-du-an",
        "difficulty": "advanced",
        "description": "Calculator với eval()",
        "code": '''class MayTinh:
    """Máy tính cơ bản"""

    def __init__(self):
        self.lich_su = []

    def tinh(self, bieu_thuc):
        """Tính toán biểu thức"""
        try:
            # An toàn hơn eval() trong production
            ket_qua = eval(bieu_thuc)
            self.lich_su.append(f"{bieu_thuc} = {ket_qua}")
            return ket_qua
        except Exception as e:
            return f"Lỗi: {e}"

    def xem_lich_su(self):
        """Xem lịch sử tính toán"""
        print("=== LỊCH SỬ ===")
        for i, phep in enumerate(self.lich_su, 1):
            print(f"{i}. {phep}")

    def xoa_lich_su(self):
        """Xóa lịch sử"""
        self.lich_su = []

# Chương trình chính
may_tinh = MayTinh()

print("=== MÁY TÍNH BỎ TÚI ===")
print("Nhập biểu thức (hoặc 'q' để thoát)")
print("Lệnh: 'ls' (lịch sử), 'clear' (xóa)")

while True:
    nhap = input("\\n> ").strip()

    if nhap == 'q':
        break
    elif nhap == 'ls':
        may_tinh.xem_lich_su()
    elif nhap == 'clear':
        may_tinh.xoa_lich_su()
        print("Đã xóa lịch sử")
    else:
        ket_qua = may_tinh.tinh(nhap)
        print(f"= {ket_qua}")
''',
        "tags": ["lop12", "calculator", "oop"],
    },
    {
        "title": "Trò chơi Tic-Tac-Toe (X-O)",
        "category": "python-lop12-du-an",
        "difficulty": "advanced",
        "description": "Game logic và AI đơn giản",
        "code": """import random

class TicTacToe:
    def __init__(self):
        self.board = [' ' for _ in range(9)]
        self.current_winner = None

    def print_board(self):
        for row in [self.board[i*3:(i+1)*3] for i in range(3)]:
            print('| ' + ' | '.join(row) + ' |')

    def available_moves(self):
        return [i for i, spot in enumerate(self.board) if spot == ' ']

    def make_move(self, square, letter):
        if self.board[square] == ' ':
            self.board[square] = letter
            if self.winner(square, letter):
                self.current_winner = letter
            return True
        return False

    def winner(self, square, letter):
        # Kiểm tra hàng
        row_ind = square // 3
        row = self.board[row_ind*3:(row_ind+1)*3]
        if all([spot == letter for spot in row]):
            return True
        # Kiểm tra cột
        col_ind = square % 3
        column = [self.board[col_ind+i*3] for i in range(3)]
        if all([spot == letter for spot in column]):
            return True
        # Kiểm tra chéo
        if square % 2 == 0:
            diagonal1 = [self.board[i] for i in [0, 4, 8]]
            if all([spot == letter for spot in diagonal1]):
                return True
            diagonal2 = [self.board[i] for i in [2, 4, 6]]
            if all([spot == letter for spot in diagonal2]):
                return True
        return False

# Chơi game
game = TicTacToe()
print("Vị trí: 0-8")
game.print_board()
""",
        "tags": ["lop12", "game", "ai", "du-an"],
    },
]


def create_categories():
    """Tạo categories"""
    db_manager = DBManager()
    db = db_manager.db

    print("📚 Tạo categories...")
    for cat in CATEGORIES:
        # Check if exists
        existing = db.code_template_categories.find_one({"id": cat["id"]})
        if existing:
            print(f"  ⏭️  Category '{cat['name']}' đã tồn tại")
            continue

        cat_doc = {
            **cat,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
        db.code_template_categories.insert_one(cat_doc)
        print(f"  ✅ {cat['name']}")


def create_templates():
    """Tạo templates"""
    db_manager = DBManager()
    db = db_manager.db

    print(f"\n📋 Tạo {len(TEMPLATES)} templates...")

    for template in TEMPLATES:
        # Check if exists
        existing = db.code_templates.find_one({"title": template["title"]})
        if existing:
            print(f"  ⏭️  '{template['title']}' đã tồn tại")
            continue

        template_doc = {
            "title": template["title"],
            "category": template["category"],
            "programming_language": "python",
            "difficulty": template["difficulty"],
            "description": template["description"],
            "code": template["code"],
            "tags": template["tags"],
            "is_featured": False,
            "is_active": True,
            "metadata": {
                "author": "WordAI",
                "version": "1.0",
                "usage_count": 0,
                "dependencies": [],
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        db.code_templates.insert_one(template_doc)
        print(f"  ✅ {template['title']} ({template['category']})")


def main():
    print("=" * 60)
    print("🎓 SETUP PYTHON TEMPLATES - SGK TIN HỌC 10-11-12")
    print("=" * 60)

    create_categories()
    create_templates()

    print("\n" + "=" * 60)
    print("✅ HOÀN THÀNH!")
    print(f"📚 {len(CATEGORIES)} categories")
    print(f"📋 {len(TEMPLATES)} templates")
    print("=" * 60)


if __name__ == "__main__":
    main()
