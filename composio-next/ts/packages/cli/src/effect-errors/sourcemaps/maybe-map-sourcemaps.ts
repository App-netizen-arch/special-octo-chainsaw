import type { FileSystem } from '@effect/platform/FileSystem';
import type { Path } from '@effect/platform/Path';
import { Effect } from 'effect';

import { sourceFileWithMapPointerRegex } from 'effect-errors/logic/stack';

import { getErrorRelatedSources } from './get-error-related-sources';
import { MappedSources, type MaybeMappedSources } from './mapped-sources';

export const maybeMapSourcemaps = (
  name: string,
  stacktrace: string[]
): Effect.Effect<MaybeMappedSources[], never, FileSystem | Path> =>
  Effect.forEach(stacktrace, stackLine =>
    Effect.gen(function* () {
      const trimmed = stackLine.trimStart().replace(/^at /, '');
      const match = sourceFileWithMapPointerRegex.exec(trimmed);
      const mapFileReportedPath = match ? match[0] : undefined;

      if (mapFileReportedPath === undefined) {
        return MappedSources['stack-entry']({
          runPath: stackLine.replaceAll(/ {4}at /g, 'at '),
        });
      }

      const details = yield* getErrorRelatedSources(name, mapFileReportedPath);
      if (details === undefined) {
        return MappedSources['stack-entry']({
          runPath: stackLine.replaceAll(/ {4}at /g, 'at '),
        });
      }

      return details;
    })
  );
