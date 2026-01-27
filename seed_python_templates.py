"""
Script: Seed Python Templates for All Topics
Adds comprehensive code templates for each Python learning topic
"""

import sys
import os
from datetime import datetime
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database.db_manager import DBManager

# WordAI Team user ID (from migration)
WORDAI_TEAM_UID = "tienhoi.lh@gmail.com"
WORDAI_TEAM_EMAIL = "tienhoi.lh@gmail.com"

# Dry run mode
DRY_RUN = False  # Set to True to preview changes without executing


def create_templates():
    """
    Create comprehensive Python templates for all topics
    """
    
    print("=" * 80)
    print("SEEDING PYTHON TEMPLATES")
    print("=" * 80)
    
    if DRY_RUN:
        print("\n⚠️  DRY RUN MODE - No changes will be made")
        print("Set DRY_RUN = False to execute seeding\n")
    
    db_manager = DBManager()
    db = db_manager.db
    
    # Statistics
    stats = {
        "total_templates": 0,
        "created": 0,
        "skipped": 0,
        "errors": 0,
    }
    
    # Define templates for each topic
    templates = [
        # ==================== LỚP 10 - GIỚI THIỆU PYTHON ====================
        {
            "topic_id": "python-lop10-gioi-thieu",
            "title": "Cài đặt Python và chạy chương trình đầu tiên",
            "code": '''# Cài đặt Python từ python.org
# Kiểm tra phiên bản
import sys
print(f"Python version: {sys.version}")
print("Hello, Python!")''',
            "description": "Kiểm tra cài đặt Python và chạy chương trình đầu tiên",
            "difficulty": "beginner",
            "tags": ["lop10", "gioi-thieu", "setup"]
        },
        {
            "topic_id": "python-lop10-gioi-thieu",
            "title": "Sử dụng Python Interactive Shell",
            "code": '''# Mở terminal/cmd và gõ: python
# Thử các phép toán cơ bản
>>> 2 + 3
5
>>> 10 * 5
50
>>> print("Welcome to Python!")
Welcome to Python!''',
            "description": "Làm quen với Python Shell để thử nghiệm code nhanh",
            "difficulty": "beginner",
            "tags": ["lop10", "gioi-thieu", "shell"]
        },
        
        # ==================== LỚP 10 - BIẾN VÀ KIỂU DỮ LIỆU ====================
        {
            "topic_id": "python-lop10-bien-kieu-du-lieu",
            "title": "Kiểu Boolean (True/False)",
            "code": '''# Boolean - giá trị đúng/sai
is_student = True
has_passed = False

print(f"Là học sinh: {is_student}")
print(f"Đã qua môn: {has_passed}")

# Kết quả so sánh trả về boolean
age = 16
is_adult = age >= 18
print(f"Đã trưởng thành: {is_adult}")''',
            "description": "Kiểu dữ liệu Boolean để biểu diễn giá trị logic",
            "difficulty": "beginner",
            "tags": ["lop10", "bien", "boolean"]
        },
        {
            "topic_id": "python-lop10-bien-kieu-du-lieu",
            "title": "Toán tử số học nâng cao",
            "code": '''# Các toán tử số học
a = 17
b = 5

print(f"Cộng: {a} + {b} = {a + b}")
print(f"Trừ: {a} - {b} = {a - b}")
print(f"Nhân: {a} * {b} = {a * b}")
print(f"Chia: {a} / {b} = {a / b}")
print(f"Chia lấy phần nguyên: {a} // {b} = {a // b}")
print(f"Chia lấy dư: {a} % {b} = {a % b}")
print(f"Lũy thừa: {a} ** 2 = {a ** 2}")''',
            "description": "Các phép toán số học cơ bản và nâng cao trong Python",
            "difficulty": "beginner",
            "tags": ["lop10", "bien", "toan-tu"]
        },
        
        # ==================== LỚP 10 - NHẬP/XUẤT DỮ LIỆU ====================
        {
            "topic_id": "python-lop10-nhap-xuat",
            "title": "Định dạng output với f-string",
            "code": '''# f-string - cách định dạng hiện đại nhất
name = "Nguyễn Văn A"
age = 16
score = 8.75

# Chèn biến vào chuỗi
print(f"Tên: {name}")
print(f"Tuổi: {age}")
print(f"Điểm: {score}")

# Định dạng số thập phân
pi = 3.14159265
print(f"Pi = {pi:.2f}")  # 2 chữ số thập phân

# Căn lề
print(f"{'Tên':<10} {'Điểm':>5}")
print(f"{name:<10} {score:>5.1f}")''',
            "description": "Sử dụng f-string để định dạng output đẹp mắt",
            "difficulty": "beginner",
            "tags": ["lop10", "nhap-xuat", "format"]
        },
        {
            "topic_id": "python-lop10-nhap-xuat",
            "title": "Nhập nhiều giá trị cùng lúc",
            "code": '''# Nhập nhiều giá trị trên cùng một dòng
print("Nhập họ tên và tuổi (cách nhau bởi dấu cách):")
data = input().split()
name = data[0]
age = int(data[1])

print(f"Xin chào {name}, bạn {age} tuổi")

# Cách ngắn gọn hơn
print("Nhập chiều dài và chiều rộng:")
length, width = map(float, input().split())
area = length * width
print(f"Diện tích: {area} m²")''',
            "description": "Nhập nhiều giá trị cùng lúc và xử lý",
            "difficulty": "intermediate",
            "tags": ["lop10", "nhap-xuat", "split"]
        },
        
        # ==================== LỚP 10 - CẤU TRÚC ĐIỀU KIỆN ====================
        {
            "topic_id": "python-lop10-dieu-kien",
            "title": "Ternary Operator (If rút gọn)",
            "code": '''# Toán tử ba ngôi - viết if else trên một dòng
age = 17
status = "Trưởng thành" if age >= 18 else "Chưa trưởng thành"
print(status)

# So sánh với if else thường
if age >= 18:
    status = "Trưởng thành"
else:
    status = "Chưa trưởng thành"
print(status)

# Ví dụ khác
score = 7.5
result = "Đậu" if score >= 5 else "Rớt"
print(f"Kết quả: {result}")''',
            "description": "Viết điều kiện ngắn gọn với ternary operator",
            "difficulty": "intermediate",
            "tags": ["lop10", "dieu-kien", "ternary"]
        },
        
        # ==================== LỚP 10 - VÒNG LẶP ====================
        {
            "topic_id": "python-lop10-vong-lap",
            "title": "Vòng lặp For với range()",
            "code": '''# range(start, stop, step)
# In số từ 0 đến 4
for i in range(5):
    print(i, end=" ")
print()

# In số từ 1 đến 10
for i in range(1, 11):
    print(i, end=" ")
print()

# In số chẵn từ 0 đến 10
for i in range(0, 11, 2):
    print(i, end=" ")
print()

# Đếm ngược từ 10 về 1
for i in range(10, 0, -1):
    print(i, end=" ")
print()''',
            "description": "Sử dụng range() để tạo vòng lặp với các bước khác nhau",
            "difficulty": "beginner",
            "tags": ["lop10", "vong-lap", "range"]
        },
        {
            "topic_id": "python-lop10-vong-lap",
            "title": "Break và Continue",
            "code": '''# Break - thoát khỏi vòng lặp
print("Tìm số chia hết cho 7:")
for i in range(1, 100):
    if i % 7 == 0:
        print(f"Số đầu tiên chia hết cho 7: {i}")
        break

# Continue - bỏ qua lần lặp hiện tại
print("\\nIn số lẻ từ 1 đến 10:")
for i in range(1, 11):
    if i % 2 == 0:  # Nếu là số chẵn
        continue     # Bỏ qua, không in
    print(i, end=" ")
print()''',
            "description": "Điều khiển vòng lặp với break và continue",
            "difficulty": "intermediate",
            "tags": ["lop10", "vong-lap", "break", "continue"]
        },
        {
            "topic_id": "python-lop10-vong-lap",
            "title": "Nested Loop (Vòng lặp lồng nhau)",
            "code": '''# In bảng cửu chương
for i in range(1, 10):
    for j in range(1, 10):
        print(f"{i} x {j} = {i*j:2d}", end="  |  ")
    print()

# In hình tam giác sao
print("\\nHình tam giác:")
for i in range(1, 6):
    for j in range(i):
        print("*", end=" ")
    print()

# In hình chữ nhật
print("\\nHình chữ nhật 5x3:")
for i in range(3):
    for j in range(5):
        print("# ", end="")
    print()''',
            "description": "Vòng lặp lồng nhau để tạo các mẫu hình",
            "difficulty": "intermediate",
            "tags": ["lop10", "vong-lap", "nested"]
        },
        
        # ==================== LỚP 10 - LIST VÀ STRING ====================
        {
            "topic_id": "python-lop10-list-string",
            "title": "List Methods - Các phương thức List",
            "code": '''# Tạo list
fruits = ["táo", "chuối", "cam"]

# Thêm phần tử
fruits.append("dưa")        # Thêm vào cuối
fruits.insert(1, "nho")     # Thêm vào vị trí 1
print(f"Sau khi thêm: {fruits}")

# Xóa phần tử
fruits.remove("chuối")      # Xóa theo giá trị
item = fruits.pop()         # Xóa phần tử cuối
print(f"Đã xóa: {item}")
print(f"Sau khi xóa: {fruits}")

# Sắp xếp
fruits.sort()               # Sắp xếp tăng dần
print(f"Đã sắp xếp: {fruits}")

# Đảo ngược
fruits.reverse()
print(f"Đảo ngược: {fruits}")''',
            "description": "Các phương thức làm việc với List",
            "difficulty": "beginner",
            "tags": ["lop10", "list", "methods"]
        },
        {
            "topic_id": "python-lop10-list-string",
            "title": "String Methods - Các phương thức String",
            "code": '''# String methods
text = "  Hello Python World  "

# Loại bỏ khoảng trắng
print(f"strip(): '{text.strip()}'")
print(f"lstrip(): '{text.lstrip()}'")
print(f"rstrip(): '{text.rstrip()}'")

# Chuyển đổi chữ hoa/thường
print(f"upper(): {text.upper()}")
print(f"lower(): {text.lower()}")
print(f"title(): {text.title()}")

# Tìm và thay thế
print(f"replace(): {text.replace('Python', 'Java')}")
print(f"find(): {text.find('Python')}")

# Tách chuỗi
words = text.strip().split()
print(f"split(): {words}")''',
            "description": "Các phương thức xử lý chuỗi trong Python",
            "difficulty": "beginner",
            "tags": ["lop10", "string", "methods"]
        },
        
        # ==================== LỚP 10 - HÀM CƠ BẢN ====================
        {
            "topic_id": "python-lop10-ham",
            "title": "Hàm với Return",
            "code": '''# Hàm trả về giá trị
def tinh_tong(a, b):
    return a + b

def tinh_trung_binh(numbers):
    if len(numbers) == 0:
        return 0
    return sum(numbers) / len(numbers)

def kiem_tra_chan(n):
    return n % 2 == 0

# Sử dụng hàm
tong = tinh_tong(5, 3)
print(f"Tổng: {tong}")

diem = [8, 7.5, 9, 6.5]
tb = tinh_trung_binh(diem)
print(f"Điểm trung bình: {tb:.2f}")

so = 10
print(f"{so} là số chẵn: {kiem_tra_chan(so)}")''',
            "description": "Tạo hàm trả về giá trị với return",
            "difficulty": "beginner",
            "tags": ["lop10", "ham", "return"]
        },
        {
            "topic_id": "python-lop10-ham",
            "title": "Hàm với tham số mặc định",
            "code": '''# Tham số mặc định
def chao_mung(name, greeting="Xin chào"):
    return f"{greeting}, {name}!"

# Gọi hàm với 1 tham số
print(chao_mung("An"))

# Gọi hàm với 2 tham số
print(chao_mung("Bình", "Chào buổi sáng"))

# Hàm tính diện tích hình chữ nhật
def dien_tich_hcn(dai, rong=None):
    if rong is None:
        rong = dai  # Nếu không có rộng -> hình vuông
    return dai * rong

print(f"Hình vuông 5x5: {dien_tich_hcn(5)}")
print(f"Hình chữ nhật 5x3: {dien_tich_hcn(5, 3)}")''',
            "description": "Sử dụng tham số mặc định trong hàm",
            "difficulty": "intermediate",
            "tags": ["lop10", "ham", "default-param"]
        },
        
        # ==================== LỚP 10 - BÀI TẬP THỰC HÀNH ====================
        {
            "topic_id": "python-lop10-bai-tap",
            "title": "Kiểm tra số nguyên tố",
            "code": '''def kiem_tra_nguyen_to(n):
    """Kiểm tra số nguyên tố"""
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True

# Test
so = int(input("Nhập số cần kiểm tra: "))
if kiem_tra_nguyen_to(so):
    print(f"{so} là số nguyên tố")
else:
    print(f"{so} không phải số nguyên tố")

# In các số nguyên tố từ 1 đến 100
print("\\nCác số nguyên tố từ 1 đến 100:")
for i in range(1, 101):
    if kiem_tra_nguyen_to(i):
        print(i, end=" ")
print()''',
            "description": "Viết chương trình kiểm tra và liệt kê số nguyên tố",
            "difficulty": "intermediate",
            "tags": ["lop10", "bai-tap", "nguyen-to"]
        },
        {
            "topic_id": "python-lop10-bai-tap",
            "title": "Tìm ước số chung lớn nhất (ƯCLN)",
            "code": '''def tim_ucln(a, b):
    """Tìm ước chung lớn nhất bằng thuật toán Euclid"""
    while b != 0:
        temp = b
        b = a % b
        a = temp
    return a

def tim_bcnn(a, b):
    """Tìm bội chung nhỏ nhất"""
    return (a * b) // tim_ucln(a, b)

# Test
a = int(input("Nhập số thứ nhất: "))
b = int(input("Nhập số thứ hai: "))

ucln = tim_ucln(a, b)
bcnn = tim_bcnn(a, b)

print(f"ƯCLN({a}, {b}) = {ucln}")
print(f"BCNN({a}, {b}) = {bcnn}")''',
            "description": "Tìm ước chung lớn nhất và bội chung nhỏ nhất",
            "difficulty": "intermediate",
            "tags": ["lop10", "bai-tap", "ucln"]
        },
        {
            "topic_id": "python-lop10-bai-tap",
            "title": "Tính giai thừa và tổ hợp",
            "code": '''def giai_thua(n):
    """Tính giai thừa của n"""
    if n == 0 or n == 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

def to_hop(n, k):
    """Tính tổ hợp C(n, k) = n! / (k! * (n-k)!)"""
    if k > n:
        return 0
    return giai_thua(n) // (giai_thua(k) * giai_thua(n - k))

# Test
n = int(input("Nhập n: "))
print(f"{n}! = {giai_thua(n)}")

k = int(input("Nhập k: "))
print(f"C({n}, {k}) = {to_hop(n, k)}")

# In tam giác Pascal
print(f"\\nTam giác Pascal ({n} dòng):")
for i in range(n + 1):
    for j in range(i + 1):
        print(to_hop(i, j), end=" ")
    print()''',
            "description": "Tính giai thừa, tổ hợp và vẽ tam giác Pascal",
            "difficulty": "intermediate",
            "tags": ["lop10", "bai-tap", "giai-thua"]
        },
        
        # ==================== LỚP 11 - CƠ BẢN NÂNG CAO ====================
        {
            "topic_id": "python-lop11-co-ban",
            "title": "Tuple - Dữ liệu bất biến",
            "code": '''# Tuple - không thể thay đổi sau khi tạo
coordinates = (10, 20)
print(f"Tọa độ: {coordinates}")
print(f"x = {coordinates[0]}, y = {coordinates[1]}")

# Unpacking tuple
x, y = coordinates
print(f"x = {x}, y = {y}")

# Tuple với nhiều giá trị
student = ("Nguyễn Văn A", 17, "Lớp 11A", 8.5)
name, age, class_name, score = student
print(f"Tên: {name}, Tuổi: {age}, Lớp: {class_name}, Điểm: {score}")

# Tuple methods
numbers = (1, 2, 3, 2, 4, 2, 5)
print(f"Số lần xuất hiện của 2: {numbers.count(2)}")
print(f"Vị trí đầu tiên của 3: {numbers.index(3)}")''',
            "description": "Làm việc với Tuple - kiểu dữ liệu bất biến",
            "difficulty": "intermediate",
            "tags": ["lop11", "tuple", "immutable"]
        },
        {
            "topic_id": "python-lop11-co-ban",
            "title": "Dictionary - Từ điển",
            "code": '''# Dictionary - lưu trữ cặp key-value
student = {
    "name": "Nguyễn Văn A",
    "age": 17,
    "class": "11A",
    "scores": {"math": 8, "physics": 7.5, "chemistry": 9}
}

# Truy cập giá trị
print(f"Tên: {student['name']}")
print(f"Điểm toán: {student['scores']['math']}")

# Thêm/sửa giá trị
student["phone"] = "0123456789"
student["age"] = 18

# Lặp qua dictionary
print("\\nThông tin học sinh:")
for key, value in student.items():
    print(f"{key}: {value}")

# Dictionary methods
print(f"\\nCác keys: {student.keys()}")
print(f"Các values: {student.values()}")''',
            "description": "Sử dụng Dictionary để lưu trữ dữ liệu có cấu trúc",
            "difficulty": "intermediate",
            "tags": ["lop11", "dictionary", "dict"]
        },
        {
            "topic_id": "python-lop11-co-ban",
            "title": "Set - Tập hợp",
            "code": '''# Set - tập hợp không có phần tử trùng lặp
numbers = {1, 2, 3, 4, 5}
print(f"Tập hợp: {numbers}")

# Tự động loại bỏ phần tử trùng
duplicate_numbers = {1, 2, 2, 3, 3, 3, 4}
print(f"Sau khi loại trùng: {duplicate_numbers}")

# Các phép toán tập hợp
A = {1, 2, 3, 4, 5}
B = {4, 5, 6, 7, 8}

print(f"A = {A}")
print(f"B = {B}")
print(f"Hợp (A ∪ B): {A | B}")
print(f"Giao (A ∩ B): {A & B}")
print(f"Hiệu (A - B): {A - B}")
print(f"Hiệu đối xứng (A △ B): {A ^ B}")

# Set methods
A.add(6)
A.remove(1)
print(f"A sau khi thêm 6 và xóa 1: {A}")''',
            "description": "Làm việc với Set và các phép toán tập hợp",
            "difficulty": "intermediate",
            "tags": ["lop11", "set", "tap-hop"]
        },
        
        # ==================== LỚP 11 - XỬ LÝ CHUỖI & LIST NÂNG CAO ====================
        {
            "topic_id": "python-lop11-chuoi-list",
            "title": "List Comprehension",
            "code": '''# List comprehension - cách tạo list ngắn gọn
# Cách thông thường
squares = []
for i in range(1, 11):
    squares.append(i ** 2)
print(f"Bình phương: {squares}")

# Với list comprehension
squares = [i ** 2 for i in range(1, 11)]
print(f"Bình phương (comprehension): {squares}")

# Với điều kiện - chỉ lấy số chẵn
even_squares = [i ** 2 for i in range(1, 11) if i % 2 == 0]
print(f"Bình phương số chẵn: {even_squares}")

# Nested list comprehension
matrix = [[i * j for j in range(1, 4)] for i in range(1, 4)]
print(f"Ma trận 3x3: {matrix}")''',
            "description": "Tạo list nhanh chóng với list comprehension",
            "difficulty": "intermediate",
            "tags": ["lop11", "list", "comprehension"]
        },
        {
            "topic_id": "python-lop11-chuoi-list",
            "title": "Lambda Functions",
            "code": '''# Lambda - hàm ẩn danh (anonymous function)
# Hàm thông thường
def square(x):
    return x ** 2

# Lambda function
square_lambda = lambda x: x ** 2

print(f"Bình phương 5 (hàm thường): {square(5)}")
print(f"Bình phương 5 (lambda): {square_lambda(5)}")

# Sử dụng lambda với map()
numbers = [1, 2, 3, 4, 5]
squared = list(map(lambda x: x ** 2, numbers))
print(f"Map với lambda: {squared}")

# Sử dụng lambda với filter()
even_numbers = list(filter(lambda x: x % 2 == 0, numbers))
print(f"Filter số chẵn: {even_numbers}")

# Sử dụng lambda với sorted()
students = [("An", 8), ("Bình", 9), ("Chi", 7.5)]
sorted_students = sorted(students, key=lambda x: x[1], reverse=True)
print(f"Sắp xếp theo điểm: {sorted_students}")''',
            "description": "Sử dụng lambda functions cho code ngắn gọn",
            "difficulty": "advanced",
            "tags": ["lop11", "lambda", "functional"]
        },
        {
            "topic_id": "python-lop11-chuoi-list",
            "title": "String Formatting nâng cao",
            "code": '''# Các cách format string
name = "Nguyễn Văn A"
age = 17
score = 8.75

# 1. %-formatting (cũ)
print("Tên: %s, Tuổi: %d, Điểm: %.2f" % (name, age, score))

# 2. str.format()
print("Tên: {}, Tuổi: {}, Điểm: {:.2f}".format(name, age, score))
print("Tên: {n}, Tuổi: {a}, Điểm: {s:.2f}".format(n=name, a=age, s=score))

# 3. f-string (hiện đại nhất)
print(f"Tên: {name}, Tuổi: {age}, Điểm: {score:.2f}")

# Format số
number = 1234567.89
print(f"Dấu phân cách: {number:,.2f}")
print(f"Phần trăm: {0.85:.2%}")

# Alignment
print(f"{'Left':<10}|{'Center':^10}|{'Right':>10}")''',
            "description": "Các cách định dạng chuỗi trong Python",
            "difficulty": "intermediate",
            "tags": ["lop11", "string", "formatting"]
        },
        
        # ==================== LỚP 11 - THAO TÁC VỚI FILE ====================
        {
            "topic_id": "python-lop11-file",
            "title": "Đọc file text line by line",
            "code": '''# Đọc file từng dòng
try:
    with open('data.txt', 'r', encoding='utf-8') as file:
        # Cách 1: Đọc tất cả
        content = file.read()
        print("Toàn bộ nội dung:")
        print(content)
        
    # Cách 2: Đọc từng dòng
    with open('data.txt', 'r', encoding='utf-8') as file:
        print("\\nĐọc từng dòng:")
        for line_number, line in enumerate(file, 1):
            print(f"Dòng {line_number}: {line.strip()}")
            
    # Cách 3: Đọc vào list
    with open('data.txt', 'r', encoding='utf-8') as file:
        lines = file.readlines()
        print(f"\\nTổng số dòng: {len(lines)}")
        
except FileNotFoundError:
    print("Không tìm thấy file!")
except Exception as e:
    print(f"Lỗi: {e}")''',
            "description": "Các cách đọc file text trong Python",
            "difficulty": "intermediate",
            "tags": ["lop11", "file", "read"]
        },
        {
            "topic_id": "python-lop11-file",
            "title": "Xử lý file CSV",
            "code": '''import csv

# Ghi file CSV
students = [
    ['Tên', 'Tuổi', 'Lớp', 'Điểm'],
    ['Nguyễn Văn A', 17, '11A', 8.5],
    ['Trần Thị B', 16, '11B', 9.0],
    ['Lê Văn C', 17, '11A', 7.5]
]

with open('students.csv', 'w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerows(students)
print("Đã ghi file students.csv")

# Đọc file CSV
print("\\nNội dung file CSV:")
with open('students.csv', 'r', encoding='utf-8') as file:
    reader = csv.reader(file)
    for row in reader:
        print(', '.join(row))

# Đọc CSV thành dictionary
print("\\nĐọc CSV thành dictionary:")
with open('students.csv', 'r', encoding='utf-8') as file:
    reader = csv.DictReader(file)
    for row in reader:
        print(f"{row['Tên']}: {row['Điểm']}")''',
            "description": "Đọc và ghi file CSV để lưu trữ dữ liệu dạng bảng",
            "difficulty": "intermediate",
            "tags": ["lop11", "file", "csv"]
        },
        
        # ==================== LỚP 11 - HÀM VÀ CHƯƠNG TRÌNH CON ====================
        {
            "topic_id": "python-lop11-ham-nang-cao",
            "title": "Args và Kwargs",
            "code": '''# *args - nhận số lượng tham số bất kỳ
def tinh_tong(*args):
    """Tính tổng các số"""
    return sum(args)

print(f"Tổng: {tinh_tong(1, 2, 3)}")
print(f"Tổng: {tinh_tong(1, 2, 3, 4, 5)}")

# **kwargs - nhận tham số có tên
def thong_tin_hoc_sinh(**kwargs):
    """In thông tin học sinh"""
    for key, value in kwargs.items():
        print(f"{key}: {value}")

print("\\nThông tin học sinh 1:")
thong_tin_hoc_sinh(name="An", age=17, score=8.5)

print("\\nThông tin học sinh 2:")
thong_tin_hoc_sinh(name="Bình", age=16, class_name="11A", phone="0123")

# Kết hợp cả hai
def mixed_function(required, *args, **kwargs):
    print(f"Bắt buộc: {required}")
    print(f"Args: {args}")
    print(f"Kwargs: {kwargs}")

mixed_function("value1", "arg1", "arg2", key1="kwarg1", key2="kwarg2")''',
            "description": "Sử dụng *args và **kwargs cho hàm linh hoạt",
            "difficulty": "advanced",
            "tags": ["lop11", "ham", "args", "kwargs"]
        },
        {
            "topic_id": "python-lop11-ham-nang-cao",
            "title": "Recursion - Đệ quy",
            "code": '''# Hàm đệ quy - gọi chính nó
def giai_thua(n):
    """Tính giai thừa bằng đệ quy"""
    if n == 0 or n == 1:
        return 1
    return n * giai_thua(n - 1)

print(f"5! = {giai_thua(5)}")

# Fibonacci bằng đệ quy
def fibonacci(n):
    """Số Fibonacci thứ n"""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

print("\\nDãy Fibonacci (10 số đầu):")
for i in range(10):
    print(fibonacci(i), end=" ")
print()

# Tìm ước chung lớn nhất (Euclid)
def gcd(a, b):
    """ƯCLN bằng đệ quy"""
    if b == 0:
        return a
    return gcd(b, a % b)

print(f"\\nƯCLN(48, 18) = {gcd(48, 18)}")''',
            "description": "Viết hàm đệ quy để giải quyết bài toán",
            "difficulty": "advanced",
            "tags": ["lop11", "ham", "recursion"]
        },
        {
            "topic_id": "python-lop11-ham-nang-cao",
            "title": "Decorators cơ bản",
            "code": '''# Decorator - trang trí hàm
import time

def measure_time(func):
    """Decorator đo thời gian thực thi"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"Thời gian: {end - start:.4f}s")
        return result
    return wrapper

@measure_time
def count_to_million():
    """Đếm đến 1 triệu"""
    total = 0
    for i in range(1000000):
        total += i
    return total

result = count_to_million()
print(f"Kết quả: {result}")

# Decorator với tham số
def repeat(times):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for _ in range(times):
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator

@repeat(times=3)
def say_hello():
    print("Hello!")

say_hello()''',
            "description": "Sử dụng decorators để mở rộng chức năng hàm",
            "difficulty": "advanced",
            "tags": ["lop11", "ham", "decorator"]
        },
        
        # ==================== LỚP 11 - BÀI TẬP TỔNG HỢP ====================
        {
            "topic_id": "python-lop11-bai-tap",
            "title": "Quản lý sách thư viện",
            "code": '''# Hệ thống quản lý sách thư viện
class Library:
    def __init__(self):
        self.books = {}  # {id: {title, author, year, available}}
        self.next_id = 1
    
    def add_book(self, title, author, year):
        """Thêm sách mới"""
        self.books[self.next_id] = {
            'title': title,
            'author': author,
            'year': year,
            'available': True
        }
        print(f"Đã thêm sách ID: {self.next_id}")
        self.next_id += 1
    
    def borrow_book(self, book_id):
        """Mượn sách"""
        if book_id in self.books:
            if self.books[book_id]['available']:
                self.books[book_id]['available'] = False
                print(f"Đã mượn: {self.books[book_id]['title']}")
            else:
                print("Sách đang được mượn")
        else:
            print("Không tìm thấy sách")
    
    def return_book(self, book_id):
        """Trả sách"""
        if book_id in self.books:
            self.books[book_id]['available'] = True
            print(f"Đã trả: {self.books[book_id]['title']}")
    
    def list_books(self):
        """Liệt kê tất cả sách"""
        for id, book in self.books.items():
            status = "Có sẵn" if book['available'] else "Đang mượn"
            print(f"[{id}] {book['title']} - {book['author']} ({book['year']}) - {status}")

# Test
lib = Library()
lib.add_book("Harry Potter", "J.K. Rowling", 1997)
lib.add_book("Python Programming", "John Doe", 2020)
lib.list_books()
lib.borrow_book(1)
lib.list_books()''',
            "description": "Xây dựng hệ thống quản lý thư viện đơn giản",
            "difficulty": "advanced",
            "tags": ["lop11", "bai-tap", "project"]
        },
        
        # ==================== LỚP 12 - LẬP TRÌNH HƯỚNG ĐỐI TƯỢNG ====================
        {
            "topic_id": "python-lop12-oop",
            "title": "Class cơ bản - Student",
            "code": '''# Tạo class đơn giản
class Student:
    # Class variable (biến lớp)
    school = "THPT ABC"
    
    def __init__(self, name, age, student_id):
        # Instance variables (biến đối tượng)
        self.name = name
        self.age = age
        self.student_id = student_id
        self.scores = []
    
    def add_score(self, score):
        """Thêm điểm"""
        self.scores.append(score)
    
    def get_average(self):
        """Tính điểm trung bình"""
        if not self.scores:
            return 0
        return sum(self.scores) / len(self.scores)
    
    def __str__(self):
        """String representation"""
        return f"Student({self.name}, ID: {self.student_id})"

# Sử dụng class
student1 = Student("Nguyễn Văn A", 17, "HS001")
student1.add_score(8)
student1.add_score(9)
student1.add_score(7.5)

print(student1)
print(f"Điểm trung bình: {student1.get_average():.2f}")
print(f"Trường: {Student.school}")''',
            "description": "Tạo và sử dụng class cơ bản trong Python",
            "difficulty": "intermediate",
            "tags": ["lop12", "oop", "class"]
        },
        {
            "topic_id": "python-lop12-oop",
            "title": "Inheritance - Kế thừa",
            "code": '''# Lớp cha (Parent class)
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
    
    def introduce(self):
        return f"Tôi là {self.name}, {self.age} tuổi"

# Lớp con (Child class) kế thừa từ Person
class Student(Person):
    def __init__(self, name, age, student_id):
        super().__init__(name, age)  # Gọi __init__ của lớp cha
        self.student_id = student_id
        self.scores = []
    
    def introduce(self):
        # Override method của lớp cha
        return f"{super().introduce()}, MSSV: {self.student_id}"
    
    def add_score(self, score):
        self.scores.append(score)

class Teacher(Person):
    def __init__(self, name, age, subject):
        super().__init__(name, age)
        self.subject = subject
    
    def introduce(self):
        return f"{super().introduce()}, dạy {self.subject}"

# Sử dụng
student = Student("An", 17, "HS001")
teacher = Teacher("Bình", 35, "Toán")

print(student.introduce())
print(teacher.introduce())''',
            "description": "Kế thừa class và override methods",
            "difficulty": "intermediate",
            "tags": ["lop12", "oop", "inheritance"]
        },
        {
            "topic_id": "python-lop12-oop",
            "title": "Encapsulation - Đóng gói",
            "code": '''# Encapsulation - che giấu dữ liệu
class BankAccount:
    def __init__(self, account_number, owner, balance=0):
        self.account_number = account_number
        self.owner = owner
        self.__balance = balance  # Private attribute (__)
    
    def deposit(self, amount):
        """Nạp tiền"""
        if amount > 0:
            self.__balance += amount
            print(f"Đã nạp {amount:,.0f}đ")
        else:
            print("Số tiền không hợp lệ")
    
    def withdraw(self, amount):
        """Rút tiền"""
        if amount > 0 and amount <= self.__balance:
            self.__balance -= amount
            print(f"Đã rút {amount:,.0f}đ")
        else:
            print("Số tiền không hợp lệ hoặc không đủ số dư")
    
    def get_balance(self):
        """Xem số dư"""
        return self.__balance
    
    def __str__(self):
        return f"TK {self.account_number} - {self.owner}: {self.__balance:,.0f}đ"

# Sử dụng
account = BankAccount("001", "Nguyễn Văn A", 1000000)
print(account)
account.deposit(500000)
account.withdraw(200000)
print(f"Số dư: {account.get_balance():,.0f}đ")

# Không thể truy cập trực tiếp __balance
# print(account.__balance)  # AttributeError''',
            "description": "Đóng gói dữ liệu với private attributes",
            "difficulty": "intermediate",
            "tags": ["lop12", "oop", "encapsulation"]
        },
        {
            "topic_id": "python-lop12-oop",
            "title": "Properties và Getters/Setters",
            "code": '''# Properties - cách Pythonic để dùng getter/setter
class Circle:
    def __init__(self, radius):
        self._radius = radius
    
    @property
    def radius(self):
        """Getter cho radius"""
        return self._radius
    
    @radius.setter
    def radius(self, value):
        """Setter cho radius với validation"""
        if value > 0:
            self._radius = value
        else:
            raise ValueError("Bán kính phải > 0")
    
    @property
    def diameter(self):
        """Property chỉ đọc"""
        return self._radius * 2
    
    @property
    def area(self):
        """Diện tích"""
        import math
        return math.pi * self._radius ** 2
    
    @property
    def circumference(self):
        """Chu vi"""
        import math
        return 2 * math.pi * self._radius

# Sử dụng
circle = Circle(5)
print(f"Bán kính: {circle.radius}")
print(f"Đường kính: {circle.diameter}")
print(f"Diện tích: {circle.area:.2f}")
print(f"Chu vi: {circle.circumference:.2f}")

# Thay đổi bán kính
circle.radius = 10
print(f"\\nSau khi đổi bán kính:")
print(f"Diện tích: {circle.area:.2f}")''',
            "description": "Sử dụng @property decorator cho getters và setters",
            "difficulty": "advanced",
            "tags": ["lop12", "oop", "property"]
        },
        {
            "topic_id": "python-lop12-oop",
            "title": "Static Methods và Class Methods",
            "code": '''# Static methods và Class methods
class MathOperations:
    pi = 3.14159
    
    def __init__(self, name):
        self.name = name
    
    @staticmethod
    def add(a, b):
        """Static method - không cần self hay cls"""
        return a + b
    
    @staticmethod
    def multiply(a, b):
        return a * b
    
    @classmethod
    def create_default(cls):
        """Class method - nhận cls thay vì self"""
        return cls("Default Calculator")
    
    @classmethod
    def get_pi(cls):
        return cls.pi
    
    def instance_method(self):
        """Instance method - cần self"""
        return f"Calculator: {self.name}"

# Sử dụng static method (không cần tạo instance)
print(f"2 + 3 = {MathOperations.add(2, 3)}")
print(f"4 * 5 = {MathOperations.multiply(4, 5)}")

# Sử dụng class method
calc = MathOperations.create_default()
print(calc.instance_method())
print(f"Pi = {MathOperations.get_pi()}")

# Cũng có thể gọi từ instance
calc2 = MathOperations("My Calculator")
print(f"2 + 3 = {calc2.add(2, 3)}")''',
            "description": "Phân biệt static methods, class methods và instance methods",
            "difficulty": "advanced",
            "tags": ["lop12", "oop", "static", "classmethod"]
        },
        
        # ==================== LỚP 12 - CẤU TRÚC DỮ LIỆU ====================
        {
            "topic_id": "python-lop12-du-lieu",
            "title": "Stack - Ngăn xếp",
            "code": '''# Stack - LIFO (Last In First Out)
class Stack:
    def __init__(self):
        self.items = []
    
    def is_empty(self):
        return len(self.items) == 0
    
    def push(self, item):
        """Thêm phần tử vào đỉnh stack"""
        self.items.append(item)
    
    def pop(self):
        """Lấy và xóa phần tử ở đỉnh"""
        if not self.is_empty():
            return self.items.pop()
        return None
    
    def peek(self):
        """Xem phần tử đỉnh không xóa"""
        if not self.is_empty():
            return self.items[-1]
        return None
    
    def size(self):
        return len(self.items)
    
    def __str__(self):
        return f"Stack: {self.items}"

# Ví dụ: Kiểm tra dấu ngoặc cân bằng
def check_parentheses(expression):
    stack = Stack()
    pairs = {'(': ')', '[': ']', '{': '}'}
    
    for char in expression:
        if char in pairs.keys():
            stack.push(char)
        elif char in pairs.values():
            if stack.is_empty():
                return False
            if pairs[stack.pop()] != char:
                return False
    
    return stack.is_empty()

# Test
print(check_parentheses("(a + b) * [c - d]"))  # True
print(check_parentheses("(a + b] * (c - d)"))  # False''',
            "description": "Cài đặt Stack và ứng dụng kiểm tra ngoặc",
            "difficulty": "intermediate",
            "tags": ["lop12", "data-structure", "stack"]
        },
        {
            "topic_id": "python-lop12-du-lieu",
            "title": "Queue - Hàng đợi",
            "code": '''# Queue - FIFO (First In First Out)
class Queue:
    def __init__(self):
        self.items = []
    
    def is_empty(self):
        return len(self.items) == 0
    
    def enqueue(self, item):
        """Thêm phần tử vào cuối hàng"""
        self.items.append(item)
    
    def dequeue(self):
        """Lấy và xóa phần tử đầu hàng"""
        if not self.is_empty():
            return self.items.pop(0)
        return None
    
    def front(self):
        """Xem phần tử đầu hàng"""
        if not self.is_empty():
            return self.items[0]
        return None
    
    def size(self):
        return len(self.items)
    
    def __str__(self):
        return f"Queue: {self.items}"

# Ví dụ: Mô phỏng hàng đợi bệnh nhân
waiting_room = Queue()

print("Bệnh nhân đến:")
waiting_room.enqueue("An")
waiting_room.enqueue("Bình")
waiting_room.enqueue("Chi")
print(waiting_room)

print("\\nGọi khám:")
print(f"Bệnh nhân: {waiting_room.dequeue()}")
print(f"Bệnh nhân: {waiting_room.dequeue()}")
print(f"Còn lại: {waiting_room}")''',
            "description": "Cài đặt Queue và ứng dụng mô phỏng hàng đợi",
            "difficulty": "intermediate",
            "tags": ["lop12", "data-structure", "queue"]
        },
        {
            "topic_id": "python-lop12-du-lieu",
            "title": "Linked List - Danh sách liên kết",
            "code": '''# Linked List - Danh sách liên kết đơn
class Node:
    def __init__(self, data):
        self.data = data
        self.next = None

class LinkedList:
    def __init__(self):
        self.head = None
    
    def append(self, data):
        """Thêm vào cuối"""
        new_node = Node(data)
        if not self.head:
            self.head = new_node
            return
        
        current = self.head
        while current.next:
            current = current.next
        current.next = new_node
    
    def prepend(self, data):
        """Thêm vào đầu"""
        new_node = Node(data)
        new_node.next = self.head
        self.head = new_node
    
    def delete(self, data):
        """Xóa node có giá trị data"""
        if not self.head:
            return
        
        if self.head.data == data:
            self.head = self.head.next
            return
        
        current = self.head
        while current.next:
            if current.next.data == data:
                current.next = current.next.next
                return
            current = current.next
    
    def print_list(self):
        """In danh sách"""
        current = self.head
        while current:
            print(current.data, end=" -> ")
            current = current.next
        print("None")

# Test
llist = LinkedList()
llist.append(1)
llist.append(2)
llist.append(3)
llist.prepend(0)
llist.print_list()
llist.delete(2)
llist.print_list()''',
            "description": "Cài đặt Linked List từ đầu",
            "difficulty": "advanced",
            "tags": ["lop12", "data-structure", "linked-list"]
        },
        
        # ==================== LỚP 12 - THƯ VIỆN PYTHON ====================
        {
            "topic_id": "python-lop12-thu-vien",
            "title": "Datetime - Xử lý ngày tháng",
            "code": '''from datetime import datetime, date, timedelta

# Lấy thời gian hiện tại
now = datetime.now()
print(f"Bây giờ: {now}")
print(f"Ngày: {now.date()}")
print(f"Giờ: {now.time()}")

# Tạo datetime cụ thể
birthday = datetime(2007, 5, 15, 10, 30)
print(f"\\nNgày sinh: {birthday}")

# Định dạng datetime
print(f"Định dạng 1: {now.strftime('%d/%m/%Y %H:%M:%S')}")
print(f"Định dạng 2: {now.strftime('%A, %d %B %Y')}")

# Tính toán với timedelta
tomorrow = now + timedelta(days=1)
next_week = now + timedelta(weeks=1)
print(f"\\nNgày mai: {tomorrow.date()}")
print(f"Tuần sau: {next_week.date()}")

# Tính số ngày đã sống
age_in_days = (now - birthday).days
print(f"\\nSố ngày đã sống: {age_in_days}")

# Parse string thành datetime
date_str = "2024-12-25"
christmas = datetime.strptime(date_str, '%Y-%m-%d')
print(f"Giáng sinh: {christmas}")''',
            "description": "Làm việc với ngày tháng thời gian trong Python",
            "difficulty": "intermediate",
            "tags": ["lop12", "library", "datetime"]
        },
        {
            "topic_id": "python-lop12-thu-vien",
            "title": "Random - Số ngẫu nhiên",
            "code": '''import random

# Số ngẫu nhiên trong khoảng
print("Số ngẫu nhiên:")
print(f"Từ 1-100: {random.randint(1, 100)}")
print(f"Float từ 0-1: {random.random():.4f}")
print(f"Float từ 10-20: {random.uniform(10, 20):.2f}")

# Chọn ngẫu nhiên từ list
fruits = ["táo", "chuối", "cam", "nho", "dưa"]
print(f"\\nTrái cây ngẫu nhiên: {random.choice(fruits)}")

# Chọn nhiều phần tử
print(f"3 trái cây: {random.sample(fruits, 3)}")

# Xáo trộn list
numbers = [1, 2, 3, 4, 5]
random.shuffle(numbers)
print(f"\\nSố sau khi xáo: {numbers}")

# Ví dụ: Tung xúc xắc
def roll_dice():
    return random.randint(1, 6)

print(f"\\nTung xúc xắc: {roll_dice()}")

# Ví dụ: Rút thăm may mắn
def lottery(participants, winners=3):
    return random.sample(participants, winners)

students = ["An", "Bình", "Chi", "Dũng", "Em", "Giang"]
print(f"\\nNgười trúng thưởng: {lottery(students)}")''',
            "description": "Tạo số và lựa chọn ngẫu nhiên",
            "difficulty": "beginner",
            "tags": ["lop12", "library", "random"]
        },
        {
            "topic_id": "python-lop12-thu-vien",
            "title": "Math - Toán học",
            "code": '''import math

# Hằng số toán học
print(f"Pi: {math.pi}")
print(f"e: {math.e}")

# Hàm làm tròn
x = 3.7
print(f"\\nCeil {x}: {math.ceil(x)}")  # Làm tròn lên
print(f"Floor {x}: {math.floor(x)}")  # Làm tròn xuống
print(f"Trunc {x}: {math.trunc(x)}")  # Bỏ phần thập phân

# Lũy thừa và căn
print(f"\\n2^8 = {math.pow(2, 8)}")
print(f"√16 = {math.sqrt(16)}")
print(f"∛27 = {27 ** (1/3):.2f}")

# Logarit
print(f"\\nlog₁₀(100) = {math.log10(100)}")
print(f"ln(e) = {math.log(math.e)}")
print(f"log₂(8) = {math.log2(8)}")

# Lượng giác (radian)
angle_deg = 45
angle_rad = math.radians(angle_deg)
print(f"\\nsin(45°) = {math.sin(angle_rad):.4f}")
print(f"cos(45°) = {math.cos(angle_rad):.4f}")
print(f"tan(45°) = {math.tan(angle_rad):.4f}")

# Giá trị tuyệt đối và dấu
print(f"\\n|−5| = {abs(-5)}")
print(f"max(3,7,2,9,1) = {max(3, 7, 2, 9, 1)}")
print(f"min(3,7,2,9,1) = {min(3, 7, 2, 9, 1)}")''',
            "description": "Sử dụng module math cho các phép toán",
            "difficulty": "beginner",
            "tags": ["lop12", "library", "math"]
        },
        {
            "topic_id": "python-lop12-thu-vien",
            "title": "Collections - Counter và defaultdict",
            "code": '''from collections import Counter, defaultdict

# Counter - đếm phần tử
text = "hello world hello python"
words = text.split()
word_count = Counter(words)
print(f"Đếm từ: {word_count}")
print(f"'hello' xuất hiện: {word_count['hello']} lần")
print(f"Top 2 từ: {word_count.most_common(2)}")

# Đếm ký tự
char_count = Counter("mississippi")
print(f"\\nĐếm ký tự: {char_count}")

# defaultdict - dict với giá trị mặc định
# Nhóm học sinh theo lớp
students_by_class = defaultdict(list)
students_by_class["11A"].append("An")
students_by_class["11A"].append("Bình")
students_by_class["11B"].append("Chi")
students_by_class["11B"].append("Dũng")

print(f"\\nHọc sinh theo lớp:")
for class_name, students in students_by_class.items():
    print(f"{class_name}: {students}")

# Đếm điểm số
scores = defaultdict(int)
test_results = [("An", 8), ("Bình", 7), ("An", 9), ("Chi", 8)]
for name, score in test_results:
    scores[name] += score

print(f"\\nTổng điểm: {dict(scores)}")''',
            "description": "Sử dụng Counter và defaultdict từ collections",
            "difficulty": "intermediate",
            "tags": ["lop12", "library", "collections"]
        },
        
        # ==================== LỚP 12 - DỰ ÁN TỔNG HỢP ====================
        {
            "topic_id": "python-lop12-du-an",
            "title": "Ứng dụng To-Do List",
            "code": '''# Ứng dụng quản lý công việc (To-Do List)
import json
from datetime import datetime

class TodoList:
    def __init__(self, filename="todos.json"):
        self.filename = filename
        self.todos = self.load_todos()
    
    def load_todos(self):
        """Đọc danh sách từ file"""
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
    
    def save_todos(self):
        """Lưu danh sách vào file"""
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.todos, f, ensure_ascii=False, indent=2)
    
    def add_todo(self, task, priority="normal"):
        """Thêm công việc mới"""
        todo = {
            'id': len(self.todos) + 1,
            'task': task,
            'priority': priority,
            'completed': False,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.todos.append(todo)
        self.save_todos()
        print(f"✓ Đã thêm: {task}")
    
    def complete_todo(self, todo_id):
        """Đánh dấu hoàn thành"""
        for todo in self.todos:
            if todo['id'] == todo_id:
                todo['completed'] = True
                self.save_todos()
                print(f"✓ Hoàn thành: {todo['task']}")
                return
        print("Không tìm thấy công việc")
    
    def delete_todo(self, todo_id):
        """Xóa công việc"""
        self.todos = [t for t in self.todos if t['id'] != todo_id]
        self.save_todos()
        print("✓ Đã xóa")
    
    def list_todos(self, show_completed=True):
        """Hiển thị danh sách"""
        print("\\n" + "="*50)
        print("DANH SÁCH CÔNG VIỆC")
        print("="*50)
        
        for todo in self.todos:
            if not show_completed and todo['completed']:
                continue
            
            status = "✓" if todo['completed'] else "○"
            priority_mark = "!" if todo['priority'] == "high" else ""
            print(f"[{todo['id']}] {status} {todo['task']} {priority_mark}")
        
        print("="*50)

# Sử dụng
app = TodoList()
app.add_todo("Học Python", "high")
app.add_todo("Làm bài tập")
app.list_todos()
app.complete_todo(1)
app.list_todos()''',
            "description": "Ứng dụng quản lý công việc với lưu file JSON",
            "difficulty": "advanced",
            "tags": ["lop12", "project", "todo"]
        },
        {
            "topic_id": "python-lop12-du-an",
            "title": "Web Scraper đơn giản",
            "code": '''# Web Scraper cơ bản (cần cài requests và beautifulsoup4)
# pip install requests beautifulsoup4

import requests
from bs4 import BeautifulSoup

def scrape_website(url):
    """Lấy nội dung từ website"""
    try:
        # Gửi request
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Lấy tiêu đề
        title = soup.find('title')
        print(f"Tiêu đề: {title.text if title else 'N/A'}")
        
        # Lấy tất cả links
        links = soup.find_all('a', href=True)
        print(f"\\nSố lượng links: {len(links)}")
        print("\\n5 links đầu tiên:")
        for link in links[:5]:
            print(f"- {link['href']}")
        
        # Lấy tất cả headings
        headings = soup.find_all(['h1', 'h2', 'h3'])
        print(f"\\nCác headings:")
        for h in headings[:5]:
            print(f"{h.name}: {h.text.strip()}")
        
        return soup
        
    except requests.exceptions.RequestException as e:
        print(f"Lỗi: {e}")
        return None

# Ví dụ sử dụng
if __name__ == "__main__":
    url = "https://www.python.org"
    print(f"Scraping: {url}\\n")
    scrape_website(url)''',
            "description": "Web scraper cơ bản để lấy dữ liệu từ website",
            "difficulty": "advanced",
            "tags": ["lop12", "project", "webscraping"]
        },
        {
            "topic_id": "python-lop12-du-an",
            "title": "API Client - Thời tiết",
            "code": '''# API Client lấy thông tin thời tiết
import requests
import json

class WeatherClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5/weather"
    
    def get_weather(self, city):
        """Lấy thông tin thời tiết của thành phố"""
        params = {
            'q': city,
            'appid': self.api_key,
            'units': 'metric',  # Celsius
            'lang': 'vi'
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                'city': data['name'],
                'temperature': data['main']['temp'],
                'feels_like': data['main']['feels_like'],
                'humidity': data['main']['humidity'],
                'description': data['weather'][0]['description'],
                'wind_speed': data['wind']['speed']
            }
        
        except requests.exceptions.RequestException as e:
            print(f"Lỗi API: {e}")
            return None
    
    def display_weather(self, city):
        """Hiển thị thông tin thời tiết"""
        weather = self.get_weather(city)
        if weather:
            print(f"\\n{'='*40}")
            print(f"THỜI TIẾT TẠI {weather['city'].upper()}")
            print(f"{'='*40}")
            print(f"Nhiệt độ: {weather['temperature']}°C")
            print(f"Cảm giác như: {weather['feels_like']}°C")
            print(f"Độ ẩm: {weather['humidity']}%")
            print(f"Tốc độ gió: {weather['wind_speed']} m/s")
            print(f"Mô tả: {weather['description']}")
            print(f"{'='*40}\\n")

# Sử dụng (cần API key từ openweathermap.org)
# client = WeatherClient("YOUR_API_KEY")
# client.display_weather("Hanoi")
# client.display_weather("Ho Chi Minh")

print("Cần đăng ký API key tại: https://openweathermap.org/api")''',
            "description": "Client API lấy thông tin thời tiết từ OpenWeatherMap",
            "difficulty": "advanced",
            "tags": ["lop12", "project", "api"]
        },
    ]
    
    # Insert templates
    for template_data in templates:
        topic_id = template_data["topic_id"]
        title = template_data["title"]
        
        # Check if template already exists
        existing = db.code_templates.find_one({
            "topic_id": topic_id,
            "title": title
        })
        
        if existing:
            print(f"⏭️  Skipped (exists): {title}")
            stats["skipped"] += 1
            continue
        
        # Create template
        try:
            import uuid
            now = datetime.utcnow()
            
            template = {
                "id": str(uuid.uuid4()),
                "topic_id": topic_id,
                "category_id": "python",
                "title": title,
                "programming_language": "python",
                "code": template_data["code"],
                "description": template_data["description"],
                "difficulty": template_data["difficulty"],
                "tags": template_data["tags"],
                "source_type": "wordai_team",
                "created_by": WORDAI_TEAM_UID,
                "author_name": "WordAI Team",
                "metadata": {
                    "author": "WordAI",
                    "version": "1.0",
                    "usage_count": 0,
                    "view_count": 0,
                    "dependencies": []
                },
                "like_count": 0,
                "is_published": True,
                "is_featured": False,
                "created_at": now,
                "updated_at": now,
            }
            
            if not DRY_RUN:
                db.code_templates.insert_one(template)
            
            print(f"✅ Created: {title}")
            stats["created"] += 1
            stats["total_templates"] += 1
            
        except Exception as e:
            print(f"❌ Error creating {title}: {str(e)}")
            stats["errors"] += 1
    
    # Print summary
    print("\n" + "=" * 80)
    print("SEEDING SUMMARY")
    print("=" * 80)
    print(f"Total templates: {stats['total_templates']}")
    print(f"Created: {stats['created']}")
    print(f"Skipped (exists): {stats['skipped']}")
    print(f"Errors: {stats['errors']}")
    print("=" * 80)
    
    if DRY_RUN:
        print("\n⚠️  DRY RUN COMPLETE - No changes were made")
        print("Set DRY_RUN = False to execute seeding")
    else:
        print("\n✅ SEEDING COMPLETE")


if __name__ == "__main__":
    try:
        create_templates()
    except KeyboardInterrupt:
        print("\n\n⚠️  Seeding interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Seeding failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
