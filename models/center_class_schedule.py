from odoo import fields, models, api
from odoo.exceptions import ValidationError


class CenterClassSchedule(models.Model):
    _name = 'center.class.schedule'
    _description = 'Class Weekly Schedule'

    class_id = fields.Many2one('center.class', string="Class", ondelete='cascade')
    day_of_week = fields.Selection([
        ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
        ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday')
    ], string="Day of Week", required=True)
    start_time = fields.Float(string="Start Time", required=True)
    end_time = fields.Float(string="End Time", required=True)

    @api.constrains('start_time', 'end_time')
    def _check_time(self):
        for record in self:
            if record.start_time >= record.end_time:
                raise ValidationError("Start time must be earlier than End time.")