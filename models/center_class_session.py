
from odoo import api, fields, models, exceptions
from odoo.orm.fields_temporal import Datetime


class ClassSession(models.Model):
    _name = 'class.session'
    _description = 'Class Session (Timeline)'
    _order = 'start_datetime asc'

    name = fields.Char(string="Session Name", compute='_compute_name', store=True)
    #Class delete -> Sessions delete
    class_id = fields.Many2one('center.class', string="Class", ondelete='cascade')
    classroom_id = fields.Many2one('center.classroom', related="class_id.classroom_id", string="Classroom")

    sequence = fields.Integer(string="Session Number")

    start_datetime = fields.Datetime(string="Start Time", required=True)
    end_datetime = fields.Datetime(string="End Time", required=True)

    teacher_id = fields.Many2one('hr.employee', related='class_id.teacher_id', store=True, string="Teacher")
    student_ids = fields.Many2many('center.student', related='class_id.student_ids', string="Students")

    is_accounted = fields.Boolean(string="Is Accounted", default=False, index=True)

    def cron_add_debt_passed_sessions(self):
        now_utc = Datetime.now()
        passed_sessions = self.search([
            ('end_datetime', '<', now_utc),
            ('is_accounted', '=', False),
            ('class_id.state', '=', 'active')
        ])

        history_obj = self.env['center.debt.history']

        for session in passed_sessions:
            session_price = session.class_id.course_id.price_per_session

            for student in session.class_id.student_ids:
                student.debt += session_price

                history_obj.create({
                    'student_id': student.id,
                    'class_id': session.class_id.id,
                    'session_id': session.id,
                    'amount': session_price
                })

            session.is_accounted = True

    @api.depends('class_id', 'sequence')
    def _compute_name(self):
        for record in self:
            if record.class_id:
                record.name = f"{record.class_id.name} - Session {record.sequence}"
