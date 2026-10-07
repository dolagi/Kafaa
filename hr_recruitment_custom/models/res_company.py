from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    secretary_general_name = fields.Char(
        string='Secretary General Name',
        help='Name of the Secretary General of the company, used in decision letters for selected candidates.'
    )