<?php
/**
 * ESM Portal — the frontend school-management interface at /sms/, the
 * WordPress equivalent of the offline Flask app's own web UI. Handles
 * rewrite rules, login/logout, role-based navigation, and dispatches to
 * the per-module templates in templates/.
 *
 * Author: Valentine T Mabheka | Version: 3.0.0
 */
if (!defined('ABSPATH')) exit;

class ESM_Portal {

    public static function init() {
        add_action('init', [__CLASS__, 'register_rewrite_rules']);
        add_filter('query_vars', [__CLASS__, 'query_vars']);
        add_action('template_redirect', [__CLASS__, 'route']);
        add_action('admin_init', [__CLASS__, 'block_wp_admin']);
        add_action('wp_ajax_esm_portal_login', [__CLASS__, 'ajax_login']);
        add_action('wp_ajax_nopriv_esm_portal_login', [__CLASS__, 'ajax_login']);
    }

    public static function register_rewrite_rules() {
        add_rewrite_rule('^sms/?$',               'index.php?esm_portal=dashboard', 'top');
        add_rewrite_rule('^sms/login/?$',         'index.php?esm_portal=login',     'top');
        add_rewrite_rule('^sms/([a-z0-9\-]+)/?$', 'index.php?esm_portal=$matches[1]', 'top');
    }

    public static function query_vars($vars) {
        $vars[] = 'esm_portal';
        return $vars;
    }

    /**
     * Every WP role -> ESM role. Mirrors app.py's single 'role' field on
     * the User model; here it is the highest-priority ESM role assigned
     * to the current WP user.
     */
    public static function get_user_esm_role($user = null) {
        if (!$user) $user = wp_get_current_user();
        if (!$user || !$user->exists()) return null;
        if (in_array('administrator', (array) $user->roles, true)) return 'esm_super_admin';
        foreach (array_keys(ESM_Helpers::role_labels()) as $role) {
            if (in_array($role, (array) $user->roles, true)) return $role;
        }
        return null;
    }

    public static function block_wp_admin() {
        $user = wp_get_current_user();
        $role = self::get_user_esm_role($user);
        if (!$role) return;
        if ($role === 'esm_super_admin' || in_array('administrator', (array) $user->roles, true)) return;
        if (defined('DOING_AJAX') && DOING_AJAX) return;

        if (isset($_GET['page']) && strpos($_GET['page'], 'excel-schools') === 0) {
            if (current_user_can('esm_manage_sync') || current_user_can('esm_manage_settings')) return;
        }
        wp_redirect(home_url('/sms/'));
        exit;
    }

    /**
     * Main router — dispatches /sms/<page>/ to the matching template,
     * after checking the visitor is logged in and the current role is
     * permitted to view that page (mirrors app.py's ROLE_NAV_ITEMS gate).
     */
    public static function route() {
        $page = get_query_var('esm_portal', false);
        if ($page === false) return;

        if ($page === 'login') {
            self::render_login();
            exit;
        }

        if (!is_user_logged_in()) {
            wp_redirect(home_url('/sms/login/'));
            exit;
        }

        $user = wp_get_current_user();
        $role = self::get_user_esm_role($user);
        if (!$role) {
            self::render_forbidden(null);
            exit;
        }

        $allowed_pages = ESM_Helpers::role_nav_items()[$role] ?? [];
        if (!in_array($page, $allowed_pages, true)) {
            self::render_forbidden($role);
            exit;
        }

        // Handle privileged portal actions before any layout output so file
        // downloads and redirects can send their headers safely.
        if ($page === 'classes' && $_SERVER['REQUEST_METHOD'] === 'POST') {
            self::handle_class_create($role, $user);
        }
        if ($page === 'dashboard' && $_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['esm_manual_json_import'])) {
            self::handle_manual_json_import($role);
        }
        if ($page === 'reports' && isset($_GET['download'])) {
            self::download_report($role);
        }
        if ($page === 'reports' && isset($_GET['pdf'])) {
            self::download_report_pdf($role);
        }
        if ($page === 'invoices' && isset($_GET['pdf'])) {
            self::download_invoice_pdf($role);
        }

        self::render_portal($page, $role, $user);
        exit;
    }

    public static function home_url_for_role($role) {
        $page = ESM_Helpers::role_home_page()[$role] ?? 'dashboard';
        return home_url('/sms/' . $page . '/');
    }

    // ─── Login ──────────────────────────────────────────────────────

    private static function render_login() {
        if (is_user_logged_in()) {
            $role = self::get_user_esm_role(wp_get_current_user());
            if ($role) {
                wp_redirect(self::home_url_for_role($role));
                exit;
            }
        }
        $theme = ESM_Helpers::get_theme();
        include ESM_PLUGIN_DIR . 'templates/portal/login.php';
    }

    public static function ajax_login() {
        check_ajax_referer('esm_portal_login', 'nonce');
        $creds = [
            'user_login'    => sanitize_text_field($_POST['username'] ?? ''),
            'user_password' => $_POST['password'] ?? '',
            'remember'      => true,
        ];
        $user = wp_signon($creds, false);
        if (is_wp_error($user)) {
            wp_send_json_error(['message' => 'Invalid username or password.']);
        }
        wp_set_current_user($user->ID);
        $role = self::get_user_esm_role($user);
        if (!$role) {
            wp_logout();
            wp_send_json_error(['message' => 'This account has no Excel Schools role assigned. Contact the administrator.']);
        }
        wp_send_json_success(['redirect' => self::home_url_for_role($role)]);
    }

    // ─── Portal actions ─────────────────────────────────────────────

    private static function handle_class_create($role, $user) {
        if (!in_array($role, ['esm_super_admin', 'esm_bursar'], true) || !current_user_can('esm_manage_students')) {
            self::render_forbidden($role);
            exit;
        }
        check_admin_referer('esm_create_class', 'esm_class_nonce');

        global $wpdb;
        $pfx = $wpdb->prefix;
        $level = sanitize_text_field($_POST['level'] ?? '');
        $stream = sanitize_text_field($_POST['stream'] ?? '');
        $name = sanitize_text_field($_POST['name'] ?? '');
        if (!$name) $name = trim($level . ' ' . $stream);
        $academic_year_id = absint($_POST['academic_year_id'] ?? 0) ?: null;

        if (!$level || !$name) {
            wp_safe_redirect(add_query_arg('class_error', 'missing', home_url('/sms/classes/')));
            exit;
        }
        $duplicate = $wpdb->get_var($wpdb->prepare(
            "SELECT id FROM {$pfx}esm_classes WHERE name=%s AND (academic_year_id=%d OR (%d=0 AND academic_year_id IS NULL))",
            $name, (int) $academic_year_id, (int) $academic_year_id
        ));
        if ($duplicate) {
            wp_safe_redirect(add_query_arg('class_error', 'duplicate', home_url('/sms/classes/')));
            exit;
        }

        $record = [
            'name' => $name,
            'level' => $level,
            'stream' => $stream,
            'teacher_id' => absint($_POST['teacher_id'] ?? 0) ?: null,
            'capacity' => max(1, absint($_POST['capacity'] ?? 40)),
            'academic_year_id' => $academic_year_id,
            'sync_id' => wp_generate_uuid4(),
        ];
        if (!$wpdb->insert("{$pfx}esm_classes", $record)) {
            wp_safe_redirect(add_query_arg('class_error', 'database', home_url('/sms/classes/')));
            exit;
        }

        $class_id = (int) $wpdb->insert_id;
        $wpdb->insert("{$pfx}esm_sync_log", [
            'entity_type' => 'Class',
            'entity_id' => $class_id,
            'action' => 'CREATE',
            'data_snapshot' => wp_json_encode(array_merge(['id' => $class_id], $record)),
            'sync_status' => 'pending',
            'created_at' => current_time('mysql'),
        ]);
        do_action('esm_after_class_save', $class_id, 'CREATE');

        wp_safe_redirect(add_query_arg('class_created', '1', home_url('/sms/classes/')));
        exit;
    }

    private static function handle_manual_json_import($role) {
        if (!in_array($role, ['esm_super_admin', 'esm_bursar'], true) || !current_user_can('esm_manage_sync')) {
            self::render_forbidden($role);
            exit;
        }
        check_admin_referer('esm_portal_json_import', 'esm_import_nonce');
        $result = esm_process_manual_json_upload('json_file');
        set_transient('esm_manual_import_' . get_current_user_id(), $result, 120);
        wp_safe_redirect(home_url('/sms/dashboard/'));
        exit;
    }

    private static function download_report($role) {
        if ($role !== 'esm_super_admin') {
            self::render_forbidden($role);
            exit;
        }
        $report = sanitize_key($_GET['download'] ?? 'all');
        $allowed = ['all', 'students', 'staff', 'fees', 'exams'];
        if (!in_array($report, $allowed, true)) $report = 'all';

        global $wpdb;
        $pfx = $wpdb->prefix;
        $reports = [
            'students' => [
                ['Admission Number', 'First Name', 'Last Name', 'Class', 'Status'],
                $wpdb->get_results("SELECT s.admission_number,s.first_name,s.last_name,c.name AS class_name,s.status FROM {$pfx}esm_students s LEFT JOIN {$pfx}esm_classes c ON c.id=s.class_id ORDER BY s.last_name,s.first_name", ARRAY_N),
            ],
            'staff' => [
                ['Employee Number', 'First Name', 'Last Name', 'Position', 'Status'],
                $wpdb->get_results("SELECT employee_number,first_name,last_name,position,status FROM {$pfx}esm_staff ORDER BY last_name,first_name", ARRAY_N),
            ],
            'fees' => [
                ['Receipt', 'Student', 'Amount', 'Payment Date', 'Method'],
                $wpdb->get_results("SELECT p.receipt_number,CONCAT(s.first_name,' ',s.last_name),p.amount,p.payment_date,p.payment_method FROM {$pfx}esm_fee_payments p LEFT JOIN {$pfx}esm_students s ON s.id=p.student_id ORDER BY p.payment_date DESC", ARRAY_N),
            ],
            'exams' => [
                ['Exam', 'Results Recorded', 'Average Mark'],
                $wpdb->get_results("SELECT e.name,COUNT(r.id),AVG(r.marks_obtained) FROM {$pfx}esm_exams e LEFT JOIN {$pfx}esm_exam_results r ON r.exam_id=e.id GROUP BY e.id ORDER BY e.start_date DESC", ARRAY_N),
            ],
        ];

        nocache_headers();
        header('Content-Type: text/csv; charset=utf-8');
        header('Content-Disposition: attachment; filename="school-' . $report . '-report-' . gmdate('Y-m-d') . '.csv"');
        $out = fopen('php://output', 'w');
        $safe_csv_row = function ($row) {
            return array_map(function ($value) {
                $value = (string) $value;
                return preg_match('/^[=+\-@]/', $value) ? "'" . $value : $value;
            }, (array) $row);
        };
        $selected = $report === 'all' ? array_keys($reports) : [$report];
        foreach ($selected as $key) {
            if ($report === 'all') fputcsv($out, [strtoupper($key) . ' REPORT']);
            fputcsv($out, $reports[$key][0]);
            foreach ($reports[$key][1] as $row) fputcsv($out, $safe_csv_row($row));
            if ($report === 'all') fputcsv($out, []);
        }
        fclose($out);
        exit;
    }

    private static function download_report_pdf($role) {
        if (!current_user_can('esm_manage_reports')) {
            self::render_forbidden($role);
            exit;
        }
        $report = sanitize_key($_GET['pdf'] ?? 'all');
        if (!in_array($report, ['all', 'students', 'fees', 'exams'], true)) $report = 'all';
        global $wpdb;
        $pfx = $wpdb->prefix;
        $sections = [];

        if ($report === 'all' || $report === 'students') {
            $rows = $wpdb->get_results("SELECT c.name,COUNT(s.id) AS total FROM {$pfx}esm_classes c LEFT JOIN {$pfx}esm_students s ON s.class_id=c.id AND s.status='Active' GROUP BY c.id ORDER BY c.name");
            $data = [['Class', 'Active Students']];
            foreach ($rows as $row) $data[] = [$row->name, $row->total];
            $sections[] = ['title' => 'Student Enrollment by Class', 'rows' => $data];
        }
        if ($report === 'all' || $report === 'fees') {
            $rows = $wpdb->get_results("SELECT DATE_FORMAT(payment_date,'%Y-%m') AS month,SUM(amount) AS total FROM {$pfx}esm_fee_payments GROUP BY month ORDER BY month DESC LIMIT 24");
            $data = [['Month', 'Fees Collected']];
            foreach ($rows as $row) $data[] = [$row->month, '$' . number_format($row->total, 2)];
            $sections[] = ['title' => 'Fee Collection', 'rows' => $data];
        }
        if ($report === 'all' || $report === 'exams') {
            $rows = $wpdb->get_results("SELECT e.name,COUNT(r.id) AS total,AVG(r.marks_obtained) AS average_mark FROM {$pfx}esm_exams e LEFT JOIN {$pfx}esm_exam_results r ON r.exam_id=e.id GROUP BY e.id ORDER BY e.start_date DESC");
            $data = [['Exam', 'Results', 'Average Mark']];
            foreach ($rows as $row) $data[] = [$row->name, $row->total, $row->average_mark === null ? '-' : number_format($row->average_mark, 1)];
            $sections[] = ['title' => 'Exam Results Summary', 'rows' => $data];
        }
        $school = ESM_Helpers::get_theme()['school_name'] ?? 'Excel Schools';
        ESM_PDF::download(
            'school-' . $report . '-report-' . gmdate('Y-m-d') . '.pdf',
            $school . ' - ' . ucfirst($report) . ' Report',
            $sections
        );
    }

    private static function download_invoice_pdf($role) {
        if (!current_user_can('esm_manage_fees')) {
            self::render_forbidden($role);
            exit;
        }
        $invoice_id = absint($_GET['pdf'] ?? 0);
        global $wpdb;
        $pfx = $wpdb->prefix;
        $invoice = $wpdb->get_row($wpdb->prepare(
            "SELECT i.*,s.first_name,s.last_name,s.admission_number,c.name AS class_name,ay.name AS academic_year,t.name AS term_name FROM {$pfx}esm_invoices i LEFT JOIN {$pfx}esm_students s ON s.id=i.student_id LEFT JOIN {$pfx}esm_classes c ON c.id=s.class_id LEFT JOIN {$pfx}esm_academic_years ay ON ay.id=i.academic_year_id LEFT JOIN {$pfx}esm_terms t ON t.id=i.term_id WHERE i.id=%d",
            $invoice_id
        ));
        if (!$invoice) {
            status_header(404);
            wp_die('Invoice not found.');
        }
        $items = $wpdb->get_results($wpdb->prepare(
            "SELECT description,amount FROM {$pfx}esm_invoice_items WHERE invoice_id=%d ORDER BY id",
            $invoice_id
        ));
        $paid = (float) $wpdb->get_var($wpdb->prepare(
            "SELECT COALESCE(SUM(amount),0) FROM {$pfx}esm_fee_payments WHERE student_id=%d AND (term_id=%d OR %d=0) AND (academic_year_id=%d OR %d=0)",
            $invoice->student_id, (int) $invoice->term_id, (int) $invoice->term_id,
            (int) $invoice->academic_year_id, (int) $invoice->academic_year_id
        ));
        $item_rows = [['Description', 'Amount']];
        foreach ($items as $item) $item_rows[] = [$item->description, '$' . number_format($item->amount, 2)];
        if (!$items) $item_rows[] = ['Tuition and school charges', '$' . number_format($invoice->subtotal, 2)];
        $school = ESM_Helpers::get_theme()['school_name'] ?? 'Excel Schools';
        $sections = [
            ['title' => 'Invoice Details', 'rows' => [
                ['Invoice Number', $invoice->invoice_number],
                ['Student', trim($invoice->first_name . ' ' . $invoice->last_name)],
                ['Admission Number', $invoice->admission_number],
                ['Class', $invoice->class_name ?: '-'],
                ['Academic Year / Term', trim(($invoice->academic_year ?: '-') . ' / ' . ($invoice->term_name ?: '-'))],
                ['Issue Date', $invoice->issue_date],
                ['Due Date', $invoice->due_date ?: '-'],
                ['Status', $invoice->status],
            ]],
            ['title' => 'Charges', 'rows' => $item_rows],
            ['title' => 'Totals', 'rows' => [
                ['Subtotal', '$' . number_format($invoice->subtotal, 2)],
                ['Discount', '$' . number_format($invoice->discount_amount, 2)],
                ['Total Billed', '$' . number_format($invoice->total_amount, 2)],
                ['Paid', '$' . number_format($paid, 2)],
                ['Balance', '$' . number_format(max(0, $invoice->total_amount - $paid), 2)],
            ]],
        ];
        ESM_PDF::download(
            'invoice-' . $invoice->invoice_number . '.pdf',
            $school . ' - Student Fee Invoice',
            $sections
        );
    }

    // ─── Rendering ──────────────────────────────────────────────────

    private static function render_forbidden($role) {
        status_header(403);
        $theme = ESM_Helpers::get_theme();
        include ESM_PLUGIN_DIR . 'templates/portal/forbidden.php';
    }

    private static function render_portal($page, $role, $user) {
        global $wpdb;
        $pfx = $wpdb->prefix;
        $theme = ESM_Helpers::get_theme();
        $role_label = ESM_Helpers::role_labels()[$role] ?? $role;
        $nav_sections = ESM_Helpers::role_nav_sections()[$role] ?? [];
        $nav_items = ESM_Helpers::role_nav_items()[$role] ?? [];

        // Resolve the Staff/Student/Parent record linked to this WP user,
        // mirroring how app.py resolves session['user_id'] to a role record.
        $staff_id = $wpdb->get_var($wpdb->prepare("SELECT id FROM {$pfx}esm_staff WHERE user_id=%d", $user->ID));
        $student_id = $wpdb->get_var($wpdb->prepare("SELECT id FROM {$pfx}esm_students WHERE user_id=%d", $user->ID));
        $parent_id = $wpdb->get_var($wpdb->prepare("SELECT id FROM {$pfx}esm_parents WHERE user_id=%d", $user->ID));

        if ($page === 'dashboard' && $role === 'esm_super_admin') {
            $template_file = ESM_PLUGIN_DIR . 'templates/portal/dashboard-admin.php';
        } elseif ($page === 'dashboard' && $role === 'esm_bursar') {
            $template_file = ESM_PLUGIN_DIR . 'templates/portal/dashboard-bursar.php';
        } else {
            $template_file = ESM_PLUGIN_DIR . 'templates/portal/' . $page . '.php';
        }
        if (!file_exists($template_file)) {
            $template_file = ESM_PLUGIN_DIR . 'templates/portal/dashboard.php';
            $page = 'dashboard';
        }

        include ESM_PLUGIN_DIR . 'templates/portal/layout-header.php';
        include $template_file;
        include ESM_PLUGIN_DIR . 'templates/portal/layout-footer.php';
    }
}
