from datetime import timedelta, datetime, time

import pytz

from odoo import api, fields, models, exceptions
from odoo.exceptions import ValidationError


class CenterClass(models.Model):
    _name = 'center.class'
    _description = 'Running Class'

    name = fields.Char(string="Class Code", readonly=True, copy=False, default='New')
    course_id = fields.Many2one('center.course', string="Course", required=True)

    state = fields.Selection([
        ('recruiting', 'Recruiting'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], string="Status", default='recruiting')

    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", readonly=True)

    schedule_ids = fields.One2many('center.class.schedule', 'class_id', string="Weekly Schedule")

    student_ids = fields.Many2many('center.student', string="Students")
    session_ids = fields.One2many('class.session', 'class_id', string="Sessions Timeline")

    assignment_ids = fields.One2many('center.assignment', 'class_id', string="Assignments")
    available_teacher_ids = fields.Many2many('center.teacher', compute='_compute_available_teachers')
    teacher_id = fields.Many2one(
        'center.teacher',
        string="Teacher",
        domain="[('id', 'in', available_teacher_ids)]"
    )
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('course_id') and vals.get('start_date'):
                course = self.env['center.course'].browse(vals['course_id'])
                start_date = fields.Date.from_string(vals['start_date'])
                vals['name'] = f"{course.name} - {start_date.strftime('%m/%Y')}"
        return super(CenterClass, self).create(vals_list)

    @api.depends('schedule_ids.day_of_week', 'schedule_ids.start_time', 'schedule_ids.end_time')
    def _compute_available_teachers(self):
        for record in self:
            all_teachers = self.env['center.teacher'].search([])

            if not record.schedule_ids:
                record.available_teacher_ids = all_teachers.ids
                continue

            qualified = []
            for teacher in all_teachers:
                is_overlap = False

                busy_classes = self.env['center.class'].search([
                    ('id', '!=', record._origin.id if record._origin else record.id),
                    ('state', '=', 'active'),
                    ('teacher_id', '=', teacher.id)
                ])

                for busy_class in busy_classes:
                    for busy_sched in busy_class.schedule_ids:
                        for current_sched in record.schedule_ids:
                            # Nếu trùng Thứ
                            if str(busy_sched.day_of_week) == str(current_sched.day_of_week):
                                # Kiểm tra xem giờ có đè lên nhau không
                                if current_sched.start_time < busy_sched.end_time and current_sched.end_time > busy_sched.start_time:
                                    is_overlap = True
                                    break
                        if is_overlap: break
                    if is_overlap: break

                # Nếu không trùng bất kỳ giờ của lớp nào khác -> Đủ điều kiện dạy lớp này
                if not is_overlap:
                    qualified.append(teacher.id)

            record.available_teacher_ids = qualified

    @api.constrains('student_ids', 'schedule_ids')
    def _check_student_schedule_overlap(self):
        """ Prevent assigning a student to classes with overlapping schedules. """
        for record in self:
            if record.state == 'closed' or not record.schedule_ids:
                continue

            for student in record.student_ids:
                # Find other active/recruiting classes this student is enrolled in
                overlapping_classes = self.env['center.class'].search([
                    ('id', '!=', record.id),
                    ('state', 'in', ['recruiting', 'active']),
                    ('student_ids', 'in', student.id)
                ])

                for other_class in overlapping_classes:
                    for my_sched in record.schedule_ids:
                        for other_sched in other_class.schedule_ids:
                            # Check overlap on the same day of the week
                            if str(my_sched.day_of_week) == str(other_sched.day_of_week):
                                if my_sched.start_time < other_sched.end_time and my_sched.end_time > other_sched.start_time:
                                    raise ValidationError(
                                        f"Student '{student.name}' has a schedule conflict with class '{other_class.name}'.")

    def action_active_class(self):
        """ Generate physical sessions based on schedule lines and timezone """
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')

        def float_to_time(f):
            h = int(f)
            m = int(round((f - h) * 60))
            if m == 60:
                h, m = h + 1, 0
            return time(hour=h, minute=m)

        for rec in self:
            if not rec.teacher_id:
                raise ValidationError("Please select a Teacher.")
            if not rec.schedule_ids:
                raise ValidationError("Please configure at least one schedule slot.")

            rec.state = 'active'
            rec.session_ids.unlink()

            current_date = rec.start_date
            session_count = 0

            while session_count < rec.course_id.total_sessions:
                weekday_str = str(current_date.weekday())
                # Find if current date matches any configured schedule day
                schedules = rec.schedule_ids.filtered(lambda s: s.day_of_week == weekday_str)

                for sched in schedules:
                    if session_count >= rec.course_id.total_sessions:
                        break
                    session_count += 1

                    # Convert to local timezone datetime
                    start_local = user_tz.localize(datetime.combine(current_date, float_to_time(sched.start_time)))
                    end_local = user_tz.localize(datetime.combine(current_date, float_to_time(sched.end_time)))

                    # Convert to UTC to store properly in Database
                    start_utc = start_local.astimezone(pytz.UTC).replace(tzinfo=None)
                    end_utc = end_local.astimezone(pytz.UTC).replace(tzinfo=None)

                    self.env['class.session'].create({
                        'class_id': rec.id,
                        'sequence': session_count,
                        'start_datetime': start_utc,
                        'end_datetime': end_utc,
                    })
                current_date += timedelta(days=1)

            rec.end_date = current_date - timedelta(days=1)