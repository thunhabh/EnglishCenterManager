from odoo import fields, models


class CenterCertificateTag(models.Model):
    _name = 'center.certificate.tag'
    _description = 'Teacher certificate tag'
    _order = 'name'

    _check_unique = models.Constraint(
        'UNIQUE(name)',
        'The type of certificate must be unique.',
    )

    name = fields.Char(required=True)
    color = fields.Integer(string="Color")