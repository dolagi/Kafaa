from werkzeug import Response

from odoo import http
from odoo.http import request
import logging
import json


_logger = logging.getLogger(__name__)


class PortalContact(http.Controller):

    @http.route('/contact-us/send', type='http', auth='bearer', methods=['POST'], csrf=False)
    def send_contact_email(self, **post):
        headers = {'Content-Type': 'application/json'}
        user = request.env.user

        # --- Validation ---
        subject = post.get('subject') or ''
        message = post.get('message') or ''
        sender_name = post.get('name') or ''
        sender_email = post.get('email') or ''

        if not message:
            return request.make_response(
                json.dumps({'error': 'Message is required'}),
                headers=headers,
                status=400
            )

        if not sender_email:
            return request.make_response(
                json.dumps({'error': 'Email is required'}),
                headers=headers,
                status=400
            )

        if len(message) > 5000:
            return request.make_response(
                json.dumps({'error': 'Message is too long'}),
                headers=headers,
                status=400
            )

        company = request.env.company
        company_email = company.email or 'support@company.com'

        body_html = f"""
        <div style="font-family: Arial, sans-serif; direction: rtl; text-align: right;">
            <h2 style="color: #714B67; border-bottom: 2px solid #714B67; padding-bottom: 8px;">
                رسالة جديدة من كفاءة
            </h2>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr style="background: #f8f5ff;">
                    <td style="padding: 8px 12px; font-weight: bold; width: 30%;">الاسم:</td>
                    <td style="padding: 8px 12px;">{sender_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 12px; font-weight: bold;">البريد الإلكتروني:</td>
                    <td style="padding: 8px 12px;">{sender_email}</td>
                </tr>
                <tr style="background: #f8f5ff;">
                    <td style="padding: 8px 12px; font-weight: bold;">الموضوع:</td>
                    <td style="padding: 8px 12px;">{subject}</td>
                </tr>
            </table>
            <h3 style="color: #714B67;">نص الرسالة:</h3>
            <div style="background: #f9f9f9; border-right: 4px solid #714B67;
                        padding: 15px; border-radius: 4px; white-space: pre-wrap;">
                {message}
            </div>
            <p style="color: #999; font-size: 12px; margin-top: 20px;">
                تم الإرسال من كفاءة - {company.name}
            </p>
        </div>
        """

        try:
            # --- إنشاء وإرسال الإيميل ---
            mail_values = {
                'subject': f"[Portal] {subject}",
                'email_from': f"{sender_name} <{sender_email}>",
                'email_to': company_email,
                'body_html': body_html,
                'reply_to': sender_email,
                'auto_delete': False,  # keep record so we can check state after send
            }

            mail = request.env['mail.mail'].sudo().create(mail_values)
            mail.send()

            # --- Check if mail actually failed after send() ---
            # Odoo sets state='exception' and stores failure_reason when SMTP fails
            if mail.state == 'exception':
                failure_reason = mail.failure_reason or 'Unknown error'
                _logger.error(
                    "Portal contact email failed for user %s (%s) - reason: %s",
                    user.id, sender_email, failure_reason
                )
                # clean up the failed mail record
                mail.sudo().unlink()
                return request.make_response(
                    json.dumps({
                        'message': {
                            'en': 'Failed to send message. Please try again later.',
                            'ar': 'فشل إرسال الرسالة. يرجى المحاولة مرة أخرى لاحقاً.'
                        }
                    }),
                    headers=headers,
                    status=500
                )

            # --- Success: clean up and respond ---
            mail.sudo().unlink()
            _logger.info(
                "Portal contact email sent from user %s (%s) - subject: %s",
                user.id, sender_email, subject
            )
            return request.make_response(
                json.dumps({
                    'message': {
                        'en': 'Your message has been sent successfully',
                        'ar': 'تم إرسال رسالتك بنجاح'
                    }
                }),
                headers=headers
            )

        except Exception as e:
            _logger.error("Portal contact unexpected error: %s", str(e))
            return Response(
                json.dumps({
                    'message': {
                        'en': 'Internal server error',
                        'ar': 'خطأ في السيرفر'
                    }
                }),
                headers=headers,
                status=500
            )
