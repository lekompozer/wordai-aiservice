"""
Các hàm tiện ích xử lý văn bản
"""


def number_to_words_vietnamese(n: int) -> str:
    """
    Chuyển đổi số nguyên thành chữ tiếng Việt.
    Ví dụ: 55000000 -> "năm mươi lăm triệu"
    """
    if n == 0:
        return "không"

    units = ["", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
    teens = [
        "mười",
        "mười một",
        "mười hai",
        "mười ba",
        "mười bốn",
        "mười lăm",
        "mười sáu",
        "mười bảy",
        "mười tám",
        "mười chín",
    ]
    tens = [
        "",
        "mười",
        "hai mươi",
        "ba mươi",
        "bốn mươi",
        "năm mươi",
        "sáu mươi",
        "bảy mươi",
        "tám mươi",
        "chín mươi",
    ]
    thousands = ["", "nghìn", "triệu", "tỷ"]

    def convert_group_of_three(num):
        """Chuyển đổi nhóm 3 chữ số"""
        if num == 0:
            return ""

        result = []

        # Hàng trăm
        hundreds = num // 100
        if hundreds > 0:
            result.append(units[hundreds] + " trăm")

        # Hàng chục và đơn vị
        remainder = num % 100
        if remainder == 0:
            pass  # Không thêm gì
        elif remainder < 10:
            if hundreds > 0:
                result.append("linh " + units[remainder])
            else:
                result.append(units[remainder])
        elif remainder < 20:
            if remainder == 10:
                result.append("mười")
            elif remainder == 15:
                result.append("mười lăm")
            else:
                result.append(teens[remainder - 10])
        else:
            tens_digit = remainder // 10
            units_digit = remainder % 10

            tens_word = tens[tens_digit]

            if units_digit == 0:
                result.append(tens_word)
            elif units_digit == 1:
                result.append(tens_word + " mốt")
            elif units_digit == 5 and tens_digit > 1:
                result.append(tens_word + " lăm")
            else:
                result.append(tens_word + " " + units[units_digit])

        return " ".join(result)

    if n < 0:
        return "âm " + number_to_words_vietnamese(abs(n))

    # Chia số thành các nhóm 3 chữ số
    groups = []
    group_index = 0

    while n > 0:
        group = n % 1000
        if group != 0:
            group_text = convert_group_of_three(group)
            if group_index > 0:
                group_text += " " + thousands[group_index]
            groups.append(group_text)
        n //= 1000
        group_index += 1

    # Ghép các nhóm lại (đảo ngược vì ta đã tách từ cuối)
    result = " ".join(reversed(groups))

    # Làm sạch khoảng trắng thừa
    return " ".join(result.split())


def number_to_words(amount: float, currency: str = "đồng") -> str:
    """
    Chuyển đổi số tiền thành chữ tiếng Việt
    """
    if amount == 0:
        return f"Không {currency}"

    integer_part = int(amount)
    decimal_part = round((amount - integer_part) * 100)

    result = number_to_words_vietnamese(integer_part)

    if decimal_part > 0:
        result += f" {currency} {number_to_words_vietnamese(decimal_part)} xu"
    else:
        result += f" {currency}"

    # Viết hoa chữ cái đầu
    return result.capitalize()
