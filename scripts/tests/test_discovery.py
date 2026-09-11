"""Regression coverage for usable discovery commands and their shell boundaries."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_hook  # noqa: E402
import harness  # noqa: E402


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'modules/application').mkdir(parents=True)
        (self.root / '.agents').mkdir()
        (self.root / '.agents/AGENTS.md').write_text('Instructions\n')
        (self.root / 'README.md').write_text('module example\n')
        (self.root / 'modules/application/main.tf').write_text('locals { example = 1 }\n')
        (self.root / '.env').write_text('PRIVATE=fixture-only\n')
        (self.root / 'Makefile').write_text('.DEFAULT_GOAL := help\nhelp:\n\t@echo verify\n')

    def event(self, command, cwd=None, **extra):
        return {'hook_event_name': 'PreToolUse', 'cwd': str(cwd or self.root),
                'tool_name': 'Bash', 'tool_input': {'command': command, **extra}}

    def assertAllowed(self, command, cwd=None):
        self.assertEqual(agent_hook.handle(self.event(command, cwd), self.root), {}, command)

    def assertDenied(self, command, cwd=None):
        result = agent_hook.handle(self.event(command, cwd), self.root)
        self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny', command)
        return result['hookSpecificOutput']['permissionDecisionReason']

    def test_help_and_default_target_are_available(self):
        for command in ('make help', 'make'):
            self.assertAllowed(command)
            result = subprocess.run(['bash', '-c', command], cwd=self.root,
                                    capture_output=True, text=True, check=True)
            # Recursive make may also print entering/leaving-directory messages.
            self.assertIn('verify', result.stdout.splitlines())

    def test_common_file_exploration_forms(self):
        for command in ('ls', 'ls -la', 'ls -lah modules', 'ls -- .agents',
                        'rg --files', 'rg --files --hidden',
                        "rg --files -g '*.tf' -g '!**/.terraform/**' modules",
                        "rg --files --hidden --glob='AGENTS.md'",
                        "rg --files -g'*.tf' -- modules",
                        "find . -maxdepth 3 -type f -name '*.tf' -print",
                        "find modules -iname '*.TF'", 'find . -type d'):
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_common_content_search_forms(self):
        for command in ('rg module', 'rg -n module modules',
                        'rg -n -e module -- README.md', 'rg README.md -e module',
                        "rg -n -e 'module|output' -- modules",
                        "rg -F 'module example' README.md",
                        "rg -n -e 'module' -e 'output' modules README.md",
                        "rg -n -e 'module; output' README.md"):
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_nested_exploration_and_relative_workdir(self):
        cwd = self.root / 'modules/application'
        for command in ('ls -la', 'rg --files', 'cat main.tf', 'rg -n locals main.tf',
                        "find . -name '*.tf'"):
            with self.subTest(command=command):
                self.assertAllowed(command, cwd)
        self.assertEqual(agent_hook.handle(self.event('cat main.tf', cwd, workdir='.'), self.root), {})
        self.assertIn('repository root', self.assertDenied('make help', cwd))
        self.assertIn('repository root', self.assertDenied('make verify', cwd))

    def test_make_help_does_not_allow_make_overrides_or_other_targets(self):
        for command in ('make help SHELL=/tmp/shell', 'make help -f other.mk',
                        'make -C modules help', 'make help verify', 'make apply',
                        'make hooks-install', 'make help && terraform apply'):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_file_search_options_cannot_execute_commands_or_follow_links(self):
        for command in ('find . -delete', 'find . -exec touch marker +',
                        "find . -name '*.tf' -o -delete", 'find -L . -type f',
                        'find . -fprint output', "find . -printf '%p'", 'ls -L .',
                        'rg --files --pre=python', 'rg --files --follow',
                        'rg --files --no-ignore', 'rg --pre python module',
                        'rg --hidden module', 'rg -g .env PRIVATE',
                        'rg --files -g', 'rg --files --glob='):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_all_explicit_search_paths_are_checked_even_when_options_move(self):
        (self.root / 'alias').symlink_to(self.root / 'modules', target_is_directory=True)
        for command in ('ls /outside', 'find ../outside -name README.md',
                        'rg --files modules /outside', 'rg --files -- /outside',
                        'rg --files alias', 'find alias -type f', 'cat .env',
                        'rg .env -e PRIVATE', 'rg -e PRIVATE .env -- modules',
                        'rg /outside -e pattern', 'rg -e pattern /outside -- modules',
                        'rg -n -e pattern -- modules /outside', 'rg -n module alias'):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_shell_operators_expansion_and_unquoted_globs_remain_denied(self):
        for command in ('pwd && rg --files', 'rg --files | head', 'ls; touch marker',
                        'ls > marker', 'ls\nmake help', "rg --files -g '$(touch marker)'",
                        'rg --files -g "`touch marker`"', 'rg --files *.tf',
                        'cat .en[v]', 'cat ~', 'rg module <(cat .env)',
                        'RIPGREP_CONFIG_PATH=config rg --files', "rg --files -g '*.tf",
                        'rg --files -g "*.tf"\\\n', 'ls\x00', 'cat ' + 'a' * 2048 + '$'):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_quoted_arguments_remain_literal(self):
        command = "rg --files --glob='*.tf' -g'!**/.terraform/**' modules"
        self.assertEqual(harness.literal_words(command), [
            'rg', '--files', '--glob=*.tf', '-g!**/.terraform/**', 'modules'])
        self.assertAllowed(command)

    def test_denial_gives_discovery_examples_and_single_command_guidance(self):
        message = self.assertDenied('pwd && rg --files')
        self.assertIn('rg --files', message)
        self.assertIn('make help', message)
        self.assertIn('one command per call', message)

    @unittest.skipUnless(shutil.which('rg'), 'ripgrep required for real discovery integration')
    def test_real_shell_discovery_commands_with_globs_and_search_patterns(self):
        cases = {
            "rg --files -g '*.tf'": 'modules/application/main.tf',
            "rg --files --hidden --glob='AGENTS.md'": '.agents/AGENTS.md',
            "rg -n -e 'module|output' README.md": '1:module example',
            "find . -maxdepth 4 -name '*.tf'": './modules/application/main.tf',
            'ls modules/application': 'main.tf',
        }
        before = (self.root / '.env').read_bytes()
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertAllowed(command)
                result = subprocess.run(['bash', '-c', command], cwd=self.root,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)
        self.assertEqual((self.root / '.env').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
