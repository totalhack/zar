const path = require('path');
import { defineConfig } from 'vite';

export default defineConfig({
  clearScreen: false,
  build: {
    lib: {
      entry: path.resolve(__dirname, 'src/zar.js'),
      name: 'zar',
      formats: ['es', 'umd', 'iife'],
      fileName: (format) => `zar.${format}.js`
    },
    // Prevents minification from using syntax only supported by recent browsers
    target: 'es6',
    sourcemap: true
  }
});
