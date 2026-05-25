from odoo import api, fields, models, exceptions
from odoo.exceptions import ValidationError, AccessError


class CenterStudent(models.Model):
    _name = 'center.student'
    _description = 'Student Profiles'

    name = fields.Char(string="Student Name", required=True)
    email = fields.Char(string="Login Email", required=True)
    parent_name = fields.Char(string="Parent Name", required=True)
    parent_phone = fields.Char(string="Parent Phone", required=True)

    user_id = fields.Many2one('res.users', string='Student Account', ondelete='cascade')
    credit = fields.Integer(string="Credits (Sessions left)", default=0)
    debt = fields.Float(string="Debt Balance", default=0.0)

    class_ids = fields.Many2many('center.class', string="Enrolled Classes")

    _check_unique = models.Constraint(
        'UNIQUE(email)',
        'This email already exists in the system.',
    )

    @api.constrains('parent_phone')
    def _check_student_constraints(self):
        for rec in self:
            if not rec.parent_phone.isdigit() or len(rec.parent_phone) != 10:
                raise ValidationError("Parent's phone number must contain exactly 10 digits.")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('base.group_erp_manager'):
            raise AccessError("Strict Security: Only Administrators are allowed to create new students.")

        for vals in vals_list:
            email = vals.get('email')
            if email:
                existing_user = self.env['res.users'].search([('login', '=', email)])
                if existing_user:
                    raise ValidationError(f"Email '{email}' is already registered as a user account!")

                student_group = self.env.ref('english_center.group_center_student')
                internal_user_group = self.env.ref('base.group_user')

                user_vals = {
                    'name': vals.get('name'),
                    'login': email,
                    'password': '12345678',
                    'email': email,
                    'group_ids': [(6, 0, [student_group.id, internal_user_group.id])],
                }

                new_user = self.env['res.users'].create(user_vals)
                vals['user_id'] = new_user.id

        return super(CenterStudent, self).create(vals_list)

    def action_view_student_schedule(self):
        """ Open the study schedule for this student """
        return {
            'name': 'Study Schedule',
            'type': 'ir.actions.act_window',
            'res_model': 'class.session',
            'view_mode': 'calendar,list',
            'domain': [('student_ids', 'in', self.id)],
            'context': {'default_student_ids': [(4, self.id)]},
        }

    def write(self, vals):
        if 'email' in vals and self.env.user.has_group('english_center.group_center_student'):
            raise ValidationError("You are not allowed to change your registered email address!")

        return super(CenterStudent, self).write(vals)