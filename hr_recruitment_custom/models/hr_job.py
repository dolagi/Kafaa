from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError

class HrJob(models.Model):
    _name = 'hr.job'
    _inherit = [
        'hr.job',
    ]
    
    description = fields.Html(string='Job Description', sanitize_attributes=False, translate=True)
    requirements = fields.Text('Requirements', translate=True)

    def _address_id_domain(self):
        return [('is_company', '=', True)]
    
    def _default_is_published(self):
        return False
    
    is_published = fields.Boolean('Is Published', copy=False, default=lambda self: self._default_is_published(), index=True)
    exam_id = fields.Many2one(
        'survey.survey',
        string='Job Exam',
        help='Survey/exam assigned to this job position.'
    )
    degree_level = fields.Selection(
        [   
            ('special_first', 'Special First Level'),
            ('special_second', 'Special Second Level'),
            ('special_third', 'Special Third Level'),
            ('first', 'First Level'),
            ('second', 'Second Level'),
            ('third', 'Third Level'),
            ('fourth', 'Fourth Level'),
            ('fifth', 'Fifth Level'),
            ('sixth', 'Sixth Level'),
            ('seventh', 'Seventh Level'),
            ('eighth', 'Eighth Level'),
            ('ninth', 'Ninth Level'),
            ('tenth', 'Tenth Level'),
            ('eleventh', 'Eleventh Level'),
            ('twelfth', 'Twelfth Level'),
            ('thirteenth', 'Thirteenth Level'),
            ('fourteenth', 'Fourteenth Level'),
            ('fifteenth', 'Fifteenth Level'),
            ('sixteenth', 'Sixteenth Level'),
            ('seventeenth', 'Seventeenth Level'),
        ],
        string='Degree Level',
        help='Required degree level for the job position.'
    )
    experience_years = fields.Integer(
        string='Years of Experience',
        help='Minimum years of experience required for the job position.'
    )
    responsibilities = fields.Text(
        string='Responsibilities',
        help='List of responsibilities for the job position.',
        translate=True
    )
    announcement_date = fields.Date(
        string='Announcement Date',
        help='Date when the job was announced.'
    )
    working_period = fields.Selection(
        [
            ('full_time', 'Full Time'),
            ('part_time', 'Part Time'),
        ],
        string='Working Period',
        required=True,
        default='full_time'
    )

    attendance_type = fields.Selection(
        [
            ('onsite', 'On-site'),
            ('remote', 'Remote'),
            ('hybrid', 'Hybrid'),
        ],
        string='Attendance Type',
        required=True,
        default='onsite'
    )
    academic_degree = fields.Selection(
        [
            ('high_school', 'High School'),
            ('diploma', 'Diploma'),
            ('bachelor', 'Bachelor’s Degree'),
            ('master', 'Master’s Degree'),
            ('phd', 'PhD'),
        ],
        string='Academic Degree',
        required=False
    )
    closing_date = fields.Date(
        string='Closing Date',
        help='Date when the job application closes.'
    )
    feedback_survey_id = fields.Many2one(
        'survey.survey',
        string='Feedback Survey',   
    )
    scoring_criteria = fields.Selection([
        ('exam_only', 'Exam Only'),
        ('interview_only', 'Interview Only'),
        ('exam_and_interview', 'Exam and Observation'),
    ], string='Scoring Criteria', default='exam_and_interview', required=True)
    exam_participants_count = fields.Integer(
        compute='_compute_exam_participants_count',
        string='Exam Participants',
    )
    appointed_applicants_count = fields.Integer(
        compute='_compute_appointed_applicants_count',
        string='Appointed Applicants',
    )
    selected_applicant_ids = fields.Many2many(
        'hr.applicant', compute='_compute_selected_applicants',
        string='Selected Applicants',
    )
    selected_applicants_count = fields.Integer(
        compute='_compute_selected_applicants', string='Selected Applicants',
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('closed', 'Closed'),
    ], default='draft', tracking=True)

    @api.constrains('announcement_date')
    def _check_announcement_date_not_in_past(self):
        """A job announcement cannot be dated before today."""
        today = fields.Date.context_today(self)
        for job in self:
            if job.announcement_date and job.announcement_date < today:
                raise ValidationError(_(
                    'The announcement date cannot be earlier than today.'
                ))

    @api.constrains('announcement_date', 'closing_date')
    def _check_closing_date_after_announcement_date(self):
        """The application period must end after the announcement date."""
        for job in self:
            if (
                job.announcement_date
                and job.closing_date
                and job.closing_date <= job.announcement_date
            ):
                raise ValidationError(_(
                    'The closing date must be after the announcement date.'
                ))

    def write(self, vals):
        # Capture old exam_ids before write for recompute triggers
        old_exam_survey_ids = set()
        if 'exam_id' in vals:
            for job in self:
                if job.exam_id:
                    old_exam_survey_ids.add(job.exam_id.id)

        # Publishing is only allowed once the job position has been approved.
        # Keep this server-side check so imports and RPC calls cannot bypass
        # the form-view restriction.
        if vals.get('is_published'):
            unapproved_jobs = self.filtered(lambda job: job.state != 'approved')
            if unapproved_jobs:
                raise ValidationError(_(
                    'A job position must be approved before it can be published.'
                ))

        if 'state' in vals:
            if not self.env.user.has_group(
                'hr_recruitment_custom.group_general_secretariat'
            ):
                raise AccessError(_(
                    'Only the General Secretariat can change a job status.'
                ))
            if vals['state'] == 'closed':
                self._check_can_close()
                if not self.env.context.get('job_close_confirmed'):
                    raise AccessError(_(
                        'Close the job through the confirmation action.'
                    ))
            elif vals['state'] == 'approved' and any(
                job.state != 'draft' for job in self
            ):
                raise ValidationError(_(
                    'Only draft job positions can be approved.'
                ))

        if 'is_published' in vals and vals['is_published'] == True:
            vals['announcement_date'] = fields.Date.today()
        elif (
            'is_published' in vals and vals['is_published'] is False
            and vals.get('state') != 'closed'
        ):
            vals['closing_date'] = fields.Date.today()

        SECRETARIAT_ALLOWED = {'state', 'is_published', 'announcement_date', 'closing_date'}
        unauthorized = set(vals.keys()) - SECRETARIAT_ALLOWED
        if unauthorized and self.env.user.has_group('hr_recruitment_custom.group_general_secretariat'):
            raise AccessError("You are only allowed to change the job status.")

        result = super().write(vals)

        # Recompute applicant_exam_score if exam changed
        if 'exam_id' in vals:
            new_exam_id = vals.get('exam_id')
            if new_exam_id:
                old_exam_survey_ids.add(new_exam_id)
            if old_exam_survey_ids:
                inputs = self.env['survey.user_input'].sudo().search([
                    ('survey_id', 'in', list(old_exam_survey_ids)),
                ])
                if inputs:
                    inputs.invalidate_recordset(['applicant_exam_score'])

        return result
    
    def _compute_exam_participants_count(self):
        UserInput = self.env['survey.user_input']
        for job in self:
            if not job.exam_id:
                job.exam_participants_count = 0
            else:
                job.exam_participants_count = UserInput.search_count([
                    ('survey_id', '=', job.exam_id.id),
                    ('job_id', '=', job.id),
                ])

    def _compute_appointed_applicants_count(self):
        UserInput = self.env['survey.user_input']
        for job in self:
            if not job.survey_id:
                job.appointed_applicants_count = 0
            else:
                job.appointed_applicants_count = UserInput.search_count([
                    ('survey_id', '=', job.survey_id.id),
                    ('job_id', '=', job.id),
                ])

    def _compute_selected_applicants(self):
        Applicant = self.env['hr.applicant']
        for job in self:
            selected = Applicant.search([
                ('job_id', '=', job.id),
                ('stage_id.hired_stage', '=', True),
            ])
            job.selected_applicant_ids = selected
            job.selected_applicants_count = len(selected)

    def action_view_exam_participants(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exam Participants'),
            'res_model': 'survey.user_input',
            'view_mode': 'list,form',
            'domain': [
                ('survey_id', '=', self.exam_id.id),
                ('job_id', '=', self.id),
            ],
            'context': {'default_survey_id': self.exam_id.id},
        }

    def action_view_appointed_applicants(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Appointed Applicants'),
            'res_model': 'survey.user_input',
            'view_mode': 'list,form',
            'domain': [('survey_id', '=', self.survey_id.id), ('job_id', '=', self.id)],
            'context': {'default_survey_id': self.survey_id.id, 'default_job_id': self.id},
        }

    def action_view_selected_applicants(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Selected Applicants'),
            'res_model': 'hr.applicant',
            'view_mode': 'list,form',
            'domain': [
                ('job_id', '=', self.id),
                ('stage_id.hired_stage', '=', True),
            ],
        }

    def action_approve(self):
        if not self.env.user.has_group(
            'hr_recruitment_custom.group_general_secretariat'
        ):
            raise AccessError(_('Only the General Secretariat can approve jobs.'))
        for job in self:
            if job.state != 'draft':
                raise ValidationError(_('Only draft job positions can be approved.'))
            job.write({'state': 'approved'})

    def _check_can_close(self):
        """Closing is allowed only from the approved state."""
        for job in self:
            if job.state != 'approved':
                raise ValidationError(_('Only approved job positions can be closed.'))

    def action_close(self):
        if not self.env.user.has_group(
            'hr_recruitment_custom.group_general_secretariat'
        ):
            raise AccessError(_('Only the General Secretariat can close jobs.'))
        for job in self:
            job._check_can_close()
            return {
                'type': 'ir.actions.act_window',
                'name': _('Confirm Job Closure'),
                'res_model': 'hr.job.close.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_job_id': job.id},
            }

    def _close_job(self):
        """Close an approved job and stop its publication after confirmation."""
        for job in self:
            job._check_can_close()
            job.with_context(job_close_confirmed=True).write({
                'state': 'closed',
                'is_published': False,
            })

    def _action_unpublish_expired_jobs(self):
        """Scheduled action: unpublish jobs whose closing_date has passed."""
        today = fields.Date.today()
        expired_jobs = self.search([
            ('is_published', '=', True),
            ('closing_date', '!=', False),
            ('closing_date', '<=', today),
        ])
        for job in expired_jobs:
            job.write({'is_published': False})
