from odoo import api, fields, models


class CenterClassroom(models.Model):
    _name = 'center.classroom'
    _description = 'Center Classroom'
    _order = 'name'
    _check_unique_name =models.Constraint(
        "UNIQUE(name)",
        "This classroom is already in the database."
    )
    floor = fields.Integer(required=True)
    direction = fields.Selection(required =True, selection=[('north', 'North'),
                                            ('south', 'South'),
                                            ('east', 'East'),
                                            ('west', 'West'),])
    name = fields.Char(compute='_compute_name', store=True)
    class_ids = fields.One2many('center.class', 'classroom_id')
    total_classes = fields.Integer(compute='_compute_total_classes')

    @api.depends('floor', 'direction')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.floor} - {record.direction}"

    @api.depends('class_ids')
    def _compute_total_classes(self):
        for record in self:
            record.total_classes = len(record.class_ids)

    def action_view_classroom_schedule(self):
        return {
            'name': f'Schedule for Room {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'class.session',
            'view_mode': 'calendar,list',
            'domain': [('class_id.classroom_id', '=', self.id)],
            'context': {},
        }