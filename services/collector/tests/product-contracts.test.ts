import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

import { Ajv2020, type ErrorObject, type ValidateFunction } from 'ajv/dist/2020.js';
import { createRequire } from 'node:module';

import type { DecisionRecordV1 } from '../src/contracts/decision-record.js';
import type { DiagnosisV1 } from '../src/contracts/diagnosis.js';
import type { SignalV1 } from '../src/contracts/signal.js';

const root = new URL('../../../', import.meta.url);
const require = createRequire(import.meta.url);
const addFormats = require('ajv-formats') as typeof import('ajv-formats').default;

async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(fileURLToPath(new URL(path, root)), 'utf8')) as T;
}

function validator(schema: Record<string, unknown>): ValidateFunction {
  const ajv = new Ajv2020({ allErrors: true, strict: true, allowUnionTypes: true, strictRequired: false });
  addFormats(ajv);
  return ajv.compile(schema);
}

function assertError(errors: ErrorObject[] | null | undefined, instancePath: string, keyword: string): void {
  assert.ok(errors?.some((error) => error.instancePath === instancePath && error.keyword === keyword));
}

function copy<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

test('validates the synthetic signal and preserves generated SignalV1 shape', async () => {
  const schema = await readJson<Record<string, unknown>>('contracts/signal.schema.json');
  const signal = await readJson<SignalV1>('contracts/examples/signal.synthetic.json');
  const validate = validator(schema);

  assert.equal(validate(signal), true);
  assert.equal(signal.source_refs.length, 1);
  assert.equal(signal.detection_data.sellable_stock?.value, null);
  assert.equal(signal.detection_data.sellable_stock?.is_unknown, true);
});

test('rejects signal without rub assessment method and with empty source refs', async () => {
  const schema = await readJson<Record<string, unknown>>('contracts/signal.schema.json');
  const signal = await readJson<SignalV1>('contracts/examples/signal.synthetic.json');
  const validate = validator(schema);

  const missingMethod = { ...signal, rub_assessment: { value_rub: 0 } };
  assert.equal(validate(missingMethod), false);
  assertError(validate.errors, '/rub_assessment', 'required');

  const emptyRefs = { ...signal, source_refs: [] };
  assert.equal(validate(emptyRefs), false);
  assertError(validate.errors, '/source_refs', 'minItems');
});

test('validates diagnosis and enforces positional source-ref invariant', async () => {
  const schema = await readJson<Record<string, unknown>>('contracts/diagnosis.schema.json');
  const diagnosis = await readJson<DiagnosisV1>('contracts/examples/diagnosis.synthetic.json');
  const validate = validator(schema);

  assert.equal(validate(diagnosis), true);
  assert.equal(diagnosis.source_refs.length, 1 + diagnosis.alternatives.length + diagnosis.unknowns.length);
});

test('diagnosis-bad-refs fixture on disk violates the positional invariant', async () => {
  const diagnosis = await readJson<DiagnosisV1>('contracts/examples/diagnosis-bad-refs.synthetic.json');
  const expected = 1 + diagnosis.alternatives.length + diagnosis.unknowns.length;

  assert.notEqual(diagnosis.source_refs.length, expected);
});

test('rejects diagnosis with fewer than two alternatives and empty source refs', async () => {
  const schema = await readJson<Record<string, unknown>>('contracts/diagnosis.schema.json');
  const diagnosis = await readJson<DiagnosisV1>('contracts/examples/diagnosis.synthetic.json');
  const validate = validator(schema);

  const oneAlternative = { ...diagnosis, alternatives: [diagnosis.alternatives[0]] };
  assert.equal(validate(oneAlternative), false);
  assertError(validate.errors, '/alternatives', 'minItems');

  const emptyRefs = { ...diagnosis, source_refs: [] };
  assert.equal(validate(emptyRefs), false);
  assertError(validate.errors, '/source_refs', 'minItems');
});

test('rejects rub assessment and metric values that are not money strings', async () => {
  const signalSchema = await readJson<Record<string, unknown>>('contracts/signal.schema.json');
  const signal = await readJson<SignalV1>('contracts/examples/signal.synthetic.json');
  const signalValidate = validator(signalSchema);

  assert.equal(signal.rub_assessment?.value_rub, '12345.67');
  const numberValue = { ...signal, rub_assessment: { value_rub: 12345.67, method: 'revenue' } };
  assert.equal(signalValidate(numberValue), false);
  assertError(signalValidate.errors, '/rub_assessment/value_rub', 'type');

  const looseString = { ...signal, rub_assessment: { value_rub: '12345.6', method: 'revenue' } };
  assert.equal(signalValidate(looseString), false);
  assertError(signalValidate.errors, '/rub_assessment/value_rub', 'pattern');

  const decisionSchema = await readJson<Record<string, unknown>>('contracts/decision-record.schema.json');
  const decision = await readJson<DecisionRecordV1>('contracts/examples/decision-record.synthetic.json');
  const decisionValidate = validator(decisionSchema);

  assert.equal(decision.expected.metrics[0].value, '1200.00');
  const numericMetric = copy(decision) as unknown as { expected: { metrics: [{ value: unknown } & Record<string, unknown>] } };
  numericMetric.expected.metrics[0].value = 1200;
  assert.equal(decisionValidate(numericMetric), false);
  assertError(decisionValidate.errors, '/expected/metrics/0/value', 'type');
});

test('validates an open decision record with the generated DecisionRecordV1 shape', async () => {
  const schema = await readJson<Record<string, unknown>>('contracts/decision-record.schema.json');
  const decision = await readJson<DecisionRecordV1>('contracts/examples/decision-record.synthetic.json');
  const validate = validator(schema);

  assert.equal(validate(decision), true);
  assert.equal(decision.actual, null);
  assert.equal('outcome' in decision, false);
});

test('rejects rejected decision without reason and closed decision without outcome', async () => {
  const schema = await readJson<Record<string, unknown>>('contracts/decision-record.schema.json');
  const decision = await readJson<DecisionRecordV1>('contracts/examples/decision-record.synthetic.json');
  const validate = validator(schema);

  const missingReason = { ...decision, decision: 'rejected', reason: null };
  assert.equal(validate(missingReason), false);
  assertError(validate.errors, '/reason', 'type');

  const closedWithoutOutcome = {
    ...decision,
    actual: { ...decision.expected },
  };
  assert.equal(validate(closedWithoutOutcome), false);
  assertError(validate.errors, '', 'required');
});
