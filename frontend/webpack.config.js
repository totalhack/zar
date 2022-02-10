const path = require('path');
const { merge } = require('webpack-merge');

const BASE = {
  entry: './src/zar.js',
  mode: "production",
  devtool: "source-map",
  resolve: {
    extensions: ['*', '.js']
  },
  output: {
    library: 'zar',
    libraryTarget: 'umd',
    path: path.resolve(__dirname, 'dist')
  },
};

module.exports = [
  merge(BASE,
    {
      name: 'modern',
      module: {
        rules: [
          {
            test: /\.(js)$/,
            exclude: /node_modules/,
            use: [
              {
                loader: "babel-loader",
                options: {
                  envName: 'modern'
                }
              }
            ]
          }
        ]
      },
      output: {
        filename: 'zar.modern.bundle.js'
      },
    }),
  merge(BASE,
    {
      name: 'legacy',
      module: {
        rules: [
          {
            test: /\.(js)$/,
            exclude: /node_modules/,
            use: [
              {
                loader: "babel-loader",
                options: {
                  envName: 'legacy'
                }
              }
            ]
          }
        ]
      },
      output: {
        filename: 'zar.legacy.bundle.js',
        // https://stackoverflow.com/questions/52821427/javascript-babel-preset-env-not-transpiling-arrow-functions-for-ie11
        // https://webpack.js.org/configuration/output/#outputenvironment
        environment: {
          // The environment supports arrow functions ('() => { ... }').
          arrowFunction: false,
          // The environment supports BigInt as literal (123n).
          bigIntLiteral: false,
          // The environment supports const and let for variable declarations.
          const: false,
          // The environment supports destructuring ('{ a, b } = obj').
          destructuring: false,
          // The environment supports an async import() function to import EcmaScript modules.
          dynamicImport: false,
          // The environment supports 'for of' iteration ('for (const x of array) { ... }').
          forOf: false,
          // The environment supports ECMAScript Module syntax to import ECMAScript modules (import ... from '...').
          module: false,
        },
      },
    })
];
