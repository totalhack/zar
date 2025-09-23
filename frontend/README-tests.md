Running tests

- Install deps: npm install
- Run all tests: npm run test
- Watch mode: npm run test:watch
- Coverage: npm run coverage

Notes
- Tests run in a jsdom browser-like environment via vitest.
- Internal helpers are exposed under the __test__ export solely for testing.
