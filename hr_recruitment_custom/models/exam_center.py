
from odoo import models, fields

class ExamCenter(models.Model):
    _name = 'exam.center'
    _description = 'Exam Center'
    _order = 'name'

    name = fields.Char(string='Location', required=True)
    capacity = fields.Integer(string='Capacity', required=True)
    active = fields.Boolean(default=True)