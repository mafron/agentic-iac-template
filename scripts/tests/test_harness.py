"""Regression tests for bypasses, stale evidence and native hook contracts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import harness  # noqa: E402
import agent_hook  # noqa: E402


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.file = self.root / 'main.tf'
        self.file.write_text('locals { example = "one" }\n')

    def receipt(self):
        harness.record_success(self.root, harness.fingerprint(self.root))

    def git(self, *args, check=True):
        return subprocess.run(['git', '-C', str(self.root), *args], check=check,
                              capture_output=True, text=True)

    def init_git(self):
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Harness test')
        self.git('config', 'user.email', 'harness@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        (self.root / '.gitignore').write_text('.harness/\n*.auto.tfvars\n')
        self.git('add', '.')
        self.git('-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'fixture')

    def push_line(self):
        sha = self.git('rev-parse', 'HEAD').stdout.strip()
        return f'refs/heads/main {sha} refs/heads/main {"0" * 40}\n'

    def test_command_allowlist(self):
        for command in ('make verify', 'make fmt', 'make harness-status', 'git diff --cached',
                        'make plan ENV=dev VAR_FILE=/private/dev.tfvars BACKEND_CONFIG=/private/dev.s3.hcl',
                        'make policy ENV=prod PLAN_JSON=/private/plan.json',
                        'make risk-summary ENV=dev PLAN_JSON=/private/plan.json'):
            with self.subTest(command=command):
                self.assertTrue(harness.command_allowed(command))

    def test_shell_bypasses_and_unsafe_commands_are_denied(self):
        for command in ('terraform apply', 'terraform state rm x', 'terraform import x y',
                        'terraform force-unlock x', 'aws s3 ls', 'python3 -c pass',
                        'make verify; terraform apply', 'make verify\nterraform apply',
                        'make verify && true', 'make verify | cat', 'make verify > file',
                        'make verify $(id)', 'make verify `id`', 'ENV=prod make plan',
                        'make -C /tmp verify', 'make verify SHELL=/tmp/bypass',
                        'make verify -f /tmp/bypass', 'make hooks-install',
                        'make plan ENV=prod VAR_FILE=/x BACKEND_CONFIG=/y',
                        'make plan ENV=dev ENV=staging VAR_FILE=/x BACKEND_CONFIG=/y',
                        'make plan ENV=dev VAR_FILE=relative BACKEND_CONFIG=/y'):
            with self.subTest(command=command):
                self.assertFalse(harness.command_allowed(command))

    def test_normal_edit_allowed(self):
        path = harness.guarded_path(self.root, self.root, 'modules/application/main.tf')
        self.assertEqual(path, self.root / 'modules/application/main.tf')

    def test_protected_and_private_edits_denied(self):
        for path in ('../main.tf', '/outside/main.tf', '.git/config', 'AGENTS.md',
                     'modules/network/main.tf', 'environments/prod/main.tf',
                     'environments/dev/backend.tf', 'modules/application/versions.tf',
                     'scripts/harness.py', '.agents/skills/a/SKILL.md', '.codex/config.toml',
                     '.codex/hooks.json', '.codex/rules/terraform.rules',
                     '.claude/settings.json', '.github/workflows/check.yml',
                     'Makefile', 'makefile', 'GNUmakefile', 'terraform.tfstate.backup', '.env', 'dev.tfvars'):
            with self.subTest(path=path), self.assertRaises(harness.GateError):
                harness.guarded_path(self.root, self.root, path)

    def test_symlink_edit_denied(self):
        (self.root / 'link').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(harness.GateError):
            harness.guarded_path(self.root, self.root, 'link/main.tf')
        with self.assertRaises(harness.GateError):
            harness.fingerprint(self.root)

    def test_receipt_missing_malformed_and_current(self):
        self.assertFalse(harness.verification_status(self.root)[0])
        self.receipt()
        self.assertTrue(harness.verification_status(self.root)[0])
        (self.root / harness.RECEIPT).write_text('[]')
        self.assertFalse(harness.verification_status(self.root)[0])
        (self.root / harness.RECEIPT).write_text('{broken')
        self.assertFalse(harness.verification_status(self.root)[0])

    def test_edit_same_mtime_invalidates_receipt(self):
        self.receipt()
        before = self.file.stat()
        self.file.write_text('locals { example = "two" }\n')
        os.utime(self.file, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertFalse(harness.verification_status(self.root)[0])

    def test_rename_and_delete_invalidates_receipt(self):
        self.receipt()
        self.file.rename(self.root / 'renamed.tf')
        self.assertFalse(harness.verification_status(self.root)[0])
        self.receipt()
        (self.root / 'renamed.tf').unlink()
        self.assertFalse(harness.verification_status(self.root)[0])

    def test_ignored_terraform_inputs_are_fingerprinted(self):
        self.init_git()
        self.receipt()
        (self.root / 'local.auto.tfvars').write_text('owner = "changed"\n')
        self.assertEqual(self.git('status', '--porcelain').stdout, '')
        self.assertFalse(harness.verification_status(self.root)[0])

    def test_source_with_state_word_is_still_fingerprinted(self):
        self.receipt()
        (self.root / 'old.tfstate.tf').write_text('locals { a = 1 }\n')
        self.assertFalse(harness.verification_status(self.root)[0])

    def test_cache_does_not_invalidate_receipt(self):
        self.receipt()
        (self.root / '.harness/output').write_text('cache')
        (self.root / '__pycache__').mkdir()
        (self.root / '__pycache__/temp.pyc').write_bytes(b'cache')
        self.assertTrue(harness.verification_status(self.root)[0])

    def test_edit_during_verify_refuses_receipt(self):
        expected = harness.fingerprint(self.root)
        self.file.write_text('changed')
        with self.assertRaises(harness.GateError):
            harness.record_success(self.root, expected)
        self.assertFalse((self.root / harness.RECEIPT).exists())

    def test_failed_verify_removes_prior_receipt(self):
        # Exercise the real shell wrapper up to a deterministic tool/context error.
        (self.root / 'scripts').mkdir()
        for name in ('verify.sh', 'common.sh', 'harness.py'):
            shutil.copy(SCRIPTS / name, self.root / 'scripts' / name)
        self.receipt()
        env = {**os.environ, 'TF_CLI_ARGS': '-unsafe-test-argument'}
        result = subprocess.run(['bash', 'scripts/verify.sh'], cwd=self.root, env=env,
                                capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / harness.RECEIPT).exists())

    def test_staged_artifact_rejected_even_if_worktree_removed(self):
        self.init_git()
        secret = self.root / 'terraform.tfstate.backup'
        secret.write_text('{}')
        self.git('add', str(secret))
        secret.unlink()
        with self.assertRaises(harness.GateError):
            harness.pre_commit(self.root)

    @unittest.skipUnless(shutil.which('terraform'), 'Pinned Terraform required for real staged-blob fmt test')
    def test_real_staged_fmt_ignores_corrected_worktree(self):
        self.init_git()
        self.file.write_text('locals {\nexample="bad format"\n}\n')
        self.git('add', 'main.tf')
        self.file.write_text('locals {\n  example = "bad format"\n}\n')
        with self.assertRaises(harness.GateError):
            harness.pre_commit(self.root)
        self.git('add', 'main.tf')
        harness.pre_commit(self.root)

    def test_push_only_current_verified_clean_branch(self):
        self.init_git()
        self.receipt()
        harness.pre_push(self.root, self.push_line())
        self.file.write_text('changed')
        with self.assertRaises(harness.GateError):
            harness.pre_push(self.root, self.push_line())

    def test_push_other_refs_and_deletions_denied(self):
        self.init_git()
        self.receipt()
        sha = self.git('rev-parse', 'HEAD').stdout.strip()
        for lines in ('', f'refs/heads/main {"1" * 40} refs/heads/main {sha}',
                      f'refs/tags/v1 {sha} refs/tags/v1 {"0" * 40}',
                      f'(delete) {"0" * 40} refs/heads/old {sha}'):
            with self.subTest(lines=lines), self.assertRaises(harness.GateError):
                harness.pre_push(self.root, lines)

    def test_push_without_receipt_denied(self):
        self.init_git()
        with self.assertRaises(harness.GateError):
            harness.pre_push(self.root, self.push_line())

    def test_hook_install_preserves_existing_custom_hooks(self):
        self.init_git()
        self.git('config', '--local', 'core.hooksPath', '/custom/hooks')
        with self.assertRaises(harness.GateError):
            harness.install_hooks(self.root)
        self.assertEqual(self.git('config', 'core.hooksPath').stdout.strip(), '/custom/hooks')

    def test_real_git_hook_entrypoints(self):
        self.init_git()
        (self.root / '.githooks').mkdir()
        (self.root / 'scripts').mkdir()
        for name in ('pre-commit', 'pre-push'):
            shutil.copy2(SCRIPTS.parent / '.githooks' / name, self.root / '.githooks' / name)
        shutil.copy(SCRIPTS / 'harness.py', self.root / 'scripts/harness.py')
        self.git('add', '.')
        self.git('-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'install files')
        harness.install_hooks(self.root)
        (self.root / 'tfplan').write_text('sensitive plan')
        self.git('add', 'tfplan')
        rejected = self.git('commit', '-m', 'must fail', check=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn('artifact', rejected.stderr)
        self.git('reset', '--', 'tfplan')
        (self.root / 'tfplan').unlink()
        self.receipt()
        pushed = subprocess.run([str(self.root / '.githooks/pre-push')], cwd=self.root,
                                input=self.push_line(), text=True, capture_output=True)
        self.assertEqual(pushed.returncode, 0, pushed.stderr)


class AdapterTests(unittest.TestCase):
    def event(self, phase, **extra):
        return {'hook_event_name': phase, 'cwd': str(harness.ROOT), **extra}

    def test_pretool_pass_abstains_and_deny_is_native_json(self):
        allowed = agent_hook.handle(self.event('PreToolUse', tool_name='Bash',
                                              tool_input={'command': 'make verify'}))
        self.assertEqual(allowed, {})
        denied = agent_hook.handle(self.event('PreToolUse', tool_name='Bash',
                                             tool_input={'command': 'terraform apply'}))
        self.assertEqual(denied['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_nested_cwd_cannot_select_different_makefile(self):
        event = self.event('PreToolUse', tool_name='Bash', tool_input={'command': 'make verify'})
        event['cwd'] = str(harness.ROOT / 'modules/application')
        self.assertEqual(agent_hook.handle(event)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_missing_and_unhandled_input_fail_closed(self):
        with self.assertRaises(ValueError):
            agent_hook.handle([])
        with self.assertRaises(ValueError):
            agent_hook.handle({'hook_event_name': 'Stop', 'cwd': '/outside'})
        denied = agent_hook.handle(self.event('PreToolUse', tool_name='Bash', tool_input={}))
        self.assertEqual(denied['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_post_edit_failure_feedback(self):
        with patch.object(agent_hook, 'fmt_feedback', return_value=(False, 'Fmt check failed.')):
            result = agent_hook.handle(self.event('PostToolUse', tool_name='apply_patch'))
        self.assertEqual(result['hookSpecificOutput']['additionalContext'], 'Fmt check failed.')

    def test_stop_has_bounded_repair_and_no_false_pass(self):
        with patch.object(agent_hook, 'verification_status', return_value=(False, 'Run make verify.')):
            first = agent_hook.handle(self.event('Stop', stop_hook_active=False))
            second = agent_hook.handle(self.event('Stop', stop_hook_active=True))
        self.assertEqual(first['decision'], 'block')
        self.assertIn('remains FAIL', second['systemMessage'])
        self.assertNotIn('decision', second)  # Can report failure instead of an infinite repair loop.
        with patch.object(agent_hook, 'verification_status', return_value=(True, 'PASS')):
            self.assertEqual(agent_hook.handle(self.event('Stop')), {})

    def test_missing_formatter_does_not_report_pass(self):
        with patch.object(harness.subprocess, 'run', side_effect=FileNotFoundError):
            self.assertFalse(harness.fmt_feedback(harness.ROOT)[0])

    def test_json_adapter_cli_exit_contract(self):
        bad = subprocess.run([sys.executable, str(SCRIPTS / 'agent_hook.py')],
                             input='{broken', capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        good = subprocess.run([sys.executable, str(SCRIPTS / 'agent_hook.py')],
                              input=json.dumps(self.event('PreToolUse', tool_name='Bash',
                                                         tool_input={'command': 'make verify'})),
                              capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads(good.stdout), {})


if __name__ == '__main__':
    unittest.main()
