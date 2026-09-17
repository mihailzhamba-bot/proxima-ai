#!/usr/bin/python3 -I
"""Root operator finite PR-only batch; Paperclip remains the only scheduler.

--manifest JSON requires tasks (1..4), template_bases, end_at (epoch seconds),
job_timeout_seconds (1..2700), poll_seconds (10..30), disk_floor_bytes (>=2 GiB),
state_file, evidence_root, work_root, glm_config, glm_script, review_receipts,
operator_key_file, runner_key_file. Tasks contain key, job_id, template,
template_fingerprint and optional existing_run_id. All paths must be absolute.
Optional acceptance_command is a fixed argv of trusted absolute executable/helper
paths and flags; it receives checkout, base, head, job_id before model review.
Optional runtime_owner_uid (default 1000) is trusted only for work/evidence paths.
Restart never repeats uncertain dispatch or model calls; halt needs manual review.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from .glm_review import (DEFERRED_EXIT, NoRedirect, read_key, strict_json,
                             trusted_snapshot, git, diff_digest)
    from . import model_router
except ImportError:
    from glm_review import (DEFERRED_EXIT, NoRedirect, read_key, strict_json,
                            trusted_snapshot, git, diff_digest)
    import model_router

BRIDGE = 'http://127.0.0.1:18771'
ID = re.compile(r'[a-z0-9][a-z0-9-]{2,40}')
RUN = re.compile(r'[A-Za-z0-9-]{1,80}')
SHA = re.compile(r'[a-f0-9]{40}')
DIGEST = re.compile(r'[a-f0-9]{64}')
PATHS = ('state_file', 'evidence_root', 'work_root', 'glm_config', 'glm_script',
         'review_receipts', 'operator_key_file', 'runner_key_file')


class BatchError(ValueError):
    pass


SAFE_REVIEW_DEFER_REASONS = frozenset({
    'openai_broker_busy', 'weekday_peak', 'pre_peak_guard_band'})
MAX_REVIEW_DEFER_SECONDS = 6 * 60 * 60


class ReviewDeferred(RuntimeError):
    def __init__(self, reason, resume_at, provider_route=None):
        super().__init__(reason)
        self.reason = reason
        self.resume_at = resume_at
        self.provider_route = provider_route


class HTTPError(BatchError):
    def __init__(self, code):
        self.code = code
        super().__init__('bridge_http_error')


def checked(manifest):
    required = {*PATHS, 'tasks', 'template_bases', 'end_at', 'job_timeout_seconds',
                'poll_seconds', 'disk_floor_bytes'}
    if (type(manifest) is not dict
            or set(manifest) - {'acceptance_command', 'runtime_owner_uid',
                                'pause_on_completion', 'halt_mode'} != required):
        raise BatchError('invalid_manifest')
    if type(manifest.get('pause_on_completion', True)) is not bool:
        raise BatchError('invalid_pause_on_completion')
    if manifest.get('halt_mode', 'global') not in ('global', 'local'):
        raise BatchError('invalid_halt_mode')
    runtime_uid = manifest.get('runtime_owner_uid', 1000)
    if type(runtime_uid) is not int or not 1 <= runtime_uid <= 2**31 - 1:
        raise BatchError('invalid_runtime_owner')
    if 'acceptance_command' in manifest:
        command = manifest['acceptance_command']
        if (type(command) is not list or not 1 <= len(command) <= 8
            or any(type(item) is not str or not item or '\n' in item for item in command)
            or not Path(command[0]).is_absolute()
            or any(not item.startswith('-') and not Path(item).is_absolute() for item in command[1:])):
            raise BatchError('invalid_acceptance_command')
    tasks = manifest['tasks']
    if type(tasks) is not list or not 1 <= len(tasks) <= 4:
        raise BatchError('invalid_tasks')
    keys, jobs = set(), set()
    bases = manifest['template_bases']
    if type(bases) is not dict:
        raise BatchError('invalid_bases')
    for task in tasks:
        if type(task) is not dict or set(task) - {'key', 'job_id', 'template', 'template_fingerprint', 'existing_run_id'}:
            raise BatchError('invalid_task')
        for key in ('key', 'job_id', 'template'):
            if type(task.get(key)) is not str or not ID.fullmatch(task[key]):
                raise BatchError('invalid_task_identity')
        if not DIGEST.fullmatch(str(task.get('template_fingerprint', ''))):
            raise BatchError('invalid_fingerprint')
        if not SHA.fullmatch(str(bases.get(task['template'], ''))):
            raise BatchError('invalid_base')
        if 'existing_run_id' in task and not RUN.fullmatch(str(task['existing_run_id'])):
            raise BatchError('invalid_existing_run')
        if task['key'] in keys or task['job_id'] in jobs:
            raise BatchError('duplicate_task')
        keys.add(task['key']); jobs.add(task['job_id'])
    for key in PATHS:
        if type(manifest[key]) is not str or not Path(manifest[key]).is_absolute():
            raise BatchError('invalid_path')
    for key, minimum, maximum in [('job_timeout_seconds', 1, 2700), ('poll_seconds', 10, 30),
                                 ('disk_floor_bytes', 2 * 1024**3, 1024**5)]:
        if type(manifest[key]) is not int or not minimum <= manifest[key] <= maximum:
            raise BatchError('invalid_limits')
    if type(manifest['end_at']) not in (int, float) or not 0 < manifest['end_at'] < 10**11:
        raise BatchError('invalid_deadline')
    return manifest


def trusted_directory(path, allowed_owners=(0,)):
    for parent in [Path(path), *Path(path).parents]:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid not in allowed_owners or info.st_mode & 0o022:
            raise BatchError('untrusted_directory')


def atomic_json(path, value, mode=0o600):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w') as output:
            json.dump(value, output, indent=2)
            output.flush(); os.fsync(output.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class BridgeClient:
    def __init__(self, manifest):
        self.keys = {'operator': read_key(manifest['operator_key_file']),
                     'runner': read_key(manifest['runner_key_file'])}
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def __call__(self, method, path, role='operator', payload=None, key=None, timeout=10):
        headers = {'Authorization': 'Bearer ' + self.keys[role], 'Content-Type': 'application/json'}
        if key:
            headers['Idempotency-Key'] = key
        request = urllib.request.Request(BRIDGE + path, method=method, headers=headers,
            data=json.dumps(payload or {}).encode() if method == 'POST' else None)
        def expired(_signal, _frame):
            raise BatchError('bridge_timeout')
        previous = signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read(100_001)
                if len(raw) > 100_000:
                    raise BatchError('bridge_response_limit')
                value = strict_json(raw)
                if type(value) is not dict:
                    raise BatchError('invalid_bridge_response')
                return value
        except urllib.error.HTTPError as error:
            raise HTTPError(error.code) from None
        except BatchError:
            raise
        except Exception:
            raise BatchError('bridge_unavailable') from None
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)


def json_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as handle:
        if os.fstat(handle.fileno()).st_size > 100_000:
            raise BatchError('evidence_limit')
        return strict_json(handle.read())


def fingerprint(checkout, base, head):
    with trusted_snapshot(checkout, base, head) as root:
        return {'base_sha': base, 'head_sha': head, 'diff_sha256': diff_digest(root, base, head)}


class ReviewStage:
    """Trusted stage discovery and root receipt writer; no candidate execution."""
    def __init__(self, manifest, execute=subprocess.run, clock=time.time):
        self.manifest = manifest
        self.execute = execute
        self.clock = clock

    def observe(self, task):
        work = Path(self.manifest['work_root'])
        candidates = sorted(work.glob('loop-' + task['job_id'] + '-*/candidate'))
        directories = sorted((Path(self.manifest['evidence_root']) / task['job_id']).glob('*'))
        if len(candidates) > 16 or len(directories) > 32:
            raise BatchError('stage_discovery_limit')
        matches = []
        for checkout in candidates:
            if checkout.is_symlink() or checkout.parent.is_symlink():
                raise BatchError('untrusted_candidate_path')
            head = git(checkout, 'rev-parse', 'HEAD').decode().strip()
            if not SHA.fullmatch(head):
                raise BatchError('invalid_candidate_sha')
            for directory in directories:
                if directory.is_symlink():
                    raise BatchError('untrusted_stage_path')
                try:
                    receipts = [json_file(directory / (stage + '-receipt.json')) for stage in ('verify', 'build')]
                except FileNotFoundError:
                    continue
                if all(receipt.get('status') == 'pass' and receipt.get('checks') ==
                    {stage: {'sha': head, 'status': 'pass', 'skipped': 0}}
                    and type(receipt['checks'][stage]['skipped']) is int
                    for receipt, stage in zip(receipts, ('verify', 'build'))):
                    scope = fingerprint(checkout, self.manifest['template_bases'][task['template']], head)
                    matches.append({'checkout': str(checkout), 'stage_path': str(directory), **scope})
                    break
        if len(matches) > 1:
            raise BatchError('ambiguous_candidate')
        return matches[0] if matches else None

    def accept(self, observation, timeout):
        command = self.manifest['acceptance_command']
        result = self.execute([*command, observation['checkout'], observation['base_sha'],
            observation['head_sha'], observation['job_id']], stdin=subprocess.DEVNULL,
            capture_output=True, timeout=min(120, timeout), check=False)
        expected = {'sha': observation['head_sha'], 'status': 'pass', 'skipped': 0}
        try:
            value = strict_json(result.stdout) if len(result.stdout) <= 100_000 else None
        except Exception:
            value = None
        passed = result.returncode == 0 and value == expected and type(value['skipped']) is int
        directory = Path(self.manifest['evidence_root']) / 'acceptance'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = directory / (observation['job_id'] + '-' + observation['head_sha'] + '.json')
        atomic_json(path, {'job_id': observation['job_id'], 'base_sha': observation['base_sha'],
            'head_sha': observation['head_sha'], 'status': 'pass' if passed else 'blocked',
            'receipt': expected if passed else None})
        if not passed:
            raise BatchError('independent_acceptance_blocked')
        return str(path)

    def review(self, observation, timeout):
        result = self.execute([sys.executable, '-I', self.manifest['glm_script'],
            '--config', self.manifest['glm_config'], '--checkout', observation['checkout'],
            '--base', observation['base_sha'], '--head', observation['head_sha'],
            '--evidence-root', str(Path(self.manifest['evidence_root']) / 'model-review')],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, check=False)
        if result.returncode == DEFERRED_EXIT and len(result.stdout) <= 100_000:
            try:
                deferred = strict_json(result.stdout)
                allowed = {'status', 'reason', 'resume_at', 'provider_route'}
                reason = deferred.get('reason')
                resume_at = deferred.get('resume_at')
                route = deferred.get('provider_route')
                now = self.clock()
                if (type(deferred) is not dict or set(deferred) - allowed
                        or deferred.get('status') != 'deferred'
                        or reason not in SAFE_REVIEW_DEFER_REASONS
                        or type(resume_at) not in (int, float)
                        or isinstance(resume_at, bool)
                        or not now < resume_at <= now + MAX_REVIEW_DEFER_SECONDS):
                    raise ValueError()
                if reason == 'openai_broker_busy':
                    if (type(route) is not dict
                            or not model_router.response_route_allowed(
                                route, route.get('model'),
                                route.get('provider'), 'review')):
                        raise ValueError()
                raise ReviewDeferred(reason, resume_at, route)
            except ReviewDeferred:
                raise
            except Exception:
                pass
        if result.returncode or len(result.stdout) > 100_000:
            reason = 'glm_review_blocked'
            try:
                observed_reason = strict_json(result.stdout).get('reason') if len(result.stdout) <= 100_000 else None
                if type(observed_reason) is str and re.fullmatch(r'[a-z_]{1,80}', observed_reason):
                    reason = observed_reason
            except Exception:
                pass
            directory = Path(self.manifest['evidence_root']) / 'model-review'
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            atomic_json(directory / ('error-' + observation['head_sha'] + '-' + str(time.time_ns()) + '.json'),
                {'artifact_type': 'model-review-error', 'reason': reason, 'head_sha': observation['head_sha'], 'observed_at': time.time()})
            raise BatchError(reason)
        value = strict_json(result.stdout)
        expected = {key: observation[key] for key in ('base_sha', 'head_sha', 'diff_sha256')}
        if value.get('status') != 'pass' or value.get('fingerprint') != expected:
            raise BatchError('glm_scope_mismatch')
        path = Path(value['evidence_path'])
        path.resolve().relative_to((Path(self.manifest['evidence_root']) / 'model-review').resolve())
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise BatchError('glm_artifact_invalid')
        artifact = json_file(path)
        if (artifact.get('artifact_type') != 'model-review-not-admission' or artifact.get('review_complete') is not True
            or {key: artifact.get(key) for key in expected} != expected
            or not model_router.identity_allowed(
                artifact.get('model'), artifact.get('provider'), 'review')
            or not model_router.response_route_allowed(
                artifact.get('actual_provider_route'), artifact.get('model'),
                artifact.get('provider'), 'review')
            or not re.fullmatch(r'[0-9a-f]{64}',
                                str(artifact.get('actual_request_sha256', '')))
            or artifact.get('verdict', {}).get('status') != 'pass'
            or artifact['verdict'].get('findings') != []):
            raise BatchError('glm_artifact_invalid')
        if fingerprint(observation['checkout'], observation['base_sha'], observation['head_sha']) != expected:
            raise BatchError('candidate_changed')
        return {'evidence_ref': str(path), 'model': artifact['model'],
                'provider': artifact['provider'],
                'reviewed_at_utc': artifact['reviewed_at_utc'], **expected}

    def admit(self, reviewed):
        if os.geteuid() != 0:
            raise BatchError('root_required_for_receipt')
        destination = Path(self.manifest['review_receipts'])
        trusted_directory(destination)
        receipt = {'base_sha': reviewed['base_sha'], 'sha': reviewed['head_sha'],
            'diff_sha256': reviewed['diff_sha256'], 'status': 'pass', 'skipped': 0,
            'reviewer': reviewed['model'], 'reviewed_at_utc': reviewed['reviewed_at_utc'],
            'evidence_ref': reviewed['evidence_ref']}
        path = destination / (reviewed['head_sha'] + '.json')
        if path.exists() or path.is_symlink():
            if json_file(path) != receipt:
                raise BatchError('review_receipt_conflict')
            return
        # Public nonsecret attestation: the unprivileged verifier must read it.
        # Ownership and all write permissions remain restricted to root.
        atomic_json(path, receipt, mode=0o644)


class Batch:
    def __init__(self, manifest, call, stage, clock=time.time, sleep=time.sleep,
                 disk_free=lambda path: shutil.disk_usage(path).free):
        self.manifest = checked(manifest)
        self.call, self.stage, self.clock, self.sleep, self.disk_free = call, stage, clock, sleep, disk_free
        self.path = Path(manifest['state_file'])
        self.digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        self.state = None

    def save(self):
        self.state['updated_at'] = self.clock()
        atomic_json(self.path, self.state)
        atomic_json(self.path.parent / 'status.json', self.state)

    def request(self, method, path, **kwargs):
        remaining = self.manifest['end_at'] - self.clock()
        if remaining <= 0:
            raise BatchError('batch_deadline')
        return self.call(method, path, timeout=min(10, remaining), **kwargs)

    def halt(self, reason, task_state=None):
        self.state['status'], self.state['reason'] = 'blocked', reason
        self.save()  # halt durable before any best-effort external effects
        global_reasons = {'disk_floor', 'disk_start_floor', 'bridge_unavailable',
                          'batch_already_running', 'untrusted_reviewer_install'}
        paths = ([] if self.manifest.get('halt_mode', 'global') == 'local' and reason not in global_reasons
                 else ['/v1/pause'])
        if task_state and task_state.get('run_id'):
            paths.append('/v1/runs/' + task_state['run_id'] + '/stop')
        for path in paths:
            try:
                self.call('POST', path, payload={}, timeout=5)
            except Exception:
                pass
        return self.state

    def run(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(str(self.path) + '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise BatchError('batch_already_running') from None
            if self.path.exists() or self.path.is_symlink():
                self.state = json_file(self.path)
                if self.state.get('manifest_sha256') != self.digest:
                    raise BatchError('manifest_changed')
                if (self.state.get('status') not in ('running', 'blocked', 'completed')
                    or type(self.state.get('tasks')) is not list
                    or len(self.state['tasks']) != len(self.manifest['tasks'])
                    or any(type(saved) is not dict or saved.get('key') != task['key']
                        or saved.get('job_id') != task['job_id']
                        or saved.get('phase') not in ('pending', 'dispatching', 'monitoring', 'reviewing', 'ready_pr')
                        for saved, task in zip(self.state['tasks'], self.manifest['tasks']))
                    or type(self.state.get('reviews', {})) is not dict
                    or len(self.state.get('reviews', {})) > 4):
                    raise BatchError('invalid_saved_state')
                if self.state['status'] == 'completed' and any(task['phase'] != 'ready_pr' for task in self.state['tasks']):
                    raise BatchError('incomplete_saved_batch')
            else:
                self.state = {'version': 1, 'manifest_sha256': self.digest, 'status': 'running',
                    'reviews': {},
                    'tasks': [{'key': task['key'], 'job_id': task['job_id'], 'phase': 'pending'} for task in self.manifest['tasks']]}
                self.save()
            if self.state['status'] != 'running':
                return self.state
            self.state.setdefault('reviews', {})
            current = None
            try:
                for task, current in zip(self.manifest['tasks'], self.state['tasks']):
                    if current['phase'] == 'ready_pr':
                        continue
                    if current['phase'] in ('dispatching', 'reviewing'):
                        return self.halt('uncertain_' + current['phase'], current)
                    while True:
                        now = self.clock()
                        if now >= self.manifest['end_at']:
                            return self.halt('batch_deadline', current)
                        if self.disk_free(self.manifest['work_root']) < self.manifest['disk_floor_bytes']:
                            return self.halt('disk_floor', current)
                        if current['phase'] == 'pending':
                            if self.disk_free(self.manifest['work_root']) < max(3 * 1024**3, self.manifest['disk_floor_bytes']):
                                return self.halt('disk_start_floor', current)
                            current['started_at'] = now
                            if task.get('existing_run_id'):
                                current['run_id'] = task['existing_run_id']
                            else:
                                current['phase'] = 'dispatching'; self.save()
                                response = self.request('POST', '/v1/wake', payload={
                                    'source': 'operator_batch', 'job_id': task['job_id'],
                                    'template': task['template'], 'template_fingerprint': task['template_fingerprint']}, key=task['key'])
                                if not RUN.fullmatch(str(response.get('run_id', ''))):
                                    raise BatchError('dispatch_identity_missing')
                                current['run_id'] = response['run_id']
                            current['phase'] = 'monitoring'; self.save()
                        if now >= current['started_at'] + self.manifest['job_timeout_seconds']:
                            return self.halt('job_timeout', current)
                        run = self.request('GET', '/v1/runs/' + current['run_id'])
                        run_status = run.get('status', run.get('state'))
                        if run_status not in ('queued', 'dispatching', 'running', 'completed'):
                            return self.halt('run_terminal_or_unknown', current)
                        try:
                            job = self.request('GET', '/v1/runner/jobs/' + task['job_id'], role='runner')
                        except HTTPError as error:
                            if error.code != 404:
                                raise
                            job = None
                        if self.clock() >= self.manifest['end_at']:
                            return self.halt('batch_deadline', current)
                        if self.clock() >= current['started_at'] + self.manifest['job_timeout_seconds']:
                            return self.halt('job_timeout', current)
                        if job is None:
                            if run_status == 'completed':
                                current.setdefault('no_job_since', self.clock()); self.save()
                                if self.clock() - current['no_job_since'] >= 60:
                                    return self.halt('completed_without_job', current)
                        else:
                            current.pop('no_job_since', None)
                            if job.get('parent_run_id') != current['run_id']:
                                return self.halt('job_parent_run_mismatch', current)
                            if job.get('template') != task['template'] or job.get('template_fingerprint') != task['template_fingerprint']:
                                return self.halt('job_scope_mismatch', current)
                            status = job.get('state')
                            if status == 'ready_pr':
                                if not current.get('reviewed'):
                                    return self.halt('ready_pr_without_batch_review', current)
                                if (not isinstance(job.get('pr_url'), str) or not job['pr_url'].startswith('https://')
                                    or not SHA.fullmatch(str(job.get('candidate_sha', '')))):
                                    return self.halt('ready_pr_evidence_missing', current)
                                if current.get('reviewed') and job['candidate_sha'] != current['reviewed']['head_sha']:
                                    return self.halt('ready_pr_sha_mismatch', current)
                                current.update(phase='ready_pr', pr_url=job['pr_url'], head_sha=job.get('candidate_sha'))
                                self.save(); break
                            if status not in ('queued', 'dispatching', 'publishing'):
                                return self.halt('job_terminal_or_unknown', current)
                            retry_at = current.get('review_retry_at')
                            if retry_at is not None:
                                if (type(retry_at) not in (int, float)
                                        or isinstance(retry_at, bool)):
                                    return self.halt('invalid_review_retry', current)
                                if self.clock() < retry_at:
                                    current['observed_run_status'] = run_status
                                    current['observed_job_status'] = status
                                    self.save()
                                    self.sleep(min(self.manifest['poll_seconds'],
                                        max(0, retry_at - self.clock()),
                                        max(0, self.manifest['end_at'] - self.clock())))
                                    continue
                            observed = self.stage.observe(task)
                            if observed:
                                observed['job_id'] = task['job_id']
                                retry_scope = current.get('review_retry_scope')
                                if retry_scope and any(
                                        observed.get(key) != retry_scope.get(key)
                                        for key in ('base_sha', 'head_sha', 'diff_sha256')):
                                    return self.halt('review_retry_candidate_changed', current)
                                if current.get('reviewed'):
                                    if observed['head_sha'] != current['reviewed']['head_sha']:
                                        return self.halt('reviewed_candidate_changed', current)
                                else:
                                    current.update(phase='reviewing', review_sha=observed['head_sha']); self.save()
                                    timeout = min(240, self.manifest['end_at'] - self.clock(),
                                        current['started_at'] + self.manifest['job_timeout_seconds'] - self.clock())
                                    if timeout <= 0:
                                        return self.halt('review_deadline', current)
                                    if (self.manifest.get('acceptance_command')
                                            and not current.get('acceptance_ref')):
                                        current['acceptance_ref'] = self.stage.accept(observed, timeout)
                                        self.save()
                                        timeout = min(240, self.manifest['end_at'] - self.clock(),
                                            current['started_at'] + self.manifest['job_timeout_seconds'] - self.clock())
                                        if timeout <= 0:
                                            return self.halt('acceptance_deadline', current)
                                    prior = self.state['reviews'].get(observed['head_sha'])
                                    if prior:
                                        if prior.get('phase') != 'completed':
                                            return self.halt('uncertain_sha_review', current)
                                        reviewed = prior['reviewed']
                                        if any(reviewed[key] != observed[key] for key in ('base_sha', 'head_sha', 'diff_sha256')):
                                            return self.halt('reused_review_scope_mismatch', current)
                                    else:
                                        if len(self.state['reviews']) >= 4:
                                            return self.halt('model_call_limit', current)
                                        self.state['reviews'][observed['head_sha']] = {'phase': 'reviewing'}
                                        self.save()
                                        try:
                                            reviewed = self.stage.review(observed, timeout)
                                        except ReviewDeferred as deferred:
                                            reservation = self.state['reviews'].get(observed['head_sha'])
                                            if reservation != {'phase': 'reviewing'}:
                                                return self.halt('uncertain_sha_review', current)
                                            self.state['reviews'].pop(observed['head_sha'])
                                            current.update(phase='monitoring',
                                                review_retry_at=deferred.resume_at,
                                                review_retry_reason=deferred.reason,
                                                review_retry_scope={key: observed[key] for key in
                                                    ('base_sha', 'head_sha', 'diff_sha256')})
                                            current.pop('review_sha', None)
                                            self.save()
                                            continue
                                    if self.clock() >= min(self.manifest['end_at'], current['started_at'] + self.manifest['job_timeout_seconds']):
                                        return self.halt('review_deadline', current)
                                    fresh_run = self.request('GET', '/v1/runs/' + current['run_id'])
                                    fresh_job = self.request('GET', '/v1/runner/jobs/' + task['job_id'], role='runner')
                                    if (fresh_run.get('status', fresh_run.get('state')) not in ('running', 'completed')
                                        or fresh_job.get('state') not in ('dispatching', 'publishing')
                                        or fresh_job.get('parent_run_id') != current['run_id']
                                        or fresh_job.get('template_fingerprint') != task['template_fingerprint']):
                                        return self.halt('review_attempt_revoked', current)
                                    if self.clock() >= min(self.manifest['end_at'], current['started_at'] + self.manifest['job_timeout_seconds']):
                                        return self.halt('review_deadline', current)
                                    self.stage.admit(reviewed)
                                    self.state['reviews'][observed['head_sha']] = {'phase': 'completed', 'reviewed': reviewed}
                                    current.update(phase='monitoring', reviewed=reviewed)
                                    for name in ('review_retry_at', 'review_retry_reason',
                                                 'review_retry_scope', 'review_sha'):
                                        current.pop(name, None)
                                    self.save()
                        current['observed_run_status'] = run_status
                        current['observed_job_status'] = job.get('state') if job else 'absent'
                        self.save()
                        self.sleep(min(self.manifest['poll_seconds'], max(0, self.manifest['end_at'] - self.clock())))
                self.state['reason'] = 'finite_admitted_batch_completed'
                self.state['automatic_job_admission'] = False
                self.state['next_action'] = 'await_new_admitted_batch_manifest'
                if self.manifest.get('pause_on_completion', True):
                    # Remain nonterminal until the default pause is confirmed.
                    # A crash here makes ExecStopPost fail closed.
                    self.state['status'] = 'running'
                    self.state['queue_state'] = 'pause_pending'
                    self.save()
                    # Default finite-batch policy prevents unrelated later wakeups.
                    try:
                        paused = self.call('POST', '/v1/pause', payload={}, timeout=5)
                        if (paused.get('paused') is not True
                                and paused.get('status') not in ('paused', 'stopped')):
                            raise BatchError('final_pause_unconfirmed')
                    except Exception:
                        self.state['status'] = 'blocked'
                        self.state['reason'] = 'final_pause_unconfirmed'
                        self.state['queue_state'] = 'pause_unconfirmed'
                        self.save()
                    else:
                        self.state['status'] = 'completed'
                        self.state['queue_state'] = 'paused_after_finite_batch'
                        self.save()
                else:
                    # The finite manifest is exhausted. A distinct admitted
                    # manifest is still required before this operator wakes work.
                    self.state['status'] = 'completed'
                    self.state['queue_state'] = 'available_for_admitted_batch'
                    self.save()
                return self.state
            except Exception as error:
                reason = str(error) if isinstance(error, BatchError) else 'batch_operation_failed'
                return self.halt(reason, current)
        finally:
            os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = checked(json_file(args.manifest))
        if os.geteuid() != 0:
            raise BatchError('root_operator_required')
        for key in ('work_root', 'evidence_root'):
            trusted_directory(manifest[key], allowed_owners=(0, manifest.get('runtime_owner_uid', 1000)))
        trusted_directory(manifest['review_receipts'])
        trusted_directory(Path(manifest['state_file']).parent)
        for key in ('glm_script', 'glm_config'):
            trusted_directory(Path(manifest[key]).parent)
            info = Path(manifest[key]).lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise BatchError('untrusted_reviewer_install')
        for value in manifest.get('acceptance_command', []):
            if value.startswith('-'):
                continue
            path = Path(value).resolve(strict=True)
            trusted_directory(path.parent)
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise BatchError('untrusted_acceptance_helper')
        result = Batch(manifest, BridgeClient(manifest), ReviewStage(manifest)).run()
    except Exception as error:
        result = {'status': 'blocked', 'reason': str(error) if isinstance(error, BatchError) else 'batch_failed'}
    print(json.dumps(result))
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
