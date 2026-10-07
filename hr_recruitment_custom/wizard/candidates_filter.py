from odoo import models, fields, _


class CandidatesFilterWizard(models.TransientModel):
    _name = 'candidates.filter.wizard'
    _description = 'Filter Candidates Wizard'

    applicant_ids = fields.Many2many(
        'hr.applicant',
        string='Applicants',
        required=True,
    )
    filter_stage_id = fields.Many2one(
        'hr.recruitment.stage',
        string='Filter by Stage',
    )
    job_id = fields.Many2one('hr.job', string='Job')

    # ── Certification filter ────────────────────────────────────────────────
    qualification_level = fields.Selection([
        ('high_school', 'High School'),
        ('diploma',     'Diploma'),
        ('bachelor',    'Bachelor'),
        ('master',      'Master'),
        ('phd',         'PhD'),
    ],
        string='Minimum Qualification Level',
        help='Keep only candidates whose highest certification is at least this level.',
    )

    # ── Specialization filter ───────────────────────────────────────────────
    specialization_ids = fields.Many2many(
        'candidate.specialization',
        string='Required Specializations',
        help=(
            'Keep only candidates who have at least one education entry '
            'matching one of the selected specializations. '
            'Leave empty to skip this filter.'
        ),
    )

    # ── Experience filter ───────────────────────────────────────────────────
    years_of_experience = fields.Integer(
        string='Years of Experience',
        help='Threshold used together with the operator below.',
    )
    operator = fields.Selection([
        ('bigger', 'Greater Than'),
        ('less',   'Less Than'),
        ('equal',  'Equal To'),
        ('bigger_equal', 'Greater Than or Equal To'),
        ('less_equal', 'Less Than or Equal To'),
    ],
        string='Experience Operator',
        default='bigger',
    )

    # ── Helpers ────────────────────────────────────────────────────────────
    _CERT_ORDER = ['high_school', 'diploma', 'bachelor', 'master', 'phd']

    def _cert_rank(self, cert):
        try:
            return self._CERT_ORDER.index(cert)
        except ValueError:
            return -1

    # ── Shared filter logic ────────────────────────────────────────────────
    def _get_passing_ids(self):
        """Return list of applicant IDs that pass all active filters."""
        passing_ids = []

        min_cert_rank = (
            self._cert_rank(self.qualification_level)
            if self.qualification_level else -1
        )
        required_spec_ids = set(self.specialization_ids.ids)

        for applicant in self.applicant_ids:
            candidate = applicant.candidate_id

            if self.filter_stage_id:
                if applicant.stage_id != self.filter_stage_id:
                    continue

            if self.job_id:
                if applicant.job_id != self.job_id:
                    continue

            if self.qualification_level:
                edu_certifications = candidate.education_ids.mapped('certification')
                best_rank = max(
                    (self._cert_rank(c) for c in edu_certifications),
                    default=-1
                )
                if best_rank < min_cert_rank:
                    continue

            if required_spec_ids:
                edu_spec_ids = set(
                    candidate.education_ids.mapped('specialization_id').ids
                )
                if not edu_spec_ids.intersection(required_spec_ids):
                    continue

            if self.years_of_experience:
                total_exp = candidate.total_experience_years or 0.0
                threshold = float(self.years_of_experience)
                if self.operator == 'bigger' and total_exp <= threshold:
                    continue
                elif self.operator == 'less' and total_exp >= threshold:
                    continue
                elif self.operator == 'equal' and round(total_exp, 2) != threshold:
                    continue
                elif self.operator == 'bigger_equal' and total_exp < threshold:
                    continue
                elif self.operator == 'less_equal' and total_exp > threshold:
                    continue

            passing_ids.append(applicant.id)

        return passing_ids

    # ── Action: Filter only ────────────────────────────────────────────────
    def action_apply_filters(self):
        passing_ids = self._get_passing_ids()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Filtered Candidates'),
            'res_model': 'hr.applicant',
            'view_mode': 'list,form',
            'domain': [('id', 'in', passing_ids)],
        }

    # ── Action: Filter then open Transfer Wizard ───────────────────────────
    def action_filter_and_transfer(self):
        passing_ids = self._get_passing_ids()

        if not passing_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Candidates'),
                    'message': _('No candidates passed the selected filters.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        return {
            'type': 'ir.actions.act_window',
            'name': _('Transfer Filtered Candidates'),
            'res_model': 'transfer.applicants.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_applicant_ids': passing_ids,
            },
        }