from odoo import models, fields

class JobExamReportWizard(models.TransientModel):
    _name = 'applicant.result.report.wizard'
    _description = 'Job Exam Report Wizard'

    job_id = fields.Many2one(
        'hr.job',
        string='Job',
        required=True
    )

    def action_print_pdf(self):
        return self.env.ref(
            'hr_recruitment_custom.action_applicant_result_report'
        ).report_action(self)
