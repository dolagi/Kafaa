from odoo import models, api


class InterviewFormReport(models.AbstractModel):
    _name = 'report.hr_recruitment_custom.interview_form_report'
    _description = 'Interview Evaluation Form Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        jobs = self.env['hr.job'].browse(docids)
        reports = []

        for job in jobs:
            if not job.survey_id:
                continue

            # Dynamic columns: only scored questions (exclude section headers)
            questions = job.survey_id.question_ids.filtered(
                lambda q: q.is_scored_question
            )

            # Max score map: question_id -> answer_score (fixed on the question itself)
            max_score_map = {
                q.id: q.answer_score for q in questions
            }

            # Get all applicants for this job
            applicants = self.env['hr.applicant'].search([
                ('job_id', '=', job.id),
                ('active', '=', True),
                ('stage_id.interview_stage', '=', True),
            ], order='id asc')

            candidates = []
            idx = 0
            for applicant in applicants:
                candidate = applicant.candidate_id
                partner = candidate.partner_id
                if not partner:
                    continue

                # Get this candidate's user_input for the survey
                user_input = self.env['survey.user_input'].search([
                    ('survey_id', '=', job.survey_id.id),
                    ('partner_id', '=', partner.id),
                    ('job_id', '=', job.id),
                ], limit=1, order='create_date desc')

                # Only display applicants that have a user_input for this survey
                if not user_input:
                    continue

                idx += 1

                # Resolve candidate name
                name = (
                    candidate.partner_name
                    or applicant.partner_name
                    or ''
                )

                # Build score map: question_id -> achieved answer_score
                score_map = {}
                for line in user_input.user_input_line_ids:
                    if line.question_id.id in score_map:
                        continue
                    score_map[line.question_id.id] = line.answer_score or 0

                candidates.append({
                    'index': idx,
                    'name': name,
                    'scores': score_map,
                    'total': round(user_input.scoring_percentage, 2),
                })

            reports.append({
                'job': job,
                'questions': questions,
                'max_score_map': max_score_map,
                'candidates': candidates,
            })

        return {
            'doc_ids': docids,
            'doc_model': 'hr.job',
            'reports': reports,
        }   