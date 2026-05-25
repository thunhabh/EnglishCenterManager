from odoo import fields, models, api
from odoo.exceptions import ValidationError


class CenterTeacher(models.Model):
    _name = 'center.teacher'
    _description = 'Teacher Profile'

    name = fields.Char(string="Teacher Name", required=True)
    user_id = fields.Many2one('res.users', string='Linked Account', readonly=True)

    work_email = fields.Char(string="Work Email", required=True)
    work_phone = fields.Char(string="Work Phone", required=True)
    identification_id = fields.Char(required=True, string="National ID")

    expertise = fields.Selection(
        string='Expertise',
        required=True,
        selection=[
            ('primary', "Primary School"),
            ('secondary', "Secondary School"),
            ('highschool', "High School"),
            ('college', "College"),
            ('ielts', 'IELTS')
        ]
    )

    certificate_tag_ids = fields.Many2many("center.certificate.tag", string="Certificates", required=True)

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
                    'group_ids': [(4, teacher_group.id)],
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
            'domain': [('teacher_id', '=', self.id)],
            'context': {'default_teacher_id': self.id},
        }