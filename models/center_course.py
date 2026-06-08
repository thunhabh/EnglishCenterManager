from odoo import fields, models, api
from odoo.exceptions import ValidationError
from odoo.fields import Command


class CenterCourse(models.Model):
    _name = 'center.course'
    _description = 'Course Template'

    name = fields.Char(string="Course Name", required=True)
    total_sessions = fields.Integer(string="Total Sessions", required=True)
    description = fields.Text(string="Course Description")
    class_ids = fields.One2many('center.class', 'course_id', string="Classes")
    price_per_session = fields.Float(string="Price per Session", required=True, default=100000.0)
    total_revenue = fields.Float(string="Total Revenue", compute="_compute_total_revenue")

    total_classes = fields.Integer(string="Total Classes", compute='_compute_total_classes', store=True)

    @api.depends('class_ids')
    def _compute_total_classes(self):
        for record in self:
            record.total_classes = len(record.class_ids)

    @api.depends('class_ids.total_revenue')
    def _compute_total_revenue(self):
        for course in self:
            course.total_revenue = sum(course.class_ids.mapped('total_revenue'))

    registered_student_ids = fields.Many2many(
        'center.student',
        'course_student_registration_rel',
        'course_id', 'student_id',
        string="Waiting Students"
    )
    registered_count = fields.Integer(string="Number of register", compute="_compute_registered_count")

    @api.depends('registered_student_ids')
    def _compute_registered_count(self):
        for rec in self:
            rec.registered_count = len(rec.registered_student_ids)

    def action_open_register_wizard(self):
        self.ensure_one()
        is_student = self.env.user.has_group('english_center.group_center_student')
        default_student_id = False

        if is_student:
            student = self.env['center.student'].search([('user_id', '=', self.env.uid)], limit=1)
            if student:
                default_student_id = student.id

        return {
            'name': 'Course Registration',
            'type': 'ir.actions.act_window',
            'res_model': 'center.course.register.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_course_id': self.id,
                'default_student_id': default_student_id,
            }
        }


class CenterCourseRegisterWizard(models.TransientModel):
    _name = 'center.course.register.wizard'
    _description = 'Course Registration Wizard'

    course_id = fields.Many2one('center.course', string="Course", required=True, readonly=True)
    student_id = fields.Many2one('center.student', string="Student", required=True)
    is_student_user = fields.Boolean(compute='_compute_is_student')

    @api.depends()
    def _compute_is_student(self):
        for rec in self:
            rec.is_student_user = self.env.user.has_group('english_center.group_center_student')

    def action_confirm(self):
        self.ensure_one()
        if self.student_id in self.course_id.registered_student_ids:
            raise ValidationError(f"Student {self.student_id.name} has already been registered!")

        self.course_id.sudo().registered_student_ids = [Command.link(self.student_id.id)]

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Registered for {self.course_id.name}!',
                'type': 'success',
                'sticky': False,
            }
        }