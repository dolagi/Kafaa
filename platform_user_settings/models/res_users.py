from odoo import api, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form':
            field_name = 'in_group_%s' % self.env.ref('base.group_multi_company').id
            for node in arch.xpath('//field[@name=$name] | //label[@for=$name]', name=field_name):
                node.set('invisible', '1')
        return arch, view

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        result = super().fields_get(allfields=allfields, attributes=attributes)
        internal = self.env.ref('base.group_user')
        user_type_ids = {
            internal.id,
            self.env.ref('base.group_portal').id,
            self.env.ref('base.group_public').id,
        }
        for name, definition in result.items():
            if not name.startswith('sel_groups_'):
                continue
            group_ids = {int(group_id) for group_id in name[len('sel_groups_'):].split('_')}
            if group_ids == user_type_ids and 'selection' in definition:
                definition['selection'] = [
                    option for option in definition['selection']
                    if option[0] == internal.id
                ]
        return result
