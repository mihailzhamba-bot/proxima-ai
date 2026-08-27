import { PromotionError } from '../facts/promote-order-counts.js';

export const PROMOTION_REQUIRED_ARGUMENTS = [
  'tenant',
  'task-id',
  'database-url-file',
] as const;

type PromotionArgument = (typeof PROMOTION_REQUIRED_ARGUMENTS)[number];

export function parsePromotionArgs(argv: string[]): Record<PromotionArgument, string> {
  const values = new Map<string, string>();
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith('--') || !value || value.startsWith('--') || values.has(key.slice(2))) {
      throw new PromotionError('PROMOTION_FAILED', 'invalid promotion arguments');
    }
    values.set(key.slice(2), value);
  }

  if (
    values.size !== PROMOTION_REQUIRED_ARGUMENTS.length ||
    !PROMOTION_REQUIRED_ARGUMENTS.every((argument) => values.has(argument))
  ) {
    throw new PromotionError('PROMOTION_FAILED', 'required promotion argument is missing');
  }

  return Object.fromEntries(
    PROMOTION_REQUIRED_ARGUMENTS.map((argument) => [argument, values.get(argument)!]),
  ) as Record<PromotionArgument, string>;
}
