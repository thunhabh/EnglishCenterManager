from odoo import api, fields, models, exceptions

class ClassSession(models.Model):
    _name = 'class.session'
    _description = 'Class Session (Timeline)'
    _order = 'start_datetime asc'

    name = fields.Char(string="Session Name", compute='_compute_name', store=True)
    class_id = fields.Many2one('center.class', string="Class", ondelete='cascade')
    sequence = fields.Integer(string="Session Number")

    start_datetime = fields.Datetime(string="Start Time", required=True)
    end_datetime = fields.Datetime(string="End Time", required=True)

    teacher_id = fields.Many2one('center.teacher', related='class_id.teacher_id', store=True, string="Teacher")
    student_ids = fields.Many2many('center.student', related='class_id.student_ids', string="Students")

    @api.depends('class_id', 'sequence')
    def _compute_name(self):
        for record in self:
            if record.class_id:
                record.name = f"{record.class_id.name} - Session {record.sequence}"
