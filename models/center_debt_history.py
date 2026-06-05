from odoo import models, fields, api
from datetime import datetime

class CenterDebtHistory(models.Model):
    _name = 'center.debt.history'
    _description = 'Student Debt & Revenue Logs'
    _order = 'execution_date desc'

    student_id = fields.Many2one('center.student', string="Student", required=True, readonly=True)
    class_id = fields.Many2one('center.class', string="Class", required=True, readonly=True)
    course_id = fields.Many2one('center.course', string="Course", related='class_id.course_id', store=True)
    session_id = fields.Many2one('class.session', string="Session", required=True, readonly=True)

    amount = fields.Float(string="Bill Added", required=True, readonly=True)
    execution_date = fields.Datetime(string="Recorded Time", default=fields.Datetime.now, readonly=True)
