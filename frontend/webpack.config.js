const path = require('path');
const { merge } = require('webpack-merge');

const BASE = {
  entry: './src/zar.js',
  mode: "production",
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
      name: 'full',
      module: {
        rules: [
          {
            test: /\.(js)$/,
            exclude: /node_modules/,
            use: [
              {
                loader: "babel-loader",
                options: {
                  envName: 'full'
                }
              }
            ]
          }
        ]
      },
      output: {
        filename: 'zar.bundle.js'
      },
    })
];
