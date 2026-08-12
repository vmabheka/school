<?php
/**
 * wp-admin Settings page — general school info + appearance (theme),
 * mirroring the offline app's own /settings and /appearance pages.
 */
if (!defined('ABSPATH')) exit;
global $wpdb;
$pfx = $wpdb->prefix;
$tab = isset($_GET['tab']) ? sanitize_text_field($_GET['tab']) : 'general';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['esm_nonce'])) {
    check_admin_referer('esm_settings_action', 'esm_nonce');

    if (($_POST['esm_action'] ?? '') === 'save_general') {
        foreach (['school_name', 'school_motto', 'school_phone', 'school_email', 'school_address'] as $key) {
            $val = sanitize_text_field($_POST[$key] ?? '');
            $exists = $wpdb->get_var($wpdb->prepare("SELECT id FROM {$pfx}esm_school_settings WHERE setting_key=%s", $key));
            if ($exists) {
                $wpdb->update("{$pfx}esm_school_settings", ['setting_value' => $val], ['setting_key' => $key]);
            } else {
                $wpdb->insert("{$pfx}esm_school_settings", ['setting_key' => $key, 'setting_value' => $val]);
            }
        }
        echo '<div class="notice notice-success"><p>General settings saved.</p></div>';
    }

    if (($_POST['esm_action'] ?? '') === 'save_appearance') {
        $keys = array_keys(ESM_Helpers::default_theme());
        foreach ($keys as $key) {
            if (!isset($_POST[$key])) continue;
            $val = sanitize_text_field($_POST[$key]);
            $exists = $wpdb->get_var($wpdb->prepare("SELECT id FROM {$pfx}esm_appearance_settings WHERE setting_key=%s", $key));
            if ($exists) {
                $wpdb->update("{$pfx}esm_appearance_settings", ['setting_value' => $val], ['setting_key' => $key]);
            } else {
                $wpdb->insert("{$pfx}esm_appearance_settings", ['setting_key' => $key, 'setting_value' => $val]);
            }
        }
        if (!empty($_FILES['logo_upload']['name'])) {
            $upload = wp_handle_upload($_FILES['logo_upload'], ['test_form' => false]);
            if (!isset($upload['error'])) {
                $wpdb->update("{$pfx}esm_appearance_settings", ['setting_value' => $upload['url']], ['setting_key' => 'logo_url']);
            }
        }
        echo '<div class="notice notice-success"><p>Appearance saved.</p></div>';
    }
}

$theme = ESM_Helpers::get_theme();
$school_settings = $wpdb->get_results("SELECT setting_key, setting_value FROM {$pfx}esm_school_settings", OBJECT_K);
function esm_setting($school_settings, $key, $default = '') {
    return isset($school_settings[$key]) ? $school_settings[$key]->setting_value : $default;
}
?>
<div class="wrap">
    <h1>MobiSchola — Settings</h1>
    <h2 class="nav-tab-wrapper">
        <a href="?page=excel-schools-settings&tab=general" class="nav-tab <?php echo $tab === 'general' ? 'nav-tab-active' : ''; ?>">General</a>
        <a href="?page=excel-schools-settings&tab=appearance" class="nav-tab <?php echo $tab === 'appearance' ? 'nav-tab-active' : ''; ?>">Appearance</a>
    </h2>

    <?php if ($tab === 'general'): ?>
    <form method="POST" style="max-width:600px;margin-top:20px;">
        <?php wp_nonce_field('esm_settings_action', 'esm_nonce'); ?>
        <input type="hidden" name="esm_action" value="save_general">
        <table class="form-table">
            <tr><th>School Name</th><td><input type="text" name="school_name" class="regular-text" value="<?php echo esc_attr(esm_setting($school_settings, 'school_name', $theme['school_name'])); ?>"></td></tr>
            <tr><th>Motto</th><td><input type="text" name="school_motto" class="regular-text" value="<?php echo esc_attr(esm_setting($school_settings, 'school_motto', $theme['school_motto'])); ?>"></td></tr>
            <tr><th>Phone</th><td><input type="text" name="school_phone" class="regular-text" value="<?php echo esc_attr(esm_setting($school_settings, 'school_phone')); ?>"></td></tr>
            <tr><th>Email</th><td><input type="email" name="school_email" class="regular-text" value="<?php echo esc_attr(esm_setting($school_settings, 'school_email')); ?>"></td></tr>
            <tr><th>Address</th><td><textarea name="school_address" class="regular-text"><?php echo esc_textarea(esm_setting($school_settings, 'school_address')); ?></textarea></td></tr>
        </table>
        <?php submit_button('Save General Settings'); ?>
    </form>

    <?php else: ?>
    <form method="POST" enctype="multipart/form-data" style="max-width:600px;margin-top:20px;">
        <?php wp_nonce_field('esm_settings_action', 'esm_nonce'); ?>
        <input type="hidden" name="esm_action" value="save_appearance">
        <table class="form-table">
            <tr><th>Primary Color</th><td><input type="color" name="primary_color" value="<?php echo esc_attr($theme['primary_color']); ?>"></td></tr>
            <tr><th>Secondary Color</th><td><input type="color" name="secondary_color" value="<?php echo esc_attr($theme['secondary_color']); ?>"></td></tr>
            <tr><th>Accent Color</th><td><input type="color" name="accent_color" value="<?php echo esc_attr($theme['accent_color']); ?>"></td></tr>
            <tr><th>School Logo</th><td>
                <input type="file" name="logo_upload" accept="image/*">
                <?php if (!empty($theme['logo_url'])): ?><p><img src="<?php echo esc_url($theme['logo_url']); ?>" style="max-height:60px;"></p><?php endif; ?>
            </td></tr>
        </table>
        <?php submit_button('Save Appearance'); ?>
    </form>
    <?php endif; ?>

    <hr>
    <p><a href="<?php echo esc_url(admin_url('admin.php?page=excel-schools-portal-link')); ?>" class="button button-primary">⇱ Open Portal (/sms/)</a></p>
</div>
