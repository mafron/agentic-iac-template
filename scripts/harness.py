#!/usr/bin/env python3
"""Small, deterministic local gates. These are not an authorization sandbox."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = Path('.harness/verification.json')
SKIP_DIRS = {'.git', '.terraform', '.harness', '__pycache__', '.pytest_cache'}
SIMPLE_TARGETS = {
    'help', 'fmt', 'validate', 'test', 'lint', 'verify', 'python-test',
    'policy-test', 'demo', 'harness-status',
}
PROTECTED_DIRS = {'.github', '.githooks', '.agents', '.codex', '.claude', 'scripts', 'policies'}
PROTECTED_NAMES = {
    'AGENTS.md', 'CLAUDE.md', 'Makefile', 'makefile', 'GNUmakefile', '.gitignore', '.gitattributes',
    '.terraform-version', '.tflint-version', '.opa-version', '.tflint.hcl',
    '.terraform.lock.hcl', 'versions.tf', 'backend.tf',
}


class GateError(Exception):
    pass


def run_git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def private_path(path):
    """Prevent accidental known artifacts; NOT a general secret scanner."""
    p = Path(path)
    n = p.name
    if n.endswith('.example'):
        return False
    return ('.harness' in p.parts or '.terraform' in p.parts
            or 'terraform.tfstate.d' in p.parts
            or '.tfstate' in n or n == 'tfplan' or n.endswith('.tfplan')
            or n in {'plan.json', 'crash.log', 'credentials'}
            or n.startswith('crash.') or n == '.env' or n.startswith('.env.')
            or n.endswith(('.tfvars', '.tfvars.json', '.s3.hcl', '.pem', '.key'))
            or n == 'settings.local.json')


def fingerprint(root):
    """Hash file paths, contents and executable bits, including ignored tfvars.

    Only tool outputs/caches are excluded. Refuse symlinks rather than trusting
    inputs outside this checkout. No source or secret values are printed.
    """
    digest = hashlib.sha256()
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in dirs + sorted(files):
            path = Path(base) / name
            if path.is_symlink():
                raise GateError('Symlink input is unsupported; use regular repository files.')
        for name in sorted(files):
            path = Path(base) / name
            if (name.endswith(('.pyc', '.tfstate', '.tfstate.backup')) or name == 'tfplan'
                    or name.endswith('.tfplan') or name == 'plan.json'
                    or name.startswith('crash.')):
                continue
            rel = path.relative_to(root).as_posix().encode()
            content = path.read_bytes()
            for part in (rel, str(path.stat().st_mode & 0o111).encode(), content):
                digest.update(len(part).to_bytes(8, 'big'))
                digest.update(part)
    return digest.hexdigest()


def record_success(root, expected):
    if fingerprint(root) != expected:
        raise GateError('Inputs changed during verification. Run make verify again.')
    path = root / RECEIPT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'schema': 1, 'command': 'make verify',
                               'sha256': expected}, sort_keys=True) + '\n')
    tmp.replace(path)


def verification_status(root):
    try:
        receipt = json.loads((root / RECEIPT).read_text())
        if not isinstance(receipt, dict) or receipt.get('schema') != 1:
            raise ValueError('schema')
        if receipt.get('command') != 'make verify':
            raise ValueError('command')
        if receipt.get('sha256') != fingerprint(root):
            return False, 'Inputs changed since verification. Run make verify.'
    except (OSError, ValueError, GateError):
        return False, 'No valid verification receipt. Run make verify.'
    return True, 'PASS: current inputs match a successful make verify.'


def readable_path(root, raw_path, cwd=None):
    """Allow scoped source reads without accepting options, secrets or symlinks."""
    if not raw_path or raw_path.startswith('-'):
        return False
    supplied = Path(raw_path)
    if '..' in supplied.parts:
        return False
    root = root.resolve()
    path = supplied if supplied.is_absolute() else Path(cwd or root) / supplied
    if not path.is_relative_to(root):
        return False
    rel = path.relative_to(root)
    if '.git' in rel.parts or private_path(rel):
        return False
    if any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(root)):
        return False
    return path.is_file() or path.is_dir()


# Accept literal shell words, including quoted glob/regex arguments. Unquoted
# shell operators, expansion, escapes and control characters remain unsupported.
SHELL_WORD = (
    r'''(?:[^\s'"`$\\;&|<>(){}\[\]*?!#~\x00-\x1f]'''
    r'''|'[^'`$\\\x00-\x1f]*'|"[^"`$\\\x00-\x1f]*")+'''
)


def literal_words(command):
    if not isinstance(command, str) or not re.fullmatch(
            rf'[ \t]*{SHELL_WORD}(?:[ \t]+{SHELL_WORD})*[ \t]*', command):
        return None
    return shlex.split(command)


def file_listing_allowed(args, root, cwd):
    """rg --files only lists names; never enable preprocessors or symlink following."""
    paths = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--':
            paths.extend(args[i + 1:])
            break
        if arg in {'--hidden', '--no-config'}:
            pass
        elif arg in {'-g', '--glob'}:
            i += 1
            if i >= len(args) or not args[i]:
                return False
        elif arg.startswith('--glob=') or (arg.startswith('-g') and len(arg) > 2):
            if arg == '--glob=':
                return False
        elif arg.startswith('-'):
            return False
        else:
            paths.append(arg)
        i += 1
    return all(readable_path(root, p, cwd) for p in paths)


def search_allowed(args, root, cwd):
    """Common rg content searches with literal patterns and scoped paths."""
    patterns = []
    paths = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--':
            paths.extend(args[i + 1:])
            break
        if arg in {'-n', '--line-number', '-i', '--ignore-case', '-F', '--fixed-strings',
                   '-S', '--smart-case', '--no-config'}:
            pass
        elif arg in {'-e', '--regexp'}:
            i += 1
            if i >= len(args):
                return False
            patterns.append(args[i])
        elif arg.startswith('-'):
            return False
        else:
            paths.append(arg)
        i += 1
    # With any -e present, ALL positional arguments are paths, even those before
    # -e. Otherwise the first positional argument is the search pattern.
    if not patterns and paths:
        patterns.append(paths.pop(0))
    return bool(patterns) and all(readable_path(root, p, cwd) for p in paths)


def find_allowed(args, root, cwd):
    """One search root, name/type/depth filters and printing; no action predicates."""
    if not args or not readable_path(root, args[0], cwd):
        return False
    options = args[1:]
    if options and options[-1] == '-print':
        options = options[:-1]
    if len(options) % 2:
        return False
    for flag, value in zip(options[::2], options[1::2]):
        if flag == '-maxdepth':
            if not re.fullmatch(r'[0-9]+', value):
                return False
        elif flag == '-type':
            if value not in {'f', 'd'}:
                return False
        elif flag not in {'-name', '-iname'}:
            return False
    return True


def command_allowed(command, root=ROOT, cwd=None):
    """A deliberately narrow shell grammar; never execute agent-supplied text."""
    words = literal_words(command)
    if not words:
        return False
    root = root.resolve()
    cwd = Path(cwd or root)
    if not readable_path(root, str(cwd)) or not cwd.is_dir():
        return False
    if words in (['git', 'status', '--short'], ['git', 'diff'],
                 ['git', 'diff', '--stat'], ['git', 'diff', '--cached']):
        return True
    if words == ['pwd']:
        return True
    if words[0] == 'ls':
        args = words[1:]
        if args and re.fullmatch(r'-[alhd1F]+', args[0]):
            args = args[1:]
        if args and args[0] == '--':
            args = args[1:]
        return all(readable_path(root, p, cwd) for p in args)
    if len(words) >= 2 and words[0] == 'cat':
        return all(readable_path(root, p, cwd) and (cwd / p).is_file() for p in words[1:])
    if words[:2] == ['rg', '--files']:
        return file_listing_allowed(words[2:], root, cwd)
    if words[0] == 'rg':
        return search_allowed(words[1:], root, cwd)
    if words[0] == 'find':
        return find_allowed(words[1:], root, cwd)
    if (len(words) == 4 and words[:2] == ['sed', '-n']
            and re.fullmatch(r'[1-9][0-9]*(,[1-9][0-9]*)?p', words[2])):
        return readable_path(root, words[3], cwd) and (cwd / words[3]).is_file()
    # Make must use the reviewed root Makefile even when read-only tools use a
    # nested session cwd. No -C / -f / shell or environment overrides are allowed.
    if words[0] != 'make' or cwd != root:
        return False
    if words == ['make']:
        return True  # The reviewed default target is help.
    if len(words) == 2 and words[0] == 'make' and words[1] in SIMPLE_TARGETS:
        return True
    if len(words) < 3 or words[0] != 'make':
        return False
    values = {}
    for word in words[2:]:
        key, sep, value = word.partition('=')
        if not sep or key in values or not value:
            return False
        values[key] = value
    if words[1] == 'plan':
        return (set(values) == {'ENV', 'VAR_FILE', 'BACKEND_CONFIG'}
                and values['ENV'] in {'dev', 'staging'}
                and all(Path(values[k]).is_absolute() for k in ('VAR_FILE', 'BACKEND_CONFIG')))
    if words[1] in {'policy', 'risk-summary'}:
        return (set(values) == {'ENV', 'PLAN_JSON'}
                and values['ENV'] in {'dev', 'staging', 'prod'}
                and Path(values['PLAN_JSON']).is_absolute())
    return False


def guarded_path(root, cwd, raw_path):
    if (not isinstance(raw_path, str) or not raw_path
            or any(ord(c) < 32 for c in raw_path)):
        raise GateError('Missing file path.')
    root = root.resolve()
    cwd = Path(cwd).resolve()
    if not cwd.is_relative_to(root):
        raise GateError('Working directory must be inside this checkout.')
    supplied = Path(raw_path)
    if '..' in supplied.parts:
        raise GateError('Parent traversal is not accepted.')
    path = supplied if supplied.is_absolute() else cwd / supplied
    if not path.is_relative_to(root):
        raise GateError('File must be inside this checkout.')
    rel = path.relative_to(root)
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise GateError('Symlink writes are not accepted.')
    if not rel.parts or '.git' in rel.parts or private_path(rel):
        raise GateError('State, credential and generated artifacts are outside the edit workflow.')
    if (rel.parts[0] in PROTECTED_DIRS or rel.name in PROTECTED_NAMES
            or rel.parts[:2] == ('environments', 'prod')):
        raise GateError('Protected control or high-risk scope: prepare a human-reviewed maintenance change.')
    return path


def fmt_feedback(root):
    try:
        result = subprocess.run(['terraform', 'fmt', '-check', '-recursive'], cwd=root,
                                capture_output=True, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, 'Fmt was not completed (missing Terraform or timeout). Run make verify when available.'
    if result.returncode:
        return False, 'Fmt check failed. Run make fmt, review the diff, then make verify.'
    return True, 'Fmt check passed. Full verification is still required: make verify.'


def pre_commit(root):
    paths = run_git(root, 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z')
    for raw in filter(None, paths.split(b'\0')):
        path = raw.decode('utf-8')
        if private_path(path):
            raise GateError('Staged state, plan or credential artifact detected; remove it from the index.')
        if path.endswith(('.tf', '.tftest.hcl', '.terraform.lock.hcl')):
            # Read the INDEX, not a possibly different working-tree copy.
            content = run_git(root, 'show', ':' + path)
            try:
                result = subprocess.run(['terraform', 'fmt', '-check', '-'], input=content,
                                        capture_output=True, timeout=20)
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                raise GateError('Staged fmt not completed: install pinned Terraform and retry.') from exc
            if result.returncode:
                raise GateError('Staged Terraform is not formatted or valid HCL. Run make fmt and re-stage.')


def pre_push(root, ref_lines):
    head = run_git(root, 'rev-parse', 'HEAD').decode().strip()
    lines = ref_lines.splitlines()
    if not lines:
        raise GateError('Missing push ref input.')
    for line in lines:
        parts = line.split()
        if (len(parts) != 4 or not parts[0].startswith('refs/heads/')
                or not parts[2].startswith('refs/heads/') or parts[1] != head):
            raise GateError('Only the verified current HEAD branch may be pushed; other refs need separate verification.')
    if run_git(root, 'status', '--porcelain', '--untracked-files=all'):
        raise GateError('Commit or remove pending source changes before push, then run make verify.')
    ok, reason = verification_status(root)
    if not ok:
        raise GateError(reason)


def install_hooks(root):
    current = subprocess.run(['git', '-C', str(root), 'config', '--get', 'core.hooksPath'],
                             capture_output=True, text=True)
    if current.returncode not in (0, 1):
        raise GateError('Cannot read Git hook configuration.')
    if current.stdout.strip() not in ('', '.githooks'):
        raise GateError('Existing core.hooksPath found; integrate explicitly instead of overwriting it.')
    run_git(root, 'config', '--local', 'core.hooksPath', '.githooks')
    print('Installed repository-local Git hooks. CI remains mandatory.')


def check_codex_rules(root):
    for command in (['terraform', '-chdir=environments/prod', 'apply'],
                    ['aws', 'sts', 'get-caller-identity']):
        try:
            result = subprocess.run(
                ['codex', 'execpolicy', 'check', '--rules',
                 str(root / '.codex/rules/terraform.rules'), '--', *command],
                check=True, capture_output=True, text=True, timeout=30)
        except FileNotFoundError as exc:
            raise GateError('NOT RUN: install Codex CLI to validate native rules.') from exc
        verdict = json.loads(result.stdout)
        if not isinstance(verdict, dict) or verdict.get('decision') != 'forbidden':
            raise GateError('Native Codex rule did not forbid the test command.')
    print('PASS: native Codex rules forbid direct Terraform and AWS commands.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gate', choices=['fingerprint', 'record', 'status', 'pre-commit', 'pre-push', 'install', 'rules-check'])
    parser.add_argument('--expected')
    args = parser.parse_args()
    try:
        if args.gate == 'fingerprint':
            print(fingerprint(ROOT))
        elif args.gate == 'record':
            if not args.expected:
                raise GateError('Missing verification input hash.')
            record_success(ROOT, args.expected)
        elif args.gate == 'status':
            ok, reason = verification_status(ROOT)
            print(reason)
            return 0 if ok else 1
        elif args.gate == 'pre-commit':
            pre_commit(ROOT)
        elif args.gate == 'pre-push':
            pre_push(ROOT, sys.stdin.read())
        elif args.gate == 'install':
            install_hooks(ROOT)
        elif args.gate == 'rules-check':
            check_codex_rules(ROOT)
    except (GateError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
