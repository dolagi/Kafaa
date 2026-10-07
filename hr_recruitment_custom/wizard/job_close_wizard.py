from odoo import fields, models, _
from odoo.exceptions import AccessError


class HrJobCloseWizard(models.TransientModel):
    _name = 'hr.job.close.wizard'
    _description = 'Confirm Job Closure Below Target'

    job_id = fields.Many2one('hr.job', required=True, readonly=True)
    selected_count = fields.Integer(
        related='job_id.selected_applicants_count', readonly=True,
        string='Selected Count',
    )
    required_count = fields.Integer(
        related='job_id.no_of_recruitment', readonly=True,
        string='Required Count',
    )
    is_below_target = fields.Boolean(compute='_compute_is_below_target')

    def _compute_is_below_target(self):
        for wizard in self:
            wizard.is_below_target = bool(
                wizard.required_count
                and wizard.selected_count < wizard.required_count
            )

    def action_confirm_close(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'hr_recruitment_custom.group_general_secretariat'
        ):
            raise AccessError(_('Only the General Secretariat can close jobs.'))
        self.job_id._close_job()
        return {'type': 'ir.actions.act_window_close'}
