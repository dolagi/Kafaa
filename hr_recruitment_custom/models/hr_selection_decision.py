from odoo import api, models, fields


class HrSelectionDecision(models.Model):
    """قرار اختيار خبرات — created automatically when applicants are
    transferred into a 'hired' stage from the Transfer Applicants wizard.
    Kept as a persistent record so the decision letter can be re-printed
    later and so decision numbers are never reused.
    """
    _name = 'hr.selection.decision'
    _description = 'Selection Decision'
    _order = 'id desc'

    name = fields.Char(
        string='Decision Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'hr.selection.decision'
        ) or '/',
    )
    date = fields.Date(string='Date', default=fields.Date.today, required=True)
    year = fields.Char(string='Year', required=True,
                        default=lambda self: str(fields.Date.today().year))
    job_id = fields.Many2one('hr.job', string='Job Position')
    degree = fields.Char(string='Degree Level', help='Degree level for the selected candidates')
    show_education_columns = fields.Boolean(
        compute='_compute_show_education_columns',
    )

    manager_name = fields.Char(
        string='Requesting Entity Manager',
        required=True,
        help='Name of the manager of the entity requesting the hiring of the selected candidates (e.g., a university).',
    )
    entity_name = fields.Char(
        string='Requesting Entity Name',
        required=True,
        help='Name of the entity requesting the hiring of the selected candidates (e.g., a university).',
    )
    sector = fields.Char(
        string='Sector',
        required=True,
        help='The sector in which the selected candidates will work (appears in the line "in the sector")',
    )
    letter_number = fields.Char(
        string='Their Letter Number',
        help='The number mentioned in the letter from the requesting entity',
    )
    letter_date = fields.Date(string='Their Letter Date')

    applicant_ids = fields.Many2many(
        'hr.applicant',
        string='Selected Applicants',
        required=True,
    )
    applicant_count = fields.Integer(
        string='Count', compute='_compute_applicant_count'
    )

    def _compute_applicant_count(self):
        for rec in self:
            rec.applicant_count = len(rec.applicant_ids)

    @api.depends('job_id.degree_level')
    def _compute_show_education_columns(self):
        hidden_levels = {'eleventh', 'twelfth', 'thirteenth', 'fourteenth'}
        for rec in self:
            rec.show_education_columns = rec.job_id.degree_level not in hidden_levels

    def action_print_decision(self):
        return self.env.ref(
            'hr_recruitment_custom.action_hired_selection_decision_report'
        ).report_action(self)
