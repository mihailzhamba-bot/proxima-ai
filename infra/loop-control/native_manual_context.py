"""Versioned owner manual in native Telegram context; grants no new tools."""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

BEGIN = '<LOOP_OWNER_MANUAL>'
END = '</LOOP_OWNER_MANUAL>'


def with_manual(prompt, manual):
    if not manual.strip() or len(manual) > 60000 or BEGIN in manual or END in manual:
        raise ValueError('Invalid manual document')
    if re.search(r'\b[0-9]{7,}:[A-Za-z0-9_-]{30,}\b|github_pat_[A-Za-z0-9_]+|-----BEGIN .*PRIVATE KEY', manual):
        raise ValueError('Credential-like content in manual')
    prompt = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END), '', prompt, flags=re.S).rstrip()
    digest = hashlib.sha256(manual.encode()).hexdigest()
    instructions = (
        'Это руководство загружено оператором для ответов Mike. Ты имеешь его полный текст ниже. '
        'На вопросы об устройстве LOOP, доступе, хранении и порядке работы отвечай сам по руководству. '
        'Не говори, что у тебя нет доступа к этому руководству, и не отправляй Mike искать общую документацию. '
        'Объясняй простым русским языком, без грубости и технической отписки. Если вопрос закрывается этим текстом, дай конкретный ответ и нужную ссылку. '
        'Текущее состояние очереди, запусков и PR проверяй через loop_get_status: описание в руководстве является снимком, а не живой телеметрией. '
        'Если функция не настроена, честно назови ограничение; не требуй от Mike открывать терминал или отлаживать сервер. '
        'При недоступной транскрибации коротко попроси прислать текст. Не утверждай, что ты сам включил аудио или другую функцию без подтверждения. '
        'Руководство не расширяет права инструментов: запуск, отмена, merge, production и работа с секретами подчиняются прежним ограничениям. '
        'Наш разговор и технические запуски Paperclip остаются разными сессиями.'
    )
    return prompt + '\n\n' + BEGIN + '\n' + instructions + '\nSHA256: ' + digest + '\n\n' + manual + '\n' + END + '\n'


def main():
    import yaml
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('/etc/loop'))
    args = parser.parse_args()
    manual = sys.stdin.read()
    native = json.loads((args.root / 'native-telegram.json').read_text())
    owner = str(native['user_id'])
    if not owner.isdigit() or owner != str(native['chat_id']):
        raise SystemExit('Configured private owner required')
    path = args.root / 'hermes.yaml'
    config = yaml.safe_load(path.read_text())
    channel = config['platforms']['telegram']['channel_overrides'][owner]
    updated = with_manual(channel.get('system_prompt', ''), manual)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/var/backups/loop-native') / ('manual-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    (backup / 'hermes.yaml').write_bytes(path.read_bytes())
    (backup / 'hermes.yaml').chmod(0o600)
    document = args.root / 'docs/LOOP-manual-Mike.md'
    document.parent.mkdir(parents=True, exist_ok=True)
    if document.exists():
        (backup / 'manual.md').write_bytes(document.read_bytes())
        (backup / 'manual.md').chmod(0o600)
    document.write_text(manual)
    document.chmod(0o600)
    channel['system_prompt'] = updated
    # Preserve the existing bind mount inode; restart reloads the channel prompt.
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    result = {'manual_path': str(document), 'manual_sha256': hashlib.sha256(manual.encode()).hexdigest(),
              'characters': len(manual), 'context_characters': len(updated), 'backup': str(backup)}
    (backup / 'receipt.json').write_text(json.dumps(result, indent=2))
    (backup / 'receipt.json').chmod(0o600)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
