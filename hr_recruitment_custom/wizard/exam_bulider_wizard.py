import random

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExamBuilderWizard(models.TransientModel):
    _name = 'exam.builder.wizard'
    _description = 'Build Exam From Question Bank'

    name = fields.Char(string='New Exam Name')

    total_time = fields.Float(
        string='Exam Duration (Minutes)',
        
        default=45,
        help='Total time allowed for the generated exam.',
    )
    total_questions_count = fields.Integer(
        string='Total Number of Questions',
        
        help='Maximum number of questions the generated exam may contain. '
             'The sum of questions picked from all source exams below must not exceed this number.',
    )
    passing_score = fields.Float(
        string='Passing Score (%)',
        default=50,
        help='Minimum scoring percentage required to pass the generated exam.',
    )

    line_ids = fields.One2many(
        'exam.builder.wizard.line', 'wizard_id', string='Source Exams'
    )

    selected_questions_count = fields.Integer(
        string='Selected Questions',
        compute='_compute_selected_questions_count',
    )

    @api.depends('line_ids.questions_count')
    def _compute_selected_questions_count(self):
        for wizard in self:
            wizard.selected_questions_count = sum(
                wizard.line_ids.mapped('questions_count')
            )

    # ── Validation ───────────────────────────────────────────────────────
    @api.constrains('line_ids', 'total_questions_count')
    def _check_total_questions_count(self):
        for wizard in self:
            selected = sum(wizard.line_ids.mapped('questions_count'))
            if selected > wizard.total_questions_count:
                raise ValidationError(_(
                    'The number of questions selected from the source exams (%(selected)s) '
                    'exceeds the total number of questions allowed for this exam (%(total)s).'
                ) % {
                    'selected': selected,
                    'total': wizard.total_questions_count,
                })

    def _check_availability(self):
        self.ensure_one()
        for line in self.line_ids:
            if line.questions_count > line.available_questions_count:
                raise ValidationError(_(
                    'Source exam "%(survey)s" only has %(available)s scorable question(s), '
                    'but %(requested)s were requested.'
                ) % {
                    'survey': line.source_survey_id.title,
                    'available': line.available_questions_count,
                    'requested': line.questions_count,
                })

    # ── Action ───────────────────────────────────────────────────────────
    def action_confirm(self):
        self.ensure_one()

        if not self.line_ids:
            raise ValidationError(_('Please add at least one source exam.'))

        self._check_total_questions_count()
        self._check_availability()

        new_survey = self.env['survey.survey'].create({
            'title': self.name,
            'survey_type': 'assessment',
            'scoring_type': 'scoring_with_answers',
            'scoring_success_min': self.passing_score,
            'is_time_limited': True,
            'time_limit': self.total_time,
            'questions_selection': 'random',
            'access_mode': 'public',
        })

        sequence = 1
        for line in self.line_ids:
            # Create the section (page) that will hold this source exam's questions.
            # random_questions_count = questions_count so that, under 'random'
            # selection mode, every question we picked for this section is used
            # (only their order gets shuffled per user via shared_question_ids).
            self.env['survey.question'].create({
                'survey_id': new_survey.id,
                'title': line.section_name,
                'is_page': True,
                'sequence': sequence,
                'random_questions_count': line.questions_count,
            })
            sequence += 1

            source_questions = line.source_survey_id.question_ids.filtered(
                lambda q: not q.is_page and q.question_type == 'simple_choice'
            )
            picked = random.sample(list(source_questions), line.questions_count)

            for question in picked:
                new_question = question.copy({
                    'survey_id': new_survey.id,
                    'sequence': sequence,
                })

                if new_question.question_type != 'simple_choice':
                    raise ValidationError(_(
                        'Question "%(title)s" from source exam "%(survey)s" is not a '
                        'single-choice question. This wizard only supports simple_choice '
                        'questions.'
                    ) % {
                        'title': new_question.title,
                        'survey': line.source_survey_id.title,
                    })

                new_question.write({'is_scored_question': True})

                # For single-choice questions, the actual score lives on
                # each suggested answer, not on the question itself.
                new_question.suggested_answer_ids.filtered('is_correct').write({
                    'answer_score': line.score_per_question,
                })
                new_question.suggested_answer_ids.filtered(lambda a: not a.is_correct).write({
                    'answer_score': 0,
                })

                sequence += 1

        return {
            'type': 'ir.actions.act_window',
            'name': _('Generated Exam'),
            'res_model': 'survey.survey',
            'view_mode': 'form',
            'res_id': new_survey.id,
        }


class ExamBuilderWizardLine(models.TransientModel):
    _name = 'exam.builder.wizard.line'
    _description = 'Exam Builder Source Line'

    wizard_id = fields.Many2one(
        'exam.builder.wizard', required=True, ondelete='cascade'
    )
    source_survey_id = fields.Many2one(
        'survey.survey',
        string='Source Exam',
        domain=[('survey_type', '=', 'custom')],
        help='One of the exams in the question bank.',
    )
    section_name = fields.Char(
        string='Section Name',
        help='The section (page) title that will group this source exam\'s '
             'questions inside the generated exam, e.g. "Example: Subject Exam Section / Aptitude Section".',
    )
    available_questions_count = fields.Integer(
        string='Available Questions',
        compute='_compute_available_questions_count',
    )
    questions_count = fields.Integer(
        string='Number of Questions to Pick',
    )
    score_per_question = fields.Float(
        string='Score per Question',
    )

    @api.depends('source_survey_id')
    def _compute_available_questions_count(self):
        for line in self:
            line.available_questions_count = len(
                line.source_survey_id.question_ids.filtered(
                    lambda q: not q.is_page and q.question_type == 'simple_choice'
                )
            )

    @api.constrains('questions_count', 'available_questions_count')
    def _check_line_questions_count(self):
        for line in self:
            if line.source_survey_id and line.questions_count > line.available_questions_count:
                raise ValidationError(_(
                    'Source exam "%(survey)s" only has %(available)s question(s) available.'
                ) % {
                    'survey': line.source_survey_id.title,
                    'available': line.available_questions_count,
                })