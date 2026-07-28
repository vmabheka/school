<?php if (!defined('ABSPATH')) exit; ?><!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Access Denied | <?php echo esc_html($theme['school_name']); ?></title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { font-family: <?php echo esc_html($theme['font_family']); ?>; background: <?php echo esc_html($theme['bg_color']); ?>; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .box { text-align: center; padding: 40px; }
        .box i { font-size: 48px; color: #ef4444; margin-bottom: 16px; }
        .box a { display: inline-block; margin-top: 16px; background: <?php echo esc_html($theme['primary_color']); ?>; color: #fff; padding: 10px 20px; border-radius: 8px; text-decoration: none; }
    </style>
</head>
<body>
    <div class="box">
        <i class="fas fa-ban"></i>
        <h2>Access Denied</h2>
        <p>You do not have permission to view this page.</p>
        <a href="<?php echo esc_url(home_url('/sms/')); ?>">Back to Dashboard</a>
    </div>
</body>
</html>
