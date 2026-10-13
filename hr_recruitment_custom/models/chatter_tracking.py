import hashlib

from odoo import api, fields, models, _
from markupsafe import Markup, escape


TRACKED_MODELS = frozenset({
    'hr.job', 'hr.applicant', 'hr.candidate', 'hr.candidate.skill',
    'hr.recruitment.stage', 'candidate.education', 'candidate.work.experience',
    'candidate.language', 'candidate.specialization', 'exam.center',
    'survey.survey', 'survey.question', 'survey.question.answer',
    'survey.user_input', 'survey.user_input.line', 'survey.user_input.signature',
    'hr.selection.decision', 'news.news', 'res.company', 'res.partner',
    'hr.recruitment.source',
})


class RecruitmentChatterTracking(models.AbstractModel):
    _inherit = 'base'

    def _recruitment_queue_question_summary(self):
        for record in self:
            if self._name == 'survey.question' and record.is_page:
                continue
            survey = record.survey_id if self._name == 'survey.question' else (
                record.question_id or record.matrix_question_id
            ).survey_id
            if not survey:
                continue
            key = 'recruitment.questions.%s.%s' % (survey.id, self.env.uid)
            pending = self.env.cr.precommit.data
            if key not in pending:
                pending[key] = {'questions': set(), 'choices': set()}

                def post_summary(survey=survey, key=key, author=self.env.user.partner_id.id):
                    changes = self.env.cr.precommit.data.pop(key, None)
                    if changes and survey.exists():
                        text = _(
                            'Exam content updated: %(questions)s questions, %(choices)s answer choices.',
                            questions=len(self.env['survey.question'].sudo().browse(
                                list(changes['questions'])
                            ).exists().filtered(lambda question: not question.is_page and question.survey_id == survey)),
                            choices=len(changes['choices']),
                        )
                        survey.sudo().with_context(mail_create_nosubscribe=True).message_post(
                            body=text, subtype_xmlid='mail.mt_note', author_id=author,
                        )

                self.env.cr.precommit.add(post_summary)
            bucket = 'questions' if self._name == 'survey.question' else 'choices'
            pending[key][bucket].add(record.id)

    def _recruitment_chatter_snapshot(self, field_names=None):
        snapshots = {}
        for record in self.sudo().with_context(bin_size=False):
            values = {}
            for name, field in record._fields.items():
                if (
                    (field_names is not None and name not in field_names)
                    or
                    not field.store or (field.compute and name not in {
                        'scoring_percentage', 'scoring_total', 'scoring_success',
                        'answer_score', 'answer_is_correct',
                    })
                    or name in {'id', 'create_uid', 'write_uid', 'create_date', 'write_date'}
                    or name.startswith(('message_', 'activity_', 'website_message_', 'alias_'))
                    or any(part in name.lower() for part in ('password', 'token', 'secret', 'api_key'))
                ):
                    continue
                value = record[name]
                if field.type in ('many2one', 'many2many', 'one2many'):
                    value = {'ids': value.ids, 'label': ', '.join(value.mapped('display_name'))}
                elif field.type == 'binary' and value:
                    content = value.encode() if isinstance(value, str) else value
                    value = {'sha256': hashlib.sha256(content).hexdigest()}
                elif field.type in ('date', 'datetime') and value:
                    value = str(value)
                values[name] = value
            snapshots[record.id] = values
        return snapshots

    def _recruitment_chatter_value(self, field, value):
        if isinstance(value, dict):
            if 'label' in value:
                return value['label'] or _('Not set')
            return _('File updated')
        if field and field.type == 'boolean':
            return _('Yes') if value else _('No')
        if value is False or value is None or value == '':
            return _('Not set')
        if field and field.type == 'selection':
            return dict(field._description_selection(self.env)).get(value, str(value))
        text = str(value)
        return text[:160] + '…' if len(text) > 160 else text

    def _recruitment_chatter_append(self, operation, before, after):
        if self._name in {'survey.question', 'survey.question.answer'}:
            self._recruitment_queue_question_summary()
            return
        labels = {'create': _('Created'), 'write': _('Updated'),
                  'approve': _('Approved')}
        for record in self:
            old, new = before.get(record.id, {}), after.get(record.id, {})
            changed = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
            if not changed and operation != 'create':
                continue
            op = operation
            if operation == 'write' and old.get('state') != new.get('state') and new.get('state') == 'approved':
                op = 'approve'
            target = record
            if not hasattr(target, 'message_post'):
                parent_fields = ('user_input_id', 'candidate_id', 'survey_id', 'question_id')
                for field in parent_fields:
                    if field in target._fields and target[field]:
                        target = target[field]
                        if hasattr(target, 'message_post'):
                            break
                        if 'survey_id' in target._fields:
                            target = target.survey_id
                            break
            if not hasattr(target, 'message_post'):
                continue
            # mail.thread already posts the creation message for its own record.
            if operation == 'create' and target == record:
                continue
            lines = []
            for name in changed:
                if self._name == 'survey.survey' and name in {'question_ids', 'question_and_page_ids'}:
                    continue
                field = record._fields.get(name)
                # Let standard Odoo tracking display fields it already tracks.
                if target == record and field and getattr(field, 'tracking', False):
                    continue
                label = field._description_string(self.env) if field else name
                lines.append(Markup('<li>%s: %s → %s</li>') % (
                    escape(label), escape(record._recruitment_chatter_value(field, old.get(name))),
                    escape(record._recruitment_chatter_value(field, new.get(name))),
                ))
            if not lines and operation != 'create':
                continue
            body = Markup('<p>%s — %s</p><ul>%s</ul>') % (
                escape(labels[op]), escape(record.display_name),
                Markup('').join(lines),
            )
            if operation == 'create':
                body = Markup('<p>%s — %s</p>') % (escape(labels[op]), escape(record.display_name))
            target.sudo().with_context(mail_create_nosubscribe=True).message_post(
                body=body, subtype_xmlid='mail.mt_note',
                author_id=self.env.user.partner_id.id,
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self._name in TRACKED_MODELS:
            records._recruitment_chatter_append('create', {}, {})
        return records

    def write(self, vals):
        audited = self._name in TRACKED_MODELS
        before = self._recruitment_chatter_snapshot(set(vals)) if audited else {}
        result = super().write(vals)
        if audited:
            self._recruitment_chatter_append('write', before, self._recruitment_chatter_snapshot(set(vals)))
        return result
