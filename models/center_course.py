from odoo import fields, models, api


class CenterCourse(models.Model):
    _name = 'center.course'
    _description = 'Course Template'

    name = fields.Char(string="Course Name", required=True)
    total_sessions = fields.Integer(string="Total Sessions", required=True)
    description = fields.Text(string="Course Description")
    class_ids = fields.One2many('center.class', 'course_id', string="Classes")

    total_classes = fields.Integer(string="Total Classes", compute='_compute_total_classes', store=True)

    @api.depends('class_ids')
    def _compute_total_classes(self):
        for record in self:
            record.total_classes = len(record.class_ids)