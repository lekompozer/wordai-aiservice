"""
Brevo Email Service
Handles email sending through Brevo REST API (more reliable than SMTP)
"""

import logging
import os
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class BrevoEmailService:
    """
    Service for sending emails via Brevo REST API
    More reliable than SMTP - no IP whitelist required
    """

    def __init__(self):
        """Initialize Brevo email service with credentials from environment"""
        self.api_key = os.getenv("BREVO_API_KEY", "")
        self.sender_email = os.getenv("BREVO_SENDER_EMAIL", "noreply@wordai.pro")
        self.sender_name = os.getenv("BREVO_SENDER_NAME", "WordAI Notification")
        self.api_url = "https://api.brevo.com/v3/smtp/email"

        if not self.api_key:
            logger.warning(
                "⚠️ Brevo API key not configured. Email sending will be disabled."
            )
        else:
            logger.info("✅ Brevo email service initialized (REST API)")

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        """
        Send email via Brevo REST API

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text email body (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if not self.api_key:
                logger.warning(f"⚠️ Brevo not configured. Skipping email to {to_email}")
                return False

            # Prepare email data
            data = {
                "sender": {"name": self.sender_name, "email": self.sender_email},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": html_body,
            }

            # Add text version if provided
            if text_body:
                data["textContent"] = text_body

            # Send via REST API
            response = requests.post(
                self.api_url,
                headers={
                    "accept": "application/json",
                    "api-key": self.api_key,
                    "content-type": "application/json",
                },
                json=data,
                timeout=10,
            )

            if response.status_code == 201:
                result = response.json()
                message_id = result.get("messageId", "unknown")
                logger.info(
                    f"✅ Email sent successfully to {to_email} (ID: {message_id})"
                )
                return True
            else:
                logger.error(
                    f"❌ Failed to send email to {to_email}: {response.status_code}"
                )
                logger.error(f"   Response: {response.text}")
                return False

        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout sending email to {to_email}")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {e}")
            return False

    def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        """
        Send welcome email when user registers

        Args:
            to_email: User's email address
            user_name: User's display name

        Returns:
            True if email sent successfully
        """
        subject = "Chào mừng bạn đến với WordAI! 🎉"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                           color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #667eea;
                          color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Chào mừng đến với WordAI!</h1>
                </div>
                <div class="content">
                    <p>Xin chào <strong>{user_name}</strong>,</p>

                    <p>Chúc mừng bạn đã đăng ký tài khoản thành công trên <strong>WordAI</strong>!</p>

                    <p>WordAI là nền tảng AI thông minh giúp bạn:</p>
                    <ul>
                        <li>📝 Soạn thảo và chỉnh sửa tài liệu với AI</li>
                        <li>💬 Chat với tài liệu của bạn</li>
                        <li>�� Chia sẻ files với đồng nghiệp</li>
                        <li>📚 Quản lý thư viện tài liệu</li>
                    </ul>

                    <p style="text-align: center;">
                        <a href="https://wordai.pro" class="button">Bắt đầu sử dụng ngay</a>
                    </p>

                    <p>Nếu bạn có bất kỳ câu hỏi nào, đừng ngại liên hệ với chúng tôi.</p>

                    <p>Trân trọng,<br><strong>Đội ngũ WordAI</strong></p>
                </div>
                <div class="footer">
                    <p>Email này được gửi từ WordAI - Nền tảng AI thông minh</p>
                    <p>© 2025 WordAI. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        Chào mừng bạn đến với WordAI!

        Xin chào {user_name},

        Chúc mừng bạn đã đăng ký tài khoản thành công trên WordAI!

        WordAI là nền tảng AI thông minh giúp bạn:
        - Soạn thảo và chỉnh sửa tài liệu với AI
        - Chat với tài liệu của bạn
        - Chia sẻ files với đồng nghiệp
        - Quản lý thư viện tài liệu

        Truy cập: https://wordai.pro

        Trân trọng,
        Đội ngũ WordAI
        """

        return self.send_email(to_email, subject, html_body, text_body)

    def send_file_share_notification(
        self,
        to_email: str,
        recipient_name: str,
        owner_name: str,
        filename: str,
        permission: str,
        share_url: str = "https://wordai.pro/shared",
    ) -> bool:
        """
        Send notification when file is shared

        Args:
            to_email: Recipient's email
            recipient_name: Recipient's name
            owner_name: File owner's name
            filename: Name of shared file
            permission: Permission level (view/download/edit)
            share_url: URL to access shared file

        Returns:
            True if email sent successfully
        """
        # Permission labels
        permission_labels = {
            "view": "Xem",
            "download": "Tải xuống",
            "edit": "Chỉnh sửa",
        }
        permission_text = permission_labels.get(permission, permission)

        subject = f"{owner_name} đã chia sẻ file với bạn - {filename}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                           color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .file-info {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0;
                             border-left: 4px solid #667eea; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #667eea;
                          color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .permission {{ display: inline-block; padding: 6px 12px; background: #e3f2fd;
                              color: #1976d2; border-radius: 4px; font-weight: bold; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📄 File được chia sẻ</h1>
                </div>
                <div class="content">
                    <p>Xin chào <strong>{recipient_name}</strong>,</p>

                    <p><strong>{owner_name}</strong> đã chia sẻ một file với bạn trên WordAI.</p>

                    <div class="file-info">
                        <p><strong>�� Tên file:</strong> {filename}</p>
                        <p><strong>🔐 Quyền truy cập:</strong> <span class="permission">{permission_text}</span></p>
                        <p><strong>👤 Người chia sẻ:</strong> {owner_name}</p>
                    </div>

                    <p style="text-align: center;">
                        <a href="{share_url}" class="button">Xem file ngay</a>
                    </p>

                    <p><strong>Quyền của bạn:</strong></p>
                    <ul>
                        <li>{'✅' if permission in ['view', 'download', 'edit'] else '❌'} Xem nội dung file</li>
                        <li>{'✅' if permission in ['download', 'edit'] else '❌'} Tải xuống file</li>
                        <li>{'✅' if permission == 'edit' else '❌'} Chỉnh sửa file</li>
                    </ul>

                    <p>File này đã được chia sẻ an toàn qua hệ thống WordAI.</p>

                    <p>Trân trọng,<br><strong>Đội ngũ WordAI</strong></p>
                </div>
                <div class="footer">
                    <p>Email này được gửi từ WordAI - Nền tảng AI thông minh</p>
                    <p>© 2025 WordAI. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        File được chia sẻ - WordAI

        Xin chào {recipient_name},

        {owner_name} đã chia sẻ một file với bạn trên WordAI.

        Tên file: {filename}
        Quyền truy cập: {permission_text}
        Người chia sẻ: {owner_name}

        Truy cập file tại: {share_url}

        Quyền của bạn:
        - {'✓' if permission in ['view', 'download', 'edit'] else '✗'} Xem nội dung file
        - {'✓' if permission in ['download', 'edit'] else '✗'} Tải xuống file
        - {'✓' if permission == 'edit' else '✗'} Chỉnh sửa file

        Trân trọng,
        Đội ngũ WordAI
        """

        return self.send_email(to_email, subject, html_body, text_body)


# Singleton instance
_brevo_service: Optional[BrevoEmailService] = None


def get_brevo_service() -> BrevoEmailService:
    """Get singleton Brevo email service instance"""
    global _brevo_service
    if _brevo_service is None:
        _brevo_service = BrevoEmailService()
    return _brevo_service
