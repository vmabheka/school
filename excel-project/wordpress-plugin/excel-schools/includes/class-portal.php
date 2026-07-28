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

        $template_file = ESM_PLUGIN_DIR . 'templates/portal/' . $page . '.php';
        if (!file_exists($template_file)) {
            $template_file = ESM_PLUGIN_DIR . 'templates/portal/dashboard.php';
            $page = 'dashboard';
        }

        include ESM_PLUGIN_DIR . 'templates/portal/layout-header.php';
        include $template_file;
        include ESM_PLUGIN_DIR . 'templates/portal/layout-footer.php';
    }
}
