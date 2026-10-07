from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError

import base64
from io import BytesIO
import xlsxwriter

class Survey(models.Model):
    _inherit = 'survey.survey'

    def _default_pass_stage_id(self):
        if self.env.context.get('default_survey_type') != 'assessment':
            return False
        return self.env['hr.recruitment.stage'].search(
            [('interview_stage', '=', True)], limit=1
        )

    pass_stage_id = fields.Many2one('hr.recruitment.stage', string='Pass Stage',
        help='The recruitment stage to set when the candidate passes the exam.',
        default=_default_pass_stage_id,)
    progression_mode = fields.Selection([
        ('percent', 'Percentage left'),
        ('number', 'Number')], string='Display Progress as', default='number',
        help="If Number is selected, it will display the number of questions answered on the total number of question to answer.")
    access_mode = fields.Selection([
        ('public', 'Anyone with the link'),
        ('token', 'Invited people only')], string='Access Mode',
        default='public', required=True)
    questions_selection = fields.Selection([
        ('all', 'All questions'),
        ('random', 'Randomized per Section')],
        string="Question Selection", required=True, default='random',
        help="If randomized is selected, you can configure the number of random questions by section. This mode is ignored in live session.")

    @api.onchange('survey_type')
    def _onchange_survey_type_access_mode(self):
        self.access_mode = 'public'

class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    job_id = fields.Many2one('hr.job', string='Job Position', index=True)
    is_interview_form = fields.Boolean(
        compute='_compute_interview_applicant_partners',
    )
    interview_applicant_partner_ids = fields.Many2many(
        'res.partner',
        compute='_compute_interview_applicant_partners',
    )
    state = fields.Selection(
        selection_add=[('approved', 'Approved')]
    )
    applicant_exam_score = fields.Float(
    string='Exam Score (%)',
    compute='_compute_applicant_exam_score',
    store=True,
    compute_sudo=True,
)
    
    feedback_survey_url = fields.Char(
        string='Feedback Survey URL',
        compute='_compute_feedback_survey_url',
    )
    signature_ids = fields.One2many(
    'survey.user_input.signature',
    'user_input_id',
    string='Committee Signatures',
)

    def _check_committee_evaluation_scope(self, values=None):
        """Keep committee members within interview evaluations assigned to a job.

        ACLs grant the committee write access to survey responses so it can enter
        scores.  This additional server-side guard prevents use of that access
        for ordinary examinations or responses outside the interview stage.
        """
        if not self.env.user.has_group(
            'hr_recruitment_custom.group_inspection_committee'
        ):
            return

        values = values or {}
        for record in self or [self]:
            survey = self.env['survey.survey'].browse(
                values.get('survey_id', record.survey_id.id)
            )
            job = self.env['hr.job'].browse(values.get('job_id', record.job_id.id))
            partner = self.env['res.partner'].browse(
                values.get('partner_id', record.partner_id.id)
            )
            applicant = self.env['hr.applicant'].search([
                ('job_id', '=', job.id),
                ('candidate_id.partner_id', '=', partner.id),
                ('stage_id.interview_stage', '=', True),
                ('active', '=', True),
            ], limit=1)
            if (
                not job or not partner or job.survey_id.id != survey.id
                or not applicant
            ):
                raise AccessError(_(
                    'Inspection committee members may only edit evaluations for '
                    'applicants currently in the interview stage.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.has_group(
            'hr_recruitment_custom.group_inspection_committee'
        ):
            for vals in vals_list:
                self.browse()._check_committee_evaluation_scope(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._check_committee_evaluation_scope(vals)
        return super().write(vals)

    @api.depends('survey_id', 'job_id')
    def _compute_interview_applicant_partners(self):
        """Provide partners eligible for an interview evaluation form."""
        Applicant = self.env['hr.applicant']
        Job = self.env['hr.job']

        for record in self:
            record.is_interview_form = False
            record.interview_applicant_partner_ids = False

            if not record.survey_id:
                continue

            if record.job_id:
                jobs = record.job_id.filtered(
                    lambda job: job.survey_id == record.survey_id
                )
            else:
                jobs = Job.search([('survey_id', '=', record.survey_id.id)])

            if not jobs:
                continue

            record.is_interview_form = True
            applicants = Applicant.search([
                ('job_id', 'in', jobs.ids),
                ('active', '=', True),
                ('stage_id.interview_stage', '=', True),
            ])
            record.interview_applicant_partner_ids = applicants.mapped(
                'candidate_id.partner_id'
            )

    # def _compute_feedback_survey_url(self):
    #     base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #     for rec in self:
    #         rec.feedback_survey_url = False

    #         # find the job linked to this exam
    #         job = self.env['hr.job'].search([
    #             ('exam_id', '=', rec.survey_id.id)
    #         ], limit=1)

    #         if not job or not job.feedback_survey_id:
    #             continue

    #         feedback_survey = job.feedback_survey_id

    #         # find or create feedback answer
    #         feedback_answer = self.env['survey.user_input'].search([
    #             ('survey_id', '=', feedback_survey.id),
    #             ('partner_id', '=', rec.partner_id.id),
    #             ('state', '!=', 'done'),
    #         ], limit=1)

    #         if not feedback_answer:
    #             # check if already completed
    #             completed = self.env['survey.user_input'].search([
    #                 ('survey_id', '=', feedback_survey.id),
    #                 ('partner_id', '=', rec.partner_id.id),
    #                 ('state', '=', 'done'),
    #             ], limit=1)

    #             if completed:
    #                 # already rated — don't show button
    #                 continue

    #             feedback_answer = feedback_survey.sudo()._create_answer(
    #                 partner=rec.partner_id
    #             )
    #             feedback_answer.sudo().write({'state': 'in_progress'})

    #         if feedback_answer.state != 'done':
    #             rec.feedback_survey_url = '%s/survey/%s/%s' % (
    #                 base_url,
    #                 feedback_survey.access_token,
    #                 feedback_answer.access_token,
    #             )


    def _compute_feedback_survey_url(self):
        """READ-ONLY. Never creates records here — this runs on every read()."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.feedback_survey_url = False

            job = self.env['hr.job'].search([
                ('exam_id', '=', rec.survey_id.id)
            ], limit=1)

            if not job or not job.feedback_survey_id:
                continue

            feedback_survey = job.feedback_survey_id

            # only look for an existing, not-yet-completed answer — never create one here
            feedback_answer = self.env['survey.user_input'].sudo().search([
                ('survey_id', '=', feedback_survey.id),
                ('partner_id', '=', rec.partner_id.id),
                ('state', '!=', 'done'),
            ], limit=1)

            if feedback_answer:
                rec.feedback_survey_url = '%s/survey/%s/%s' % (
                    base_url,
                    feedback_survey.access_token,
                    feedback_answer.access_token,
                )

    def _ensure_feedback_answer(self):
        """Create the feedback survey answer exactly once, when the exam is actually completed."""
        self.ensure_one()
        job = self.env['hr.job'].search([
            ('exam_id', '=', self.survey_id.id)
        ], limit=1)

        if not job or not job.feedback_survey_id:
            return

        feedback_survey = job.feedback_survey_id

        # already exists (in progress or done) -> nothing to do
        existing = self.env['survey.user_input'].sudo().search([
            ('survey_id', '=', feedback_survey.id),
            ('partner_id', '=', self.partner_id.id),
        ], limit=1)
        if existing:
            return

        feedback_answer = feedback_survey.sudo()._create_answer(partner=self.partner_id)
        feedback_answer.sudo().write({'state': 'in_progress'})
        print("Created feedback survey answer for partner %s on survey %s" % (self.partner_id.id, feedback_answer))

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') in ('done', 'approved'):
            for rec in self:
                if rec.state in ('done', 'approved'):
                    rec._ensure_feedback_answer()
        return res



    @api.depends('scoring_percentage', 'survey_id', 'partner_id', 'state')
    def _compute_applicant_exam_score(self):
        for rec in self:
            rec.applicant_exam_score = 0.0 

            if not rec.partner_id:
                continue

            jobs = self.env['hr.job'].search([
                ('survey_id', '=', rec.survey_id.id)
            ])
            if not jobs:
                continue

            for job in jobs:
                if not job.exam_id:
                    continue

                applicant = self.env['hr.applicant'].search([
                    ('job_id', '=', job.id),
                    ('candidate_id.partner_id', '=', rec.partner_id.id),
                ], limit=1)
                if not applicant:
                    continue

                exam_answer = self.env['survey.user_input'].search([
                    ('survey_id', '=', job.exam_id.id),
                    ('partner_id', '=', rec.partner_id.id),
                    ('state', 'in', ['done', 'approved']),
                ], limit=1, order='create_date desc')

                if exam_answer:
                    rec.applicant_exam_score = exam_answer.scoring_percentage
                    break

    def action_approve(self):
        for input in self:
            input.state = 'approved'

    @api.onchange('survey_id')
    def _onchange_survey_id(self):
        # Explicitly clear the previous survey's answers before adding the
        # selected survey's questions.  This also makes the removal visible
        # immediately in the form, before it is saved.
        lines = [(5, 0, 0)]
        if self.survey_id:
            for question in self.survey_id.question_ids:
                line_values = {
                    'question_id': question.id,
                    'answer_type': question.question_type,
                    'value_char_box': '1',
                }
                # Odoo computes the score while creating the line.  A numeric
                # question without a value reaches ``float(None)`` there;
                # zero is a valid evaluation value and must be explicit.
                if question.question_type == 'numerical_box':
                    line_values['value_numerical_box'] = 0.0
                elif question.question_type == 'scale':
                    line_values['value_scale'] = 0
                lines.append((0, 0, line_values))

        self.user_input_line_ids = lines

    def action_set_application_stage(self):
        """
        Move the candidate's application to the stage defined on the exam if the candidate passes.
        """
        applicants = self.env['hr.applicant']
        for input in self :
            # Only process approved exams
            if input.state != 'approved':
                continue

            # Check if the exam has a pass stage defined
            survey = input.survey_id
            if not survey.pass_stage_id:
                continue

            # Find related applicant(s)
            applicant = self.env['hr.applicant'].search([
                ('job_id.exam_id', '=', survey.id),
                ('candidate_id.partner_id', '=', input.partner_id.id)
            ], limit=1)
            if not applicant:
                continue

            # Determine if candidate passed the exam
            # Using exam scoring
            if input.scoring_percentage >= survey.scoring_success_min:
                applicants |= applicant

        if not applicants:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Move To Next Stage'),
            'res_model': 'transfer.applicants.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_applicant_ids': [(6, 0, applicants.ids)],
                'default_stage_id': survey.pass_stage_id.id,
            }
        }
    
    def open_send_participants_wizard(self) :
        return {
    'type': 'ir.actions.act_window',
    'name': _('Send Email'),
    'res_model': 'survey.send.participants.wizard',
    'view_mode': 'form',
    'target': 'new',

}

class SurveyUserInputLine(models.Model):
    _inherit = 'survey.user_input.line'

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.has_group(
            'hr_recruitment_custom.group_inspection_committee'
        ):
            for vals in vals_list:
                user_input = self.env['survey.user_input'].browse(
                    vals.get('user_input_id')
                )
                user_input._check_committee_evaluation_scope()
        return super().create(vals_list)

    def write(self, vals):
        if self.env.user.has_group(
            'hr_recruitment_custom.group_inspection_committee'
        ):
            self.mapped('user_input_id')._check_committee_evaluation_scope()
        return super().write(vals)

    @api.model
    def _get_answer_score_values(self, vals, compute_speed_score=True):
        """Treat an empty numeric value as zero when scoring manual forms."""
        if (
            vals.get('answer_type') == 'numerical_box'
            and vals.get('value_numerical_box') is None
        ):
            vals = dict(vals, value_numerical_box=0.0)
        return super()._get_answer_score_values(vals, compute_speed_score)

    question_max_score = fields.Float(
        related='question_id.answer_score',
        string='Maximum Score',
        readonly=True,
    )

    @api.onchange('answer_score', 'question_id', 'question_max_score')
    def _check_answer_score_does_not_exceed_question_maximum(self):
        for line in self:
            if line.answer_score > line.question_max_score:
                raise UserError(_(
                    'The answer score (%(score)s) cannot exceed the maximum score '
                    'for this question (%(maximum)s).'
                ) % {
                    'score': line.answer_score,
                    'maximum': line.question_max_score,
                })

class SurveyUserInputSignature(models.Model):
    _name = 'survey.user_input.signature'
    _description = 'Interview Form Signature'

    user_input_id = fields.Many2one(
        'survey.user_input',
        string='Interview Form',
        required=True,
        ondelete='cascade',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Committee Member',
        required=True,
        default=lambda self: self.env.user,
    )
    signature = fields.Binary(
        string='Signature',
        attachment=True,
    )
    signed_date = fields.Date(
        string='Date Signed',
        default=fields.Date.today,
    )

    _sql_constraints = [
        ('unique_user_per_input',
         'UNIQUE(user_input_id, user_id)',
         'This committee member has already signed this form.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.has_group(
            'hr_recruitment_custom.group_inspection_committee'
        ):
            for vals in vals_list:
                if vals.get('user_id', self.env.user.id) != self.env.user.id:
                    raise AccessError(_('A committee member can only add their own signature.'))
                self.env['survey.user_input'].browse(
                    vals.get('user_input_id')
                )._check_committee_evaluation_scope()
        return super().create(vals_list)

    def write(self, vals):
        if self.env.user.has_group(
            'hr_recruitment_custom.group_inspection_committee'
        ):
            if vals.get('user_id') and vals['user_id'] != self.env.user.id:
                raise AccessError(_('A committee member can only edit their own signature.'))
            if any(signature.user_id != self.env.user for signature in self):
                raise AccessError(_('A committee member can only edit their own signature.'))
            self.mapped('user_input_id')._check_committee_evaluation_scope()
        return super().write(vals)
