<?php
/**
 * Login page — visual port of the offline app's templates/auth/login.html.
 * Authenticates via WordPress (wp_signon) through AJAX so the same WP
 * user accounts work here as everywhere else on the site.
 */
if (!defined('ABSPATH')) exit;
?><!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign In | <?php echo esc_html($theme['school_name']); ?></title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: <?php echo esc_html($theme['primary_color']); ?>;
            --primary-dark: <?php echo esc_html($theme['primary_dark']); ?>;
            --secondary: <?php echo esc_html($theme['secondary_color']); ?>;
            --text-light: #6b7280; --border: #e5e7eb; --danger: #ef4444;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: <?php echo esc_html($theme['font_family']); ?>; background: <?php echo esc_html($theme['bg_color']); ?>; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .card { width: 100%; max-width: 420px; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,.08); }
        .card-top { padding: 40px 32px; text-align: center; background: linear-gradient(135deg, var(--primary-dark), var(--primary)); }
        .card-top img, .card-top .logo-fallback { width: 90px; height: 90px; border-radius: 50%; margin: 0 auto 16px; display: flex; align-items: center; justify-content: center; background: #fff; padding: 6px; box-shadow: 0 4px 12px rgba(0,0,0,.25); object-fit: cover; font-size: 28px; font-weight: 700; color: var(--primary-dark); }
        .card-top h1 { color: #fff; font-size: 20px; }
        .card-top p { color: rgba(255,255,255,.7); font-size: 13px; margin-top: 4px; }
        .card-body { padding: 32px; }
        .card-body h2 { text-align: center; margin-bottom: 24px; font-size: 18px; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; }
        .form-control { width: 100%; padding: 10px 14px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; }
        .btn-primary { width: 100%; justify-content: center; padding: 12px; font-size: 14px; margin-top: 8px; background: var(--primary); color: #fff; border: none; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 6px; }
        .foot { text-align: center; margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border); }
        .foot p { font-size: 11px; color: var(--text-light); }
        .role-chip { color: #fff; padding: 2px 6px; border-radius: 8px; font-size: 9px; margin: 0 2px; }
        #loginError { color: var(--danger); font-size: 13px; text-align: center; margin-top: 10px; display: none; }
    </style>
</head>
<body>
    <div class="card">
        <div class="card-top">
            <?php if (!empty($theme['logo_url'])): ?>
                <img src="<?php echo esc_url($theme['logo_url']); ?>" alt="Logo">
            <?php else: ?>
                <div class="logo-fallback">E</div>
            <?php endif; ?>
            <h1><?php echo esc_html($theme['school_name']); ?></h1>
            <p><?php echo esc_html($theme['school_motto']); ?></p>
        </div>
        <div class="card-body">
            <h2>Sign In</h2>
            <form id="esmLoginForm">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="username" class="form-control" placeholder="Enter username" required autofocus>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" class="form-control" placeholder="Enter password" required>
                </div>
                <button type="submit" class="btn-primary"><i class="fas fa-sign-in-alt"></i> Sign In</button>
                <div id="loginError"></div>
            </form>
            <div class="foot">
                <div>
                    <span class="role-chip" style="background:#ef4444;">Super Admin</span>
                    <span class="role-chip" style="background:#10b981;">Accountant</span>
                    <span class="role-chip" style="background:#3b82f6;">Bursar</span>
                    <span class="role-chip" style="background:#f59e0b;">Teacher</span>
                    <span class="role-chip" style="background:#c8a951;">Parent</span>
                    <span class="role-chip" style="background:#e85d26;">Student</span>
                </div>
                <p style="margin-top:8px;">MobiSchola v2.5.0 — By Edutechweb 0772577666 — Manage smarter—even offline.</p>
            </div>
        </div>
    </div>
    <script>
        document.getElementById('esmLoginForm').addEventListener('submit', function (e) {
            e.preventDefault();
            var form = e.target;
            var errBox = document.getElementById('loginError');
            errBox.style.display = 'none';
            var data = new FormData();
            data.append('action', 'esm_portal_login');
            data.append('nonce', '<?php echo esc_js(wp_create_nonce('esm_portal_login')); ?>');
            data.append('username', form.username.value);
            data.append('password', form.password.value);
            fetch('<?php echo esc_url(admin_url('admin-ajax.php')); ?>', { method: 'POST', body: data, credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    if (res.success) {
                        window.location.href = res.data.redirect;
                    } else {
                        errBox.textContent = (res.data && res.data.message) || 'Login failed.';
                        errBox.style.display = 'block';
                    }
                })
                .catch(function () {
                    errBox.textContent = 'Network error — please try again.';
                    errBox.style.display = 'block';
                });
        });
    </script>
</body>
</html>
