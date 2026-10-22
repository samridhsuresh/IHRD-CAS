# CampusTrack entity relationships

```mermaid
erDiagram
    USERS ||--o{ AUTH_SESSIONS : has
    USERS ||--o{ TEACHER_ASSIGNMENTS : receives
    DEPARTMENTS ||--o{ COURSES : offers
    DEPARTMENTS ||--o{ CLASSES : contains
    COURSES ||--o{ CLASSES : organizes
    CLASSES ||--o{ TEACHER_ASSIGNMENTS : grants
    SUBJECTS ||--o{ TEACHER_ASSIGNMENTS : scopes
    STUDENTS ||--o{ ENROLLMENTS : has
    CLASSES ||--o{ ENROLLMENTS : includes
    STUDENTS ||--o{ STUDENT_GUARDIANS : links
    GUARDIANS ||--o{ STUDENT_GUARDIANS : links
    CLASSES ||--o{ ATTENDANCE_SESSIONS : schedules
    ATTENDANCE_SESSIONS ||--o{ ATTENDANCE_RECORDS : records
    STUDENTS ||--o{ ATTENDANCE_RECORDS : receives
    ATTENDANCE_RECORDS ||--o{ SMS_MESSAGES : triggers
    SMS_MESSAGES ||--o{ SMS_DELIVERY_LOGS : tracks
    USERS ||--o{ AUDIT_LOGS : performs
```

Additional tables: `calendar_days` (optional class scope), `sms_templates`, and `settings`. The first migration creates all tables, foreign keys, indexes, and unique constraints. Enrollment start and end dates preserve class history. Attendance sessions have a `(class_id, day, session_key)` unique key and a version counter. Each student has one record per session. A teacher assignment can scope a class to a particular subject.
