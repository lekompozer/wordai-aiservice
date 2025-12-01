"""
Public API routes (no authentication required)
Used for wordai.pro homepage
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging

from src.models.contact_models import ContactRequest, ContactPurpose
from src.services.mongodb_service import get_mongodb_service
from src.services.brevo_email_service import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["Public"])


@router.post(
    "/contact",
    response_model=dict,
    summary="Submit contact form",
    description="Public endpoint for wordai.pro contact form - sends email to admin",
)
async def submit_contact_form(request: ContactRequest):
    """
    Submit contact form from wordai.pro homepage

    **Purpose:**
    - Public endpoint (no auth required)
    - Used by /contact page on wordai.pro
    - Sends email notification to admin
    - Stores contact request in database for tracking

    **Required Fields:**
    - full_name: Họ và tên (2-100 characters)
    - email: Email address (valid format)
    - purpose: Mục đích liên hệ (business_cooperation, investment, technical_support, other)
    - message: Nội dung tin nhắn (10-2000 characters)

    **Optional Fields:**
    - phone: Số điện thoại (max 20 characters)
    - company: Tên công ty/tổ chức (max 100 characters)

    **Email Notification:**
    - Sent to: tienhoi.lh@gmail.com
    - Contains: Full contact details and message
    - Subject: 📧 Liên hệ mới từ WordAI - [Purpose]
    """
    try:
        logger.info(f"📧 New contact form submission from: {request.email}")
        logger.info(f"   Name: {request.full_name}")
        logger.info(f"   Purpose: {request.purpose}")

        mongo_service = get_mongodb_service()
        contact_requests = mongo_service.db["contact_requests"]

        # Map purpose to Vietnamese
        purpose_map = {
            ContactPurpose.BUSINESS_COOPERATION: "Hợp tác kinh doanh",
            ContactPurpose.INVESTMENT: "Đầu tư",
            ContactPurpose.TECHNICAL_SUPPORT: "Hỗ trợ kỹ thuật",
            ContactPurpose.OTHER: "Khác",
        }
        purpose_vn = purpose_map.get(request.purpose, request.purpose)

        # Create contact request document
        contact_doc = {
            "full_name": request.full_name,
            "email": request.email,
            "phone": request.phone,
            "company": request.company,
            "purpose": request.purpose,
            "purpose_display": purpose_vn,
            "message": request.message,
            "status": "new",  # new, contacted, resolved
            "created_at": datetime.utcnow(),
            "source": "wordai.pro",
        }

        # Insert to database
        result = contact_requests.insert_one(contact_doc)
        contact_id = str(result.inserted_id)

        logger.info(f"✅ Contact request saved with ID: {contact_id}")

        # Prepare email to admin
        admin_email = "tienhoi.lh@gmail.com"
        subject = f"📧 Liên hệ mới từ WordAI - {purpose_vn}"

        # Build HTML email
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                           color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .section {{ background: white; padding: 20px; margin: 15px 0; border-radius: 8px;
                           box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .label {{ font-weight: bold; color: #667eea; margin-right: 10px; }}
                .value {{ color: #333; }}
                .message-box {{ background: #f0f4ff; padding: 15px; border-left: 4px solid #667eea;
                               border-radius: 4px; margin-top: 10px; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
                .badge {{ display: inline-block; padding: 5px 15px; background: #667eea;
                         color: white; border-radius: 20px; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0; font-size: 28px;">📧 Liên hệ mới từ WordAI</h1>
                    <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">
                        {datetime.utcnow().strftime("%d/%m/%Y %H:%M UTC")}
                    </p>
                </div>

                <div class="content">
                    <div class="section">
                        <h2 style="color: #667eea; margin-top: 0;">👤 Thông tin người liên hệ</h2>
                        <p><span class="label">Họ và tên:</span><span class="value">{request.full_name}</span></p>
                        <p><span class="label">Email:</span><span class="value">{request.email}</span></p>
                        <p><span class="label">Số điện thoại:</span><span class="value">{request.phone or 'Không cung cấp'}</span></p>
                        <p><span class="label">Công ty/Tổ chức:</span><span class="value">{request.company or 'Không cung cấp'}</span></p>
                    </div>

                    <div class="section">
                        <h2 style="color: #667eea; margin-top: 0;">🎯 Mục đích liên hệ</h2>
                        <p><span class="badge">{purpose_vn}</span></p>
                    </div>

                    <div class="section">
                        <h2 style="color: #667eea; margin-top: 0;">💬 Nội dung tin nhắn</h2>
                        <div class="message-box">
                            {request.message.replace(chr(10), '<br>')}
                        </div>
                    </div>

                    <div class="section">
                        <h2 style="color: #667eea; margin-top: 0;">📊 Thông tin hệ thống</h2>
                        <p><span class="label">Contact ID:</span><span class="value">{contact_id}</span></p>
                        <p><span class="label">Nguồn:</span><span class="value">wordai.pro/contact</span></p>
                        <p><span class="label">Trạng thái:</span><span class="badge" style="background: #28a745;">Mới</span></p>
                    </div>

                    <div style="text-align: center; margin-top: 30px;">
                        <a href="https://ai.wordai.pro/admin/contacts/{contact_id}"
                           style="display: inline-block; padding: 15px 40px; background: #667eea;
                                  color: white; text-decoration: none; border-radius: 8px;
                                  font-weight: bold; font-size: 16px;">
                            Xem chi tiết & Phản hồi
                        </a>
                    </div>

                    <div class="footer">
                        <p>⚠️ Vui lòng phản hồi trong vòng 24 giờ để đảm bảo trải nghiệm tốt nhất cho khách hàng.</p>
                        <p style="margin-top: 10px; font-size: 12px; color: #999;">
                            Email này được gửi tự động từ hệ thống WordAI<br>
                            © 2025 WordAI - AI-Powered Assessment Platform
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        # Send email to admin
        try:
            email_sent = send_email(
                to_email=admin_email,
                to_name="Admin WordAI",
                subject=subject,
                html_content=html_content,
            )

            if email_sent:
                logger.info(f"✅ Contact notification email sent to {admin_email}")
                # Update status to indicate email was sent
                contact_requests.update_one(
                    {"_id": result.inserted_id}, {"$set": {"email_sent": True}}
                )
            else:
                logger.warning(
                    f"⚠️ Email sending failed for contact {contact_id}, but request was saved"
                )
                contact_requests.update_one(
                    {"_id": result.inserted_id}, {"$set": {"email_sent": False}}
                )

        except Exception as email_error:
            logger.error(f"❌ Error sending contact email: {email_error}")
            # Don't fail the request if email fails
            contact_requests.update_one(
                {"_id": result.inserted_id},
                {"$set": {"email_sent": False, "email_error": str(email_error)}},
            )

        return {
            "success": True,
            "message": "Cảm ơn bạn đã liên hệ! Chúng tôi sẽ phản hồi trong vòng 24 giờ.",
            "contact_id": contact_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to process contact form: {e}")
        raise HTTPException(
            status_code=500,
            detail="Không thể gửi tin nhắn. Vui lòng thử lại sau.",
        )
