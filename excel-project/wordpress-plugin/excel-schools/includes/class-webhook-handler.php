<?php
/**
 * ESM Webhook Handler — optional real-time push notifications.
 * When enabled, fires an immediate webhook to the Flask app whenever a
 * student/staff/fee-payment record changes in WordPress, instead of
 * waiting for the next scheduled sync cycle.
 *
 * Author: Valentine T Mabheka | Version: 3.0.0
 */
if (!defined('ABSPATH')) exit;

class ESM_Webhook_Handler {

    public static function init() {
        add_action('esm_after_student_save', [__CLASS__, 'on_student_change'], 10, 2);
        add_action('esm_after_staff_save', [__CLASS__, 'on_staff_change'], 10, 2);
        add_action('esm_after_fee_payment', [__CLASS__, 'on_fee_payment'], 10, 2);
        add_action('rest_api_init', [__CLASS__, 'register_webhook_endpoint']);
    }

    public static function on_student_change($student_id, $action) {
        if (!get_option('esm_webhook_enabled', false)) return;
        self::fire_webhook('Student', $student_id, $action, 'esm_students');
    }

    public static function on_staff_change($staff_id, $action) {
        if (!get_option('esm_webhook_enabled', false)) return;
        self::fire_webhook('Staff', $staff_id, $action, 'esm_staff');
    }

    public static function on_fee_payment($payment_id, $action) {
        if (!get_option('esm_webhook_enabled', false)) return;
        self::fire_webhook('FeePayment', $payment_id, $action, 'esm_fee_payments');
    }

    private static function fire_webhook($entity_type, $entity_id, $action, $table_suffix) {
        $endpoint = get_option('esm_flask_endpoint', '');
        $api_key  = get_option('esm_sync_api_key', '');
        if (!$endpoint) return;

        global $wpdb;
        $table = $wpdb->prefix . $table_suffix;
        $record = $wpdb->get_row($wpdb->prepare("SELECT * FROM $table WHERE id=%d", $entity_id), ARRAY_A);

        wp_remote_post(rtrim($endpoint, '/') . '/api/sync/webhook', [
            'timeout'  => 8,
            'blocking' => false, // fire-and-forget, don't slow down the admin request
            'headers'  => ['Content-Type' => 'application/json', 'X-ESM-API-Key' => $api_key],
            'body'     => wp_json_encode([
                'entity_type' => $entity_type, 'entity_id' => $entity_id,
                'event' => $action, 'data' => $record, 'api_key' => $api_key,
            ]),
        ]);
    }

    public static function register_webhook_endpoint() {
        register_rest_route('excel-schools/v2', '/webhook/incoming', [
            'methods' => 'POST',
            'callback' => [__CLASS__, 'handle_incoming_webhook'],
            'permission_callback' => [__CLASS__, 'verify_webhook_key'],
        ]);
    }

    public static function verify_webhook_key($request) {
        $api_key = $request->get_header('X-ESM-API-Key');
        $stored = get_option('esm_sync_api_key', '');
        return !empty($stored) && $api_key === $stored;
    }

    /**
     * Handle an incoming real-time webhook from Flask — apply the change
     * immediately rather than waiting for the next scheduled pull.
     */
    public static function handle_incoming_webhook($request) {
        $params = $request->get_json_params();
        $entity_type = sanitize_text_field($params['entity_type'] ?? '');
        $action = sanitize_text_field($params['event'] ?? $params['action'] ?? '');
        $data = $params['data'] ?? [];

        if (!$entity_type || !$action) {
            return new WP_Error('missing_params', 'entity_type and action required', ['status' => 400]);
        }

        // Delegate to the same upsert logic the REST API uses for normal sync.
        return ESM_REST_API::receive_sync([
            'entity_type' => $entity_type, 'action' => $action, 'data' => $data,
            'sync_id' => $data['sync_id'] ?? '',
        ]);
    }
}
