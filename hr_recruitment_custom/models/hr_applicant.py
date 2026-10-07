from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    exam_stage = fields.Boolean(
        related='stage_id.exam_stage',
        string='Exam Stage',
        help='Indicates whether the applicant is in an exam stage.'
    )
    exam_date_stage = fields.Boolean(
        related='stage_id.exam_date_stage',
        string='Exam Date Stage',
        help='Indicates whether the applicant is in an exam stage.'
    )
    interview_stage = fields.Boolean(
        related='stage_id.interview_stage',
        string='Interview Stage',
        help='Indicates whether the applicant is in an interview stage.'
    )
    exam_date = fields.Datetime(
        string='Exam Date',
        help='The date when the applicant took the exam.'
    )
    exam_center_id = fields.Many2one(
        'exam.center',
        string='Exam Center',
        help='The exam center assigned to this applicant.'
    )
    interview_date = fields.Datetime(
        string='Interview Date',
    )
    notes = fields.Text(
        string='Notes',
    )
    interview_notes = fields.Text(
        string='Interview Notes',
    )

    @api.constrains('exam_date')
    def _check_exam_date_not_in_past(self):
        """An exam cannot be scheduled before the current local date."""
        today = fields.Date.context_today(self)
        for applicant in self:
            if not applicant.exam_date:
                continue

            exam_date = fields.Datetime.context_timestamp(
                self, applicant.exam_date
            ).date()
            if exam_date < today:
                raise ValidationError(_(
                    'The exam date cannot be earlier than today.'
                ))

    @api.constrains('interview_date')
    def _check_interview_date_not_in_past(self):
        """An interview cannot be scheduled before the current local date."""
        today = fields.Date.context_today(self)
        for applicant in self:
            if not applicant.interview_date:
                continue

            interview_date = fields.Datetime.context_timestamp(
                self, applicant.interview_date
            ).date()
            if interview_date < today:
                raise ValidationError(_(
                    'The interview date cannot be earlier than today.'
                ))

    selection_decision_ids = fields.Many2many(
        'hr.selection.decision',
        string='Selection Decisions',
        compute='_compute_selection_decision_ids',
    )
    selection_decision_count = fields.Integer(
        string='Selection Decision Count',
        compute='_compute_selection_decision_ids',
    )
    hired_for_other_jobs = fields.Char(
        string='Hired for Other Jobs',
        compute='_compute_hired_for_other_jobs',
        help='Jobs for which this candidate was hired through another application.',
    )

    def _compute_selection_decision_ids(self):
        for applicant in self:
            if not applicant.candidate_id:
                applicant.selection_decision_ids = self.env['hr.selection.decision']
                applicant.selection_decision_count = 0
                continue

            related_applicants = self.env['hr.applicant'].search([
                ('candidate_id', '=', applicant.candidate_id.id)
            ])

            decisions = self.env['hr.selection.decision'].search([
                ('applicant_ids', 'in', related_applicants.ids)
            ])

            applicant.selection_decision_ids = decisions
            applicant.selection_decision_count = len(decisions)

    @api.depends('candidate_id')
    def _compute_hired_for_other_jobs(self):
        for applicant in self:
            if not applicant.candidate_id:
                applicant.hired_for_other_jobs = False
                continue

            other_applicants = self.env['hr.applicant'].search([
                ('candidate_id', '=', applicant.candidate_id.id),
                ('id', '!=', applicant.id),
            ])
            decisions = self.env['hr.selection.decision'].search([
                ('applicant_ids', 'in', other_applicants.ids),
            ])
            job_names = dict.fromkeys(
                name for name in decisions.mapped('job_id.name') if name
            )
            applicant.hired_for_other_jobs = ', '.join(job_names) or False

    @api.model_create_multi
    def create(self, vals_list):
        applicants = super().create(vals_list)

        for applicant in applicants:
            if not applicant.candidate_id:
                continue

            candidate_attachments = self.env['ir.attachment'].search([
                ('res_id', '=', applicant.candidate_id.id),
                ('res_model', '=', 'hr.candidate'),
            ])
            if not candidate_attachments:
                continue

            candidate_checksums = set(candidate_attachments.mapped('checksum'))

            applicant_attachments = self.env['ir.attachment'].search([
                ('res_id', '=', applicant.id),
                ('res_model', '=', 'hr.applicant'),
            ])

            copies = applicant_attachments.filtered(
                lambda a: a.checksum in candidate_checksums
            )
            copies.unlink()

        return applicants

    def write(self, vals):
        if 'stage_id' in vals:
            new_stage = self.env['hr.recruitment.stage'].browse(vals['stage_id'])
            if new_stage.allowed_group_ids:
                user_groups = self.env.user.groups_id

                if not (new_stage.allowed_group_ids & user_groups):
                    raise ValidationError(_(
                        "You do not have permission to move the applicant to the stage: %s"
                    ) % new_stage.name)
                
            for applicant in self:
                current_stage = applicant.stage_id
                if current_stage and new_stage:

                    #  Prevent skipping stages
                    if new_stage.sequence > current_stage.sequence + 1:
                        raise ValidationError(_(
                            "You cannot skip stages. Move to the next stage only."
                        ))
                    #  Prevent previous stages
                    if new_stage.sequence < current_stage.sequence:
                        raise ValidationError(_(
                            "You cannot move to a previous stage. Move to the next stage only."
                        ))
                if new_stage.exam_date_stage and not (vals.get('exam_date') or applicant.exam_date) :
                    raise ValidationError(
                        _('Cannot move to an exam stage without setting the exam date.')
                    )

                if new_stage.exam_date_stage and not (vals.get('exam_center_id') or applicant.exam_center_id):
                    raise ValidationError(
                        _('Cannot move to an exam stage without setting the exam center.')
                    )

                # The interview date can be sent together with the stage
                # change from the form.  Check that pending value first,
                # rather than only the value already stored on the applicant.
                interview_date = vals.get(
                    'interview_date', applicant.interview_date
                )
                if new_stage.interview_stage and not interview_date:
                    raise ValidationError(
                        _('Cannot move to an interview stage without setting the interview date.')
                    )

        return super().write(vals)

    def open_next_stage_wizard(self) :
        return {
    'type': 'ir.actions.act_window',
    'name': _('Move To Next Stage'),
    'res_model': 'transfer.applicants.wizard',
    'view_mode': 'form',
    'target': 'new',
    'context': {
        'default_applicant_ids': [(6, 0, self.ids)],
    }
}
    
    def open_filter_candidates_wizard(self) :
        return {
    'type': 'ir.actions.act_window',
    'name': _('Filter Candidates'),
    'res_model': 'candidates.filter.wizard',
    'view_mode': 'form',
    'target': 'new',
    'context': {
        'default_applicant_ids': [(6, 0, self.ids)],
    }
}

    def action_open_evaluation_wizard(self):
        self.ensure_one()

        if not self.env.user.has_group(
            'hr_recruitment_custom.group_inspection_committee'
        ):
            raise AccessError(_(
                'Only members of the inspection committee can enter interview evaluations.'
            ))

        if not self.stage_id.interview_stage:
            raise ValidationError(_('Evaluation is only available for applicants in the interview stage.'))

        survey = self.job_id.survey_id
        if not survey:
            raise ValidationError(_('No survey linked to this job position.'))

        # Find or create user_input
        user_input = self.env['survey.user_input'].search([
            ('survey_id', '=', survey.id),
            ('partner_id', '=', self.partner_id.id),
            ('job_id', '=', self.job_id.id),
        ], limit=1)

        if not user_input:
            user_input = self.env['survey.user_input'].create({
                'survey_id': survey.id,
                'partner_id': self.partner_id.id,
                'job_id': self.job_id.id,
                'state': 'done',
            })
            self.write({'response_ids': [(4, user_input.id)]})
            for question in survey.question_ids.filtered(
                lambda q: q.question_type == 'numerical_box'
            ):
                self.env['survey.user_input.line'].create({
                    'user_input_id': user_input.id,
                    'question_id': question.id,
                    'answer_type': 'numerical_box',
                    'value_numerical_box': 0.0,
                })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Evaluation'),
            'res_model': 'survey.user_input',
            'view_mode': 'form',
            'res_id': user_input.id,
            'target': 'new',
            'context': {
                'default_survey_id': survey.id,
                'default_partner_id': self.partner_id.id,
                'default_job_id': self.job_id.id,
            },
        }
