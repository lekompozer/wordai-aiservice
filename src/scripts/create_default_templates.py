"""
Script to create default document templates
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.append(str(project_root))

from datetime import datetime
from src.config.database import get_database
from src.models.document_generation_models import DocumentTemplate


def create_default_templates():
    """Create default templates for document generation"""
    db = get_database()

    # Quote template
    quote_template = DocumentTemplate(
        type="quote",
        subtype="standard",
        name="Mẫu báo giá chuẩn",
        description="Template báo giá chuẩn cho các sản phẩm/dịch vụ",
        template_content="""
        <h1 style="text-align: center;">BÁO GIÁ</h1>
        <h2 style="text-align: center;">{{ quote_number }}</h2>

        <div style="margin-top: 20px;">
            <strong>Ngày:</strong> {{ quote_date }}<br>
            <strong>Hạn hiệu lực:</strong> {{ validity_period }}
        </div>

        <h3>THÔNG TIN CÔNG TY</h3>
        <div>
            <strong>Tên công ty:</strong> {{ company.name }}<br>
            <strong>Địa chỉ:</strong> {{ company.address }}<br>
            <strong>Điện thoại:</strong> {{ company.phone }}<br>
            <strong>Email:</strong> {{ company.email }}<br>
            <strong>Mã số thuế:</strong> {{ company.tax_code }}
        </div>

        <h3>THÔNG TIN KHÁCH HÀNG</h3>
        <div>
            <strong>Tên khách hàng:</strong> {{ customer.name }}<br>
            <strong>Địa chỉ:</strong> {{ customer.address }}<br>
            <strong>Người liên hệ:</strong> {{ customer.contact_person }}<br>
            <strong>Điện thoại:</strong> {{ customer.phone }}<br>
            <strong>Email:</strong> {{ customer.email }}
        </div>

        <h3>DANH SÁCH SẢN PHẨM/DỊCH VỤ</h3>
        <table border="1" style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr>
                    <th>STT</th>
                    <th>Tên sản phẩm/dịch vụ</th>
                    <th>Số lượng</th>
                    <th>Đơn vị</th>
                    <th>Đơn giá</th>
                    <th>Thành tiền</th>
                </tr>
            </thead>
            <tbody>
                {% for product in products %}
                <tr>
                    <td>{{ product.stt }}</td>
                    <td>{{ product.name }}</td>
                    <td>{{ product.quantity }}</td>
                    <td>{{ product.unit }}</td>
                    <td>{{ product.unit_price }}</td>
                    <td>{{ product.total_price }}</td>
                </tr>
                {% endfor %}
                <tr style="font-weight: bold;">
                    <td colspan="5">TỔNG CỘNG</td>
                    <td>{{ total_amount }}</td>
                </tr>
            </tbody>
        </table>

        <h3>ĐIỀU KHOẢN THANH TOÁN</h3>
        <div>
            <strong>Phương thức thanh toán:</strong> {{ payment_terms.payment_method or 'Chuyển khoản' }}<br>
            <strong>Lịch thanh toán:</strong> {{ payment_terms.payment_schedule or 'Thanh toán 100% sau khi ký hợp đồng' }}
        </div>

        <div style="margin-top: 30px;">
            <strong>Ghi chú:</strong><br>
            {{ additional_terms or 'Báo giá này có hiệu lực trong 30 ngày kể từ ngày phát hành.' }}
        </div>

        <div style="margin-top: 50px; text-align: right;">
            <strong>NGƯỜI LẬP BÁO GIÁ</strong><br><br><br>
            <strong>{{ company.representative }}</strong><br>
            {{ company.position or 'Giám đốc' }}
        </div>
        """,
        variables=[
            "quote_number",
            "quote_date",
            "validity_period",
            "company",
            "customer",
            "products",
            "total_amount",
            "payment_terms",
            "additional_terms",
        ],
    )

    # Contract template
    contract_template = DocumentTemplate(
        type="contract",
        subtype="standard",
        name="Mẫu hợp đồng chuẩn",
        description="Template hợp đồng mua bán/cung cấp dịch vụ chuẩn",
        template_content="""
        <h1 style="text-align: center;">HỢP ĐỒNG MUA BÁN/CUNG CẤP DỊCH VỤ</h1>
        <h2 style="text-align: center;">Số: {{ contract_number }}</h2>

        <div style="margin-top: 20px;">
            <strong>Ngày ký:</strong> {{ contract_date }}<br>
            <strong>Ngày hiệu lực:</strong> {{ effective_date }}<br>
            <strong>Thời hạn:</strong> {{ contract_duration }}
        </div>

        <h3>BÊN A (BÊN BÁN/CUNG CẤP DỊCH VỤ)</h3>
        <div>
            <strong>Tên công ty:</strong> {{ company.name }}<br>
            <strong>Địa chỉ:</strong> {{ company.address }}<br>
            <strong>Mã số thuế:</strong> {{ company.tax_code }}<br>
            <strong>Người đại diện:</strong> {{ company.representative }}<br>
            <strong>Chức vụ:</strong> {{ company.position or 'Giám đốc' }}<br>
            <strong>Điện thoại:</strong> {{ company.phone }}<br>
            <strong>Email:</strong> {{ company.email }}
        </div>

        <h3>BÊN B (BÊN MUA/KHÁCH HÀNG)</h3>
        <div>
            <strong>Tên:</strong> {{ customer.name }}<br>
            <strong>Địa chỉ:</strong> {{ customer.address }}<br>
            <strong>Người đại diện:</strong> {{ customer.contact_person }}<br>
            <strong>Chức vụ:</strong> {{ customer.position or 'Đại diện' }}<br>
            <strong>Điện thoại:</strong> {{ customer.phone }}<br>
            <strong>Email:</strong> {{ customer.email }}
            {% if customer.tax_code %}
            <br><strong>Mã số thuế:</strong> {{ customer.tax_code }}
            {% endif %}
        </div>

        <h3>ĐIỀU 1: ĐỐI TƯỢNG CỦA HỢP ĐỒNG</h3>
        <table border="1" style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr>
                    <th>STT</th>
                    <th>Tên sản phẩm/dịch vụ</th>
                    <th>Mô tả</th>
                    <th>Số lượng</th>
                    <th>Đơn vị</th>
                    <th>Đơn giá</th>
                    <th>Thành tiền</th>
                </tr>
            </thead>
            <tbody>
                {% for product in products %}
                <tr>
                    <td>{{ product.stt }}</td>
                    <td>{{ product.name }}</td>
                    <td>{{ product.description }}</td>
                    <td>{{ product.quantity }}</td>
                    <td>{{ product.unit }}</td>
                    <td>{{ product.unit_price }}</td>
                    <td>{{ product.total_price }}</td>
                </tr>
                {% endfor %}
                <tr style="font-weight: bold;">
                    <td colspan="6">TỔNG GIÁ TRỊ HỢP ĐỒNG</td>
                    <td>{{ total_amount }}</td>
                </tr>
            </tbody>
        </table>

        <h3>ĐIỀU 2: GIÁ TRỊ HỢP ĐỒNG VÀ PHƯƠNG THỨC THANH TOÁN</h3>
        <div>
            <strong>2.1. Tổng giá trị hợp đồng:</strong> {{ total_amount }}<br>
            <strong>2.2. Phương thức thanh toán:</strong> {{ payment_terms.payment_method }}<br>
            <strong>2.3. Lịch thanh toán:</strong> {{ payment_terms.payment_schedule }}
            {% if payment_terms.advance_payment_percent %}
            <br><strong>2.4. Tạm ứng:</strong> {{ payment_terms.advance_payment_percent }}% giá trị hợp đồng
            {% endif %}
        </div>

        <h3>ĐIỀU 3: QUYỀN VÀ NGHĨA VỤ CỦA CÁC BÊN</h3>
        <div>
            <strong>3.1. Quyền và nghĩa vụ của Bên A:</strong><br>
            - Cung cấp sản phẩm/dịch vụ đúng chất lượng, số lượng đã thỏa thuận<br>
            - Bảo hành sản phẩm theo quy định<br>
            - Nhận thanh toán đúng thời hạn<br><br>

            <strong>3.2. Quyền và nghĩa vụ của Bên B:</strong><br>
            - Thanh toán đầy đủ, đúng thời hạn<br>
            - Kiểm tra và nghiệm thu sản phẩm/dịch vụ<br>
            - Được bảo hành theo thỏa thuận
        </div>

        <h3>ĐIỀU 4: ĐIỀU KHOẢN CHUNG</h3>
        <div>
            {{ additional_terms or '- Hợp đồng có hiệu lực kể từ ngày ký và thực hiện đúng cam kết.<br>- Mọi tranh chấp phát sinh sẽ được giải quyết thông qua thương lượng, hòa giải hoặc tòa án có thẩm quyền.' }}
        </div>

        <div style="margin-top: 50px; display: flex; justify-content: space-between;">
            <div style="text-align: center;">
                <strong>ĐẠI DIỆN BÊN A</strong><br><br><br><br>
                <strong>{{ company.representative }}</strong>
            </div>
            <div style="text-align: center;">
                <strong>ĐẠI DIỆN BÊN B</strong><br><br><br><br>
                <strong>{{ customer.contact_person }}</strong>
            </div>
        </div>
        """,
        variables=[
            "contract_number",
            "contract_date",
            "effective_date",
            "contract_duration",
            "company",
            "customer",
            "products",
            "total_amount",
            "payment_terms",
            "additional_terms",
        ],
    )

    # Appendix template
    appendix_template = DocumentTemplate(
        type="appendix",
        subtype="standard",
        name="Mẫu phụ lục hợp đồng",
        description="Template phụ lục bổ sung/thay đổi hợp đồng",
        template_content="""
        <h1 style="text-align: center;">PHỤ LỤC HỢP ĐỒNG</h1>
        <h2 style="text-align: center;">Số: {{ appendix_number }}</h2>

        <div style="margin-top: 20px;">
            <strong>Ngày ký:</strong> {{ appendix_date }}<br>
            {% if parent_contract_id %}
            <strong>Phụ lục của hợp đồng số:</strong> {{ parent_contract_id }}
            {% endif %}
        </div>

        <h3>BÊN A (BÊN BÁN/CUNG CẤP DỊCH VỤ)</h3>
        <div>
            <strong>Tên công ty:</strong> {{ company.name }}<br>
            <strong>Địa chỉ:</strong> {{ company.address }}<br>
            <strong>Mã số thuế:</strong> {{ company.tax_code }}<br>
            <strong>Người đại diện:</strong> {{ company.representative }}<br>
            <strong>Điện thoại:</strong> {{ company.phone }}
        </div>

        <h3>BÊN B (BÊN MUA/KHÁCH HÀNG)</h3>
        <div>
            <strong>Tên:</strong> {{ customer.name }}<br>
            <strong>Địa chỉ:</strong> {{ customer.address }}<br>
            <strong>Người đại diện:</strong> {{ customer.contact_person }}<br>
            <strong>Điện thoại:</strong> {{ customer.phone }}
        </div>

        <h3>NỘI DUNG THAY ĐỔI/BỔ SUNG</h3>
        <div>
            <strong>Mô tả thay đổi:</strong><br>
            {{ changes_description }}
        </div>

        {% if products %}
        <h3>DANH SÁCH SẢN PHẨM/DỊCH VỤ BỔ SUNG/THAY ĐỔI</h3>
        <table border="1" style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr>
                    <th>STT</th>
                    <th>Tên sản phẩm/dịch vụ</th>
                    <th>Số lượng</th>
                    <th>Đơn vị</th>
                    <th>Đơn giá</th>
                    <th>Thành tiền</th>
                </tr>
            </thead>
            <tbody>
                {% for product in products %}
                <tr>
                    <td>{{ product.stt }}</td>
                    <td>{{ product.name }}</td>
                    <td>{{ product.quantity }}</td>
                    <td>{{ product.unit }}</td>
                    <td>{{ product.unit_price }}</td>
                    <td>{{ product.total_price }}</td>
                </tr>
                {% endfor %}
                <tr style="font-weight: bold;">
                    <td colspan="5">TỔNG GIÁ TRỊ BỔ SUNG</td>
                    <td>{{ total_amount }}</td>
                </tr>
            </tbody>
        </table>
        {% endif %}

        <h3>ĐIỀU KHOẢN</h3>
        <div>
            {{ additional_terms or '- Phụ lục này là một phần không tách rời của hợp đồng gốc.<br>- Các điều khoản khác của hợp đồng gốc vẫn giữ nguyên hiệu lực.' }}
        </div>

        <div style="margin-top: 50px; display: flex; justify-content: space-between;">
            <div style="text-align: center;">
                <strong>ĐẠI DIỆN BÊN A</strong><br><br><br><br>
                <strong>{{ company.representative }}</strong>
            </div>
            <div style="text-align: center;">
                <strong>ĐẠI DIỆN BÊN B</strong><br><br><br><br>
                <strong>{{ customer.contact_person }}</strong>
            </div>
        </div>
        """,
        variables=[
            "appendix_number",
            "appendix_date",
            "parent_contract_id",
            "company",
            "customer",
            "products",
            "total_amount",
            "changes_description",
            "additional_terms",
        ],
    )

    # Insert templates
    templates = [quote_template, contract_template, appendix_template]

    for template in templates:
        try:
            # Check if template already exists
            existing = db.user_upload_files.find_one(
                {
                    "type": template.type,
                    "subtype": template.subtype,
                    "name": template.name,
                }
            )

            if not existing:
                result = db.user_upload_files.insert_one(template.dict(by_alias=True))
                print(
                    f"✅ Created template: {template.name} - ID: {result.inserted_id}"
                )
            else:
                print(f"⚠️ Template already exists: {template.name}")

        except Exception as e:
            print(f"❌ Error creating template {template.name}: {e}")


if __name__ == "__main__":
    create_default_templates()
