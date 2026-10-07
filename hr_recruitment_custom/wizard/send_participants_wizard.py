import base64
from io import BytesIO
import xlsxwriter

from odoo import models, fields, _

class SendParticipantsWizard(models.TransientModel):
    _name = 'survey.send.participants.wizard'
    _description = 'Send Survey Participants'

    partner_id = fields.Many2one(
        'res.partner',
        string="Send To",
        required=True
    )

    def action_send(self):
        active_ids = self.env.context.get('active_ids', [])
        records = self.env['survey.user_input'].browse(active_ids)
        if not records:
            return

        # Create Excel
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Participants')

        # --- Formats ---
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 16
        })

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',   # blue background
            'font_color': 'white',    # text color
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter'
        })

        number_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'num_format': '0.00'
        })

        # --- Title ---
        headers = ['Participant Name', 'Survey', 'Score']
        worksheet.merge_range(0, 0, 0, len(headers)-1, _("Survey Participants List"), title_format)

        # --- Headers ---
        for col, header in enumerate(headers):
            worksheet.write(1, col, header, header_format)

        # --- Data Rows ---
        row = 2
        for rec in records:
            worksheet.write(row, 0, rec.partner_id.name or '', cell_format)
            worksheet.write(row, 1, rec.survey_id.title or '', cell_format)
            worksheet.write(row, 2, rec.scoring_percentage or 0, number_format)
            row += 1

        # --- Auto column width ---
        for i, col in enumerate(headers):
            max_len = max(
                [len(str(rec.partner_id.name)) if i==0 else len(str(rec.survey_id.title)) if i==1 else len(str(rec.scoring_percentage)) for rec in records] + [len(col)]
            )
            worksheet.set_column(i, i, max_len + 5)  # add padding

        workbook.close()
        output.seek(0)

        # --- Attachment ---
        attachment = self.env['ir.attachment'].create({
            'name': 'survey_participants.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        # --- Send Email ---
        mail = self.env['mail.mail'].create({
            'subject': _("Exam Participants List"),
            'body_html': _('<p>Please find attached the exam participants list.</p>'),
            'email_to': self.partner_id.email,
            'attachment_ids': [(4, attachment.id)],
        })
        mail.send()
