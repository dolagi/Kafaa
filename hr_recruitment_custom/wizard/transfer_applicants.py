from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TransferApplicantsWizard(models.TransientModel):
    _name = 'transfer.applicants.wizard'
    _description = 'Transfer Applicants to Next Stage'

    applicant_ids = fields.Many2many(
        'hr.applicant',
        string='Applicants',
        required=True
    )
    stage_id = fields.Many2one(
        'hr.recruitment.stage',
        string='Next Stage',
        required=True
    )
    exam_date_stage = fields.Boolean(
        related='stage_id.exam_date_stage',
        string='Exam Stage',
        help='Indicates whether the applicant is in an exam stage.'
    )
    interview_stage = fields.Boolean(
        related='stage_id.interview_stage',
        string='Is Interview Stage',
        readonly=True
    )
    # NEW: detect the "hired" stage (native hr.recruitment.stage.hired_stage field)
    hired_stage = fields.Boolean(
        related='stage_id.hired_stage',
        string='Is Hired Stage',
        readonly=True,
    )
    date = fields.Datetime(
        string='Date',
    )

    exam_center_id = fields.Many2one('exam.center', string='Exam Center')
    notes = fields.Text()

    # ── NEW: fields only used to build the decision letter ───
    manager_name = fields.Char(
        string='Requesting Entity Manager',
        help='Name of the manager of the entity requesting the hiring of the selected candidates (e.g., a university).',
    )
    entity_name = fields.Char(
        string='Requesting Entity Name',
        compute='_compute_entity_name',
        help='Name of the entity requesting the hiring of the selected candidates (e.g., a university). Pulled from the job position\'s Address (address_id) field.',
    )
    sector = fields.Char(
        string='Sector',
        help='The sector in which the selected candidates will work, e.g., University',
    )
    letter_number = fields.Char(
        string='Letter Number',
        help='Letter number for the selection decision',
    )
    letter_date = fields.Date(string='Letter Date')
    # Auto-filled with the current year — not meant to be edited by the user.
    decision_year = fields.Char(
        string='Year',
        default=lambda self: str(fields.Date.today().year),
    )
    # Auto-pulled from the job's own Degree Level setting (hr.job.degree_level).
    degree = fields.Char(
        string='Degree',
        compute='_compute_degree',
        readonly=True,
    )

    @api.depends('applicant_ids')
    def _compute_degree(self):
        for wiz in self:
            jobs = wiz.applicant_ids.mapped('job_id')
            if jobs and jobs[0].degree_level:
                # Pulls the *translated* label for the current user language
                # from the module's .po translation file.
                selection = dict(
                    jobs[0]._fields['degree_level']._description_selection(jobs[0].env)
                )
                wiz.degree = _(selection.get(jobs[0].degree_level, ''))
            else:
                wiz.degree = ''

    @api.depends('applicant_ids')
    def _compute_entity_name(self):
        for wiz in self:
            jobs = wiz.applicant_ids.mapped('job_id')
            wiz.entity_name = (
                jobs[0].address_id.name if jobs and jobs[0].address_id else ''
            )

    def action_confirm(self):
        self.ensure_one()

        if self.hired_stage and not self.manager_name:
            raise ValidationError(_(
                'Please enter the requesting entity manager name before '
                'confirming the selection decision.'
            ))
        if self.hired_stage and not self.entity_name:
            raise ValidationError(_(
                'The requesting entity name could not be found — please '
                'make sure the job position has an Address (address_id) set.'
            ))
        if self.hired_stage and not self.sector:
            raise ValidationError(_(
                'Please enter the sector before confirming the '
                'selection decision.'
            ))

        if self.exam_date_stage:
            self.applicant_ids.write({
                'exam_date': self.date,
                'exam_center_id': self.exam_center_id.id,
                'notes': self.notes,
            })
        elif self.interview_stage:
            for applicant in self.applicant_ids:
                exam = applicant.job_id.exam_id
                if exam:
                    passed_input = self.env['survey.user_input'].search([
                        ('survey_id', '=', exam.id),
                        ('partner_id', '=', applicant.candidate_id.partner_id.id),
                        ('state', 'in', ['done', 'approved']),
                    ], limit=1, order='create_date desc')

                    if not passed_input:
                        raise ValidationError(_(
                            'Cannot move "%s" to an interview stage: '
                            'the candidate has not completed the job exam yet.'
                        ) % applicant.partner_name)

                    if passed_input.scoring_percentage < exam.scoring_success_min:
                        raise ValidationError(_(
                            'Cannot move "%s" to an interview stage: '
                            'exam score (%.1f%%) is below the passing threshold (%.1f%%).'
                        ) % (
                            applicant.partner_name,
                            passed_input.scoring_percentage,
                            exam.scoring_success_min,
                        ))

            self.applicant_ids.write({
                'interview_date': self.date,
                'interview_notes': self.notes,
            })
        # else:
        #     self.applicant_ids.write({
        #         'notes': self.notes,
        #     })

        self.applicant_ids.write({
            'stage_id': self.stage_id.id,
        })

        # ── NEW: when moving into the hired stage, create the persistent
        # selection-decision record and print the two-page decision letter.
        if self.hired_stage:
            decision = self.env['hr.selection.decision'].create({
                'job_id': self.applicant_ids[:1].job_id.id,
                'degree': self.degree,
                'manager_name': self.manager_name,
                'entity_name': self.entity_name,
                'sector': self.sector,
                'letter_number': self.letter_number,
                'letter_date': self.letter_date,
                'year': self.decision_year,
                'applicant_ids': [(6, 0, self.applicant_ids.ids)],
            })
            return decision.action_print_decision()