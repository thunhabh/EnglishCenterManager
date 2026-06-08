from odoo import fields, models, api
from odoo.fields import Command
from odoo.exceptions import ValidationError, AccessError


class CenterTeacher(models.Model):
    _inherit = 'hr.employee'
    _description = 'Teacher Profile'

    _check_unique_email = models.Constraint('UNIQUE(work_email)', 'The email must be unique.')
    _check_unique_phone = models.Constraint('UNIQUE(work_phone)', 'The phone number must be unique.')
    _check_unique_cccd = models.Constraint('UNIQUE(identification_id)', 'National ID must be unique.')

    @api.constrains('work_phone')
    def _check_phone(self):
        for record in self:
            if record.work_phone and (not record.work_phone.isdigit() or len(record.work_phone) != 10):
                raise ValidationError("A valid phone number with 10 digits is required.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('base.group_erp_manager'):
            raise AccessError("Strict Security: Only Administrators are allowed to create new teachers.")

        for vals in vals_list:
            email = vals.get('work_email')
            if email:
                existing_user = self.env['res.users'].search([('login', '=', email)])
                if existing_user:
                    raise ValidationError(f"Email '{email}' is already registered as a user account!")

                teacher_group = self.env.ref('english_center.group_center_teacher')
                user_vals = {
                    'name': vals.get('name'),
                    'login': email,
                    'password': '12345678',
                    'email': email,
                    'group_ids': [Command.link([teacher_group.id])]
                }
                new_user = self.env['res.users'].create(user_vals)
                vals['user_id'] = new_user.id

        return super(CenterTeacher, self).create(vals_list)

    def action_view_teacher_schedule(self):
        return {
            'name': 'Teaching Schedule',
            'type': 'ir.actions.act_window',
            'res_model': 'class.session',
            'view_mode': 'calendar,list',
            'domain': [('class_id.teacher_id', '=', self.id)],
            'context': {'default_teacher_id': self.id},
        }

    @api.model
    def action_open_teacher_profile(self):
        teacher = self.search([('user_id', '=', self.env.uid)], limit=1)
        if teacher:
            return {
                'type': 'ir.actions.act_window',
                'name': 'My Profile',
                'res_model': 'hr.employee',
                'view_mode': 'form',
                'res_id': teacher.id,
                'target': 'current',
                'view_id': self.env.ref('english_center.view_center_teacher_form_clean').id,
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Access Denied',
                'message': 'Your Account is not linked to any teacher!',
                'type': 'danger',
                'sticky': False,
            }
        }
