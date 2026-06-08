from datetime import timedelta, datetime, time

import pytz

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command


class CenterClass(models.Model):
    _name = 'center.class'
    _description = 'Manage Classes'

    #Name will be generated when create = The Course Template's Name + mm/yy
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

    available_student_ids = fields.Many2many(
        'center.student',
        relation='class_available_student_rel',  # naming relation avoiding duplication
        compute='_compute_available_students'
    )

    student_ids = fields.Many2many(
        'center.student',
        string="Students",
        domain="[('id', 'in', available_student_ids)]"
    )
    session_ids = fields.One2many('class.session', 'class_id', string="Sessions Timeline")

    available_classroom_ids = fields.Many2many(
        'center.classroom',
        compute='_compute_available_classrooms'
    )
    classroom_id = fields.Many2one('center.classroom',
                                   string="Classroom",
                                   domain="[('id', 'in', available_classroom_ids)]")

    assignment_ids = fields.One2many('center.assignment', 'class_id', string="Assignments")

    available_teacher_ids = fields.Many2many('hr.employee', compute='_compute_available_teachers')
    teacher_id = fields.Many2one(
        'hr.employee',
        string="Teacher",
        domain="[('id', 'in', available_teacher_ids)]"
    )

    total_revenue = fields.Float(string="Class Revenue", compute="_compute_class_revenue")

    overlap_warning_html = fields.Html(string="Schedule checking", readonly=True)

    @api.onchange('schedule_ids', 'start_date', 'end_date', 'student_ids')
    def _onchange_check_student_overlaps(self):
        for rec in self:
            if not rec.schedule_ids or not rec.student_ids:
                rec.overlap_warning_html = "<p style='color: green;'></p>"
                continue

            html_log = "<ul>"
            has_overlap_overall = False

            for student in rec.student_ids:
                is_overlap = False
                student_log = f"<li><b>{student.name}</b>:<ul>"

                real_student_id = student._origin.id if student._origin else student.id
                if not real_student_id:
                    continue

                busy_classes = self.env['center.class'].search([
                    ('id', '!=', rec._origin.id if rec._origin else rec.id),
                    ('state', 'in', ['active', 'recruiting']),
                    ('student_ids', 'in', real_student_id)
                ])

                for bc in busy_classes:
                    if rec.start_date and bc.end_date and rec.start_date > bc.end_date: continue
                    if rec.end_date and bc.start_date and rec.end_date < bc.start_date: continue

                    for bs in bc.schedule_ids:
                        for cs in rec.schedule_ids:
                            if str(bs.day_of_week) == str(cs.day_of_week):
                                if cs.start_time < bs.end_time and cs.end_time > bs.start_time:
                                    is_overlap = True
                                    try:
                                        day_name = int(bs.day_of_week) + 2
                                    except ValueError:
                                        day_name = bs.day_of_week
                                    student_log += f"<li>Having class <b>{bc.name}</b> ( {day_name}, {bs.start_time}h - {bs.end_time}h)</li>"

                student_log += "</ul></li>"

                if is_overlap:
                    has_overlap_overall = True
                    html_log += f"<div style='color: red; padding: 5px; border: 1px dashed red; margin-bottom: 5px;'>{student_log}</div>"
                else:
                    html_log += f"<div style='color: green; margin-bottom: 5px;'>Available: {student.name} can attend this class.</div>"

            html_log += "</ul>"

            if has_overlap_overall:
                rec.overlap_warning_html = f"<b><i style='color:red;'>WARNING: Active this class will push student with busy schedule back to course's waiting list!</i></b><br/>" + html_log
            else:
                rec.overlap_warning_html = html_log

    def action_active_class(self):
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')

        def float_to_time(f):
            h = int(f)
            m = int(round((f - h) * 60))
            if m == 60: h, m = h + 1, 0
            return time(hour=h, minute=m)

        for rec in self:
            valid_students = []
            invalid_students = []
            missing_fields = []

            if not rec.start_date:
                missing_fields.append("Start Date")
            if not rec.teacher_id:
                missing_fields.append("Teacher")
            if not rec.schedule_ids:
                missing_fields.append("Weekly Schedule")
            if not rec.student_ids:
                missing_fields.append("Student List")
            if not rec.classroom_id:
                missing_fields.append("Classroom")

            if missing_fields:
                error_msg = "Can't active this class! Missing field:\n- " + "\n- ".join(missing_fields)
                raise ValidationError(error_msg)

            for student in rec.student_ids:
                is_overlap = False
                busy_classes = self.env['center.class'].search([
                    ('id', '!=', rec.id), ('state', 'in', ['active', 'recruiting']), ('student_ids', 'in', student.id)
                ])
                for bc in busy_classes:
                    if rec.start_date and bc.end_date and rec.start_date > bc.end_date: continue
                    if rec.end_date and bc.start_date and rec.end_date < bc.start_date: continue
                    for bs in bc.schedule_ids:
                        for cs in rec.schedule_ids:
                            if str(bs.day_of_week) == str(cs.day_of_week):
                                if cs.start_time < bs.end_time and cs.end_time > bs.start_time:
                                    is_overlap = True
                                    break
                            if is_overlap: break
                        if is_overlap: break

                if is_overlap:
                    invalid_students.append(student.id)
                else:
                    valid_students.append(student.id)

            if invalid_students:
                rec.student_ids = [Command.unlink(s_id) for s_id in invalid_students]

            if valid_students and rec.course_id:
                rec.course_id.registered_student_ids = [Command.unlink(s_id) for s_id in valid_students]

            rec.overlap_warning_html = False
            rec.state = 'active'
            rec.session_ids.unlink()

            current_date = rec.start_date
            session_count = 0

            while session_count < rec.course_id.total_sessions:
                weekday_str = str(current_date.weekday())
                schedules = rec.schedule_ids.filtered(lambda s: s.day_of_week == weekday_str)
                for sched in schedules:
                    if session_count >= rec.course_id.total_sessions: break
                    session_count += 1

                    start_local = user_tz.localize(datetime.combine(current_date, float_to_time(sched.start_time)))
                    end_local = user_tz.localize(datetime.combine(current_date, float_to_time(sched.end_time)))
                    start_utc = start_local.astimezone(pytz.UTC).replace(tzinfo=None)
                    end_utc = end_local.astimezone(pytz.UTC).replace(tzinfo=None)

                    self.env['class.session'].create({
                        'class_id': rec.id, 'sequence': session_count,
                        'start_datetime': start_utc, 'end_datetime': end_utc,
                    })
                current_date += timedelta(days=1)
            rec.end_date = current_date - timedelta(days=1)

    def _compute_class_revenue(self):
        for rec in self:
            histories = self.env['center.debt.history'].search([('class_id', '=', rec.id)])
            rec.total_revenue = sum(histories.mapped('amount'))

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
        is_student = self.env.user.has_group('english_center.group_center_student')

        for record in self:
            if is_student:
                record.available_teacher_ids = False
                continue

        for record in self:
            all_teachers = self.env['hr.employee'].search([])

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
                            if str(busy_sched.day_of_week) == str(current_sched.day_of_week):
                                if current_sched.start_time < busy_sched.end_time and current_sched.end_time > busy_sched.start_time:
                                    is_overlap = True
                                    break
                        if is_overlap: break
                    if is_overlap: break

                if not is_overlap:
                    qualified.append(teacher.id)

            record.available_teacher_ids = qualified

    @api.depends('schedule_ids.day_of_week', 'schedule_ids.start_time', 'schedule_ids.end_time')
    def _compute_available_classrooms(self):
        for record in self:
            all_classrooms = self.env['center.classroom'].search([])

            if not record.schedule_ids:
                record.available_classroom_ids = all_classrooms.ids
                continue

            qualified = []
            for aclass in all_classrooms:
                is_overlap = False

                here_classes = self.env['center.class'].search([
                    ('id', '!=', record._origin.id if record._origin else record.id),
                    ('state', '=', 'active'),
                    ('classroom_id', '=', aclass.id)
                ])

                for here_class in here_classes:
                    for busy_sched in here_class.schedule_ids:
                        for current_sched in record.schedule_ids:
                            if str(busy_sched.day_of_week) == str(current_sched.day_of_week):
                                if current_sched.start_time < busy_sched.end_time and current_sched.end_time > busy_sched.start_time:
                                    is_overlap = True
                                    break
                        if is_overlap: break
                    if is_overlap: break

                if not is_overlap:
                    qualified.append(aclass.id)

            record.available_classroom_ids = qualified

    @api.constrains('start_date')
    def _check_start_date(self):
        for record in self:
            if record.start_date and record.start_date < fields.Date.today():
                raise ValidationError("Error: Start date cannot be in the past.")

    @api.depends('schedule_ids.day_of_week', 'schedule_ids.start_time', 'schedule_ids.end_time', 'course_id')
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

    @api.depends('schedule_ids.day_of_week', 'schedule_ids.start_time', 'schedule_ids.end_time')
    def _compute_available_students(self):
        for record in self:
            all_students = self.env['center.student'].search([])

            if not record.schedule_ids:
                record.available_student_ids = all_students.ids
                continue

            qualified = []
            for student in all_students:
                is_overlap = False

                # Find other classes that this student attending
                # 'Active' + 'Recuriting' classes
                busy_classes = self.env['center.class'].search([
                    ('id', '!=', record._origin.id if record._origin else record.id),
                    ('state', 'in', ['active', 'recruiting']),
                    ('student_ids', 'in', student.id)
                ])

                for busy_class in busy_classes:
                    for busy_sched in busy_class.schedule_ids:
                        for current_sched in record.schedule_ids:
                            if str(busy_sched.day_of_week) == str(current_sched.day_of_week):
                                if current_sched.start_time < busy_sched.end_time and current_sched.end_time > busy_sched.start_time:
                                    is_overlap = True
                                    break
                        if is_overlap: break
                    if is_overlap: break

                if not is_overlap:
                    qualified.append(student.id)

                # all student on waiting list still appear
                # whether their schedules are free or not
                if record.course_id and record.course_id.registered_student_ids:
                    qualified.extend(record.course_id.registered_student_ids.ids)

                # use list to erase duplicates
                record.available_student_ids = list(set(qualified))

    def action_view_class_schedule(self):
        return {
            'name': f'Schedule: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'class.session',
            'view_mode': 'calendar,list',
            'domain': [('class_id', '=', self.id)],
            'context': {'default_class_id': self.id},
        }

    @api.onchange('course_id')
    def _onchange_course_id_pull_students(self):
        for rec in self:
            if rec.course_id and rec.course_id.registered_student_ids:
                rec.student_ids = Command.set(rec.course_id.registered_student_ids.ids)
            else:
                rec.student_ids = False