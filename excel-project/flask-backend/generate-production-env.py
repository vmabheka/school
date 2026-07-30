#!/usr/bin/env python3
"""Create a production env file with cryptographically secure local secrets."""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', default='.env.production.example')
    parser.add_argument('--output', default='.env.production')
    parser.add_argument('--force', action='store_true', help='replace an existing output file')
    args = parser.parse_args()

    template = Path(args.template)
    output = Path(args.output)
    if not template.is_file():
        parser.error(f'template not found: {template}')
    if output.exists() and not args.force:
        parser.error(f'{output} already exists; use --force to replace it')

    secret_key = secrets.token_urlsafe(64)
    admin_password = secrets.token_urlsafe(32)
    database_password = secrets.token_urlsafe(32)
    content = template.read_text(encoding='utf-8')
    replacements = {
        'REPLACE_WITH_OUTPUT_OF_python_-c_import_secrets_print_secrets_token_urlsafe_64': secret_key,
        'REPLACE_WITH_A_UNIQUE_16_PLUS_CHARACTER_ADMIN_PASSWORD': admin_password,
        'REPLACE_WITH_A_LONG_RANDOM_DATABASE_PASSWORD': database_password,
    }
    for placeholder, value in replacements.items():
        if placeholder not in content:
            raise SystemExit(f'Expected placeholder is missing from template: {placeholder}')
        content = content.replace(placeholder, value)

    output.write_text(content, encoding='utf-8')
    output.chmod(0o600)
    print(f'Created {output} with secure generated secrets.')
    print('Set SYNC_API_KEY and review the domain/origin values before deployment.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
