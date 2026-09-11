"""Codex wire-contract and multi-file patch scope regressions; no model calls."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_hook  # noqa: E402
import harness  # noqa: E402


class CodexHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'modules/application').mkdir(parents=True)
        (self.root / 'README.md').write_text('Terraform example\n')
        (self.root / 'AGENTS.md').write_text('Agent instructions\n')

    def event(self, tool, command, **extra):
        return {'hook_event_name': 'PreToolUse', 'session_id': 'test-session',
                'turn_id': 'test-turn', 'cwd': str(self.root), 'tool_name': tool,
                'tool_input': {'command': command, **extra}}

    def patch_result(self, body):
        return agent_hook.handle(self.event('apply_patch', '*** Begin Patch\n' + body + '\n*** End Patch'), self.root)

    def assertDenied(self, result):
        self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_codex_add_update_delete_and_move_paths(self):
        patch = ('*** Begin Patch\n*** Add File: modules/application/new.tf\n+locals { a = 1 }\n'
                 '*** Update File: modules/application/main.tf\n*** Move to: modules/application/renamed.tf\n'
                 '@@\n-old\n+new\n*** Delete File: modules/application/old.tf\n*** End Patch')
        self.assertEqual(agent_hook.patch_paths(patch), [
            'modules/application/new.tf', 'modules/application/main.tf',
            'modules/application/renamed.tf', 'modules/application/old.tf'])
        self.assertEqual(agent_hook.handle(self.event('apply_patch', patch), self.root), {})

    def test_mixed_patch_denies_entire_call(self):
        self.assertDenied(self.patch_result(
            '*** Add File: modules/application/ok.tf\n+locals { a = 1 }\n'
            '*** Update File: environments/prod/main.tf\n@@\n-old\n+new'))

    def test_move_checks_both_source_and_destination(self):
        for source, target in [('modules/application/main.tf', '.codex/hooks.json'),
                               ('.codex/config.toml', 'modules/application/copy.tf'),
                               ('modules/application/main.tf', '../outside.tf')]:
            with self.subTest(source=source, target=target):
                self.assertDenied(self.patch_result(
                    f'*** Update File: {source}\n*** Move to: {target}\n@@\n-old\n+new'))

    def test_protected_delete_and_absolute_outside_are_denied(self):
        for body in ('*** Delete File: AGENTS.md', '*** Add File: /outside/new.tf\n+x',
                     '*** Add File: modules/application/../network/main.tf\n+x',
                     '*** Delete File: terraform.tfstate',
                     '*** Update File: .codex/rules/terraform.rules\n@@\n-old\n+new'):
            with self.subTest(body=body):
                self.assertDenied(self.patch_result(body))

    def test_patch_refuses_symlink_target(self):
        (self.root / 'alias').symlink_to(self.root / 'modules/application', target_is_directory=True)
        self.assertDenied(self.patch_result('*** Add File: alias/main.tf\n+x'))

    def test_unsupported_or_malformed_patch_fails_closed(self):
        for patch in ('', None, '*** Begin Patch\n*** End Patch',
                      '*** Begin Patch\n*** Add File: main.tf\nnot-an-added-line\n*** End Patch',
                      '*** Begin Patch\n*** Rename File: main.tf\n*** End Patch',
                      '*** Begin Patch\n*** Move to: main.tf\n*** End Patch',
                      '*** Begin Patch\n*** Add File: main.tf\n+x',
                      '*** Begin Patch\n*** Add File: \n+x\n*** End Patch'):
            with self.subTest(patch=patch):
                self.assertDenied(agent_hook.handle(self.event('apply_patch', patch), self.root))

    def test_patch_content_cannot_be_confused_with_directives(self):
        result = self.patch_result('*** Add File: modules/application/note.txt\n'
                                   '+*** Delete File: AGENTS.md\n+*** End Patch')
        self.assertEqual(result, {})

    def test_old_claude_file_path_payload_is_not_accepted(self):
        self.assertDenied(agent_hook.handle(self.event('Edit', '', file_path='README.md'), self.root))
        self.assertDenied(agent_hook.handle(self.event('apply_patch', None, file_path='README.md'), self.root))

    def test_codex_source_reads_are_available(self):
        for command in ('pwd', 'rg --files', 'rg --files modules', 'cat README.md AGENTS.md',
                        "sed -n '1,100p' README.md", 'rg -n -e Terraform -- README.md',
                        'rg -n -e module -- modules'):
            with self.subTest(command=command):
                self.assertEqual(agent_hook.handle(self.event('Bash', command), self.root), {})

    def test_read_commands_cannot_write_or_escape(self):
        (self.root / '.env').write_text('PRIVATE=value\n')
        (self.root / 'alias.md').symlink_to(self.root / 'README.md')
        for command in ('cat ../outside', 'cat /etc/passwd', 'cat .env', 'cat alias.md',
                        'cat README.md > AGENTS.md', 'rg --pre=python README.md',
                        'rg --files --hidden', 'rg -n -e Terraform -- .env',
                        "sed -n '1,2w AGENTS.md' README.md", 'cat --help',
                        'make verify; python3 -c pass'):
            with self.subTest(command=command):
                self.assertDenied(agent_hook.handle(self.event('Bash', command), self.root))

    def test_tool_workdir_override_is_denied(self):
        self.assertDenied(agent_hook.handle(self.event('Bash', 'make verify', workdir='/outside'), self.root))
        self.assertDenied(agent_hook.handle(self.event('Bash', 'make verify', cwd='modules/application'), self.root))

    def test_configured_command_resolves_from_nested_checkout_cwd(self):
        config = json.loads((harness.ROOT / '.codex/hooks.json').read_text())
        groups = config['hooks']['PreToolUse']
        group = next(g for g in groups if re.search(g['matcher'], 'apply_patch'))
        command = group['hooks'][0]['command']
        cwd = harness.ROOT / 'modules/application'
        event = {'hook_event_name': 'PreToolUse', 'cwd': str(cwd), 'tool_name': 'apply_patch',
                 'tool_input': {'command': '*** Begin Patch\n*** Add File: sample.tf\n+x\n*** End Patch'}}
        result = subprocess.run(['bash', '-c', command], cwd=cwd, input=json.dumps(event),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})
        # This is only an adapter invocation; it must not apply the supplied patch.
        self.assertFalse((cwd / 'sample.tf').exists())


if __name__ == '__main__':
    unittest.main()
