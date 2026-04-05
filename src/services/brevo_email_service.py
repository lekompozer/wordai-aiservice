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

    def send_test_invitation(
        self,
        to_email: str,
        recipient_name: str,
        sharer_name: str,
        test_title: str,
        test_id: str,
        num_questions: int,
        time_limit_minutes: Optional[int],
        deadline: Optional[str] = None,
        message: Optional[str] = None,
        test_url: str = "https://wordai.pro/tests",
    ) -> bool:
        """
        Send test invitation email

        Args:
            to_email: Recipient email
            recipient_name: Recipient's name
            sharer_name: Person who shared the test
            test_title: Test title
            test_id: Test ID for direct link
            num_questions: Number of questions
            time_limit_minutes: Time limit (optional)
            deadline: Deadline string (optional)
            message: Personal message from sharer (optional)
            test_url: Base URL for tests

        Returns:
            True if email sent successfully
        """
        subject = f"{sharer_name} đã chia sẻ bài thi với bạn: {test_title}"

        # Direct link to test
        direct_test_url = f"{test_url}/{test_id}"

        # Format time limit
        time_info = (
            f"{time_limit_minutes} phút" if time_limit_minutes else "Không giới hạn"
        )

        # Build HTML body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .test-info {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
                .test-info h3 {{ margin-top: 0; color: #667eea; }}
                .info-row {{ margin: 10px 0; }}
                .info-row strong {{ color: #555; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
                .button:hover {{ background: #5568d3; }}
                .message-box {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                .deadline-warning {{ background: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0; border-radius: 5px; color: #721c24; }}
                .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
                .success-box {{ background: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0; border-radius: 5px; color: #155724; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📝 Bài thi được chia sẻ</h1>
                </div>
                <div class="content">
                    <p>Xin chào <strong>{recipient_name}</strong>,</p>

                    <p><strong>{sharer_name}</strong> đã chia sẻ một bài thi với bạn trên WordAI.</p>

                    <div class="success-box">
                        <strong>✅ Bài thi đã sẵn sàng!</strong><br>
                        Bài thi đã được thêm vào danh sách của bạn và bạn có thể bắt đầu làm ngay.
                    </div>

                    {"<div class='message-box'><strong>💬 Lời nhắn:</strong><br>" + message + "</div>" if message else ""}

                    <div class="test-info">
                        <h3>📋 Thông tin bài thi</h3>
                        <div class="info-row"><strong>📌 Tiêu đề:</strong> {test_title}</div>
                        <div class="info-row"><strong>❓ Số câu hỏi:</strong> {num_questions}</div>
                        <div class="info-row"><strong>⏱️ Thời gian:</strong> {time_info}</div>
                        <div class="info-row"><strong>👤 Người chia sẻ:</strong> {sharer_name}</div>
                    </div>

                    {"<div class='deadline-warning'><strong>⏰ Hạn chót:</strong> " + deadline + "<br>Vui lòng hoàn thành bài thi trước thời hạn này.</div>" if deadline else ""}

                    <p style="text-align: center;">
                        <a href="{direct_test_url}" class="button">🚀 Bắt đầu làm bài ngay</a>
                    </p>

                    <p style="color: #666; font-size: 14px;">
                        <strong>Lưu ý:</strong> Bài thi đã tự động xuất hiện trong mục "Bài thi được chia sẻ" của bạn.
                        Nếu không muốn làm, bạn có thể xóa khỏi danh sách của mình.
                    </p>

                    <p>Chúc bạn làm bài tốt!<br><strong>Đội ngũ WordAI</strong></p>
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
        Bài thi được chia sẻ - WordAI

        Xin chào {recipient_name},

        {sharer_name} đã chia sẻ một bài thi với bạn trên WordAI.

        ✅ Bài thi đã sẵn sàng! Bạn có thể bắt đầu làm ngay.

        {"Lời nhắn: " + message if message else ""}

        Thông tin bài thi:
        - Tiêu đề: {test_title}
        - Số câu hỏi: {num_questions}
        - Thời gian: {time_info}
        - Người chia sẻ: {sharer_name}

        {"Hạn chót: " + deadline if deadline else ""}

        Bắt đầu làm bài tại:
        {direct_test_url}

        Lưu ý: Bạn cần chấp nhận lời mời trước khi có thể làm bài thi.

        Chúc bạn làm bài tốt!
        Đội ngũ WordAI
        """

        return self.send_email(to_email, subject, html_body, text_body)

    def send_test_deadline_reminder(
        self,
        to_email: str,
        recipient_name: str,
        test_title: str,
        deadline: str,
        hours_remaining: int,
    ) -> bool:
        """
        Send deadline reminder email (24h before deadline)

        Args:
            to_email: Recipient email
            recipient_name: Recipient's name
            test_title: Test title
            deadline: Deadline string
            hours_remaining: Hours until deadline

        Returns:
            True if email sent successfully
        """
        subject = (
            f"⏰ Nhắc nhở: Bài thi '{test_title}' sắp hết hạn ({hours_remaining}h)"
        )

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .warning-box {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 20px; margin: 20px 0; border-radius: 5px; }}
                .button {{ display: inline-block; background: #f5576c; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
                .button:hover {{ background: #e04055; }}
                .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⏰ Nhắc nhở hạn chót</h1>
                </div>
                <div class="content">
                    <p>Xin chào <strong>{recipient_name}</strong>,</p>

                    <div class="warning-box">
                        <h3 style="margin-top: 0; color: #856404;">⚠️ Bài thi sắp hết hạn!</h3>
                        <p><strong>Bài thi:</strong> {test_title}</p>
                        <p><strong>Hạn chót:</strong> {deadline}</p>
                        <p><strong>Thời gian còn lại:</strong> khoảng {hours_remaining} giờ</p>
                    </div>

                    <p>Bạn chưa hoàn thành bài thi này. Vui lòng hoàn thành trước khi hết hạn để tránh bị hết quyền truy cập.</p>

                    <p style="text-align: center;">
                        <a href="https://wordai.pro/tests" class="button">Làm bài ngay</a>
                    </p>

                    <p>Chúc bạn làm bài tốt!<br><strong>Đội ngũ WordAI</strong></p>
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
        ⏰ Nhắc nhở hạn chót - WordAI

        Xin chào {recipient_name},

        Bài thi sắp hết hạn!

        Bài thi: {test_title}
        Hạn chót: {deadline}
        Thời gian còn lại: khoảng {hours_remaining} giờ

        Bạn chưa hoàn thành bài thi này. Vui lòng hoàn thành trước khi hết hạn.

        Truy cập: https://wordai.pro/tests

        Chúc bạn làm bài tốt!
        Đội ngũ WordAI
        """

        return self.send_email(to_email, subject, html_body, text_body)

    def send_test_completion_notification(
        self,
        to_email: str,
        owner_name: str,
        user_name: str,
        test_title: str,
        score: float,
        is_passed: bool,
        time_taken_minutes: int,
    ) -> bool:
        """
        Send notification to test owner when someone completes their test

        Args:
            to_email: Test owner's email
            owner_name: Test owner's name
            user_name: Person who completed the test
            test_title: Test title
            score: Test score (0-10 scale)
            is_passed: Whether user passed
            time_taken_minutes: Time taken in minutes

        Returns:
            True if email sent successfully
        """
        status_emoji = "✅" if is_passed else "❌"
        status_text = "Đạt" if is_passed else "Chưa đạt"
        status_color = "#28a745" if is_passed else "#dc3545"

        subject = f"{status_emoji} {user_name} đã hoàn thành bài thi: {test_title}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .result-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid {status_color}; }}
                .score-badge {{ display: inline-block; background: {status_color}; color: white; padding: 10px 20px; border-radius: 20px; font-size: 24px; font-weight: bold; margin: 10px 0; }}
                .info-row {{ margin: 10px 0; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
                .button:hover {{ background: #5568d3; }}
                .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Thông báo hoàn thành bài thi</h1>
                </div>
                <div class="content">
                    <p>Xin chào <strong>{owner_name}</strong>,</p>

                    <p><strong>{user_name}</strong> đã hoàn thành bài thi của bạn!</p>

                    <div class="result-box">
                        <h3 style="margin-top: 0; color: #667eea;">📝 {test_title}</h3>

                        <div style="text-align: center;">
                            <div class="score-badge">{score:.1f}/10</div>
                            <p style="font-size: 18px; color: {status_color}; font-weight: bold;">{status_emoji} {status_text}</p>
                        </div>

                        <div class="info-row"><strong>👤 Người làm bài:</strong> {user_name}</div>
                        <div class="info-row"><strong>📊 Điểm số:</strong> {score:.1f}/10</div>
                        <div class="info-row"><strong>⏱️ Thời gian:</strong> {time_taken_minutes} phút</div>
                        <div class="info-row"><strong>📈 Kết quả:</strong> <span style="color: {status_color};">{status_text}</span></div>
                    </div>

                    <p style="text-align: center;">
                        <a href="https://wordai.pro/tests/analytics" class="button">Xem chi tiết</a>
                    </p>

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
        Thông báo hoàn thành bài thi - WordAI

        Xin chào {owner_name},

        {user_name} đã hoàn thành bài thi của bạn!

        Bài thi: {test_title}
        Người làm bài: {user_name}
        Điểm số: {score:.1f}/10
        Thời gian: {time_taken_minutes} phút
        Kết quả: {status_text}

        Xem chi tiết tại: https://wordai.pro/tests/analytics

        Trân trọng,
        Đội ngũ WordAI
        """

        return self.send_email(to_email, subject, html_body, text_body)

    def send_grading_complete_notification(
        self,
        to_email: str,
        student_name: str,
        test_title: str,
        score: float,
        is_passed: bool,
    ) -> bool:
        """
        Send notification to student when essay grading is completed

        Args:
            to_email: Student's email
            student_name: Student's name
            test_title: Test title
            score: Final score (0-10 scale)
            is_passed: Whether student passed

        Returns:
            True if email sent successfully
        """
        status_emoji = "🎉" if is_passed else "📚"
        status_text = "Đạt yêu cầu" if is_passed else "Chưa đạt yêu cầu"
        status_color = "#28a745" if is_passed else "#dc3545"
        message = "Chúc mừng bạn!" if is_passed else "Hãy tiếp tục cố gắng!"

        subject = f"{status_emoji} Bài thi '{test_title}' đã được chấm điểm!"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .result-box {{ background: white; padding: 25px; border-radius: 8px; margin: 20px 0; text-align: center; border: 2px solid {status_color}; }}
                .score-badge {{ display: inline-block; background: {status_color}; color: white; padding: 15px 30px; border-radius: 25px; font-size: 32px; font-weight: bold; margin: 15px 0; }}
                .status-message {{ color: {status_color}; font-size: 20px; font-weight: bold; margin: 10px 0; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
                .button:hover {{ background: #5568d3; }}
                .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📝 Kết quả chấm điểm</h1>
                </div>
                <div class="content">
                    <p>Xin chào <strong>{student_name}</strong>,</p>

                    <p>Bài thi <strong>"{test_title}"</strong> của bạn đã được giáo viên chấm điểm xong!</p>

                    <div class="result-box">
                        <h3 style="margin-top: 0; color: #667eea;">{status_emoji} Kết quả của bạn</h3>
                        <div class="score-badge">{score:.1f}/10</div>
                        <p class="status-message">{status_text}</p>
                        <p style="font-size: 16px; color: #666; margin-top: 10px;">{message}</p>
                    </div>

                    <p style="text-align: center;">
                        <a href="https://wordai.pro/tests/results" class="button">Xem chi tiết kết quả</a>
                    </p>

                    <p>Bạn có thể xem chi tiết điểm số từng câu hỏi, nhận xét của giáo viên và đáp án đúng tại trang kết quả.</p>

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
        Kết quả chấm điểm - WordAI

        Xin chào {student_name},

        Bài thi "{test_title}" của bạn đã được giáo viên chấm điểm xong!

        Điểm số: {score:.1f}/10
        Kết quả: {status_text}
        {message}

        Xem chi tiết tại: https://wordai.pro/tests/results

        Trân trọng,
        Đội ngũ WordAI
        """

        return self.send_email(to_email, subject, html_body, text_body)

    def send_grade_updated_notification(
        self,
        to_email: str,
        student_name: str,
        test_title: str,
        score: float,
        is_passed: bool,
    ) -> bool:
        """
        Send notification to student when a grade is updated

        Args:
            to_email: Student's email
            student_name: Student's name
            test_title: Test title
            score: Updated score (0-10 scale)
            is_passed: Whether student passed

        Returns:
            True if email sent successfully
        """
        status_emoji = "🎉" if is_passed else "📚"
        status_text = "Đạt yêu cầu" if is_passed else "Chưa đạt yêu cầu"
        status_color = "#28a745" if is_passed else "#dc3545"

        subject = f"📝 Điểm bài thi '{test_title}' đã được cập nhật"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .result-box {{ background: white; padding: 25px; border-radius: 8px; margin: 20px 0; text-align: center; border: 2px solid {status_color}; }}
                .score-badge {{ display: inline-block; background: {status_color}; color: white; padding: 15px 30px; border-radius: 25px; font-size: 32px; font-weight: bold; margin: 15px 0; }}
                .status-message {{ color: {status_color}; font-size: 18px; font-weight: bold; margin: 10px 0; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
                .button:hover {{ background: #5568d3; }}
                .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔄 Cập nhật điểm số</h1>
                </div>
                <div class="content">
                    <p>Xin chào <strong>{student_name}</strong>,</p>

                    <p>Giáo viên đã cập nhật lại điểm cho bài thi <strong>"{test_title}"</strong> của bạn.</p>

                    <div class="result-box">
                        <h3 style="margin-top: 0; color: #667eea;">{status_emoji} Điểm mới</h3>
                        <div class="score-badge">{score:.1f}/10</div>
                        <p class="status-message">{status_text}</p>
                    </div>

                    <p style="text-align: center;">
                        <a href="https://wordai.pro/tests/results" class="button">Xem chi tiết</a>
                    </p>

                    <p>Vui lòng kiểm tra lại kết quả và nhận xét của giáo viên.</p>

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
        Cập nhật điểm số - WordAI

        Xin chào {student_name},

        Giáo viên đã cập nhật lại điểm cho bài thi "{test_title}" của bạn.

        Điểm mới: {score:.1f}/10
        Kết quả: {status_text}

        Xem chi tiết tại: https://wordai.pro/tests/results

        Trân trọng,
        Đội ngũ WordAI
        """

        return self.send_email(to_email, subject, html_body, text_body)

    def send_new_submission_notification(
        self,
        to_email: str,
        owner_name: str,
        student_name: str,
        test_title: str,
        essay_count: int,
    ) -> bool:
        """
        Send notification to test owner when new essay submission arrives

        Args:
            to_email: Test owner's email
            owner_name: Test owner's name
            student_name: Student who submitted
            test_title: Test title
            essay_count: Number of essay questions to grade

        Returns:
            True if email sent successfully
        """
        subject = f"📝 Có bài thi mới cần chấm: {test_title}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .info-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }}
                .button {{ display: inline-block; background: #667eea; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
                .button:hover {{ background: #5568d3; }}
                .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📝 Bài thi mới cần chấm</h1>
                </div>
                <div class="content">
                    <p>Xin chào <strong>{owner_name}</strong>,</p>

                    <p>Bạn có bài thi mới cần chấm điểm!</p>

                    <div class="info-box">
                        <h3 style="margin-top: 0; color: #667eea;">📋 Thông tin bài thi</h3>
                        <p><strong>Bài thi:</strong> {test_title}</p>
                        <p><strong>Học viên:</strong> {student_name}</p>
                        <p><strong>Số câu tự luận:</strong> {essay_count} câu</p>
                    </div>

                    <p style="text-align: center;">
                        <a href="https://wordai.pro/tests/grading" class="button">Chấm điểm ngay</a>
                    </p>

                    <p>Vui lòng chấm điểm sớm để học viên nhận được kết quả.</p>

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
        Bài thi mới cần chấm - WordAI

        Xin chào {owner_name},

        Bạn có bài thi mới cần chấm điểm!

        Bài thi: {test_title}
        Học viên: {student_name}
        Số câu tự luận: {essay_count} câu

        Chấm điểm tại: https://wordai.pro/tests/grading

        Trân trọng,
        Đội ngũ WordAI
        """

        return self.send_email(to_email, subject, html_body, text_body)

    def send_social_plan_content_done_email(
        self,
        to_email: str,
        campaign_name: str,
        total_days: int,
        plan_url: str = "https://wordai.pro/social-plan",
    ) -> bool:
        """
        Send notification email when social plan batch content generation is complete.
        """
        subject = f"✅ Nội dung '{campaign_name}' đã được tạo xong!"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .info-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f5576c; }}
                .button {{ display: inline-block; background: #f5576c; color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
                .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Kế hoạch nội dung hoàn thành!</h1>
                </div>
                <div class="content">
                    <p>Xin chào,</p>
                    <p>Nội dung cho chiến dịch của bạn đã được tạo xong và sẵn sàng để sử dụng!</p>
                    <div class="info-box">
                        <h3 style="margin-top: 0; color: #f5576c;">📋 Chi tiết</h3>
                        <p><strong>Chiến dịch:</strong> {campaign_name}</p>
                        <p><strong>Số ngày:</strong> {total_days} ngày</p>
                    </div>
                    <p style="text-align: center;">
                        <a href="{plan_url}" class="button">Xem kế hoạch ngay</a>
                    </p>
                    <p>Trân trọng,<br><strong>Đội ngũ WordAI</strong></p>
                </div>
                <div class="footer">
                    <p>© 2025 WordAI. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        Kế hoạch nội dung hoàn thành - WordAI

        Nội dung cho chiến dịch '{campaign_name}' ({total_days} ngày) đã được tạo xong!

        Xem tại: {plan_url}

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
