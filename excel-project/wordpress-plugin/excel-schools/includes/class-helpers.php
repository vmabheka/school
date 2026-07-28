<?php
/**
 * ESM Helpers — utility functions mirrored directly from the offline
 * Flask app's helper functions (app.py: is_primary_level, get_fee_level_name,
 * PRIMARY_LEARNING_AREAS, DEFAULT_THEME, effective_fee_multiplier, etc.)
 *
 * Author: Valentine T Mabheka | Version: 3.0.0
 */
if (!defined('ABSPATH')) exit;

class ESM_Helpers {

    // Heritage-Based Curriculum (HBC) — 6 learning areas for primary level
    // (ECD A through Grade 7), mirrored from app.py: PRIMARY_LEARNING_AREAS.
    const PRIMARY_LEARNING_AREAS = [
        'Language, Literacy and Communication',
        'Mathematical Concepts and Numerical Activities',
        'Science and Technology',
        'Heritage Studies',
        'Physical Education, Health and Wellbeing',
        'Visual and Performing Arts',
    ];

    // ─── Number generators (mirror app.py admission/employee/receipt
    //     numbering schemes so records created in WP look native) ──────

    public static function generate_admission_number() {
        global $wpdb;
        $prefix = 'EXC' . date('Y');
        $last = $wpdb->get_var($wpdb->prepare(
            "SELECT admission_number FROM {$wpdb->prefix}esm_students WHERE admission_number LIKE %s ORDER BY id DESC LIMIT 1",
            $prefix . '%'
        ));
        $num = $last ? intval(substr($last, -4)) + 1 : 1;
        return $prefix . sprintf('%04d', $num);
    }

    public static function generate_employee_number() {
        global $wpdb;
        $last = $wpdb->get_var("SELECT employee_number FROM {$wpdb->prefix}esm_staff ORDER BY id DESC LIMIT 1");
        $num = $last ? intval(str_replace('EMP', '', $last)) + 1 : 1;
        return 'EMP' . sprintf('%04d', $num);
    }

    public static function generate_receipt_number() {
        global $wpdb;
        $prefix = 'REC' . date('Ym');
        $last = $wpdb->get_var($wpdb->prepare(
            "SELECT receipt_number FROM {$wpdb->prefix}esm_fee_payments WHERE receipt_number LIKE %s ORDER BY id DESC LIMIT 1",
            $prefix . '%'
        ));
        $num = $last ? intval(substr($last, -4)) + 1 : 1;
        return $prefix . sprintf('%04d', $num);
    }

    public static function generate_invoice_number() {
        global $wpdb;
        $prefix = 'INV' . date('Ym');
        $last = $wpdb->get_var($wpdb->prepare(
            "SELECT invoice_number FROM {$wpdb->prefix}esm_invoices WHERE invoice_number LIKE %s ORDER BY id DESC LIMIT 1",
            $prefix . '%'
        ));
        $num = $last ? intval(substr($last, -4)) + 1 : 1;
        return $prefix . sprintf('%04d', $num);
    }

    // ─── Level / fee-level mapping — verbatim port of app.py's
    //     is_primary_level() and get_fee_level_name() ───────────────────

    public static function is_primary_level($level) {
        if (!$level) return false;
        $lvl = trim(strtolower($level));
        if (strpos($lvl, 'ecd') === 0) return true;
        if (strpos($lvl, 'grade') === 0 || strpos($lvl, 'gr') === 0) {
            if (preg_match('/(\d+)/', $lvl, $m)) {
                $grade_num = intval($m[1]);
                return $grade_num >= 1 && $grade_num <= 7;
            }
        }
        return false;
    }

    public static function get_fee_level_name($level) {
        if (!$level) return null;
        if (self::is_primary_level($level)) {
            $lvl = trim(strtolower($level));
            if (strpos($lvl, 'ecd') === 0) return 'ECD';
            return 'Junior';
        }
        if (preg_match('/form\s*(\d+)/i', $level, $m)) {
            $f = intval($m[1]);
            if ($f >= 1 && $f <= 4) return 'O Level';
            if ($f >= 5) return 'A Level';
        }
        return null;
    }

    // ─── Scholarship maths — verbatim port of Student.effective_fee_multiplier ─
    public static function effective_fee_multiplier($student) {
        $fee_classification = is_object($student) ? $student->fee_classification : ($student['fee_classification'] ?? '');
        $scholarship_type    = is_object($student) ? $student->scholarship_type : ($student['scholarship_type'] ?? '');
        $scholarship_pct     = is_object($student) ? $student->scholarship_percentage : ($student['scholarship_percentage'] ?? 0);

        if ($fee_classification === 'Orphan' || $scholarship_type === 'Full') {
            return 0.0;
        } elseif ($scholarship_type === 'Partial') {
            return 1.0 - (floatval($scholarship_pct) / 100.0);
        }
        return 1.0;
    }

    // ─── Theme / appearance — mirrors app.py DEFAULT_THEME ────────────

    public static function default_theme() {
        return [
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
    }

    public static function get_theme() {
        global $wpdb;
        $pfx = $wpdb->prefix;
        $rows = $wpdb->get_results("SELECT setting_key, setting_value FROM {$pfx}esm_appearance_settings", ARRAY_A);
        $theme = self::default_theme();
        foreach ($rows as $row) {
            $theme[$row['setting_key']] = $row['setting_value'];
        }
        return $theme;
    }

    // ─── Roles — mirrors app.py ROLE_LABELS / ROLE_NAV_SECTIONS ───────

    public static function role_labels() {
        return [
            'esm_super_admin' => 'Super Admin',
            'esm_accountant'  => 'Accountant',
            'esm_bursar'      => 'Bursar',
            'esm_teacher'     => 'Teacher',
            'esm_parent'      => 'Parent',
            'esm_student'     => 'Student',
        ];
    }

    public static function role_descriptions() {
        return [
            'esm_super_admin' => 'Directors & Principals — Full system access',
            'esm_accountant'  => 'Financial management — Fees, payments, reports',
            'esm_bursar'      => 'Student admissions, financial oversight & sync management',
            'esm_teacher'     => 'Academic access — Exams, class management',
            'esm_parent'      => 'View child information — Fees, results, attendance',
            'esm_student'     => 'Personal portal — Results, timetable, attendance',
        ];
    }

    // Which nav sections each role can see (mirrors app.py ROLE_NAV_SECTIONS)
    public static function role_nav_sections() {
        return [
            'esm_super_admin' => ['main', 'people', 'academic', 'finance', 'resources', 'communication', 'analytics', 'system'],
            'esm_accountant'  => ['main', 'finance', 'analytics', 'communication'],
            'esm_bursar'      => ['main', 'people', 'finance', 'communication', 'analytics', 'system'],
            'esm_teacher'     => ['main', 'people', 'academic', 'resources', 'communication', 'analytics'],
            'esm_parent'      => ['main', 'communication'],
            'esm_student'     => ['main', 'academic', 'communication'],
        ];
    }

    // Which specific portal pages each role can access (mirrors
    // app.py ROLE_NAV_ITEMS, translated to this plugin's /sms/ page slugs)
    public static function role_nav_items() {
        return [
            'esm_super_admin' => ['dashboard', 'students', 'classes', 'staff', 'exams', 'timetable',
                                   'fees', 'invoices', 'debtors', 'fee-levels', 'hostel',
                                   'communication', 'reports', 'sync', 'settings',
                                   'parent-portal', 'student-portal', 'users'],
            'esm_accountant'  => ['dashboard', 'fees', 'invoices', 'debtors', 'fee-levels',
                                   'reports', 'communication', 'users'],
            'esm_bursar'      => ['dashboard', 'students', 'classes', 'fees', 'invoices', 'debtors',
                                   'communication', 'reports', 'sync'],
            'esm_teacher'     => ['dashboard', 'students', 'exams', 'timetable',
                                   'communication', 'reports'],
            'esm_parent'      => ['dashboard', 'parent-portal', 'communication'],
            'esm_student'     => ['dashboard', 'student-portal', 'communication'],
        ];
    }

    // Default landing page per role (mirrors app.py get_role_home_endpoint)
    public static function role_home_page() {
        return [
            'esm_super_admin' => 'dashboard',
            'esm_accountant'  => 'fees',
            'esm_bursar'      => 'dashboard',
            'esm_teacher'     => 'dashboard',
            'esm_parent'      => 'parent-portal',
            'esm_student'     => 'student-portal',
        ];
    }
}
