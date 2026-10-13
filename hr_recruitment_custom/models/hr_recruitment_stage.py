from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

class HrRecruitmentStage(models.Model):
    _inherit = 'hr.recruitment.stage'

    def _check_stage_settings_access(self):
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only administrators can change recruitment stage settings.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_stage_settings_access()
        return super().create(vals_list)

    def write(self, vals):
        self._check_stage_settings_access()
        return super().write(vals)

    def unlink(self):
        self._check_stage_settings_access()
        return super().unlink()

    filtering_stage = fields.Boolean(
        string='Is Filtering Stage',
        help='Applicants must pass candidate filtering before moving beyond this stage.',
    )

    exam_date_stage = fields.Boolean(
        string='Is Exam Date Stage',
        help='Setting an exam date and exam center is mandatory for this stage.'
    )

    exam_stage = fields.Boolean(
        string='Is Exam Stage',
        help='The candidate sits for an exam at this stage.'
    )
    interview_stage = fields.Boolean(
        string='Is Interview Stage',
        help='The candidate is interviewed at this stage.'
    )

    @api.constrains('exam_stage', 'interview_stage')
    def _check_exam_interview_mutual_exclusion(self):
        for rec in self:
            if rec.exam_stage and rec.interview_stage:
                raise ValidationError(
                    'A stage cannot be both an exam stage and an interview stage.'
                )
    allowed_group_ids = fields.Many2many(
        'res.groups',
        string='Allowed Groups',
        help='Users must belong to one of these groups to move applicants to this stage.'
    )
