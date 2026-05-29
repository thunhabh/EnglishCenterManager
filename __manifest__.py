{
    "name": "English Center Manager",
    "description": "Module to manage English Center",
    "category": "Education",
    "author": "NHAT",
    "depends": [
        "base","hr",
    ],
    "data": [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/security_rules.xml',

        'views/teacher_views.xml',
        'views/student_views.xml',

        'views/center_menus_views.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
    'installable': True,
}