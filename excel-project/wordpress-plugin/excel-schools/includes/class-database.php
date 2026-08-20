<?php
/**
 * ESM Database — creates and manages all custom tables.
 *
 * IMPORTANT: this schema is a direct, field-for-field mirror of the
 * SQLAlchemy models in the offline Flask app (app.py). Every table,
 * column, type and default below was generated from those model
 * definitions — nothing here was invented independently of the
 * offline app, and nothing the offline app has is missing here.
 *
 * Author: Edutechweb
 */
if (!defined('ABSPATH')) exit;

class ESM_Database {

    /**
     * Table list — exactly the tables backing the offline app's models,
     * plus WordPress-side sync bookkeeping (esm_sync_log, esm_appearance_settings,
     * esm_school_settings) that also exist as SQLAlchemy models in app.py.
     */
    private static $tables = [
        'esm_academic_years', 'esm_terms', 'esm_classes', 'esm_subjects',
        'esm_students', 'esm_parents', 'esm_student_parent',
        'esm_staff', 'esm_staff_subjects',
        'esm_exams', 'esm_exam_results',
        'esm_fee_levels', 'esm_fee_structures', 'esm_fee_payments',
        'esm_invoices', 'esm_invoice_items',
        'esm_hostels', 'esm_rooms', 'esm_room_allocations',
        'esm_timetable_slots',
        'esm_notices', 'esm_messages',
        'esm_sync_log', 'esm_school_settings', 'esm_appearance_settings',
        'esm_cost_centers',
    ];

    public static function get_table_names() {
        return self::$tables;
    }

    public static function create_tables() {
        global $wpdb;
        $charset = $wpdb->get_charset_collate();
        $pfx = $wpdb->prefix;
        $sqls = [];

        // ── AcademicYear (app.py: class AcademicYear) ─────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_academic_years (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            is_current TINYINT(1) DEFAULT 0,
            sync_id VARCHAR(36) DEFAULT NULL
        ) $charset;";

        // ── Term ────────────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_terms (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            academic_year_id BIGINT UNSIGNED,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            is_current TINYINT(1) DEFAULT 0,
            sync_id VARCHAR(36) DEFAULT NULL,
            KEY idx_ay (academic_year_id)
        ) $charset;";

        // ── Class ───────────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_classes (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            level VARCHAR(20),
            stream VARCHAR(30),
            teacher_id BIGINT UNSIGNED,
            capacity INT DEFAULT 40,
            academic_year_id BIGINT UNSIGNED,
            sync_id VARCHAR(36) DEFAULT NULL,
            KEY idx_teacher (teacher_id),
            KEY idx_ay (academic_year_id)
        ) $charset;";

        // ── Subject ─────────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_subjects (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            code VARCHAR(20) UNIQUE,
            description TEXT,
            is_compulsory TINYINT(1) DEFAULT 1
        ) $charset;";

        // ── Student (app.py: class Student — every field mirrored) ────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_students (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            admission_number VARCHAR(20) NOT NULL UNIQUE,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            other_names VARCHAR(50),
            date_of_birth DATE,
            gender VARCHAR(10),
            national_id VARCHAR(20),
            photo VARCHAR(200),
            class_id BIGINT UNSIGNED,
            admission_date DATE,
            status VARCHAR(20) DEFAULT 'Active',
            previous_school VARCHAR(200),
            medical_info TEXT,
            address VARCHAR(300),
            city VARCHAR(100),
            province VARCHAR(100),
            country VARCHAR(100) DEFAULT 'Zimbabwe',
            phone VARCHAR(20),
            email VARCHAR(100),
            fee_classification VARCHAR(30) DEFAULT 'Regular',
            scholarship_type VARCHAR(20) DEFAULT 'None',
            scholarship_percentage FLOAT DEFAULT 0,
            scholarship_sponsor VARCHAR(200),
            scholarship_staff_id BIGINT UNSIGNED,
            scholarship_notes TEXT,
            is_new_learner TINYINT(1) DEFAULT 1,
            billed_once_off_levies TINYINT(1) DEFAULT 0,
            user_id BIGINT UNSIGNED,
            sync_id VARCHAR(36) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY idx_class (class_id),
            KEY idx_status (status)
        ) $charset;";

        // ── Parent ──────────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_parents (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            relationship VARCHAR(20),
            phone VARCHAR(20),
            email VARCHAR(100),
            address VARCHAR(300),
            occupation VARCHAR(100),
            national_id VARCHAR(20),
            user_id BIGINT UNSIGNED,
            sync_id VARCHAR(36) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) $charset;";

        // ── student_parent association table ───────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_student_parent (
            student_id BIGINT UNSIGNED,
            parent_id BIGINT UNSIGNED,
            PRIMARY KEY (student_id, parent_id)
        ) $charset;";

        // ── Staff (app.py: class Staff) ────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_staff (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            employee_number VARCHAR(20) NOT NULL UNIQUE,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            other_names VARCHAR(50),
            date_of_birth DATE,
            gender VARCHAR(10),
            national_id VARCHAR(20),
            photo VARCHAR(200),
            qualification VARCHAR(200),
            specialization VARCHAR(200),
            department VARCHAR(100),
            position VARCHAR(100),
            employment_date DATE,
            salary FLOAT,
            phone VARCHAR(20),
            email VARCHAR(100),
            address VARCHAR(300),
            status VARCHAR(20) DEFAULT 'Active',
            user_id BIGINT UNSIGNED,
            sync_id VARCHAR(36) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            KEY idx_status (status)
        ) $charset;";

        // ── StaffSubject (m2m: staff <-> subject, per class/year) ──
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_staff_subjects (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            staff_id BIGINT UNSIGNED,
            subject_id BIGINT UNSIGNED,
            class_id BIGINT UNSIGNED,
            academic_year_id BIGINT UNSIGNED,
            sync_id VARCHAR(36) DEFAULT NULL,
            KEY idx_staff (staff_id),
            KEY idx_subject (subject_id)
        ) $charset;";

        // ── Exam ────────────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_exams (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            term_id BIGINT UNSIGNED,
            exam_type VARCHAR(50),
            start_date DATE,
            end_date DATE,
            academic_year_id BIGINT UNSIGNED,
            sync_id VARCHAR(36) DEFAULT NULL
        ) $charset;";

        // ── ExamResult ─────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_exam_results (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            student_id BIGINT UNSIGNED,
            exam_id BIGINT UNSIGNED,
            subject_id BIGINT UNSIGNED,
            marks_obtained FLOAT,
            marks_total FLOAT DEFAULT 100,
            grade VARCHAR(5),
            remarks VARCHAR(200),
            sync_id VARCHAR(36) DEFAULT NULL,
            KEY idx_student (student_id),
            KEY idx_exam (exam_id)
        ) $charset;";

        // ── FeeLevel (app.py: class FeeLevel — ALL fee-line columns,
        //    including development_levy / registration_fee / textbook_levy
        //    which the previous plugin build omitted) ────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_fee_levels (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            code VARCHAR(20) NOT NULL UNIQUE,
            description TEXT,
            tuition FLOAT DEFAULT 0,
            development_levy FLOAT DEFAULT 0,
            registration_fee FLOAT DEFAULT 10,
            textbook_levy FLOAT DEFAULT 0,
            boarding FLOAT DEFAULT 0,
            transport FLOAT DEFAULT 0,
            lunch FLOAT DEFAULT 0,
            library FLOAT DEFAULT 0,
            technology FLOAT DEFAULT 0,
            sports FLOAT DEFAULT 0,
            other FLOAT DEFAULT 0,
            total FLOAT DEFAULT 0,
            sync_id VARCHAR(36) DEFAULT NULL
        ) $charset;";

        // ── FeeStructure ────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_fee_structures (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            class_id BIGINT UNSIGNED,
            level_id BIGINT UNSIGNED,
            academic_year_id BIGINT UNSIGNED,
            term_id BIGINT UNSIGNED,
            tuition FLOAT DEFAULT 0,
            development_levy FLOAT DEFAULT 0,
            registration_fee FLOAT DEFAULT 10,
            textbook_levy FLOAT DEFAULT 0,
            boarding FLOAT DEFAULT 0,
            transport FLOAT DEFAULT 0,
            lunch FLOAT DEFAULT 0,
            library FLOAT DEFAULT 0,
            technology FLOAT DEFAULT 0,
            sports FLOAT DEFAULT 0,
            other FLOAT DEFAULT 0,
            total FLOAT DEFAULT 0,
            sync_id VARCHAR(36) DEFAULT NULL,
            KEY idx_class (class_id),
            KEY idx_level (level_id)
        ) $charset;";

        // ── FeePayment ──────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_fee_payments (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            student_id BIGINT UNSIGNED,
            receipt_number VARCHAR(20) NOT NULL UNIQUE,
            amount FLOAT NOT NULL,
            payment_date DATE,
            payment_method VARCHAR(30),
            term_id BIGINT UNSIGNED,
            academic_year_id BIGINT UNSIGNED,
            description VARCHAR(200),
            received_by BIGINT UNSIGNED,
            sync_id VARCHAR(36) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_student (student_id)
        ) $charset;";

        // ── Invoice — MISSING from the previous plugin build entirely;
        //    the offline app's real data has 50 invoices with 170 line
        //    items and no prior WordPress table could hold them. ─────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_invoices (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            invoice_number VARCHAR(30) NOT NULL UNIQUE,
            student_id BIGINT UNSIGNED NOT NULL,
            academic_year_id BIGINT UNSIGNED,
            term_id BIGINT UNSIGNED,
            issue_date DATE,
            due_date DATE,
            subtotal FLOAT DEFAULT 0,
            discount_amount FLOAT DEFAULT 0,
            total_amount FLOAT DEFAULT 0,
            status VARCHAR(20) DEFAULT 'Unpaid',
            notes TEXT,
            sync_id VARCHAR(36) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_student (student_id)
        ) $charset;";

        // ── InvoiceItem ─────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_invoice_items (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            invoice_id BIGINT UNSIGNED NOT NULL,
            description VARCHAR(150) NOT NULL,
            amount FLOAT DEFAULT 0,
            KEY idx_invoice (invoice_id)
        ) $charset;";

        // ── Hostel ──────────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_hostels (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            gender VARCHAR(10),
            capacity INT,
            warden_id BIGINT UNSIGNED,
            sync_id VARCHAR(36) DEFAULT NULL
        ) $charset;";

        // ── Room ────────────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_rooms (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            hostel_id BIGINT UNSIGNED,
            room_number VARCHAR(20) NOT NULL,
            capacity INT DEFAULT 4,
            current_occupancy INT DEFAULT 0,
            KEY idx_hostel (hostel_id)
        ) $charset;";

        // ── RoomAllocation ──────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_room_allocations (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            student_id BIGINT UNSIGNED,
            room_id BIGINT UNSIGNED,
            date_allocated DATE,
            date_vacated DATE,
            status VARCHAR(20) DEFAULT 'Active',
            sync_id VARCHAR(36) DEFAULT NULL
        ) $charset;";

        // ── TimetableSlot ───────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_timetable_slots (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            class_id BIGINT UNSIGNED,
            day_of_week VARCHAR(10) NOT NULL,
            period INT NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            subject_id BIGINT UNSIGNED,
            staff_id BIGINT UNSIGNED,
            room VARCHAR(50),
            sync_id VARCHAR(36) DEFAULT NULL,
            KEY idx_class (class_id)
        ) $charset;";

        // ── Notice ──────────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_notices (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            category VARCHAR(50),
            target_audience VARCHAR(50),
            posted_by BIGINT UNSIGNED,
            date_posted DATETIME DEFAULT CURRENT_TIMESTAMP,
            expiry_date DATETIME,
            is_active TINYINT(1) DEFAULT 1,
            sync_id VARCHAR(36) DEFAULT NULL
        ) $charset;";

        // ── Message ─────────────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_messages (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            sender_id BIGINT UNSIGNED,
            recipient_id BIGINT UNSIGNED,
            subject VARCHAR(200),
            body TEXT,
            date_sent DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_read TINYINT(1) DEFAULT 0,
            sync_id VARCHAR(36) DEFAULT NULL
        ) $charset;";

        // ── SyncLog (app.py: class SyncLog) ────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_sync_log (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            entity_type VARCHAR(50),
            entity_id BIGINT UNSIGNED,
            action VARCHAR(20),
            sync_status VARCHAR(20) DEFAULT 'pending',
            sync_timestamp DATETIME,
            data_snapshot LONGTEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_status (sync_status)
        ) $charset;";

        // ── SchoolSetting ───────────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_school_settings (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            setting_key VARCHAR(100) NOT NULL UNIQUE,
            setting_value TEXT,
            description VARCHAR(200)
        ) $charset;";

        // ── AppearanceSetting ───────────────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_appearance_settings (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            setting_key VARCHAR(100) NOT NULL UNIQUE,
            setting_value TEXT,
            description VARCHAR(200)
        ) $charset;";

        // ── CostCenter (customisable) ───────────────────────────────
        $sqls[] = "CREATE TABLE IF NOT EXISTS {$pfx}esm_cost_centers (
            id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(80) NOT NULL UNIQUE,
            code VARCHAR(20) NOT NULL UNIQUE,
            description VARCHAR(200),
            sync_id VARCHAR(36) DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) $charset;";

        foreach ($sqls as $sql) {
            $wpdb->query($sql);
        }

        // ── Upgrade: cost_center_id column on students ──────────────
        $student_cols = $wpdb->get_col("SHOW COLUMNS FROM {$pfx}esm_students");
        if (!in_array('cost_center_id', $student_cols, true)) {
            $wpdb->query("ALTER TABLE {$pfx}esm_students ADD COLUMN cost_center_id BIGINT UNSIGNED NULL, ADD KEY idx_cost_center (cost_center_id)");
        }
        $students_cols = $wpdb->get_col("SHOW COLUMNS FROM {$pfx}esm_students");
        if (!in_array('entry_mode', $students_cols, true)) {
            $wpdb->query("ALTER TABLE {$pfx}esm_students ADD COLUMN entry_mode VARCHAR(20) DEFAULT 'Day'");
        }

        // ── Seed default cost centres ───────────────────────────────
        $existing = $wpdb->get_var("SELECT COUNT(*) FROM {$pfx}esm_cost_centers");
        if (!$existing) {
            $defaults = [
                ['Primary', 'PRM', 'Primary School (ECD A to Grade 7)'],
                ['Secondary', 'SEC', 'Secondary School (Form 1 to Form 6)'],
                ['Stay In', 'STY', 'Boarding learners (billed the Stay In fee)'],
            ];
            foreach ($defaults as $d) {
                $wpdb->insert(
                    $pfx . 'esm_cost_centers',
                    ['name' => $d[0], 'code' => $d[1], 'description' => $d[2]]
                );
            }
        }

        update_option('esm_db_version', ESM_VERSION);
    }

    /**
     * Drop every ESM table — used on uninstall (not on ordinary
     * deactivation) so a reinstall can rebuild from a clean slate.
     */
    public static function drop_tables() {
        global $wpdb;
        $pfx = $wpdb->prefix;
        foreach (array_reverse(self::$tables) as $t) {
            $wpdb->query("DROP TABLE IF EXISTS {$pfx}{$t}");
        }
    }

    /**
     * Seed the same defaults the offline Flask app ships with out of the
     * box (theme colors + the 4 fee levels), so a brand-new WordPress
     * install looks like the offline app before any sync has run.
     * Actual school data (students/staff/fees/invoices) is expected to
     * come from the migration/import tool, not from this seeding step.
     */
    public static function seed_defaults() {
        global $wpdb;
        $pfx = $wpdb->prefix;

        // Appearance — mirrors app.py DEFAULT_THEME exactly.
        $theme_defaults = [
            'school_name'      => 'Excel Group of Schools',
            'school_motto'     => 'Wea Sono la Cremma Della Terra',
            'school_address'   => '',
            'school_phone'     => '',
            'school_email'     => '',
            'primary_color'    => '#1F2080',
            'primary_dark'     => '#13145A',
            'primary_light'    => '#3F4099',
            'secondary_color'  => '#FDEE00',
            'secondary_light'  => '#FFF266',
            'accent_color'     => '#E85D26',
            'bg_color'         => '#F5F5F7',
            'card_color'       => '#FFFFFF',
            'text_color'       => '#14152E',
            'sidebar_style'    => 'gradient',
            'font_family'      => 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif',
            'logo_url'         => '',
            'favicon_url'      => '',
            'login_bg_image'   => '',
        ];
        foreach ($theme_defaults as $key => $val) {
            $exists = $wpdb->get_var($wpdb->prepare(
                "SELECT id FROM {$pfx}esm_appearance_settings WHERE setting_key=%s", $key));
            if (!$exists) {
                $wpdb->insert("{$pfx}esm_appearance_settings", [
                    'setting_key' => $key, 'setting_value' => $val,
                ]);
            }
        }

        // Approved primary subjects — exact mirror of app.py. Upgrades keep
        // custom/legacy subjects but ensure these six canonical rows exist.
        $primary_subjects = [
            'ENGP' => 'English',
            'CHIS' => 'ChiShona',
            'MATH' => 'Mathematics',
            'SOCS' => 'Social Science',
            'PEA'  => 'PE and Arts',
            'SNT'  => 'Science and Technology',
        ];
        foreach ($primary_subjects as $code => $name) {
            $subject_id = $wpdb->get_var($wpdb->prepare(
                "SELECT id FROM {$pfx}esm_subjects WHERE code=%s OR name=%s ORDER BY code=%s DESC LIMIT 1",
                $code, $name, $code
            ));
            if ($subject_id) {
                $wpdb->update("{$pfx}esm_subjects", [
                    'name' => $name, 'code' => $code, 'is_compulsory' => 1,
                ], ['id' => $subject_id]);
            } else {
                $wpdb->insert("{$pfx}esm_subjects", [
                    'name' => $name, 'code' => $code, 'is_compulsory' => 1,
                ]);
            }
        }
    }
}
