from odoo import models, fields


class News(models.Model):
    _name = 'news.news'
    _description = 'News'
    _order = 'create_date desc'
    _rec_name = 'title'

    title = fields.Char(string='Title', required=True, translate=True)
    content = fields.Html(string='Content', translate=True)
    image = fields.Binary(string='Image', attachment=True)
    is_published = fields.Boolean(string='Publish', default=False)