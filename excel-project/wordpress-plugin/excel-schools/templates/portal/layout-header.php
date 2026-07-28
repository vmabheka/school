<?php
/**
 * Portal layout header — visual port of the offline app's templates/base.html
 * (same CSS variables, same sidebar sections/order, same nav item labels),
 * so the WordPress /sms/ portal looks like the offline app, not a
 * reinterpretation of it.
 *
 * Available in scope: $page, $role, $role_label, $nav_sections, $nav_items,
 * $theme, $user, $staff_id, $student_id, $parent_id.
 */
if (!defined('ABSPATH')) exit;

$deployment_mode = 'online'; // this WordPress instance is always the "online" side
$avatar_letter = strtoupper(substr($user->display_name ?: $user->user_login, 0, 1));
?><!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo esc_html(ucwords(str_replace('-', ' ', $page))); ?> | <?php echo esc_html($theme['school_name']); ?></title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: <?php echo esc_html($theme['primary_color']); ?>;
            --primary-dark: <?php echo esc_html($theme['primary_dark']); ?>;
            --primary-light: <?php echo esc_html($theme['primary_light']); ?>;
            --secondary: <?php echo esc_html($theme['secondary_color']); ?>;
            --secondary-light: <?php echo esc_html($theme['secondary_light']); ?>;
            --accent: <?php echo esc_html($theme['accent_color']); ?>;
            --bg: <?php echo esc_html($theme['bg_color']); ?>;
            --card: <?php echo esc_html($theme['card_color']); ?>;
            --text: <?php echo esc_html($theme['text_color']); ?>;
            --text-light: #6b7280;
            --border: #e5e7eb;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --info: #3b82f6;
            --sidebar-width: 260px;
            --header-height: 60px;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: <?php echo esc_html($theme['font_family']); ?>; background: var(--bg); color: var(--text); min-height: 100vh; }
        .sidebar { position: fixed; left: 0; top: 0; width: var(--sidebar-width); height: 100vh; background: linear-gradient(180deg, var(--primary-dark) 0%, var(--primary) 100%); color: #fff; overflow-y: auto; z-index: 1000; transition: transform .3s ease; }
        .sidebar-header { padding: 20px; text-align: center; border-bottom: 1px solid rgba(255,255,255,.1); }
        .sidebar-header img.logo-img { width: 60px; height: 60px; border-radius: 50%; object-fit: cover; margin: 0 auto 10px; display: block; background: var(--secondary); padding: 4px; }
        .sidebar-header .logo { width: 60px; height: 60px; background: var(--secondary); border-radius: 50%; margin: 0 auto 10px; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: 700; color: var(--primary-dark); }
        .sidebar-header h2 { font-size: 16px; font-weight: 700; letter-spacing: .5px; }
        .sidebar-header p { font-size: 11px; opacity: .7; margin-top: 4px; }
        .sidebar-nav { padding: 10px 0; }
        .nav-section { padding: 10px 20px 5px; font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; opacity: .5; font-weight: 600; }
        .nav-item { display: flex; align-items: center; padding: 10px 20px; color: rgba(255,255,255,.8); text-decoration: none; transition: all .2s ease; font-size: 13.5px; border-left: 3px solid transparent; }
        .nav-item:hover { background: rgba(255,255,255,.1); color: #fff; border-left-color: var(--secondary); }
        .nav-item.active { background: rgba(255,255,255,.15); color: #fff; border-left-color: var(--secondary); font-weight: 600; }
        .nav-item i { width: 20px; margin-right: 12px; font-size: 15px; text-align: center; }
        .header { position: fixed; top: 0; left: var(--sidebar-width); right: 0; height: var(--header-height); background: var(--card); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 24px; z-index: 999; }
        .header-left { display: flex; align-items: center; gap: 16px; }
        .menu-toggle { display: none; background: none; border: none; font-size: 20px; color: var(--text); cursor: pointer; }
        .header-right { display: flex; align-items: center; gap: 16px; }
        .deployment-badge { padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
        .deployment-badge.online { background: #d1fae5; color: #065f46; }
        .header-user { display: flex; align-items: center; gap: 10px; cursor: pointer; }
        .header-user .avatar { width: 36px; height: 36px; background: var(--primary); color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 14px; }
        .header-user .user-info { font-size: 13px; }
        .header-user .user-info .name { font-weight: 600; }
        .header-user .user-info .role { color: var(--text-light); font-size: 11px; }
        .user-dropdown { position: relative; }
        .user-dropdown-menu { position: absolute; top: 100%; right: 0; background: var(--card); border: 1px solid var(--border); border-radius: 8px; min-width: 180px; box-shadow: 0 10px 25px rgba(0,0,0,.1); display: none; overflow: hidden; z-index: 100; }
        .user-dropdown-menu.show { display: block; }
        .user-dropdown-menu a { display: flex; align-items: center; gap: 10px; padding: 10px 16px; color: var(--text); text-decoration: none; font-size: 13px; transition: background .2s; }
        .user-dropdown-menu a:hover { background: var(--bg); }
        .user-dropdown-menu a.danger { color: var(--danger); }
        .main { margin-left: var(--sidebar-width); margin-top: var(--header-height); padding: 24px; min-height: calc(100vh - var(--header-height)); }
        .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 12px; }
        .page-header h1 { font-size: 22px; font-weight: 700; color: var(--text); }
        .page-header p { color: var(--text-light); font-size: 13px; margin-top: 4px; }
        .page-header .actions { display: flex; gap: 8px; }
        .card { background: var(--card); border-radius: 12px; border: 1px solid var(--border); overflow: hidden; }
        .card-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        .card-header h3 { font-size: 15px; font-weight: 600; }
        .card-body { padding: 20px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .stat-card { background: var(--card); border-radius: 12px; padding: 20px; border: 1px solid var(--border); display: flex; align-items: center; gap: 16px; }
        .stat-card .icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; }
        .stat-card .icon.green { background: #d1fae5; color: #065f46; }
        .stat-card .icon.blue { background: #dbeafe; color: #1e40af; }
        .stat-card .icon.yellow { background: #fef3c7; color: #92400e; }
        .stat-card .icon.red { background: #fee2e2; color: #991b1b; }
        .stat-card .icon.purple { background: #ede9fe; color: #5b21b6; }
        .stat-card .icon.orange { background: #ffedd5; color: #9a3412; }
        .stat-card .info h3 { font-size: 24px; font-weight: 700; }
        .stat-card .info p { font-size: 12px; color: var(--text-light); margin-top: 2px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        table th { background: var(--bg); padding: 12px 16px; text-align: left; font-weight: 600; color: var(--text-light); font-size: 12px; text-transform: uppercase; letter-spacing: .5px; white-space: nowrap; }
        table td { padding: 12px 16px; border-bottom: 1px solid var(--border); }
        table tr:hover td { background: #f9fafb; }
        .btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border: none; border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer; text-decoration: none; white-space: nowrap; }
        .btn-primary { background: var(--primary); color: #fff; }
        .btn-secondary { background: var(--bg); color: var(--text); border: 1px solid var(--border); }
        .btn-success { background: var(--success); color: #fff; }
        .btn-danger { background: var(--danger); color: #fff; }
        .btn-sm { padding: 5px 10px; font-size: 12px; }
        .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
        .badge-success { background: #d1fae5; color: #065f46; }
        .badge-danger { background: #fee2e2; color: #991b1b; }
        .badge-warning { background: #fef3c7; color: #92400e; }
        .badge-info { background: #dbeafe; color: #1e40af; }
        .empty-state { text-align: center; padding: 60px 20px; color: var(--text-light); }
        .empty-state i { font-size: 48px; margin-bottom: 16px; opacity: .3; }
        @media (max-width: 1024px) {
            .sidebar { transform: translateX(-100%); }
            .sidebar.open { transform: translateX(0); }
            .header { left: 0; }
            .main { margin-left: 0; }
            .menu-toggle { display: block; }
        }
    </style>
</head>
<body>
    <aside class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <?php if (!empty($theme['logo_url'])): ?>
                <img class="logo-img" src="<?php echo esc_url($theme['logo_url']); ?>" alt="Logo">
            <?php else: ?>
                <div class="logo">E</div>
            <?php endif; ?>
            <h2><?php echo esc_html($theme['school_name']); ?></h2>
            <p><?php echo esc_html($theme['school_motto']); ?></p>
        </div>
        <nav class="sidebar-nav">
            <?php
            $home_url = home_url('/sms/');
            function esm_nav_link($slug, $label, $icon, $current_page) {
                printf(
                    '<a href="%s" class="nav-item %s"><i class="fas %s"></i> %s</a>',
                    esc_url(home_url('/sms/' . $slug . '/')),
                    $current_page === $slug ? 'active' : '',
                    esc_attr($icon),
                    esc_html($label)
                );
            }
            ?>
            <div class="nav-section">Main</div>
            <?php esm_nav_link('dashboard', 'Dashboard', 'fa-th-large', $page); ?>

            <?php if (in_array($role, ['esm_super_admin', 'esm_bursar', 'esm_teacher'], true)): ?>
            <div class="nav-section">People</div>
            <?php esm_nav_link('students', 'Students', 'fa-user-graduate', $page); ?>
            <?php if (in_array($role, ['esm_super_admin', 'esm_bursar'], true)): ?>
            <?php esm_nav_link('classes', 'Classes', 'fa-school', $page); ?>
            <?php endif; ?>
            <?php if ($role === 'esm_super_admin'): ?>
            <?php esm_nav_link('staff', 'Staff', 'fa-chalkboard-teacher', $page); ?>
            <?php endif; ?>
            <?php endif; ?>

            <?php if (in_array($role, ['esm_teacher'], true)): ?>
            <div class="nav-section">Academic</div>
            <?php esm_nav_link('exams', 'Exams & Results', 'fa-file-alt', $page); ?>
            <?php esm_nav_link('timetable', 'Timetable', 'fa-calendar-alt', $page); ?>
            <?php endif; ?>

            <?php if (in_array($role, ['esm_super_admin', 'esm_accountant', 'esm_bursar'], true)): ?>
            <div class="nav-section">Finance</div>
            <?php esm_nav_link('fees', 'Fee Management', 'fa-dollar-sign', $page); ?>
            <?php esm_nav_link('invoices', 'Invoices', 'fa-file-invoice-dollar', $page); ?>
            <?php esm_nav_link('debtors', 'Debtors', 'fa-exclamation-triangle', $page); ?>
            <?php if (in_array($role, ['esm_super_admin', 'esm_accountant'], true)): ?>
            <?php esm_nav_link('fee-levels', 'Fee Levels', 'fa-layer-group', $page); ?>
            <?php endif; ?>
            <?php endif; ?>

            <?php if ($role === 'esm_super_admin'): ?>
            <div class="nav-section">Resources</div>
            <?php esm_nav_link('hostel', 'Hostel', 'fa-bed', $page); ?>
            <?php endif; ?>

            <div class="nav-section">Communication</div>
            <?php esm_nav_link('communication', 'Communication', 'fa-bullhorn', $page); ?>

            <?php if (in_array($role, ['esm_super_admin', 'esm_accountant', 'esm_bursar', 'esm_teacher'], true)): ?>
            <div class="nav-section">Analytics</div>
            <?php esm_nav_link('reports', 'Reports', 'fa-chart-bar', $page); ?>
            <?php endif; ?>

            <?php if ($role === 'esm_parent'): ?>
            <div class="nav-section">My Portal</div>
            <?php esm_nav_link('parent-portal', 'Parent Portal', 'fa-home', $page); ?>
            <?php endif; ?>

            <?php if ($role === 'esm_student'): ?>
            <div class="nav-section">My Portal</div>
            <?php esm_nav_link('student-portal', 'Student Portal', 'fa-home', $page); ?>
            <?php endif; ?>

            <?php if (in_array($role, ['esm_super_admin', 'esm_bursar'], true)): ?>
            <div class="nav-section">System</div>
            <a href="<?php echo esc_url(admin_url('admin.php?page=excel-schools-sync')); ?>" class="nav-item"><i class="fas fa-sync-alt"></i> Sync Center</a>
            <?php endif; ?>
            <?php if ($role === 'esm_super_admin'): ?>
            <a href="<?php echo esc_url(admin_url('admin.php?page=excel-schools-settings')); ?>" class="nav-item"><i class="fas fa-cog"></i> Settings</a>
            <?php esm_nav_link('users', 'User Management', 'fa-users-cog', $page); ?>
            <?php endif; ?>
        </nav>
    </aside>

    <header class="header">
        <div class="header-left">
            <button class="menu-toggle" onclick="document.getElementById('sidebar').classList.toggle('open')"><i class="fas fa-bars"></i></button>
        </div>
        <div class="header-right">
            <span class="deployment-badge online"><i class="fas fa-wifi"></i> online</span>
            <div class="user-dropdown">
                <div class="header-user" onclick="document.getElementById('userDropdown').classList.toggle('show')">
                    <div class="avatar"><?php echo esc_html($avatar_letter); ?></div>
                    <div class="user-info">
                        <div class="name"><?php echo esc_html($user->display_name ?: $user->user_login); ?></div>
                        <div class="role"><?php echo esc_html($role_label); ?></div>
                    </div>
                    <i class="fas fa-chevron-down" style="font-size:11px;color:var(--text-light)"></i>
                </div>
                <div class="user-dropdown-menu" id="userDropdown">
                    <a href="<?php echo esc_url(wp_lostpassword_url()); ?>"><i class="fas fa-key"></i> Change Password</a>
                    <?php if ($role === 'esm_super_admin'): ?>
                    <a href="<?php echo esc_url(admin_url('admin.php?page=excel-schools-settings')); ?>"><i class="fas fa-cog"></i> Settings</a>
                    <?php endif; ?>
                    <a href="<?php echo esc_url(wp_logout_url(home_url('/sms/login/'))); ?>" class="danger"><i class="fas fa-sign-out-alt"></i> Logout</a>
                </div>
            </div>
        </div>
    </header>

    <main class="main">
