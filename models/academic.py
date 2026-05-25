from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CenterAssignment(models.Model):
    _name = 'center.assignment'
    _description = 'Class Assignments & Materials'

    name = fields.Char(string="Title", required=True)
    class_id = fields.Many2one('center.class', string="Class", required=True)
    teacher_id = fields.Many2one('center.teacher', related='class_id.teacher_id', store=True, string="Teacher")

    description = fields.Html(string="Requirements")
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")

    due_date = fields.Datetime(string="Deadline")
    submission_ids = fields.One2many('center.submission', 'assignment_id', string="Submissions")

    state_for_student = fields.Selection([
            ('submitted', 'Submitted'),
            ('pending', 'Pending'),
            ('overdue', 'Overdue'),
            ('graded', 'Graded')
    ], compute='_compute_states')

    state_for_teacher = fields.Selection([
            ('all_submitted', 'All Submitted'),
            ('partial', 'Partial'),
            ('overdue', 'Overdue'),
            ('finished', 'Finished')
    ], compute='_compute_states')

    def _compute_states(self):
        for record in self:
            user_id = self.env.user.id
            sub = record.submission_ids.filtered(lambda s: s.student_id.user_id.id == user_id)

            if sub and sub.score:
                record.state_for_student = 'graded'
            elif sub:
                record.state_for_student = 'submitted'
            elif record.due_date and record.due_date < fields.Datetime.now():
                record.state_for_student = 'overdue'
            else:
                record.state_for_student = 'pending'

            total_students = len(record.class_id.student_ids)
            submitted_count = len(record.submission_ids)
            graded_count = len(record.submission_ids.filtered(lambda s: s.score >= 0))

            if graded_count == total_students and total_students > 0:
                record.state_for_teacher = 'finished'
            elif submitted_count == total_students and total_students > 0:
                record.state_for_teacher = 'all_submitted'
            elif record.due_date and record.due_date < fields.Datetime.now():
                record.state_for_teacher = 'overdue'
            else:
                record.state_for_teacher = 'partial'


class CenterSubmission(models.Model):
    _name = 'center.submission'
    _description = 'Student Submissions'

    assignment_id = fields.Many2one('center.assignment', string="Assignment", required=True, ondelete='cascade')

    student_id = fields.Many2one('center.student', string="Student", required=True,
                                 default=lambda self: self._default_student())

    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachment File',
        required=True
    )
    file_name = fields.Char(string="File Name")

    submission_date = fields.Datetime(string="Submission date", default=fields.Datetime.now)

    score = fields.Float(string="Grade", default = -1)
    feedback = fields.Text(string="Teacher Feedback")

    def _default_student(self):
        if self.env.user.has_group('english_center.group_center_student'):
            student = self.env['center.student'].search([('user_id', '=', self.env.uid)], limit=1)
            return student.id
        return False

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.has_group('english_center.group_center_student'):
            for vals in vals_list:
                if vals.get('score') or vals.get('feedback'):
                    raise ValidationError("Security Alert: You cannot grade your own submission!")
        return super(CenterSubmission, self).create(vals_list)

    def write(self, vals):
        if self.env.user.has_group('english_center.group_center_student'):
            if 'score' in vals or 'feedback' in vals:
                raise ValidationError("Security Alert: You cannot alter the teacher's grade or feedback!")
        return super(CenterSubmission, self).write(vals)