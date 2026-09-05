import js from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    // Сгенерированный клиент не проверяется: он не правится руками (принцип II).
    ignores: ['dist/**', 'build/**', 'coverage/**', 'node_modules/**', 'src/api/generated/**', 'playwright-report/**', 'test-results/**'],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    rules: {
      // Материалы клиента MTS не попадают в код, фикстуры и тесты интерфейса
      // (принцип VI, FR-038): для них используются синтетические данные.
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['**/MTS/**', '../../../MTS/*', '@/../../MTS/*'],
              message:
                'Материалы кейса MTS не переносятся в apps/web. Используйте синтетические данные из src/mocks/fixtures/.',
            },
          ],
        },
      ],
      '@typescript-eslint/consistent-type-imports': 'error',
    },
  },
);
