from odoo import api, models


class JobResultsReport(models.AbstractModel):
    _name = 'report.hr_recruitment_custom.job_results_template'
    _description = 'Job Results Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        jobs = self.env['hr.job'].browse(docids)
        job = jobs[:1]
        needed = job.no_of_recruitment or 0

        applicants = self.env['hr.applicant'].search([
            ('job_id', '=', job.id),
            ('active', '=', True),
        ])

        results = []
        for applicant in applicants:
            partner = applicant.candidate_id.partner_id
            if not partner:
                continue

            exam_input = self.env['survey.user_input']
            if job.exam_id:
                exam_input = self.env['survey.user_input'].search([
                    ('survey_id', '=', job.exam_id.id),
                    ('partner_id', '=', partner.id),
                    ('state', 'in', ['done', 'approved']),
                ], limit=1, order='create_date desc')

            interview_input = self.env['survey.user_input']
            if job.survey_id:
                interview_input = self.env['survey.user_input'].search([
                    ('survey_id', '=', job.survey_id.id),
                    ('partner_id', '=', partner.id),
                    ('state', 'in', ['done', 'approved']),
                ], limit=1, order='create_date desc')

            exam_pct = exam_input.scoring_percentage if exam_input else 0.0
            interview_pct = interview_input.scoring_percentage if interview_input else 0.0

            if job.scoring_criteria == 'exam_only':
                if not exam_input:
                    continue
                total = exam_pct
            elif job.scoring_criteria == 'interview_only':
                if not interview_input:
                    continue
                total = interview_pct
            else:
                if not exam_input or not interview_input:
                    continue
                total = exam_pct + interview_pct

            results.append({
                'name': partner.name,
                'nationality_no': applicant.candidate_id.nationality_no or '',
                'exam_score': round(exam_pct, 2),
                'interview_score': round(interview_pct, 2),
                'total': round(total, 2),
            })

        results.sort(key=lambda result: result['total'], reverse=True)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.job',
            'docs': jobs,
            'job': job,
            'needed': needed,
            'shortlist': results[:needed],
            'others': results[needed:],
            'total_completed': len(results),
        }
