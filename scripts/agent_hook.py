#!/usr/bin/env python3
"""Codex lifecycle JSON adapter. Core checks live in harness.py."""
import json
from pathlib import Path
import sys

from harness import ROOT, GateError, command_allowed, fmt_feedback, guarded_path, verification_status


def deny(reason):
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny', 'permissionDecisionReason': reason}}


def patch_paths(command):
    """Inspect the strict apply_patch envelope; Codex validates actual hunks.

    Both ends of a move and every file in a multi-file patch must pass the gate.
    An unsupported directive is a denial, never a reason to skip a path.
    """
    if not isinstance(command, str) or not command:
        raise GateError('Missing apply_patch command.')
    lines = command.replace('\r\n', '\n').strip('\n').split('\n')
    if lines[0] != '*** Begin Patch' or lines[-1] != '*** End Patch':
        raise GateError('Expected a complete apply_patch envelope.')
    paths = []
    operation = None
    can_move = False
    for line in lines[1:-1]:
        if line.startswith(('*** Add File: ', '*** Update File: ', '*** Delete File: ')):
            operation, path = line[4:].split(': ', 1)
            paths.append(path)
            can_move = operation == 'Update File'
        elif line.startswith('*** Move to: ') and can_move:
            paths.append(line[len('*** Move to: '):])
            can_move = False
        elif operation == 'Add File' and line.startswith('+'):
            continue
        elif operation == 'Update File' and (
                line.startswith((' ', '+', '-', '@@')) or line in {'', '*** End of File'}):
            can_move = False
        else:
            raise GateError('Unsupported apply_patch directive or malformed file section.')
    if not paths:
        raise GateError('Patch contains no files.')
    return paths


def handle(event, root=ROOT):
    if not isinstance(event, dict):
        raise ValueError('Expected a JSON object.')
    phase = event.get('hook_event_name')
    cwd = event.get('cwd')
    if not isinstance(cwd, str) or not Path(cwd).resolve().is_relative_to(root.resolve()):
        raise ValueError('Hook cwd must be inside this checkout.')
    if phase == 'PreToolUse':
        tool = event.get('tool_name')
        value = event.get('tool_input')
        if not isinstance(value, dict):
            return deny('Missing tool input.')
        for key in ('cwd', 'workdir'):
            if key in value and (not isinstance(value[key], str)
                                 or Path(value[key]).resolve() != Path(cwd).resolve()):
                return deny('Tool working directory override is outside this hook profile.')
        if tool == 'Bash':
            # Make must execute at the reviewed root, not a nested/untrusted Makefile.
            if Path(cwd).resolve() != root.resolve() or not command_allowed(value.get('command'), root):
                return deny('Use an approved make command at the repository root. See docs/hooks-and-skills.md.')
        elif tool == 'apply_patch':
            try:
                for path in patch_paths(value.get('command')):
                    guarded_path(root, cwd, path)
            except GateError as exc:
                return deny(str(exc))
        else:
            return deny('This tool is not covered by the adapter.')
        # Abstain. NEVER emit "allow": preserve the client's own permissions.
        return {}
    if phase == 'PostToolUse':
        if event.get('tool_name') != 'apply_patch':
            raise ValueError('Unsupported post-edit tool.')
        _, message = fmt_feedback(root)
        return {'hookSpecificOutput': {'hookEventName': 'PostToolUse',
                                      'additionalContext': message}}
    if phase == 'Stop':
        ok, message = verification_status(root)
        if ok:
            return {}
        if event.get('stop_hook_active') is True:
            # One repair opportunity, then allow an honest failure/human handoff.
            # The receipt and Git pre-push gate STILL fail.
            return {'systemMessage': 'Verification remains FAIL. Report the blocker and hand off to a human. ' + message}
        return {'decision': 'block', 'reason': message + ' Retry once; if unavailable, report FAIL / NOT RUN.'}
    raise ValueError('Unsupported hook event.')


def main():
    try:
        result = handle(json.load(sys.stdin))
    except (ValueError, OSError, GateError) as exc:
        print(f'Hook input/check failed: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
