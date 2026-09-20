import { join } from 'node:path';

import {
  assertPublishedArtifactIntegrity,
  createPrivateTempFile,
  manifestPath,
  preparePrivateStore,
  publishManifest,
  publishRawObject,
  removePrivateTemp,
  streamXlsxToPrivateTemp,
} from './content-store.js';
import {
  assertManualWbXlsxMetadata,
  assertSourceArtifactContract,
  canonicalManifestBytes,
  createManualWbXlsxManifest,
} from './manifest.js';
import type {
  IntakeHooks,
  ManualWbXlsxIntakeResult,
  ManualWbXlsxMetadata,
} from './types.js';

export interface ManualWbXlsxIntakeOptions {
  inputPath: string;
  storeRoot: string;
  repositoryRoot: string;
  metadata: ManualWbXlsxMetadata;
  hooks?: IntakeHooks;
}

export async function intakeManualWbXlsx(
  options: ManualWbXlsxIntakeOptions,
): Promise<ManualWbXlsxIntakeResult> {
  assertManualWbXlsxMetadata(options.metadata);
  const storeRoot = await preparePrivateStore(options.storeRoot, options.repositoryRoot);
  const streamed = await streamXlsxToPrivateTemp(options.inputPath, storeRoot);
  let manifestTemporaryPath: string | undefined;
  try {
    await options.hooks?.at?.('after_temp_durable');
    await assertPublishedArtifactIntegrity(storeRoot, streamed.contentSha256, streamed.contentSize);
    const rawState = await publishRawObject(
      streamed.temporaryPath,
      storeRoot,
      streamed.contentSha256,
      streamed.contentSize,
    );
    await options.hooks?.at?.('after_raw_published');

    const manifest = createManualWbXlsxManifest(
      streamed.contentSha256,
      streamed.contentSize,
      options.metadata,
    );
    await assertSourceArtifactContract(manifest);
    const manifestBytes = canonicalManifestBytes(manifest);
    manifestTemporaryPath = await createPrivateTempFile(storeRoot, `${streamed.contentSha256}.json`, manifestBytes);
    await options.hooks?.at?.('before_manifest_published');
    const manifestState = await publishManifest(
      manifestTemporaryPath,
      manifestPath(storeRoot, streamed.contentSha256),
      manifestBytes,
      storeRoot,
    );
    await options.hooks?.at?.('after_manifest_published');
    return {
      artifactId: manifest.artifact_id,
      contentSha256: manifest.content_sha256,
      locator: manifest.locator,
      state: rawState === 'existing' && manifestState === 'existing' ? 'existing' : 'created',
    };
  } finally {
    await Promise.all([
      removePrivateTemp(streamed.temporaryPath),
      manifestTemporaryPath ? removePrivateTemp(manifestTemporaryPath) : Promise.resolve(),
    ]);
  }
}

export function defaultRepositoryRoot(): string {
  return join(import.meta.dirname, '../../../..');
}
